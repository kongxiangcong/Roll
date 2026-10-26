"""Linked feature design supplements and immutable available-at observations; no fit."""
import copy
import hashlib
import json
from datetime import datetime
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Literal
from uuid import uuid4
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from roll.accounts.ledger import encode, now
from roll.market.financial_metrics import metrics, VERSION as FINANCIAL_VERSION
from roll.research.registry import ProtocolCommand
from roll.market.sentiment import REJECT_VERSION, OBJECT_VERSION
from roll.market.news_events import GROUPING_VERSION, ASSOCIATION_VERSION
from roll.market.sentiment_series import CHECKPOINT, VERSION as SERIES_VERSION

VERSION = 'financial-sentiment-feature-protocol-v1'
VARIANTS = ('BASELINE', 'FINANCIAL', 'SENTIMENT', 'BOTH')
FINANCIAL = ('revenue_yoy', 'parent_net_profit_yoy', 'gross_margin', 'net_margin', 'cash_profit_ratio', 'debt_ratio')
SENTIMENT = ('positive_share', 'negative_share', 'neutral_share', 'rejection_share', 'coverage', 'event_support')
SCHEMA = {'financial_version': FINANCIAL_VERSION, 'financial_fields': list(FINANCIAL),
    'financial_selection': 'LATEST_REPORT_ACTUALLY_AVAILABLE_AT_CUTOFF; SAME_SCOPE_UNIT_CURRENCY_AND_FORMULA',
    'sentiment_fields': list(SENTIMENT), 'sentiment_aggregation': 'LATEST_REACHED_RECORDED_CHECKPOINT_UNIQUE_NEW_EVENTS_INCLUDING_REJECTED',
    'sentiment_share_precision': 28, 'sentiment_units': 'SHARES_AND_COVERAGE_ARE_RATIOS_0_TO_1; EVENT_SUPPORT_IS_COUNT',
    'neutral': 'UNSUPPORTED_OR_NO_OBSERVATIONS_IS_NULL_NEVER_ZERO', 'missing': 'NULL_WITH_REASON_NO_IMPUTATION_NO_SELECTIVE_DELETION',
    'cutoff': 'SOURCE_AND_CLASSIFICATION_AND_SERIES_KNOWN_BY_NOT_AFTER_CUTOFF',
    'price_volume': 'INHERIT_EXISTING_BASELINE_ARCHIVES_NOT_RECOMPUTED_HERE'}


def fingerprint(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def aware(value):
    stamp = datetime.fromisoformat(value) if isinstance(value, str) else value
    if stamp.tzinfo is None:
        raise HTTPException(422, 'FEATURE_CUTOFF_AWARE_TIME_REQUIRED')
    return stamp


def share(numerator, denominator):
    with localcontext() as context:
        context.prec = SCHEMA['sentiment_share_precision']
        return str(Decimal(numerator)/Decimal(denominator))


class FeaturePlanCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    idempotency_key: str = Field(min_length=1, max_length=128)
    basis: str = Field(min_length=1, max_length=2000)
    predecessor_id: str
    variants: list[Literal['BASELINE', 'FINANCIAL', 'SENTIMENT', 'BOTH']] = Field(min_length=1, max_length=4)
    sentiment_profile: Literal['legacy', 'finbert-adaptation-01'] = 'finbert-adaptation-01'


class FeatureSnapshotCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    idempotency_key: str = Field(min_length=1, max_length=128)
    basis: str = Field(min_length=1, max_length=2000)
    instrument: Literal['SSE:600362'] = 'SSE:600362'
    known_by: datetime
    series_id: str | None = None


class FeaturePreflightCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    idempotency_key: str = Field(min_length=1, max_length=128)
    snapshot_id: str


class FeatureProtocols:
    def __init__(self, registry, income, supplement, series):
        self.registry, self.ledger, self.evidence = registry, registry.ledger, registry.evidence
        self.income, self.supplement, self.series = income, supplement, series
        with self.ledger.connection() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS research_feature_plans(id TEXT PRIMARY KEY,key TEXT UNIQUE,command_hash TEXT,value TEXT);
                CREATE TABLE IF NOT EXISTS research_feature_snapshots(id TEXT PRIMARY KEY,key TEXT UNIQUE,command_hash TEXT,value TEXT);
                CREATE TABLE IF NOT EXISTS research_feature_preflights(id TEXT PRIMARY KEY,plan_id TEXT,key TEXT,command_hash TEXT,value TEXT,UNIQUE(plan_id,key));''')

    def prior(self, table, key, command_hash, plan_id=None):
        with self.ledger.connection() as db:
            row = db.execute(f'SELECT command_hash,value FROM {table} WHERE key=?'+(' AND plan_id=?' if plan_id else ''), (key, plan_id) if plan_id else (key,)).fetchone()
        if row:
            if row[0] != command_hash:
                raise HTTPException(409, 'FEATURE_IDEMPOTENCY_CONFLICT')
            return self.checked(json.loads(row[1]))

    def checked(self, value):
        original = json.loads(self.evidence.raw(value['archive']['sha256']).read_bytes())
        if original != {key: item for key, item in value.items() if key != 'archive'}:
            raise HTTPException(409, 'FEATURE_ARCHIVE_BINDING_MISMATCH')
        return value

    def archived(self, value):
        value['archive'] = self.evidence.archive(encode(value).encode(), 'RESEARCH_FEATURE_CONTRACT', evidence_kind=value['evidence_kind'])
        return value

    def get(self, table, identifier):
        with self.ledger.connection() as db:
            row = db.execute(f'SELECT value FROM {table} WHERE id=?', (identifier,)).fetchone()
        if not row:
            raise HTTPException(404, 'FEATURE_RECORD_NOT_FOUND')
        return self.checked(json.loads(row[0]))

    def listing(self, table):
        with self.ledger.connection() as db:
            rows = db.execute(f'SELECT value FROM {table} ORDER BY rowid DESC LIMIT 100').fetchall()
        return [self.checked(json.loads(row[0])) for row in rows]

    def budget(self, predecessor_id, db=None):
        self.registry.get(predecessor_id)
        if db is None:
            with self.ledger.connection() as connection:
                return self.budget(predecessor_id, connection)
        family = self.registry.family(predecessor_id, db)
        attempts = [json.loads(row[0]) for pid in family for row in db.execute('SELECT value FROM research_attempts WHERE protocol_id=?', (pid,))]
        fits = [attempt for attempt in attempts if attempt['category'] in ('PRIMARY_FIT', 'G5_NEIGHBOR')]
        calibrations = [attempt for attempt in attempts if attempt['category'] == 'CALIBRATION']
        plans = [json.loads(row[0]) for row in db.execute('SELECT value FROM research_feature_plans')]
        reserved = sum(len(plan['variants']) for plan in plans if plan['predecessor_id'] in family)
        return {'family_protocol_ids': family, 'fit_limit': 5, 'fit_records_including_failed_aborted': len(fits),
            'calibration_limit': 1, 'calibration_records': len(calibrations), 'reserved_feature_configurations': reserved,
            'remaining_configurations': max(0, 5-len(fits)-reserved), 'unreserved_fit_slots': 5-len(fits)-reserved,
            'attempt_ids': [attempt['attempt_id'] for attempt in attempts],
            'note': 'Registration reservations are not fits. Later executors must bind them and recheck live family budget; this API never executes training.'}

    def calculation_sources(self):
        root = Path(__file__).parents[1]/'market'
        values = {name: hashlib.sha256((root/name).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
            for name in ('financial_metrics.py', 'financial_statements.py', 'sentiment_series.py', 'sentiment_object.py', 'sentiment_contract.py')}
        values['feature_protocol.py'] = hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
        return values

    def register(self, command):
        hashed = fingerprint(command.model_dump())
        prior = self.prior('research_feature_plans', command.idempotency_key, hashed)
        if prior:
            return prior
        if not command.basis.strip():
            raise HTTPException(422, 'FEATURE_BASIS_REQUIRED')
        if command.variants != [variant for variant in VARIANTS if variant in command.variants]:
            raise HTTPException(422, 'FEATURE_VARIANTS_UNIQUE_CANONICAL_ORDER_REQUIRED')
        parent = self.registry.get(command.predecessor_id)
        design = parent.get('design') or {}
        required = ('event', 'horizon_sessions', 'costs', 'execution', 'windows', 'label_isolation', 'primary_objective', 'statistics', 'stopping', 'candidates')
        if not parent.get('dataset_id') or any(not design.get(key) for key in required):
            raise HTTPException(409, 'FEATURE_EXISTING_COMPLETE_BASELINE_DESIGN_REQUIRED')
        if 'SSE:600362' not in parent['scope'].get('instruments', []):
            raise HTTPException(409, 'FEATURE_SAME_SUPPORTED_ISSUER_SCOPE_REQUIRED')
        budget = self.budget(parent['protocol_id'])
        if len(command.variants) > budget['remaining_configurations']:
            raise HTTPException(409, {'code': 'FEATURE_FAMILY_BUDGET_INSUFFICIENT', 'budget': budget})
        sentiment_contract = None
        if any(variant in ('SENTIMENT', 'BOTH') for variant in command.variants):
            try:
                reference_sha, reference = self.series.sentiment.reference(command.sentiment_profile)
            except ValueError as error:
                raise HTTPException(409, str(error)) from error
            modern = command.sentiment_profile != 'legacy'
            sentiment_contract = {'profile': command.sentiment_profile, 'reference_sha256': reference_sha,
                'reject_layer': OBJECT_VERSION if modern else REJECT_VERSION,
                'classification_version': 'sentiment-classification-v2-three-class' if modern else 'sentiment-classification-v1',
                'news_grouping_version': GROUPING_VERSION, 'news_association_version': ASSOCIATION_VERSION,
                'labels_supported': ['POSITIVE', 'NEGATIVE', 'NEUTRAL'] if modern else ['POSITIVE', 'NEGATIVE'],
                'checkpoint': copy.deepcopy(CHECKPOINT), 'series_version': SERIES_VERSION}
        # The original core proposal remains unchanged. This linked supplement is
        # separately frozen and cannot masquerade as an executable feature model.
        child = self.registry.register(ProtocolCommand(dataset_id=parent['dataset_id'], predecessor_id=parent['protocol_id'], basis=command.basis))
        dataset = self.registry.dataset(parent['dataset_id'])
        methods = {}
        for name in ('probability-reference-v1.json', 'block-reference-v1.json'):
            body = Path(__file__).with_name('reference').joinpath(name).read_bytes()
            methods[name] = {'sha256': hashlib.sha256(body).hexdigest(), 'reference': json.loads(body)}
        value = {'plan_id': str(uuid4()), 'version': VERSION, 'registered_at': now(), 'basis': command.basis,
            'predecessor_id': parent['protocol_id'], 'protocol_id': child['protocol_id'], 'dataset_id': parent['dataset_id'],
            'parent_protocol_sha256': parent['protocol_fingerprint'], 'linked_core_protocol_sha256': child['protocol_fingerprint'],
            'core_proposal_role': 'UNCHANGED_BASELINE_PROPOSAL; FEATURE_EXTENSION_IS_SEPARATE_NOT_EXECUTABLE',
            'schema': copy.deepcopy(SCHEMA), 'variants': command.variants, 'sentiment_contract': sentiment_contract,
            'calculation_sources': self.calculation_sources(),
            'candidate_order': [{'variant': variant, 'financial': variant in ('FINANCIAL', 'BOTH'), 'sentiment': variant in ('SENTIMENT', 'BOTH')} for variant in command.variants],
            'calibration_allocation': {'primary': next((variant for variant in command.variants if variant != 'BASELINE'), 'BASELINE'),
                'maximum_family_calibration_fits': 1, 'primary_policy': 'INHERIT_ORIGINAL_HELDOUT_INTERCEPT_ONLY_CALIBRATION_AND_ALL_GATES',
                'other_variants': 'RAW_DIAGNOSTIC_ABLATIONS_ONLY_NO_INDEPENDENT_CALIBRATION_OR_PASS; NO_WINNER_SELECTION'},
            'inherited_design': copy.deepcopy(design), 'statistical_references': methods,
            'resource_plan': {'maximum_configurations': len(command.variants), 'maximum_fit_calls': len(command.variants),
                'network_calls': 0, 'model_calls': 0, 'sealed_reads': 0, 'training_authorized': False, 'natural_endpoint': design['stopping']},
            'attempt_manifest': self.registry.attempt_manifest(parent['protocol_id']), 'budget_at_registration': budget,
            'evidence_kind': 'METHOD_CASE' if dataset['source_evidence_kind'] == 'METHOD_CASE' else 'LINKED_RESEARCH_DESIGN',
            'status': 'ENGINEERING_DESIGN_REGISTERED', 'real_fit_admitted': False, 'complete_experiment_frozen': False,
            'capability': 'NOT_GRANTED', 'system_usable': False}
        self.archived(value)
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT command_hash,value FROM research_feature_plans WHERE key=?', (command.idempotency_key,)).fetchone()
            if row:
                if row[0] != hashed:
                    raise HTTPException(409, 'FEATURE_IDEMPOTENCY_CONFLICT')
                return self.checked(json.loads(row[1]))
            current = self.budget(parent['protocol_id'], db)
            if len(command.variants) > current['remaining_configurations']:
                self.registry.event(child['protocol_id'], 'FEATURE_BINDING_REFUSED_BUDGET_CHANGED', db=db, budget=current, feature_plan_created=False)
                db.commit()
                raise HTTPException(409, {'code': 'FEATURE_FAMILY_BUDGET_CHANGED', 'unbound_linked_child': child['protocol_id']})
            db.execute('INSERT INTO research_feature_plans VALUES(?,?,?,?)', (value['plan_id'], command.idempotency_key, hashed, encode(value)))
            self.registry.event(child['protocol_id'], 'FEATURE_EXTENSION_REGISTERED', db=db, plan_id=value['plan_id'], training_started=False, sealed_read=False)
            db.commit()
        return value

    def snapshot(self, command):
        hashed = fingerprint(command.model_dump(mode='json'))
        prior = self.prior('research_feature_snapshots', command.idempotency_key, hashed)
        if prior:
            return prior
        cutoff = aware(command.known_by)
        if not command.basis.strip():
            raise HTTPException(422, 'FEATURE_BASIS_REQUIRED')
        if cutoff > aware(now()):
            raise HTTPException(422, 'FEATURE_FUTURE_CUTOFF_REFUSED')
        with self.ledger.connection() as db:
            rows = db.execute('SELECT value FROM financial_income_facts WHERE instrument=? LIMIT 2001', (command.instrument,)).fetchall()
        if len(rows) > 2000:
            raise HTTPException(409, 'FEATURE_FINANCIAL_SOURCE_BOUND_EXCEEDED')
        facts = {fact['fact_id']: fact for row in rows if aware((fact := json.loads(row[0]))['available_at']) <= cutoff}
        financial = metrics(self.income, self.supplement, command.instrument, cutoff)
        latest = financial['periods'][0] if financial['periods'] else None
        fields = {key: copy.deepcopy(latest['metrics'][key]) if latest else {'status': 'UNKNOWN', 'value': None, 'reason': 'NO_AVAILABLE_FINANCIAL_PERIOD'} for key in FINANCIAL}
        source_versions = financial['source_versions']
        for identifier, source in source_versions.items():
            if identifier not in facts or aware(source['available_at']) > cutoff:
                raise HTTPException(409, 'FEATURE_FINANCIAL_AVAILABILITY_MISMATCH')
            self.evidence.raw(source['raw_sha256'])
        sentiment = {key: {'value': None, 'reason': 'NO_SELECTED_SENTIMENT_SERIES'} for key in SENTIMENT}
        source_series, day = None, None
        if command.series_id:
            source_series = self.series.get(command.series_id)
            if source_series['instrument'] != command.instrument or aware(source_series['known_by']) > cutoff:
                raise HTTPException(409, 'FEATURE_SERIES_INSTRUMENT_OR_KNOWLEDGE_CUTOFF_MISMATCH')
            days = [row for row in source_series['days'] if aware(row['checkpoint_at']) <= cutoff and row['calendar']['is_trading_day'] is True]
            day = max(days, key=lambda row: aware(row['checkpoint_at'])) if days else None
            if day and day['unique_events']:
                denominator = day['unique_events']
                for label, key in [('POSITIVE', 'positive_share'), ('NEGATIVE', 'negative_share'), ('NEUTRAL', 'neutral_share')]:
                    number = day['counts'][label]
                    sentiment[key] = {'value': share(number, denominator) if number is not None else None,
                        'reason': None if number is not None else 'LABEL_UNSUPPORTED'}
                sentiment.update(rejection_share={'value': share(day['reject_count'], denominator), 'reason': None},
                    coverage={'value': share(day['covered_events'], denominator), 'reason': None}, event_support={'value': day['unique_events'], 'reason': None})
            else:
                reason = 'NO_CONSUMED_CHECKPOINT_EVENTS' if not day else day['status']
                sentiment = {key: {'value': None, 'reason': reason} for key in SENTIMENT}
        kinds = {facts[identifier].get('evidence_kind') for identifier in source_versions}
        if source_series:
            kinds.add(source_series['evidence_kind'])
        kind = 'METHOD_CASE' if 'METHOD_CASE' in kinds else 'REAL_SAVED_FEATURE_OBSERVATION' if kinds and kinds <= {'REAL_ACQUISITION', 'REAL_ARCHIVE_IMPORT', 'REAL_SAVED_OBSERVATION_RECONSTRUCTION'} else 'SOURCE_PROVENANCE_UNVERIFIED'
        value = {'snapshot_id': str(uuid4()), 'version': VERSION, 'instrument': command.instrument, 'created_at': now(),
            'known_by': cutoff.isoformat(), 'basis': command.basis, 'schema': copy.deepcopy(SCHEMA), 'financial': fields,
            'calculation_sources': self.calculation_sources(),
            'report_period': latest['report_period'] if latest else None, 'financial_source_versions': source_versions,
            'sentiment': sentiment, 'source_series_id': command.series_id,
            'source_series_sha256': fingerprint(source_series) if source_series else None,
            'sentiment_reference_sha256': source_series['semantics']['reference_sha256'] if source_series else None,
            'sentiment_contract': {**source_series['semantics'],
                'profile': 'finbert-adaptation-01' if source_series['labels_supported'] == ['POSITIVE', 'NEGATIVE', 'NEUTRAL'] else 'legacy',
                'labels_supported': source_series['labels_supported'], 'checkpoint': source_series['checkpoint'], 'series_version': source_series['version']} if source_series else None,
            'sentiment_labels_supported': source_series['labels_supported'] if source_series else [],
            'sentiment_quality_gate_passed': source_series['quality_gate_passed'] if source_series else False,
            'consumed_checkpoint': day['checkpoint_at'] if day else None,
            'evidence_kind': kind,
            'limitations': ['HISTORICAL_ORIGINAL_REVISIONS_NOT_PROVEN', 'BASE_PRETRAINING_CORPUS_INTERVAL_UNKNOWN',
                'LABEL_MATURITY_NOT_BOUND', 'PRICE_VOLUME_BASELINE_ARTIFACT_NOT_BOUND', 'NOT_A_HISTORICAL_FORECAST_OR_TRAINING_GRANT'],
            'historical_pit_eligible': False, 'real_fit_admitted': False, 'model_calls': 0, 'network_calls': 0, 'system_usable': False, 'capability': 'NOT_GRANTED'}
        self.archived(value)
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT command_hash,value FROM research_feature_snapshots WHERE key=?', (command.idempotency_key,)).fetchone()
            if row:
                if row[0] != hashed:
                    raise HTTPException(409, 'FEATURE_IDEMPOTENCY_CONFLICT')
                return self.checked(json.loads(row[1]))
            db.execute('INSERT INTO research_feature_snapshots VALUES(?,?,?,?)', (value['snapshot_id'], command.idempotency_key, hashed, encode(value)))
            db.commit()
        return value

    def preflight(self, plan_id, command):
        hashed = fingerprint(command.model_dump())
        prior = self.prior('research_feature_preflights', command.idempotency_key, hashed, plan_id)
        if prior:
            return prior
        plan = self.get('research_feature_plans', plan_id)
        snapshot = self.get('research_feature_snapshots', command.snapshot_id)
        budget = self.budget(plan['predecessor_id'])
        parent = self.registry.get(plan['predecessor_id'])
        gaps = []
        if snapshot['instrument'] not in parent['scope'].get('instruments', []):
            gaps.append('SNAPSHOT_OUTSIDE_LINKED_FAMILY_SCOPE')
        if snapshot['schema'] != plan['schema']:
            gaps.append('FEATURE_SCHEMA_CHANGED_REQUIRES_SUCCESSOR')
        if snapshot['calculation_sources'] != plan['calculation_sources']:
            gaps.append('FEATURE_CALCULATION_CHANGED_REQUIRES_SUCCESSOR')
        if plan['calculation_sources'] != self.calculation_sources():
            gaps.append('CURRENT_FEATURE_CALCULATION_NOT_THE_REGISTERED_VERSION')
        if plan['sentiment_contract'] and snapshot['sentiment_contract'] != plan['sentiment_contract']:
            gaps.append('SENTIMENT_MODEL_LABEL_REJECT_OR_CHECKPOINT_CHANGED_OR_MISSING')
        if budget['unreserved_fit_slots'] < 0:
            gaps.append('FAMILY_BUDGET_CONSUMED_AFTER_REGISTRATION')
        if parent['protocol_fingerprint'] != plan['parent_protocol_sha256']:
            gaps.append('PARENT_PROTOCOL_BINDING_CHANGED')
        fit_gaps = list(snapshot['limitations'])+['FEATURE_FIT_EXECUTOR_AND_TRAINING_AUTHORITY_TICKET23_REQUIRED', 'COMPLETE_EXPERIMENT_FREEZE_NOT_GRANTED']
        if budget['calibration_records'] >= budget['calibration_limit']:
            fit_gaps.append('FAMILY_CALIBRATION_BUDGET_EXHAUSTED')
        if snapshot['evidence_kind'] == 'METHOD_CASE':
            fit_gaps.append('METHOD_SNAPSHOT_NOT_REAL_TRAINING_INPUT')
        if any(variant in ('FINANCIAL', 'BOTH') for variant in plan['variants']):
            fit_gaps += ['FINANCIAL_MISSING_'+key.upper() for key, value in snapshot['financial'].items() if value['value'] is None]
        if any(variant in ('SENTIMENT', 'BOTH') for variant in plan['variants']):
            fit_gaps += ['SENTIMENT_MISSING_'+key.upper() for key, value in snapshot['sentiment'].items() if value['value'] is None]
            if not snapshot['sentiment_quality_gate_passed']:
                fit_gaps.append('SENTIMENT_ORIGINAL_QUALITY_LIMIT_RETAINED')
        value = {'preflight_id': str(uuid4()), 'plan_id': plan_id, 'snapshot_id': command.snapshot_id, 'created_at': now(),
            'plan_sha256': plan['archive']['sha256'], 'snapshot_sha256': snapshot['archive']['sha256'],
            'engineering_ready': not gaps, 'engineering_gaps': gaps, 'current_budget': budget,
            'real_fit_admitted': False, 'fit_gaps': sorted(set(fit_gaps+gaps)), 'training_started': False, 'sealed_read': False,
            'evidence_kind': 'METHOD_CASE' if plan['evidence_kind'] == 'METHOD_CASE' or snapshot['evidence_kind'] == 'METHOD_CASE' else 'RESEARCH_PREFLIGHT',
            'capability': 'NOT_GRANTED'}
        self.archived(value)
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT command_hash,value FROM research_feature_preflights WHERE plan_id=? AND key=?', (plan_id, command.idempotency_key)).fetchone()
            if row:
                if row[0] != hashed:
                    raise HTTPException(409, 'FEATURE_IDEMPOTENCY_CONFLICT')
                return self.checked(json.loads(row[1]))
            db.execute('INSERT INTO research_feature_preflights VALUES(?,?,?,?,?)', (value['preflight_id'], plan_id, command.idempotency_key, hashed, encode(value)))
            db.commit()
        return value
