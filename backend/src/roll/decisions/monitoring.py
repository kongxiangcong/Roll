"""Source-bound operational checks, separate from historic validation verdicts.

Preparation reads immutable archives without a writer; the caller transaction
owns restriction, action invalidation, checkpoint consumption and the receipt.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from uuid import uuid4
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from roll.accounts.ledger import encode, now
from roll.decisions.actions import fingerprint
from roll.decisions.capabilities import moment
from roll.research.validation import development_reference, monitor_frozen, validation_code, probability_checks, continuous_checks
from roll.research.shadow import simulate
from roll.market.rules import SHANGHAI


def method_code():
    return hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


class MonitoringCommand(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    grant_id: str
    basis: str = Field(min_length=1, max_length=2000)


class CorrectionCommand(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    monitoring_check_id: str
    category: Literal['DATA_REPAIR', 'EXECUTION_ASSUMPTION', 'USER_DELAY', 'MODEL_RESEARCH']
    error_source: str = Field(min_length=1, max_length=2000)
    expected_improvement: str = Field(min_length=1, max_length=2000)
    affected_modules: list[str] = Field(min_length=1, max_length=20)
    validation_plan: str = Field(min_length=1, max_length=4000)
    changes_frozen: bool
    successor_protocol_id: str | None = None
    successor_version_fingerprint: str | None = None
    idempotency_key: str = Field(min_length=1, max_length=128)

    @model_validator(mode='after')
    def declared_plan(self):
        if any(not v.strip() for v in [self.error_source, self.expected_improvement, self.validation_plan, *self.affected_modules]):
            raise ValueError('修正来源、改善、模块和验证计划不能为空')
        if self.changes_frozen and (not self.successor_protocol_id or not self.successor_protocol_id.strip() or
                not self.successor_version_fingerprint or len(self.successor_version_fingerprint) != 64 or
                any(c not in '0123456789abcdef' for c in self.successor_version_fingerprint)):
            raise ValueError('修改冻结模型、政策或假设必须关联后继协议和版本指纹；仍待独立验证')
        return self


@dataclass(frozen=True)
class PreparedMonitoring:
    inputs: dict
    result: dict


class Monitoring:
    def __init__(self, capabilities, validation, forward, intents):
        self.capabilities, self.validation, self.forward, self.intents = capabilities, validation, forward, intents
        self.ledger, self.evidence, self.shadow = capabilities.ledger, capabilities.reviews.evidence, validation.shadow
        with self.ledger.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS capability_monitoring(id TEXT PRIMARY KEY, fingerprint TEXT UNIQUE, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS capability_monitoring_checkpoints(grant_id TEXT, boundary TEXT, check_id TEXT,
                    PRIMARY KEY(grant_id,boundary));
                CREATE TABLE IF NOT EXISTS capability_corrections(id TEXT PRIMARY KEY, key TEXT UNIQUE, fingerprint TEXT NOT NULL, value TEXT NOT NULL);
            ''')

    def records(self, db=None):
        if db is None:
            with self.ledger.connection() as connection: return self.records(connection)
        return [json.loads(r[0]) for r in db.execute('SELECT value FROM capability_monitoring ORDER BY rowid')]

    def corrections(self):
        with self.ledger.connection() as db:
            values = [json.loads(r[0]) for r in db.execute('SELECT value FROM capability_corrections ORDER BY rowid')]
        for value in values:
            if self.shadow.checked_archive(value['archive']) != {k:v for k,v in value.items() if k != 'archive'}:
                raise HTTPException(409, 'CORRECTION_ARCHIVE_CHANGED')
        return values

    def record_correction(self, command):
        check = self.get(command.monitoring_check_id)
        content = fingerprint(command.model_dump(exclude={'idempotency_key'}))
        if command.changes_frozen:
            inputs = self.shadow.checked_archive(check['input_archive'])
            if command.successor_protocol_id == inputs['grant']['protocol_id'] or command.successor_version_fingerprint == check['complete_protocol_fingerprint']:
                raise HTTPException(409, 'CORRECTION_REQUIRES_NEW_PROTOCOL_VERSION')
        if command.category == 'USER_DELAY' and 'DELAY_OUTSIDE_FROZEN_SCENARIOS' not in check['reasons']:
            raise HTTPException(409, 'USER_DELAY_NOT_ESTABLISHED_BY_SOURCE')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior = db.execute('SELECT fingerprint,value FROM capability_corrections WHERE key=?', (command.idempotency_key,)).fetchone()
            if prior:
                if prior[0] != content: raise HTTPException(409, 'CORRECTION_IDEMPOTENCY_CONFLICT')
                return json.loads(prior[1])
            value = {**command.model_dump(exclude={'idempotency_key'}), 'correction_id': str(uuid4()),
                'recorded_at': now(), 'review_state': 'OPEN', 'source_check_archive_sha256': check['archive']['sha256'],
                'source_input_fingerprint': check['input_fingerprint'], 'grant_id': check['grant_id'],
                'source_protocol_fingerprint': check['complete_protocol_fingerprint'],
                'qualification_verdict_changed': False, 'automatic_retraining': False, 'system_usable': False,
                'source_attribution': 'DECLARED_REVIEW_HYPOTHESIS_NOT_CAUSAL_MODEL_FAILURE',
                'successor_validation_state': 'PENDING_REGISTRATION_AND_VALIDATION' if command.changes_frozen else 'REGRESSION_PLAN_REQUIRED'}
            value['archive'] = self.evidence.archive(encode(value).encode(), 'CAPABILITY_CORRECTION', db=db)
            db.execute('INSERT INTO capability_corrections VALUES(?,?,?,?)',
                (value['correction_id'], command.idempotency_key, content, encode(value)))
            db.commit()
        return value

    def get(self, identifier):
        with self.ledger.connection() as db:
            row = db.execute('SELECT value FROM capability_monitoring WHERE id=?', (identifier,)).fetchone()
        if row is None: raise HTTPException(404, '监测记录不存在')
        value = json.loads(row[0])
        if self.shadow.checked_archive(value['archive']) != {k:v for k,v in value.items() if k != 'archive'}:
            raise HTTPException(409, 'MONITORING_RECORD_ARCHIVE_CHANGED')
        return value

    def boundary(self, db):
        return {'lifecycle_version': self.capabilities.lifecycle(db)['version'],
                'account_version': self.ledger.account(db=db)['version'],
                'funding_version': self.capabilities.funding.current(db=db)['version'],
                'data_fingerprint': self.capabilities.actions.data_state(db, self.ledger.account(db=db))['fingerprint'],
                'checkpoint_fingerprint': fingerprint([tuple(r) for r in db.execute('SELECT grant_id,boundary,check_id FROM capability_monitoring_checkpoints ORDER BY grant_id,boundary')])}

    def source(self, grant, checked):
        method = self.capabilities.method_package
        if grant['evidence_kind'] == 'METHOD_ENGINEERING':
            if method is None or not method.get('monitoring_basis'): raise HTTPException(409, 'FROZEN_MONITORING_SOURCE_MISSING')
            # Reuse the original host proof/archive and deployment checks. A
            # client cannot replace DEV bounds, samples or a qualification.
            with self.ledger.connection() as db:
                from roll.decisions.capabilities import GrantCommand
                self.capabilities._evidence(GrantCommand(**grant['command']), db, self.capabilities._checked_proof(grant['proof_id'], db))
            source = json.loads(encode(method['monitoring_basis']))
            if source.get('namespace') != 'METHOD_ENGINEERING': raise HTTPException(409, 'MONITORING_METHOD_NAMESPACE_MISMATCH')
            source['binding'] = {'method_package_sha256': self.capabilities.method_fingerprint, 'validation_method': validation_code()}
            return source
        validation = self.validation.get(grant['validation_id'])
        original = self.shadow.checked_archive(validation['input_archive'])
        frozen = self.shadow.get(validation['freeze_id'])
        if frozen['complete_protocol_fingerprint'] != grant['complete_protocol_fingerprint'] or original['frozen'] != frozen:
            raise HTTPException(409, 'MONITORING_FREEZE_BINDING_MISMATCH')
        reference = development_reference(original['model_input'])
        if reference != validation.get('monitoring_dev_reference'): raise HTTPException(409, 'FROZEN_DEV_REFERENCE_CHANGED')
        plan = self.forward.state(frozen['freeze_id'])
        observations = []
        for sample in plan['samples']:
            if moment(sample['recorded_at']) > checked: continue
            if self.shadow.checked_archive(sample['archive']) != {k:v for k,v in sample.items() if k != 'archive'}:
                raise HTTPException(409, 'MONITORING_SAMPLE_ARCHIVE_CHANGED')
            forecast = sample['forecast']
            if forecast['artifact_fingerprints'] != frozen['model_freeze']['artifact_fingerprints']:
                raise HTTPException(409, 'MONITORING_FORECAST_ARTIFACT_CHANGED')
            observations.append({'observation_date': sample['trading_date'], 'known_at': sample['recorded_at'],
                'instrument': forecast['instrument'], 'features': forecast['feature_snapshot']['features'], 'source_binding': sample['archive']['sha256']})
        first = moment(grant['effective_at']).astimezone(SHANGHAI).date().isoformat()
        through = checked.astimezone(SHANGHAI).date().isoformat()
        sessions = self.forward.sessions(frozen, first, through)
        assessment = plan['latest_assessment']
        results = []
        utility = None
        if assessment and moment(assessment['cutoff']) <= checked:
            if self.shadow.checked_archive(assessment['archive']) != {k:v for k,v in assessment.items() if k != 'archive'}:
                raise HTTPException(409, 'MONITORING_ASSESSMENT_ARCHIVE_CHANGED')
            results = [{**r, 'mature': True, 'known_at': assessment['recorded_at']} for r in assessment['mature']]
            results += [{**r, 'mature': False, 'known_at': assessment['recorded_at']} for r in assessment['unmatured'] + assessment['unscorable']]
            samples = {s['sample_id']: s for s in plan['samples'] if s['sample_id'] in assessment['sample_ids']}
            for result in results:
                sample = samples.get(result['sample_id'])
                if sample is None: raise HTTPException(409, 'MATURE_FORECAST_MEMBERSHIP_UNVERIFIED')
                forecast = sample['forecast']
                result.update(forecast_id=forecast['forecast_id'], instrument=forecast['instrument'],
                    observation_date=sample['trading_date'], probability=forecast['probability'])
            utility = {'namespace': 'ARCHIVED_FROZEN_DAILY_SCENARIO', 'candidate': assessment['shadow'],
                'simulation_inputs': assessment['inputs'], 'through_date': assessment['cutoff'][:10]}
        return {'frozen': frozen, 'model_input': original['model_input'], 'eligible_sessions': sessions,
                'registered_review_sessions': sessions, 'observations': observations, 'results': results,
                'development_base_rate': original['model_artifact']['base_rate'],
                'qualified_model_run_id': original['model']['model_run_id'], 'utility_basis': utility,
                'binding': {'validation_id': validation['validation_id'], 'validation_input_sha256': validation['input_archive']['sha256'],
                    'reference_fingerprint': reference['reference_fingerprint'], 'validation_method': validation_code()},
                'method_execution_facts': []}

    def executions(self, grant, db, checked):
        intents = {v['intent_id']: v for v in self.intents.listing(db)['intents'] if v['decision']['grant_id'] == grant['grant_id']}
        result = []
        for raw, in db.execute('SELECT value FROM action_fill_allocations ORDER BY rowid'):
            allocation = json.loads(raw)
            if allocation['intent_id'] not in intents or moment(allocation['known_at']) > checked: continue
            intent = intents[allocation['intent_id']]
            fraction = Decimal(allocation['allocated_quantity']) / Decimal(intent['decision']['quantity'])
            price_known = allocation.get('price') is not None
            result.append({'allocation': allocation, 'fill_fraction': str(fraction),
                'price_in_frozen_window': Decimal(intent['decision']['price_lower_yuan']) <= Decimal(allocation['price']) <= Decimal(intent['decision']['price_upper_yuan']) if price_known else None,
                # The account supplies total fees, not a proved commission or
                # quote-vs-fill decomposition. Unknown stays unknown.
                'commission_scenario_rate': None, 'slippage_each_side_rate': None, 'delay': None,
                'actual_fee_yuan': allocation.get('fee'), 'association_status': allocation['association_status'],
                'actual_time_chain': {k:allocation[k] for k in ['occurred_at','occurred_source','reported_at','reported_source','known_at','known_source']},
                'decision_time_chain': allocation['decision_time_chain']})
        return result

    def prepare(self, grant_id, checked=None):
        checked = checked or moment(now())
        with self.ledger.connection() as db:
            db.execute('BEGIN')
            row = db.execute('SELECT value FROM capability_grants WHERE id=?', (grant_id,)).fetchone()
            if row is None: raise HTTPException(404, '能力授权不存在')
            grant = json.loads(row[0])
            boundary = self.boundary(db)
            consumed = dict(db.execute('SELECT boundary,check_id FROM capability_monitoring_checkpoints WHERE grant_id=?', (grant_id,)))
            executions = self.executions(grant, db, checked)
            db.rollback()
        try:
            source = self.source(grant, checked)
            source_error = None
        except (HTTPException, KeyError, ValueError) as error:
            source, source_error = None, str(error.detail) if isinstance(error, HTTPException) else type(error).__name__
        inputs = {'grant': grant, 'boundary': boundary, 'source': source, 'source_error': source_error,
                  'actual_executions': executions, 'consumed_checkpoints': consumed,
                  'checked_at': checked.isoformat(), 'code_fingerprint': method_code()}
        return PreparedMonitoring(inputs, self.calculate(inputs))

    @staticmethod
    def calculate(inputs):
        grant, source = inputs['grant'], inputs['source']
        checked = moment(inputs['checked_at'])
        base = {'status': 'RESTRICTED', 'reasons': [], 'reference': None, 'maturity': {'review_status': 'NOT_AT_REGISTERED_CHECKPOINT',
                'mature_count': None, 'excluded_unmatured': 0, 'statistical_pass_look': False},
                'actual_execution_count': len(inputs['actual_executions']),
                'affected_scope': 'ALL_MONITOR' if grant['candidate_kind'] == 'RISK_POLICY' else 'MODEL',
                'actual_execution_observations': inputs['actual_executions'],
                'confirmation_pass_look': False, 'historic_verdict_mutated': False, 'statistical_verdict': 'NOT_REVIEWED',
                'checkpoint': None, 'method_fingerprint': inputs['code_fingerprint'], 'validation_method_fingerprint': validation_code(),
                'system_usable': False, 'evidence_kind': grant['evidence_kind'], 'complete_protocol_fingerprint': grant['complete_protocol_fingerprint']}
        if source is None:
            return {**base, 'reasons': ['REQUIRED_MONITORING_SOURCE_UNVERIFIED', inputs['source_error']]}
        frozen = source['frozen']
        if frozen['complete_protocol_fingerprint'] != grant['complete_protocol_fingerprint'] or frozen['scope'] != grant['scope']:
            return {**base, 'reasons': ['MONITORING_SCOPE_OR_FREEZE_MISMATCH']}
        reference = development_reference(source['model_input'])
        base['reference'] = reference
        if not reference['bounds']:
            return {**base, 'reasons': ['FROZEN_DEV_REFERENCE_EMPTY']}
        sessions = [day for day in source['eligible_sessions'] if date.fromisoformat(day) <= checked.astimezone(SHANGHAI).date()]
        observations = [r for r in source['observations'] if r['observation_date'] in sessions and moment(r['known_at']) <= checked]
        # Eligible missing slots are retained, rather than deleting inconvenient
        # days. METHOD calendars and source values are explicitly frozen inputs.
        features, source_gaps = [], []
        for day in sessions:
            rows = [r for r in observations if r['observation_date'] == day]
            if not rows: features.append(None); source_gaps.append(day)
            for row in rows:
                if not row.get('source_binding') or row.get('instrument') not in grant['scope']['instruments']:
                    features.append(None); source_gaps.append(day)
                else: features.append(row['features'])
        executions = inputs['actual_executions'] + source.get('method_execution_facts', [])
        results = []
        for row in source['results']:
            if moment(row['known_at']) > checked: continue
            mature_at = row.get('mature_at') or (row['maturity_date'] + 'T15:05:00+08:00' if row.get('maturity_date') else None)
            verified_mature = bool(row.get('mature') and mature_at and moment(mature_at) <= checked)
            results.append({**row, 'mature': verified_mature,
                'label': row.get('label') if verified_mature else None})
        elapsed = len([d for d in source['registered_review_sessions'] if d in sessions])
        expiry = checked >= moment(grant['expires_at'])
        operational = monitor_frozen(frozen, reference['bounds'], features, executions, results, elapsed, expiry)
        warmup = len(features) < 20
        reasons = list(operational['drift_reasons']) if not warmup else []
        if source_gaps: reasons.append('REQUIRED_MONITORING_SOURCE_UNVERIFIED')
        for record in operational['execution']:
            reasons += record['failures']
            if record['missing']: reasons.append('ACTUAL_EXECUTION_ASSUMPTIONS_UNKNOWN')
        if any(r.get('association_status') not in {None, 'USER_CONFIRMED'} for r in executions): reasons.append('ACTUAL_FILL_ASSOCIATION_UNVERIFIED')
        checkpoint = 'EXPIRY' if expiry else str(elapsed) if elapsed and elapsed % 30 == 0 else None
        maturity = operational['maturity']
        if checkpoint and elapsed != 30 and not expiry:
            maturity = monitor_frozen(frozen, reference['bounds'], features, [], results, 30)['maturity']
        if elapsed > 30 and elapsed % 30:
            maturity = {**maturity, 'missed_registered_boundary': elapsed // 30 * 30, 'review_status': 'MISSED_REGISTERED_CHECKPOINT_GAP'}
        consumed = inputs['consumed_checkpoints'].get(checkpoint)
        review = Monitoring.mature_review(source, results, sessions, checked) if checkpoint and not consumed else None
        if consumed:
            maturity = {'review_status': 'REGISTERED_CHECKPOINT_ALREADY_CONSUMED', 'original_check_id': consumed, 'statistical_pass_look': False}
        if review and review['utility'] and review['utility']['hard_failures']:
            reasons.extend('MATURE_RISK_CONSTRAINT_' + r for r in review['utility']['hard_failures'])
        return {**base, 'status': 'RESTRICTED' if reasons else 'PENDING' if warmup else 'CHECKED',
            'reasons': sorted(set(reasons)), 'operational': operational, 'maturity': maturity,
            'checkpoint': checkpoint, 'statistical_verdict': 'INCONCLUSIVE' if checkpoint and not consumed else 'NOT_REVIEWED',
            'mature_review': review,
            'mature_review_limitation': 'Registered descriptive probability/utility/support checks do not establish qualified dependent uncertainty or an extra PASS look',
            'correction_class': 'EXECUTION_ASSUMPTION' if any(r['restrict'] for r in operational['execution']) else 'MODEL_RESEARCH' if any(r.startswith('MATURE_RISK_CONSTRAINT_') for r in reasons) else 'DATA_REPAIR' if reasons else None,
            'recovery_conditions': 'Same frozen source/scope, verified current support and assumptions; reason-bound recovery check, no automatic price or clock resume'}

    @staticmethod
    def mature_review(source, results, sessions, checked):
        frozen = source['frozen']
        probability = utility = None
        gaps = []
        try:
            base = source['development_base_rate']
            forecasts, outcomes = [], {}
            for row in results:
                if row.get('observation_date') not in sessions: continue
                forecasts.append({'forecast_id': row['forecast_id'], 'instrument': row['instrument'],
                    'observation_cutoff': row['observation_date'] + 'T15:05:00+08:00', 'probability': row['probability']})
                outcomes[row['forecast_id']] = {'scoreable': row['mature'] and row.get('label') in (0,1),
                    'label': row.get('label'), 'maturity_date': checked.astimezone(SHANGHAI).date().isoformat() if row['mature'] else None}
            probability = probability_checks(frozen, {'model': {'model_run_id': source['qualified_model_run_id']},
                'model_artifact': {'base_rate': base}, 'replay': {'forecasts': forecasts,
                    'inputs': {'sessions': sessions, 'counterfactuals': outcomes},
                    'through_date': checked.astimezone(SHANGHAI).date().isoformat()}})
            probability['fit_window_reused'] = 'NO_FIT_REGISTERED_CURRENT_MATURE_OBSERVATIONS'
        except (KeyError, ValueError, TypeError): gaps.append('MATURE_PROBABILITY_INPUTS_UNVERIFIED')
        try:
            basis = source['utility_basis']
            if basis is None or basis['candidate'] is None: raise ValueError('no continuous trajectory')
            if basis['namespace'] == 'ARCHIVED_FROZEN_DAILY_SCENARIO':
                comparators = {name: simulate(frozen, basis['simulation_inputs'], [], basis['through_date'], name)
                               for name in ['CASH', 'START_HOLD', 'MA5_MA20']}
            elif source.get('namespace') == 'METHOD_ENGINEERING' and basis['namespace'] == 'METHOD_ENGINEERING_LITERAL_CASH_CHAIN':
                comparators = basis['comparators']
            else: raise ValueError('utility source not bound')
            if set(comparators) != {'CASH', 'START_HOLD', 'MA5_MA20'}: raise ValueError('missing frozen comparators')
            utility = continuous_checks(frozen, basis['candidate'], comparators)
        except (KeyError, ValueError, TypeError): gaps.append('MATURE_CONTINUOUS_UTILITY_INPUTS_UNVERIFIED')
        design = frozen['design']['statistics']
        blocks = probability['effective_time_block_upper_bound'] if probability else 0
        selected = probability['selected_mature'] if probability else 0
        bins = probability['reliability_bins'] if probability else []
        support = {'minimum_effective_time_blocks': design['minimum_effective_time_blocks'],
            'minimum_selected_mature_examples': design['minimum_selected_mature_examples'],
            'effective_time_block_upper_bound': blocks, 'selected_mature': selected,
            'occupied_bins_at_least20': bool(bins) and all(b['support_at_least20'] for b in bins),
            'meets_design_support': bool(probability) and blocks >= design['minimum_effective_time_blocks']
                and selected >= design['minimum_selected_mature_examples'] and bool(bins) and all(b['support_at_least20'] for b in bins)}
        if not support['meets_design_support']: gaps.append('REGISTERED_MATURE_SUPPORT_INSUFFICIENT')
        gaps.append('QUALIFIED_DEPENDENT_UNCERTAINTY_NOT_ESTABLISHED')
        return {'status': 'INCONCLUSIVE', 'probability': probability, 'utility': utility, 'support': support,
            'reasons': gaps, 'confirmation_pass_look': False, 'historic_verdict_mutated': False}

    def apply(self, prepared, db, basis):
        inputs, result = prepared.inputs, prepared.result
        if self.boundary(db) != inputs['boundary']: raise HTTPException(409, 'MONITORING_CURRENT_BOUNDARY_CHANGED')
        return self._persist(prepared, db, basis)

    def verify_resume(self, identifier, prepared, paused, db):
        check = self.get(identifier)
        inputs = self.shadow.checked_archive(check['input_archive'])
        if (check['grant_id'] != prepared.inputs['grant']['grant_id'] or check['status'] != 'CHECKED'
                or moment(check['checked_at']) <= moment(paused['effective_at'])
                or check['complete_protocol_fingerprint'] != prepared.inputs['grant']['complete_protocol_fingerprint']
                or inputs['code_fingerprint'] != method_code()
                or inputs['boundary'] != self.boundary(db) or prepared.inputs['boundary'] != self.boundary(db)
                or check['source_information_fingerprint'] != fingerprint([prepared.inputs['source'], prepared.inputs['actual_executions']])
                or prepared.result['status'] != 'CHECKED' or self.calculate(inputs) != check['numeric_result']):
            raise HTTPException(409, 'RECOVERY_MONITORING_REASON_SOURCE_OR_CURRENT_BOUNDARY_UNVERIFIED')

    def _persist(self, prepared, db, basis):
        inputs, result = prepared.inputs, prepared.result
        input_key = fingerprint(inputs)
        prior = db.execute('SELECT value FROM capability_monitoring WHERE fingerprint=?', (input_key,)).fetchone()
        if prior: return json.loads(prior[0])
        identifier = str(uuid4())
        checkpoint = result['checkpoint']
        if checkpoint:
            prior_checkpoint = db.execute('SELECT check_id FROM capability_monitoring_checkpoints WHERE grant_id=? AND boundary=?', (inputs['grant']['grant_id'], checkpoint)).fetchone()
            if prior_checkpoint:
                result = {**result, 'maturity': {'review_status': 'REGISTERED_CHECKPOINT_ALREADY_CONSUMED', 'original_check_id': prior_checkpoint[0], 'statistical_pass_look': False}, 'statistical_verdict': 'NOT_REVIEWED', 'mature_review': None}
            else:
                db.execute('INSERT INTO capability_monitoring_checkpoints VALUES(?,?,?)', (inputs['grant']['grant_id'], checkpoint, identifier))
        value = {'check_id': identifier, 'grant_id': inputs['grant']['grant_id'], 'checked_at': inputs['checked_at'],
                 'recorded_at': now(), 'basis': basis, 'input_fingerprint': input_key,
                 'source_information_fingerprint': fingerprint([inputs['source'], inputs['actual_executions']]),
                 'numeric_result': prepared.result,
                 'input_archive': self.evidence.archive(encode(inputs).encode(), 'CAPABILITY_MONITORING_INPUT', db=db), **result}
        if result['status'] == 'RESTRICTED':
            event = self.capabilities.restrict(db, inputs['grant']['grant_id'], result['affected_scope'],
                'EXECUTION_MISMATCH' if result.get('correction_class') == 'EXECUTION_ASSUMPTION' else 'MATURE_EVIDENCE_DETERIORATION' if result.get('correction_class') == 'MODEL_RESEARCH' else 'DATA_DRIFT',
                '；'.join(str(r) for r in result['reasons']), identifier)
            value['restriction_event_id'] = event['event_id']
        if self.capabilities.actions: self.capabilities.actions.current(db=db)
        value['archive'] = self.evidence.archive(encode(value).encode(), 'CAPABILITY_MONITORING_RECORD', db=db)
        db.execute('INSERT INTO capability_monitoring VALUES(?,?,?)', (identifier, input_key, encode(value)))
        return value

    def prepare_maintenance(self, checked):
        if not self.capabilities.lifecycle()['observations_allowed']: return []
        with self.ledger.connection() as db:
            grants = [json.loads(r[0]) for r in db.execute('SELECT value FROM capability_grants ORDER BY rowid')]
            selected = [g['grant_id'] for g in grants if self.running_allowed(db, g['grant_id'])]
        return [self.prepare(identifier, checked) for identifier in selected]

    def apply_maintenance(self, prepared, db):
        # All captured boundaries are checked before this controlled writer
        # appends any member's restrictions. No other writer can interleave.
        boundary = self.boundary(db)
        if any(p.inputs['boundary'] != boundary for p in prepared):
            raise HTTPException(409, 'MAINTENANCE_CURRENT_BOUNDARY_CHANGED')
        controls = self.capabilities.lifecycle(db)
        values = [self._persist(p, db, 'REGISTERED_MAINTENANCE') for p in prepared] if controls['observations_allowed'] else []
        expired = self.capabilities.expire(db)
        self.capabilities.actions.current(db=db)
        ids = {v['check_id'] for v in values}
        previous = {r['grant_id']: r for r in self.records(db) if r['basis'] == 'REGISTERED_MAINTENANCE' and r['check_id'] not in ids}
        source_changed = any(v['grant_id'] in previous and v['source_information_fingerprint'] != previous[v['grant_id']]['source_information_fingerprint'] for v in values)
        return {'mature_labels': {'status': 'CHECKED' if controls['observations_allowed'] else 'PAUSED_ALL_MONITOR',
                    'check_ids': [v['check_id'] for v in values], 'reviews': [v['maturity'] for v in values], 'confirmation_pass_look': False},
                'qualification_expiry': {'status': 'CHECKED', 'expired_event_count': expired},
                'new_experiment_conditions': {'status': 'REVIEW_NEW_INFORMATION_NO_AUTOMATIC_EXPERIMENT' if source_changed else 'NO_NEW_VERIFIED_INFORMATION',
                    'automatic_fit': False, 'new_protocol_required': True, 'source_fingerprint': fingerprint([p.inputs['source'] for p in prepared])}}

    def check_post_close(self, checked):
        if not self.capabilities.lifecycle()['observations_allowed']: return
        day = checked.astimezone(SHANGHAI).date().isoformat()
        phase = self.evidence.market.rules.calendar('SSE', date.fromisoformat(day), checked)['phase']
        if phase not in {'POST_CLOSE_PREP','FIXED_PRICE','AFTER_CLOSE'}: return
        with self.ledger.connection() as db:
            ids = [r[0] for r in db.execute('SELECT id FROM capability_grants ORDER BY rowid')
                   if self.running_allowed(db, r[0]) and not db.execute("SELECT 1 FROM capability_monitoring WHERE json_extract(value,'$.grant_id')=? AND json_extract(value,'$.basis')='RUNNING_POST_CLOSE' AND date(json_extract(value,'$.checked_at'),'+8 hours')=?", (r[0], day)).fetchone()]
        for identifier in ids:
            prepared = self.prepare(identifier, checked)
            with self.ledger.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                if not self.running_allowed(db, identifier): continue
                if db.execute("SELECT 1 FROM capability_monitoring WHERE json_extract(value,'$.grant_id')=? AND json_extract(value,'$.basis')='RUNNING_POST_CLOSE' AND date(json_extract(value,'$.checked_at'),'+8 hours')=?", (identifier, day)).fetchone(): continue
                self.apply(prepared, db, 'RUNNING_POST_CLOSE')
                db.commit()

    def running_allowed(self, db, grant_id):
        control = self.capabilities.lifecycle(db, grant_id)
        return control['observations_allowed'] and not any(s['state'] in {'REVOKED', 'EXPIRED'} for s in control['scopes'].values())

    def check(self, command):
        if not self.capabilities.lifecycle(grant_id=command.grant_id)['observations_allowed']: raise HTTPException(409, 'ALL_MONITOR_SUSPENDED')
        prepared = self.prepare(command.grant_id)
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if not self.capabilities.lifecycle(db, command.grant_id)['observations_allowed']: raise HTTPException(409, 'ALL_MONITOR_SUSPENDED')
            if not self.running_allowed(db, command.grant_id): raise HTTPException(409, 'TERMINAL_GRANT_MONITORING_CLOSED')
            value = self.apply(prepared, db, command.basis)
            db.commit()
        self.capabilities.journal.reconcile_committed()
        return value

    def replay(self, identifier):
        value = self.get(identifier)
        inputs = self.shadow.checked_archive(value['input_archive'])
        if inputs['code_fingerprint'] != method_code(): raise HTTPException(409, 'MONITORING_CODE_CHANGED_SUCCESSOR_REQUIRED')
        result = self.calculate(inputs)
        # A consumed checkpoint is an application disposition, not a numeric
        # result rewrite. Its original numeric inputs remain replayable.
        return {'check_id': identifier, 'matches_original': result == value['numeric_result'],
                'network_calls': 0, 'historic_verdict_mutated': False, 'confirmation_pass_look': False}
