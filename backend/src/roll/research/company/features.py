"""Read-only research candidates. No forecast, fit, budget or qualification writes."""
import json
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import Field
from roll.accounts.ledger import encode, now
from .models import Command
from .service import fail, fingerprint, record, verified
from .report_archive import archive
from .calculator import SHANGHAI

VERSION = 'company-research-features-1'
DEFINITIONS = {
    'hypothesis_revision_count': 'Count of current hypotheses with a referenced prior version; not a directional score',
    'risk_condition_count': 'Count of stated invalidation conditions; not verified risk occurrences',
    'next_validation_days': 'Calendar days to the earliest sourced future validation event; unknown dates stay null',
    'current_requirement_gap': 'Market equity / selected research scenario equity - 1, under current usable review; not upside probability',
}


class FeatureExportCommand(Command):
    snapshot_id: str
    observation_at: str
    purpose: Literal['CURRENT_RESEARCH', 'HISTORICAL_PIT'] = 'CURRENT_RESEARCH'
    scenario: str | None = Field(default=None, max_length=100)
    idempotency_key: str = Field(min_length=1, max_length=128)


def aware(value):
    try:
        result = datetime.fromisoformat(value)
        if result.tzinfo is None:
            raise ValueError()
        return result
    except (ValueError, TypeError):
        fail('FEATURE_TIME_INVALID', 'An explicit timezone-aware timestamp is required')


class ResearchFeatures:
    def __init__(self, research):
        self.research = research
        with research.transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS company_research_feature_snapshots(feature_snapshot_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS company_research_feature_protocols(protocol_id TEXT PRIMARY KEY, value TEXT NOT NULL)')

    def schema(self):
        return dict(version=VERSION, definitions=DEFINITIONS, missing='NULL_WITH_REASON',
                    authority='RESEARCH_CANDIDATES_NOT_PROBABILITIES', training_started=False, sealed_read=False)

    def protocol(self, identifier):
        with self.research.ledger.connection() as db:
            row=db.execute('SELECT value FROM company_research_feature_protocols WHERE protocol_id=?',(identifier,)).fetchone()
        if not row:
            fail('FEATURE_PROTOCOL_NOT_FOUND','Feature supplement is not registered',404)
        value=verified(json.loads(row[0]))
        body={k:v for k,v in value.items() if k not in {'content_sha256','export_archive'}}
        if json.loads(self.research.evidence.raw(value['export_archive']['sha256']).read_bytes()) != body:
            fail('RESEARCH_REFERENCE_INVALID','Feature protocol differs from its canonical archive',409)
        return value

    def register_protocol(self, command):
        from .feature_protocol import design
        request=command.model_dump()
        with self.research.ledger.connection() as db:
            prior=db.execute("SELECT value FROM company_research_feature_protocols WHERE json_extract(value,'$.idempotency_key')=?",(command.idempotency_key,)).fetchone()
        if prior:
            value=verified(json.loads(prior[0]))
            if value['request_sha256']!=fingerprint(request):
                fail('IDEMPOTENCY_CONFLICT','Protocol key was used for another request',409)
            return self.protocol(value['protocol_id'])
        specification,gaps=design(self.research,command,self.schema())
        value=dict(schema_version=1,created_at=now(),**request,request_sha256=fingerprint(request),protocol_id=str(uuid4()),
            design=specification,design_sha256=fingerprint(specification),gaps=gaps,
            status='DRAFT_UNBOUND' if gaps else 'FROZEN_SUPPLEMENT_NOT_FIT_AUTHORIZED',
            training_started=False,sealed_read=False,budget_reserved=False,real_fit_admitted=False)
        value=record(dict(value,export_archive=archive(self.research.evidence,encode(value).encode(),'COMPANY_FEATURE_PROTOCOL','json')))
        with self.research.transaction() as db:
            prior=db.execute("SELECT value FROM company_research_feature_protocols WHERE json_extract(value,'$.idempotency_key')=?",(command.idempotency_key,)).fetchone()
            if prior:
                existing=verified(json.loads(prior[0]))
                if existing['request_sha256']!=fingerprint(request):
                    fail('IDEMPOTENCY_CONFLICT','Concurrent protocol key has different input',409)
                return self.protocol(existing['protocol_id'])
            db.execute('INSERT INTO company_research_feature_protocols VALUES(?,?)',(value['protocol_id'],encode(value)))
        return value

    def coverage(self, identifiers, protocol_id=None):
        if not identifiers or len(identifiers)>200:
            fail('FEATURE_COVERAGE_BOUNDS', 'Select one to two hundred registered feature snapshots')
        values = [self.read(i) for i in dict.fromkeys(identifiers)]
        units = set()
        for value in values:
            if all(value['missing_mask'].values()):
                continue
            for evidence in value['independent_evidence']:
                if evidence['period_start'] and evidence['period_end']:
                    units.add((value['company_id'], evidence['origin_root_id'], evidence['period_start'], evidence['period_end']))
        protocol=self.protocol(protocol_id) if protocol_id else None
        if protocol and any(v['company_id'] not in protocol['company_ids'] for v in values):
            fail('CROSS_COMPANY_REFERENCE','Feature observation is outside the preregistered company scope')
        return dict(status='INCONCLUSIVE', observations=len(values), independent_evidence_units=len(units),
            independent_mature_samples=0, feature_snapshot_ids=[v['feature_snapshot_id'] for v in values],
            missing_observations=sum(all(v['missing_mask'].values()) for v in values),
            reasons=['No event-matched mature labels and immutable baseline predictions are bound; evidence units are not mature outcome samples',
                     'Repeated reports/snapshots sharing issuer, origin root and reporting period do not add independent support'],
            protocol_id=protocol_id,protocol_gaps=protocol['gaps'] if protocol else ['PREREGISTERED_BASELINE_AND_EVENT_UNBOUND'],
            budget_reserved=False, training_started=False, sealed_read=False, real_fit_admitted=False, qualification='NOT_GRANTED')

    def read(self, identifier):
        value = self.research.analysis.read('feature_snapshots', 'feature_snapshot_id', identifier)
        snapshot = self.research.analysis_snapshot(value['snapshot_id'])
        from .feature_integrity import export_references
        export_references(value, snapshot)
        body = {k:v for k,v in value.items() if k not in {'content_sha256','export_archive'}}
        if json.loads(self.research.evidence.raw(value['export_archive']['sha256']).read_bytes()) != body:
            fail('RESEARCH_REFERENCE_INVALID', 'Feature export differs from canonical archive', 409)
        return value

    def export(self, command):
        request = command.model_dump()
        with self.research.ledger.connection() as db:
            prior = db.execute("SELECT value FROM company_research_feature_snapshots WHERE json_extract(value,'$.idempotency_key')=?", (command.idempotency_key,)).fetchone()
        if prior:
            value = verified(json.loads(prior[0]))
            if value['request_sha256'] != fingerprint(request):
                fail('IDEMPOTENCY_CONFLICT', 'Feature key was used for another request', 409)
            return self.read(value['feature_snapshot_id'])
        observation = aware(command.observation_at)
        if observation > datetime.now(timezone.utc):
            fail('FEATURE_TIME_INVALID', 'Observation cannot be in the future')
        r = self.research
        snapshot = r.analysis_snapshot(command.snapshot_id)
        packet = r.analysis_input(snapshot['input_id'])
        facts = [r.fact(i, snapshot['company_id']) for i in snapshot['fact_version_ids']]
        materials = [r.material(i, snapshot['company_id']) for i in snapshot['material_ids']]
        hypotheses = snapshot['core']['hypotheses']
        timestamps = [snapshot['generated_at'], snapshot['created_at'], packet['created_at']]
        for item in [*facts,*materials]:
            timestamps.extend([item['received_at'], item['consumable_at']])
        timestamps.extend(h['created_at'] for h in hypotheses)
        review_ids = snapshot.get('economic_review_ids', [])
        presentation, gap, gap_reason = None, None, 'CURRENT_VALUATION_UNAVAILABLE'
        if len(review_ids)==1:
            review = r.economic_review(review_ids[0])
            timestamps.append(review['created_at'])
            presentation = r.valuation_presentation(review_ids[0], 'CURRENT_PRICING')
            if not presentation['usable_range']:
                gap_reason = 'CURRENT_VALUATION_BLOCKED'
            elif not command.scenario:
                gap_reason = 'SCENARIO_NOT_SELECTED'
            else:
                try:
                    pinned = r.changes.pinned(snapshot)
                    timestamps.extend([pinned['input']['created_at'], pinned['model']['created_at']])
                    market, _ = r.changes.market(snapshot, pinned)
                    selected = next(s for s in presentation['scenarios'] if s['name']==command.scenario)
                    equity = Decimal(str(selected['equity_value']))
                    if not equity.is_finite() or equity<=0:
                        raise ValueError('Selected research equity must be finite and positive')
                    candidate_gap = Decimal(str(market))/equity-1
                    if not candidate_gap.is_finite():
                        raise ValueError('Gap must be finite')
                    gap, gap_reason = float(candidate_gap), None
                except (ValueError, KeyError, StopIteration, InvalidOperation) as error:
                    gap_reason = 'CURRENT_QUOTE_OR_SCENARIO_UNAVAILABLE: '+str(error)
            for identifier in presentation.get('later_disclosure_fact_version_ids', []):
                timestamps.append(r.fact(identifier, snapshot['company_id'])['consumable_at'])
        context = snapshot.get('context', {})
        if context.get('bound_at'):
            timestamps.append(context['bound_at'])
        for quote in context.get('quotes', []):
            timestamps.append(quote['available_at'])
            for item in [*quote['facts'],*quote['materials']]:
                timestamps.extend([item['created_at'], item['received_at'], item['consumable_at']])
        available = max(timestamps, key=aware)
        origin_roots = sorted({m['origin_root_id'] for m in materials})
        refs = dict(snapshot_id=snapshot['snapshot_id'], fact_version_ids=snapshot['fact_version_ids'],
                    hypothesis_version_ids=snapshot['hypothesis_version_ids'], material_ids=snapshot['material_ids'],
                    economic_review_ids=review_ids, valuation_ids=snapshot.get('valuation_ids', []), quote_ids=snapshot.get('quote_ids', []))
        features = {}
        def put(name, value, reason=None, economic_status=None):
            features[name] = dict(value=value, missing_reason=reason, available_at=available,
                unit='ratio' if name=='current_requirement_gap' else ('calendar_days_Asia_Shanghai' if name=='next_validation_days' else 'count_of_stated_conditions' if name=='risk_condition_count' else 'count_of_current_hypotheses_with_parent'),
                information_age_seconds=max(0, (observation-aware(available)).total_seconds()) if observation>=aware(available) else None,
                source_refs=refs, economic_status=economic_status, definition_version=VERSION)
        if hypotheses:
            put('hypothesis_revision_count', sum(bool(h['parent_version_id']) for h in hypotheses))
            put('risk_condition_count', sum(len(h['invalidation_conditions']) for h in hypotheses))
        else:
            put('hypothesis_revision_count', None, 'HYPOTHESES_UNAVAILABLE')
            put('risk_condition_count', None, 'HYPOTHESES_UNAVAILABLE')
        dates = [h['next_validation_event']['date'] for h in hypotheses if h['next_validation_event'].get('date')]
        local_day=observation.astimezone(SHANGHAI).date()
        future = [(datetime.fromisoformat(d).date()-local_day).days for d in dates if datetime.fromisoformat(d).date()>=local_day]
        put('next_validation_days', min(future) if future else None, None if future else 'VALIDATION_DATE_UNKNOWN')
        put('current_requirement_gap', gap, gap_reason, presentation['status'] if presentation else 'unavailable')
        unavailable = 'DEPENDENCY_NOT_AVAILABLE_AT_OBSERVATION' if observation < aware(available) else (
            'STRICT_HISTORICAL_PIT_NOT_PROVEN' if command.purpose=='HISTORICAL_PIT' and not packet['payload'].get('historical_pit_eligible',False) else None)
        if unavailable:
            for feature in features.values():
                feature.update(value=None, missing_reason=unavailable)
        latest_consumable=max((m['consumable_at'] for m in materials),key=aware,default=None)
        latest_disclosed=max((m['disclosed_at'] for m in materials if m.get('disclosed_at')),key=aware,default=None)
        def age(stamp):
            return max(0,(observation-aware(stamp)).total_seconds()) if stamp and observation>=aware(stamp) else None
        value = dict(schema_version=1, created_at=now(), **request, request_sha256=fingerprint(request), definition_version=VERSION,
            feature_snapshot_id=str(uuid4()), company_id=snapshot['company_id'], snapshot_sha256=snapshot['content_sha256'],
            core_sha256=snapshot['core_sha256'], available_at=available, features=features,
            missing_mask={k:v['value'] is None for k,v in features.items()}, source_roots=origin_roots,
            independent_evidence=[dict(origin_root_id=m['origin_root_id'], raw_sha256=m['raw_sha256'],
                period_start=m['period_start'], period_end=m['period_end']) for m in materials],
            historical_pit_eligible=packet['payload'].get('historical_pit_eligible',False),
            valuation_presentation=presentation and {k:presentation.get(k) for k in ['status','purpose','usable_range','current_pricing_gaps','evaluated_at']},
            information_age=dict(basis='ORIGINAL_SOURCE_DISCLOSURE_AND_ACTUAL_CONSUMPTION_NOT_PAGE_READ',
                latest_source_consumable_at=latest_consumable,material_age_seconds=age(latest_consumable),
                latest_disclosed_at=latest_disclosed,disclosure_age_seconds=age(latest_disclosed),
                unknown_disclosure_times=sum(not m.get('disclosed_at') for m in materials)),
            training_started=False, sealed_read=False, probability_output_changed=False, budget_reserved=False,
            meaning='Research candidates and missingness only; conditions are not verified events or calibrated probabilities')
        value = record(dict(value, export_archive=archive(r.evidence, encode(value).encode(), 'COMPANY_RESEARCH_FEATURES', 'json')))
        with r.transaction() as db:
            prior=db.execute("SELECT value FROM company_research_feature_snapshots WHERE json_extract(value,'$.idempotency_key')=?",(command.idempotency_key,)).fetchone()
            if prior:
                existing=verified(json.loads(prior[0]))
                if existing['request_sha256']!=fingerprint(request):
                    fail('IDEMPOTENCY_CONFLICT','Concurrent export key has different input',409)
                return self.read(existing['feature_snapshot_id'])
            db.execute('INSERT INTO company_research_feature_snapshots VALUES(?,?,?)', (value['feature_snapshot_id'],value['company_id'],encode(value)))
        return value
