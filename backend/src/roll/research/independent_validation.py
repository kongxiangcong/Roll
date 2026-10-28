"""Preregistered, single-endpoint consumption of actual ForwardArchive evidence.

No client-supplied predictions, labels, independence flags or replacement limits.
Historical CAL and protected SEALED are never used as independent outcomes.
"""
from datetime import datetime
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from roll.accounts.ledger import encode
from roll.market.rules import SHANGHAI
from roll.research.models import code_fingerprint, predict
from roll.research.forward import ForwardArchive, forward_features
from roll.research.registry import deadline_preview
from roll.research.shadow import fingerprint, shadow_code, simulate
from roll.research.statistics import fingerprint as statistics_code
from roll.research.validation import combine, gate, continuous_checks, probability_checks, validation_code


class IndependentCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_complete_protocol_fingerprint: str
    basis: str = Field(min_length=1, max_length=2000)


def executor_code():
    return fingerprint({'executor': hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n')).hexdigest(),
        'model': code_fingerprint(), 'shadow': shadow_code(), 'forward': ForwardArchive.code(),
        'statistics': statistics_code(), 'validation': validation_code()})


def evaluate_endpoint(original):
    """Pure evaluation from the archived input; repeat evaluation creates no new look."""
    plan, frozen, state = (original[k] for k in ('plan', 'frozen', 'forward'))
    assessment = original['assessment']
    samples = state['samples']
    real = state['namespace'] == 'FORWARD'
    through = datetime.fromisoformat(assessment['cutoff']).astimezone(SHANGHAI).date().isoformat()
    forecasts = [s['forecast'] for s in samples]
    inputs = assessment['inputs']
    matches = True
    defects = []
    registration = datetime.fromisoformat(plan['registered_at'])
    if len({s['sample_id'] for s in samples}) != len(samples):
        defects.append('DUPLICATE_FORWARD_SAMPLE')
    for sample in samples:
        forecast = sample['forecast']
        if datetime.fromisoformat(sample['recorded_at']) <= registration:
            defects.append('PREDICTION_PRECEDES_PREREGISTRATION')
        if forecast['artifact_fingerprints'] != original['model']['artifact_fingerprints']:
            defects.append('FORECAST_MODEL_BINDING_MISMATCH')
        if real:
            if (sample['evidence_kind'] != 'FORWARD' or not sample['confirmatory_sample']
                    or not forecast.get('actual_forward_prediction')):
                defects.append('NONFORWARD_SAMPLE')
            if sample['trading_date'] <= plan['admission']['excluded_through_date']:
                defects.append('TRAIN_CAL_OR_PROTECTED_WINDOW_REUSED')
            try:
                snapshot = forward_features(sample['replay_inputs']['inputs']['facts'], sample['trading_date'],
                    datetime.fromisoformat(forecast['consumer_knowledge_cutoff']),
                    original['model']['fit']['feature_names'], frozen.get('data_use') == 'RECONSTRUCTED_RESEARCH')
                matches = matches and snapshot == forecast['feature_snapshot']
            except (ValueError, KeyError, ArithmeticError):
                defects.append('FORWARD_FEATURE_PROVENANCE_REPLAY_FAILED')
                matches = False
        prediction = predict(original['model']['fit'], forecast['feature_snapshot'],
                             original['model']['calibrator']['intercept_shift'])
        matches = matches and all(forecast.get(k) == v for k, v in prediction.items())
        archived = sample['replay_inputs']
        replay = simulate(archived['frozen'], archived['inputs'], archived['forecasts'], archived['through_date'])
        replay['revision'] = len(archived['forecasts'])
        matches = matches and replay == sample['shadow']
    classified = assessment['mature'] + assessment['unmatured'] + assessment['unscorable']
    if sorted(r['sample_id'] for r in classified) != sorted(s['sample_id'] for s in samples):
        defects.append('OUTCOME_SAMPLE_MEMBERSHIP_MISMATCH')
    if assessment['cutoff'] != state['endpoint']['cutoff']:
        defects.append('ENDPOINT_CUTOFF_MISMATCH')
    for category in ('mature', 'unmatured', 'unscorable'):
        if assessment[category] != state['endpoint'][category]:
            defects.append('ENDPOINT_OUTCOME_BINDING_MISMATCH')
    candidate = comparators = economics = probability = None
    if inputs and samples:
        candidate = simulate(frozen, inputs, forecasts, through)
        candidate['revision'] = len(samples)
        matches = matches and candidate == assessment['shadow']
        comparators = {name: simulate(frozen, inputs, [], through, name)
                      for name in ('CASH', 'START_HOLD', 'MA5_MA20')}
        # Maturity is independently recomputed from the same entry/exit/cash rules.
        for result in assessment['mature']:
            sample = next(s for s in samples if s['sample_id'] == result['sample_id'])
            maturity = sample['action']['maturity_date']
            if not maturity or datetime.fromisoformat(maturity+'T15:05:00+08:00') > datetime.fromisoformat(assessment['cutoff']):
                defects.append('IMMATURE_LABEL_ADMITTED')
                continue
            diagnostic = {**frozen, 'baseline': {'cash_yuan': '100000000.00', 'positions': []},
                'policy': {**frozen['policy'], 'probability_threshold': '0', 'maximum_gross_exposure': '1'}}
            counter = simulate(diagnostic, inputs, [sample['forecast']], maturity)
            pnl = Decimal(counter['realized_gain_yuan'])
            sold = any(e['kind'] == 'SELL_FILL' and e['forecast_id'] == sample['sample_id'] for e in counter['events'])
            if (not sold or counter['missing'] or assessment['gaps'] or not result['scoreable']
                    or result['label'] != int(pnl > 0) or Decimal(result['net_pnl_yuan']) != pnl):
                defects.append('MATURE_OUTCOME_REPLAY_MISMATCH')
        economics = continuous_checks(frozen, candidate, comparators)
        # No forecast after the maturity boundary is silently scored as a loss.
        outcomes = {r['sample_id']: r for r in assessment['mature']}
        scoring_inputs = {**inputs, 'sessions': [d for d in inputs['sessions'] if d <= through],
                          'counterfactuals': outcomes}
        probability = probability_checks(frozen, {'model': original['model'],
            'model_artifact': original['model_artifact'], 'replay': {'inputs': scoring_inputs,
            'forecasts': forecasts, 'through_date': through}})
        probability.update(independent_calibration_test=real and not defects,
                           fit_window_reused=False, scope='PREREGISTERED_FORWARD_ONLY')
    hard = economics['hard_failures'] if economics else []
    missing = bool(assessment['gaps'] or assessment['unscorable'] or state['missing_checkpoints']
                   or state['calendar_gaps'] or (candidate and candidate['missing']))
    gates = {
        'G1': gate('FAIL' if defects else 'PASS' if real and samples else 'INCONCLUSIVE',
                   sorted(set(defects)) or ([] if real and samples else ['NO_INDEPENDENT_REAL_SAMPLES']),
                   {'scope': 'Host-recorded prospective provenance only; outside-host exposure remains unknown'}),
        'G2': gate('FAIL' if not matches else 'PASS' if samples else 'INCONCLUSIVE',
                   ['FORWARD_OR_OUTCOME_REPLAY_MISMATCH'] if not matches else [] if samples else ['NO_SAMPLES_TO_REPLAY'],
                   {'scope': 'Frozen prediction and ledger arithmetic only; deployment acceptance separate'}),
        'G3': gate('INCONCLUSIVE', ['INDEPENDENT_SUPPORT_AND_SAMPLING_ASSUMPTIONS_NOT_VERIFIED'], probability),
        'G4': gate('FAIL' if hard else 'INCONCLUSIVE', hard or ['INDEPENDENT_NAV_SUPPORT_AND_RISK_MATCHING_NOT_VERIFIED'], economics),
        'G5': gate('INCONCLUSIVE', ['FROZEN_ROBUSTNESS_PACKAGE_NOT_ADMITTED']),
        'G6': gate('PASS' if real and samples and matches and not missing else 'INCONCLUSIVE',
                   [] if real and samples and matches and not missing else ['REAL_FORWARD_COVERAGE_INCOMPLETE_OR_METHOD_ONLY']),
        'G7': gate('INCONCLUSIVE', ['MATURE_FORWARD_SUPPORT_INSUFFICIENT_OR_ASSUMPTIONS_UNVERIFIED'],
                   {'mature': len(assessment['mature']), 'unmatured': len(assessment['unmatured']),
                    'unscorable': len(assessment['unscorable']), 'samples': len(samples)})}
    return {'validation_verdict': combine(gates), 'gates': gates, 'candidate': candidate, 'comparators': comparators,
        'namespace': state['namespace'], 'evidence_kind': 'REAL_ACQUISITION' if real else 'METHOD_CASE',
        'maturity': {k: assessment[k] for k in ('mature', 'unmatured', 'unscorable')},
        'missing_checkpoints': state['missing_checkpoints'], 'feasibility': plan['admission']['feasibility'],
        'statistical_pass': False, 'capability': 'NOT_GRANTED', 'system_usable': False,
        'review_status': 'PENDING_TECHNICAL_REVIEW', 'human_review': '未经人工独立复核',
        'sealed_read': False, 'calibration_refitted': False, 'network_calls': 0}


class IndependentValidation:
    def __init__(self, forward):
        self.forward = forward
        self.shadow, self.registry = forward.shadow, forward.registry
        self.ledger, self.evidence = forward.ledger, forward.evidence
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS research_independent_plans(freeze_id TEXT PRIMARY KEY, command_hash TEXT NOT NULL, value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS research_independent_results(freeze_id TEXT PRIMARY KEY, value TEXT NOT NULL)')

    def admission(self, freeze_id):
        frozen = self.shadow.get(freeze_id)
        manifest = self.registry.attempt_manifest(frozen['protocol_id'])
        protocols = [self.registry.get(pid) for pid in manifest['family_protocol_ids']]
        audits = [e for p in protocols for e in self.registry.audit(p['protocol_id'])]
        exposures = [e for e in audits if e['action'] in ('SEALED_INPUT_ACCESSED', 'ORIGINAL_ARCHIVE_EXPOSED')]
        # Metadata only; a protected or previously fitted interval is never opened.
        windows = [{'protocol_id': p['protocol_id'], 'partition': name, **window}
            for p in protocols for name, window in p.get('design', {}).get('windows', {}).items()
            if window.get('last_date')]
        excluded = max((w['last_date'] for w in windows), default='1900-01-01')
        checked = self.forward.clock()
        preview = deadline_preview(checked)
        # Even treating every natural day as tradable is a conservative upper bound.
        maximum_days = (datetime.fromisoformat(preview['deadline']).date()-checked.astimezone(SHANGHAI).date()).days+1
        limits = frozen['design']['statistics']
        needed = limits['minimum_effective_time_blocks']
        blocks = limits['dependency_sensitivity_block_sessions']
        projection = {str(b): max(0, maximum_days-20)//b for b in blocks}
        gaps = []
        try:
            plan = self.forward.plan(freeze_id)
        except HTTPException as error:
            if error.status_code != 404:
                raise
            plan = None
            gaps.append('FORWARD_PLAN_REQUIRED_BEFORE_PREREGISTRATION')
        if frozen['fingerprints']['shadow_code'] != shadow_code() or frozen['fingerprints']['model_code'] != code_fingerprint():
            gaps.append('FROZEN_CODE_CHANGED_SUCCESSOR_REQUIRED')
        if plan and plan['adapter_code_fingerprint'] != self.forward.code():
            gaps.append('FORWARD_ADAPTER_CHANGED_SUCCESSOR_REQUIRED')
        with self.ledger.connection() as db:
            count = db.execute('SELECT COUNT(*) FROM research_forward_samples WHERE protocol_id=?', (frozen['protocol_id'],)).fetchone()[0]
        if count or (plan and plan['status'] != 'WAITING_FOR_FIRST_PERSISTED_PREDICTION'):
            gaps.append('PREREGISTRATION_MUST_PRECEDE_FIRST_PREDICTION')
        if plan and plan['namespace'] == 'METHOD_CASE' and os.environ.get('ROLL_ENV') != 'test':
            gaps.append('METHOD_ONLY_ALLOWED_IN_TEST')
        if plan and plan['namespace'] == 'FORWARD' and checked.astimezone(SHANGHAI).date().isoformat() <= excluded:
            gaps.append('FORWARD_START_OVERLAPS_FITTED_OR_PROTECTED_WINDOW')
        if any(a['status'] == 'RUNNING' for a in manifest['attempts']):
            gaps.append('FAMILY_ATTEMPT_STILL_RUNNING')
        return {'admitted': not gaps, 'gaps': gaps, 'metadata_only': True, 'sealed_read': False,
            'excluded_through_date': excluded, 'excluded_windows': windows,
            'exposure_events': exposures, 'family_attempt_manifest': manifest,
            'outside_host_exposure': 'UNKNOWN_NOT_CERTIFIED',
            'feasibility': {'status': 'INFEASIBLE_FOR_PASS_UNDER_FROZEN_LIMITS' if min(projection.values()) < needed else 'ASSUMPTIONS_STILL_REQUIRE_VALIDATION',
                'maximum_natural_months': preview['maximum_natural_months'], 'natural_day_upper_bound': maximum_days,
                'mature_block_upper_bounds': projection, 'required_blocks': needed,
                'new_fit_attempts': 0, 'new_calibration_attempts': 0, 'final_looks': 1,
                'changes_to_existing_thresholds': False},
            'complete_protocol_fingerprint': frozen['complete_protocol_fingerprint']}

    def plan(self, freeze_id):
        with self.ledger.connection() as db:
            row = db.execute('SELECT value FROM research_independent_plans WHERE freeze_id=?', (freeze_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'INDEPENDENT_PREREGISTRATION_NOT_FOUND')
        value = json.loads(row[0])
        if self.shadow.checked_archive(value['archive']) != {k: v for k, v in value.items() if k != 'archive'}:
            raise HTTPException(409, 'INDEPENDENT_PLAN_ARCHIVE_MISMATCH')
        return value

    def register(self, freeze_id, command):
        command_hash = fingerprint(command.model_dump())
        with self.ledger.connection() as db:
            prior = db.execute('SELECT command_hash FROM research_independent_plans WHERE freeze_id=?', (freeze_id,)).fetchone()
        if prior:
            if prior[0] != command_hash:
                raise HTTPException(409, 'INDEPENDENT_PREREGISTRATION_IMMUTABLE')
            return self.plan(freeze_id)
        admission = self.admission(freeze_id)
        if command.expected_complete_protocol_fingerprint != admission['complete_protocol_fingerprint']:
            raise HTTPException(409, 'COMPLETE_PROTOCOL_FINGERPRINT_MISMATCH')
        if not admission['admitted']:
            raise HTTPException(409, admission)
        frozen = self.shadow.get(freeze_id)
        value = {'freeze_id': freeze_id, 'protocol_id': frozen['protocol_id'],
            'registered_at': self.forward.clock().isoformat(), 'basis': command.basis,
            'complete_protocol_fingerprint': frozen['complete_protocol_fingerprint'],
            'executor_fingerprint': executor_code(), 'admission': admission,
            'endpoint_policy': 'ORIGINAL_FORWARD_DEADLINE_OR_EARLIER_STOP; ONE_FINAL_RESULT',
            'resources': {'maximum_samples': 1000, 'maximum_sessions': 3650},
            'capability': 'NOT_GRANTED'}
        value['archive'] = self.evidence.archive(encode(value).encode(), 'INDEPENDENT_PREREGISTRATION')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior = db.execute('SELECT command_hash FROM research_independent_plans WHERE freeze_id=?', (freeze_id,)).fetchone()
            if prior:
                if prior[0] != command_hash:
                    raise HTTPException(409, 'INDEPENDENT_PREREGISTRATION_IMMUTABLE')
                return self.plan(freeze_id)
            if db.execute('SELECT COUNT(*) FROM research_forward_samples WHERE protocol_id=?', (frozen['protocol_id'],)).fetchone()[0]:
                raise HTTPException(409, 'FIRST_PREDICTION_RACED_PREREGISTRATION')
            db.execute('INSERT INTO research_independent_plans VALUES(?,?,?)', (freeze_id, command_hash, encode(value)))
            self.registry.event(frozen['protocol_id'], 'INDEPENDENT_VALIDATION_PREREGISTERED', db=db,
                freeze_id=freeze_id, archive=value['archive'], sealed_read=False)
            db.commit()
        return value

    def get(self, freeze_id):
        with self.ledger.connection() as db:
            row = db.execute('SELECT value FROM research_independent_results WHERE freeze_id=?', (freeze_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'INDEPENDENT_RESULT_NOT_FOUND')
        value = json.loads(row[0])
        if self.shadow.checked_archive(value['archive']) != {k: v for k, v in value.items() if k != 'archive'}:
            raise HTTPException(409, 'INDEPENDENT_RESULT_ARCHIVE_MISMATCH')
        self.shadow.checked_archive(value['input_archive'])
        return value

    def create(self, freeze_id):
        try:
            return self.get(freeze_id)
        except HTTPException as error:
            if error.status_code != 404:
                raise
        plan = self.plan(freeze_id)
        if plan['executor_fingerprint'] != executor_code():
            raise HTTPException(409, 'INDEPENDENT_CODE_CHANGED_SUCCESSOR_REQUIRED')
        state = self.forward.state(freeze_id)
        if state['status'] != 'CLOSED':
            raise HTTPException(409, 'FINAL_ENDPOINT_NOT_CLOSED_NO_EARLY_LOOK')
        assessment = state['latest_assessment']
        if not assessment:
            raise HTTPException(409, 'SAVED_ENDPOINT_ASSESSMENT_REQUIRED')
        if len(state['samples']) > plan['resources']['maximum_samples'] or len((assessment['inputs'] or {}).get('sessions', [])) > plan['resources']['maximum_sessions']:
            raise HTTPException(409, 'INDEPENDENT_RESOURCE_LIMIT')
        for item in [assessment, state['endpoint'], *state['samples']]:
            if self.shadow.checked_archive(item['archive']) != {k: v for k, v in item.items() if k != 'archive'}:
                raise HTTPException(409, 'FORWARD_ARCHIVE_BINDING_MISMATCH')
        frozen = self.shadow.get(freeze_id)
        model = self.forward.models.get(frozen['model_run_id'])
        original = {'plan': plan, 'frozen': frozen, 'forward': state, 'assessment': assessment,
            'model': model, 'model_artifact': self.shadow.checked_archive(model['model_artifact']),
            'audit_at_endpoint': self.admission(freeze_id)}
        if original['model_artifact']['fit'] != model['fit'] or self.shadow.checked_archive(model['calibrator_artifact'])['intercept_shift'] != model['calibrator']['intercept_shift']:
            raise HTTPException(409, 'MODEL_ARTIFACT_BINDING_MISMATCH')
        result = evaluate_endpoint(original)
        value = {'freeze_id': freeze_id, 'recorded_at': self.forward.clock().isoformat(),
            'executor_fingerprint': plan['executor_fingerprint'], 'preregistration': plan['archive'],
            'input_archive': self.evidence.archive(encode(original).encode(), 'INDEPENDENT_ENDPOINT_INPUT'),
            'result_fingerprint': fingerprint(result), 'final_look_count': 1, **result}
        value['archive'] = self.evidence.archive(encode(value).encode(), 'INDEPENDENT_VALIDATION_RESULT')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM research_independent_results WHERE freeze_id=?', (freeze_id,)).fetchone():
                return self.get(freeze_id)
            db.execute('INSERT INTO research_independent_results VALUES(?,?)', (freeze_id, encode(value)))
            self.registry.event(frozen['protocol_id'], 'INDEPENDENT_ENDPOINT_EVALUATED', db=db,
                freeze_id=freeze_id, verdict=value['validation_verdict'], final_look_count=1, sealed_read=False)
            db.commit()
        return value

    def replay(self, freeze_id):
        value = self.get(freeze_id)
        if value['executor_fingerprint'] != executor_code():
            raise HTTPException(409, 'INDEPENDENT_CODE_CHANGED_SUCCESSOR_REQUIRED')
        original = self.shadow.checked_archive(value['input_archive'])
        return {'matches_original': fingerprint(evaluate_endpoint(original)) == value['result_fingerprint'],
                'network_calls': 0, 'additional_final_looks': 0, 'capability': 'NOT_GRANTED'}
