"""Actual local HTTP export/coverage and offline restore; no model or dataset read."""
import json,hashlib
from datetime import datetime,timezone
from pathlib import Path
import httpx
from roll.runtime.backups import Backups,restore_at_start
from roll.accounts.ledger import Ledger
from roll.market.directory import MarketDirectory
from roll.market.evidence import EvidenceStore
from roll.research.company import CompanyResearch

OUT=Path(__file__).parent
ROOT=Path('D:/dsh-proj/Roll/.scratch')
SNAPSHOT='7a430e8b-4172-4598-af21-6fe8600b6b93'
COMPANY='54abcc3d-67c2-453e-83b4-8fdc92b7a292'
REPORT='b9cfb2a0-8f93-516a-a4cd-7b7801fd7911'
DELIVERY='e3e6e93c-0a17-4bfc-92af-82b86aa86487'

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

with httpx.Client(base_url='http://127.0.0.1:8031',timeout=100,trust_env=False) as client:
    def get(path):
        response=client.get(path);response.raise_for_status();return response.json()
    def post(path,value=None):
        response=client.post(path,json=value);response.raise_for_status();return response.json()
    def protected():
        values={path:get(path) for path in ['/api/account','/api/research/protocols','/api/research/feature-plans',
            '/api/research/feature-snapshots','/api/capabilities/grants','/api/capabilities/events']}
        for protocol in values['/api/research/protocols']:
            identifier=protocol.get('protocol_id') or protocol['id']
            for suffix in ['attempts','models']:
                path=f'/api/research/protocols/{identifier}/{suffix}';values[path]=get(path)
            path='/api/research/feature-budget/'+identifier;values[path]=get(path)
        return values
    before=protected()
    snapshot=get('/api/company-research/snapshots/'+SNAPSHOT)
    original=get('/api/company-research/reports/'+REPORT)
    delivery=get('/api/company-research/report-deliveries/'+DELIVERY)
    stamp=datetime.now(timezone.utc).isoformat()
    request=dict(snapshot_id=SNAPSHOT,observation_at=stamp,scenario='baseline',purpose='CURRENT_RESEARCH',idempotency_key='actual11-current-01')
    current=post('/api/company-research/feature-snapshots',request)
    assert post('/api/company-research/feature-snapshots',request)==current
    assert all(f['value'] is None for f in current['features'].values())
    assert current['features']['risk_condition_count']['missing_reason']=='HYPOTHESES_UNAVAILABLE'
    assert current['features']['current_requirement_gap']['economic_status']=='blocked'
    assert current['features']['current_requirement_gap']['missing_reason']=='CURRENT_VALUATION_BLOCKED'
    early=post('/api/company-research/feature-snapshots',dict(request,observation_at='2025-12-31T15:00:00+08:00',
        purpose='HISTORICAL_PIT',idempotency_key='actual11-early-01'))
    assert all(f['value'] is None for f in early['features'].values())
    strict=post('/api/company-research/feature-snapshots',dict(request,purpose='HISTORICAL_PIT',idempotency_key='actual11-strict-01'))
    assert all(f['value'] is None for f in strict['features'].values())
    assert strict['features']['risk_condition_count']['missing_reason']=='STRICT_HISTORICAL_PIT_NOT_PROVEN'
    protocol=post('/api/company-research/feature-protocols',dict(company_ids=[COMPANY],idempotency_key='actual11-protocol-01',
        basis='Read-only preregistration supplement; no baseline model, mature outcomes, fit permission or family budget is assumed'))
    assert protocol['status']=='DRAFT_UNBOUND'
    coverage=post('/api/company-research/feature-coverage',dict(feature_snapshot_ids=[current['feature_snapshot_id'],early['feature_snapshot_id'],strict['feature_snapshot_id']],protocol_id=protocol['protocol_id']))
    assert coverage['status']=='INCONCLUSIVE' and coverage['independent_mature_samples']==0 and not coverage['real_fit_admitted']
    rejected=client.post('/api/company-research/feature-snapshots',json=dict(request,idempotency_key='invalid-real',upward_probability=.9))
    assert rejected.status_code==422
    after=protected();assert before==after
    assert get('/api/company-research/snapshots/'+SNAPSHOT)==snapshot
    assert get('/api/company-research/reports/'+REPORT)==original
    assert get('/api/company-research/report-deliveries/'+DELIVERY)==delivery
    saved=post('/api/runtime/backups')
    bundle=client.get('/api/runtime/backups/'+saved['backup_id']+'/export');bundle.raise_for_status()

target=ROOT/'rv11-restored01'
if target.exists():raise RuntimeError('Never overwrite old recovery evidence')
restore=Backups(target);restore.stage_restore(bundle.content);restore_at_start(restore)
ledger=Ledger(target);recovered=CompanyResearch(EvidenceStore(ledger,MarketDirectory(ledger)))
for value in [current,early,strict]:assert recovered.features.read(value['feature_snapshot_id'])==value
assert recovered.features.protocol(protocol['protocol_id'])==protocol
assert recovered.features.coverage(coverage['feature_snapshot_ids'],protocol['protocol_id'])==coverage
assert recovered.reports.read(REPORT)==original
assert recovered.report_deliveries.read(DELIVERY)==delivery
assert ledger.account()['version']==before['/api/account']['version']==0
for name,value in [('current-features',current),('early-features',early),('strict-features',strict),('protocol',protocol),('coverage',coverage),('protected-before',before),('protected-after',after)]:
    (OUT/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
receipt=dict(snapshot_id=SNAPSHOT,core_sha256=snapshot['core_sha256'],feature_snapshot_ids=coverage['feature_snapshot_ids'],
    protocol_id=protocol['protocol_id'],protocol_status=protocol['status'],coverage_status=coverage['status'],
    observations=coverage['observations'],independent_evidence_units=coverage['independent_evidence_units'],independent_mature_samples=0,
    all_current_features_missing=True,blocked_value_absent=True,source_root_count=len(current['source_roots']),
    available_at=current['available_at'],actual_exported_at=current['created_at'],protected_public_metadata_sha256=digest(before),
    protected_objects_equal=True,original_snapshot_report_delivery_equal=True,probability_field_rejected=True,
    backup_id=saved['backup_id'],bundle_bytes=len(bundle.content),restore_target=str(target),restored_records_equal=True,
    archive_sha256=[v['export_archive']['sha256'] for v in [current,early,strict,protocol]],account_version=0,
    model_calls=0,source_network_calls=0,auth_read=False,sealed_read=False,training_started=False)
(OUT/'real-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt))
