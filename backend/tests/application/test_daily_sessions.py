import copy
from decimal import Decimal
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from roll.app import create_app
from roll.market import daily_sessions, authority_supplements
from test_authority_supplements import method_source, snapshot


def fact(day, volume, amount):
    return {'source_id':'baostock-daily','instrument':'SSE:600362','adjustment':'RAW','errors':[],
            'trade_date':day,'volume_shares':volume,'amount_yuan':amount,'received_at':'2026-10-20T11:15:00+00:00',
            'completion_state':'UNCONFIRMED_CURRENT_DAY' if day=='2026-10-20' else 'COMPLETE_REPORTED_HISTORICAL'}


def source():
    return authority_supplements.checked_reference(daily_sessions.REFERENCE,daily_sessions.MANIFEST)[:2]


def test_two_real_saved_days_component_arithmetic_keeps_residuals_and_timeout_unknown():
    catalog,bodies=source()
    rows=[fact('2026-10-19','19499178','762858168.3800'),fact('2026-10-20','36143433','1370825452.9800')]
    original=copy.deepcopy(rows)
    result=daily_sessions.assess(rows,bodies,catalog);a,b=result['session_rows']
    assert rows==original and result['qualified_total_bar'] is None
    assert a['fp_volume_shares']=='3800' and Decimal(a['fp_amount_cny'])==Decimal('148542')
    assert a['display_minus_component_volume']=='22.0' and a['display_minus_component_amount']=='-10.3800'
    assert b['display_minus_component_volume']=='-33.00' and b['display_minus_component_amount']=='21.0200'
    assert all(r['two_decimal_presentation_compatible'] and r['explanation']=='POST_CLOSE_COMPONENTS_PRESENTATION_COMPATIBLE' for r in [a,b])
    assert all(not r['all_session_daily_allowed'] and not r['model_daily_input_allowed'] for r in [a,b])
    assert a['block_reported_total']==0 and not a['block_negative_coverage_verified']
    assert b['block_reported_total'] is None and b['block_query_state']=='SOURCE_FAILED_NOT_ZERO'
    assert b['bao_original_completion_state']=='UNCONFIRMED_CURRENT_DAY' and b['provider_declared_ingestion_boundary_reached']


def test_wrong_date_open_phase_wrong_fixed_price_and_unsupported_scope_do_not_explain():
    import json
    catalog,bodies=source();row=fact('2026-10-19','19499178','762858168.3800')
    snap=json.loads(bodies['prior_phase_snap']);snap['date']=20261020
    with pytest.raises(HTTPException,match='DATE_OR_SELECT'):
        daily_sessions.assess([row],{**bodies,'prior_phase_snap':json.dumps(snap).encode()},catalog)
    snap['date']=20261019;snap['snap'][23]='H1'
    result=daily_sessions.assess([row],{**bodies,'prior_phase_snap':json.dumps(snap).encode()},catalog)
    assert result['session_rows'][0]['explanation']=='COMPONENT_RELATION_NOT_ESTABLISHED'
    snap['snap'][20]+=1
    with pytest.raises(HTTPException,match='FIXED_PRICE_COMPONENT_CONFLICT'):
        daily_sessions.assess([row],{**bodies,'prior_phase_snap':json.dumps(snap).encode()},catalog)
    with pytest.raises(HTTPException,match='DUPLICATE'):daily_sessions.assess([row,row],bodies,catalog)
    with pytest.raises(HTTPException,match='SCOPE_OR_QUALITY'):daily_sessions.assess([{**row,'source_id':'other'}],bodies,catalog)
    with pytest.raises(HTTPException,match='FIXED_SOURCE_BATCH'):daily_sessions.assess([{**row,'trade_date':'2026-10-12'}],bodies,catalog)
    with pytest.raises(HTTPException,match='NUMERIC_FIELD_INVALID'):daily_sessions.assess([{**row,'amount_yuan':'bad'}],bodies,catalog)


def test_public_session_reconciliation_is_method_when_provider_is_method_and_is_immutable(tmp_path):
    worker=method_source(tmp_path);data=tmp_path/'data'
    with TestClient(create_app(data,baostock_worker=worker,runtime_role='API')) as client:
        snap=snapshot(client);command={'kind':'DAILY_SESSION','snapshot_id':snap['snapshot_id'],'idempotency_key':'session'}
        response=client.post('/api/market/source-authority',json=command)
        assert response.status_code==201,response.text
        saved=response.json();assert saved['evidence_kind']=='METHOD_CASE' and not saved['system_usable']
        assert saved['reference_manifest_sha256']==daily_sessions.MANIFEST
        assert saved['details']['session_rows'][0]['explanation']=='POST_CLOSE_COMPONENTS_PRESENTATION_COMPATIBLE'
        assert client.post('/api/market/source-authority',json=command).json()==saved
        assert client.get('/api/data/snapshots/'+snap['snapshot_id']).json()==snap
        assert client.get('/api/account').json()['version']==0
    with TestClient(create_app(data,runtime_role='API')) as client:
        assert client.get('/api/market/source-authority/'+saved['assessment_id']).json()==saved
