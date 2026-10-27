"""METHOD cases at public company research feature/API/backup boundaries."""
from datetime import datetime, timezone
import pytest
from test_shared_evidence import service, company
from test_daily_research import published


def current_time():
    return datetime.now(timezone.utc).isoformat()


def test_fixed_features_keep_unknowns_and_sources_without_changing_shared_research(tmp_path):
    research = service(tmp_path)
    issuer = research.register(company())
    snapshot = published(research, issuer)
    from roll.research.company.features import FeatureExportCommand
    command = FeatureExportCommand(snapshot_id=snapshot['snapshot_id'], observation_at=current_time(),
                                   purpose='CURRENT_RESEARCH', idempotency_key='first')
    result = research.features.export(command)
    assert result['features']['hypothesis_revision_count']['value'] == 0
    assert result['features']['risk_condition_count']['value'] == 1
    assert result['features']['next_validation_days']['value'] is None
    assert result['features']['current_requirement_gap']['value'] is None
    assert result['missing_mask']['next_validation_days'] is True
    assert result['features']['next_validation_days']['missing_reason'] == 'VALIDATION_DATE_UNKNOWN'
    assert result['features']['current_requirement_gap']['economic_status'] == 'unavailable'
    assert result['available_at'] >= snapshot['generated_at']
    assert result['source_roots'] == ['issuer-annual-2025']
    assert result['training_started'] is False and result['sealed_read'] is False
    assert research.features.export(command) == result
    assert research.features.read(result['feature_snapshot_id']) == result
    assert research.analysis_snapshot(snapshot['snapshot_id']) == snapshot
    assert research.ledger.account()['version'] == 0


def test_later_revision_is_missing_at_old_cutoff_and_repeat_quarter_does_not_add_support(tmp_path):
    from test_changes import research_pair
    from roll.research.company import ResearchContextCommand
    from roll.research.company.features import FeatureExportCommand
    research = service(tmp_path)
    old, new, _ = research_pair(research)
    early = research.features.export(FeatureExportCommand(snapshot_id=new['snapshot_id'],
        observation_at=old['as_of'], purpose='HISTORICAL_PIT', idempotency_key='early'))
    assert all(f['value'] is None for f in early['features'].values())
    assert early['features']['hypothesis_revision_count']['missing_reason'] == 'DEPENDENCY_NOT_AVAILABLE_AT_OBSERVATION'
    current = research.features.export(FeatureExportCommand(snapshot_id=new['snapshot_id'],
        observation_at=current_time(), idempotency_key='current'))
    assert current['features']['hypothesis_revision_count']['value'] == 1
    context = research.freeze_research_context(ResearchContextCommand(snapshot_id=new['snapshot_id'],
        change_reason='METHOD repeat of same quarterly evidence'))
    repeated = research.features.export(FeatureExportCommand(snapshot_id=context['snapshot_id'],
        observation_at=current_time(), idempotency_key='repeat'))
    diagnostic = research.features.coverage([current['feature_snapshot_id'], repeated['feature_snapshot_id']])
    assert diagnostic['observations'] == 2
    assert diagnostic['independent_evidence_units'] == 1
    assert diagnostic['independent_mature_samples'] == 0
    assert diagnostic['status'] == 'INCONCLUSIVE'
    assert diagnostic['training_started'] is False
    strict = research.features.export(FeatureExportCommand(snapshot_id=context['snapshot_id'],
        observation_at=current_time(), purpose='HISTORICAL_PIT', idempotency_key='strict'))
    assert all(f['value'] is None for f in strict['features'].values())
    assert strict['features']['risk_condition_count']['missing_reason'] == 'STRICT_HISTORICAL_PIT_NOT_PROVEN'


def test_blocked_valuation_never_exports_its_diagnostic_gap_or_probabilities(tmp_path):
    from pydantic import ValidationError
    from test_economic_review import operating_request
    from test_changes import quote_basis
    from roll.research.company import ResearchContextCommand
    from roll.research.company.features import FeatureExportCommand
    research = service(tmp_path)
    command, _ = operating_request(research)
    result = research.calculate_operating_valuation(command)
    snapshot = research.analysis_snapshot(result['snapshot_id'])
    bound = research.freeze_research_context(ResearchContextCommand(snapshot_id=snapshot['snapshot_id'],
        quotes=quote_basis(research, snapshot), change_reason='METHOD dated valuation and current quote'))
    exported = research.features.export(FeatureExportCommand(snapshot_id=bound['snapshot_id'],
        observation_at=current_time(), scenario='base', idempotency_key='blocked'))
    gap = exported['features']['current_requirement_gap']
    assert gap['economic_status'] == 'blocked'
    assert gap['value'] is None and gap['missing_reason'] == 'CURRENT_VALUATION_BLOCKED'
    assert gap['source_refs']['economic_review_ids'] == [result['review_id']]
    assert exported['missing_mask']['current_requirement_gap'] is True
    with pytest.raises(ValidationError):
        FeatureExportCommand(snapshot_id=bound['snapshot_id'], observation_at=current_time(),
            idempotency_key='invalid', probability=.9, scenario_weight=.9)


def test_feature_http_protocol_is_read_only_and_inconclusive_without_bound_baseline(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from roll.research.company.api import router
    research = service(tmp_path)
    issuer = research.register(company())
    snapshot = published(research, issuer)
    app = FastAPI(); app.include_router(router(research))
    with TestClient(app) as client:
        base='/api/company-research'
        assert client.get(base+'/feature-schema').status_code == 200
        response=client.post(base+'/feature-snapshots', json=dict(snapshot_id=snapshot['snapshot_id'],
            observation_at=current_time(), idempotency_key='api'))
        assert response.status_code == 201, response.text
        exported=response.json()
        assert client.get(base+'/feature-snapshots/'+exported['feature_snapshot_id']).json()==exported
        invalid=client.post(base+'/feature-snapshots', json=dict(snapshot_id=snapshot['snapshot_id'],
            observation_at=current_time(), idempotency_key='bad-probability', upward_probability=.8))
        assert invalid.status_code==422
        response=client.post(base+'/feature-protocols',json=dict(company_ids=[issuer['company_id']],
            idempotency_key='draft', basis='METHOD preregistration without model or training'))
        assert response.status_code==201,response.text
        protocol=response.json()
        assert protocol['status']=='DRAFT_UNBOUND' and protocol['budget_reserved'] is False
        design=protocol['design']
        assert design['horizon_sessions']==20
        assert design['scores']==['BRIER','LOG_LOSS','CALIBRATION']
        assert design['same_sample_controls'] and design['costs'] and design['risk_exposure_controls']
        assert design['time_out_windows'] and design['stopping']
        assert client.get(base+'/feature-protocols/'+protocol['protocol_id']).json()==protocol
        diagnostic=client.post(base+'/feature-coverage', json=dict(feature_snapshot_ids=[exported['feature_snapshot_id']],
            protocol_id=protocol['protocol_id'])).json()
        assert diagnostic['status']=='INCONCLUSIVE' and diagnostic['real_fit_admitted'] is False
        assert diagnostic['protocol_gaps'] and diagnostic['budget_reserved'] is False
    assert research.ledger.account()['version']==0


def test_feature_backup_preserves_export_and_rejects_rehashed_foreign_snapshot(tmp_path):
    import json
    from fastapi import HTTPException
    from roll.accounts.ledger import encode
    from roll.runtime.backups import Backups, restore_at_start
    from roll.research.company.features import FeatureExportCommand
    from roll.research.company.feature_protocol import FeatureProtocolCommand
    from roll.research.company.service import record
    research=service(tmp_path/'source')
    issuer=research.register(company())
    snapshot=published(research,issuer)
    exported=research.features.export(FeatureExportCommand(snapshot_id=snapshot['snapshot_id'],
        observation_at=current_time(),idempotency_key='backup'))
    protocol=research.features.register_protocol(FeatureProtocolCommand(company_ids=[issuer['company_id']],
        idempotency_key='backup-protocol',basis='METHOD no execution'))
    backup=Backups(tmp_path/'source')
    bundle=backup.export(backup.create()['backup_id'])
    target=Backups(tmp_path/'restored');target.stage_restore(bundle);restore_at_start(target)
    restored=service(tmp_path/'restored')
    assert restored.features.read(exported['feature_snapshot_id'])==exported
    assert restored.features.protocol(protocol['protocol_id'])==protocol
    assert restored.features.coverage([exported['feature_snapshot_id']],protocol['protocol_id'])['status']=='INCONCLUSIVE'
    # Simulate external corruption with coherent JSON/archive hash: original snapshot binding must still fail.
    damaged={k:v for k,v in exported.items() if k not in {'content_sha256','export_archive'}}
    damaged['snapshot_sha256']='0'*64
    with research.transaction() as db:
        descriptor=research.evidence.archive(encode(damaged).encode(),'COMPANY_RESEARCH_FEATURES',db=db)
        descriptor=json.loads(db.execute('SELECT value FROM evidence_archives WHERE sha256=?',(descriptor['sha256'],)).fetchone()[0])
        changed=record(dict(damaged,export_archive=descriptor))
        db.execute('UPDATE company_research_feature_snapshots SET value=? WHERE feature_snapshot_id=?',(encode(changed),exported['feature_snapshot_id']))
    with pytest.raises(HTTPException) as invalid:
        backup.create()
    assert invalid.value.detail['code']=='RESEARCH_REFERENCE_INVALID'


def test_concurrent_same_export_key_has_one_immutable_result(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from roll.research.company.features import FeatureExportCommand
    research=service(tmp_path)
    issuer=research.register(company())
    snapshot=published(research,issuer)
    command=FeatureExportCommand(snapshot_id=snapshot['snapshot_id'],observation_at=current_time(),idempotency_key='concurrent')
    barrier=Barrier(4)
    def submit(_):
        barrier.wait()
        return research.features.export(command)
    with ThreadPoolExecutor(max_workers=4) as pool:
        exports=list(pool.map(submit,range(4)))
    assert len({e['feature_snapshot_id'] for e in exports})==1
    assert all(e==exports[0] for e in exports)


def test_sourced_today_event_uses_issuer_calendar_not_utc_date(tmp_path):
    from test_analysis_snapshots import evidence, freeze, candidate
    from roll.research.company.features import FeatureExportCommand
    from roll.research.company.calculator import SHANGHAI
    research=service(tmp_path)
    issuer=research.register(company())
    today=datetime.now(timezone.utc).astimezone(SHANGHAI).date().isoformat()
    _, fact=evidence(research,issuer,'Disclosed operating event scheduled '+today)
    packet=freeze(research,issuer,fact)
    draft=candidate(packet,fact)
    draft['hypotheses'][0]['next_validation_event']=dict(description='Disclosed operating event',date=today,date_unknown_reason=None,date_fact_version_ids=[fact['version_id']])
    snapshot=research.apply_analysis_candidate(packet['input_id'],draft)
    result=research.features.export(FeatureExportCommand(snapshot_id=snapshot['snapshot_id'],observation_at=current_time(),idempotency_key='today'))
    assert result['features']['next_validation_days']['value']==0
    assert result['features']['next_validation_days']['unit']=='calendar_days_Asia_Shanghai'
    assert result['information_age']['disclosure_age_seconds'] is None
    assert result['information_age']['unknown_disclosure_times']==1
