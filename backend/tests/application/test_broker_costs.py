from fastapi.testclient import TestClient
from roll.app import create_app
from test_account import baseline, submit
from test_funding import funding
from datetime import datetime, timezone


def contract(**changes):
    return {'expected_version': 0, 'expected_account_version': 1, 'expected_funding_version': 1,
        'idempotency_key': 'cost-v1', 'market': 'SSE', 'board': 'MAIN', 'instrument_type': 'STOCK',
        'effective_from': '2026-10-01T00:00:00+08:00', 'effective_until': '2026-11-01T00:00:00+08:00',
        'commission_including_regulatory_rate': '0.0003', 'minimum_commission_yuan': '5.00',
        'transfer_each_side_rate': '0.00001', 'source_name': 'Test user broker tariff',
        'source_text': 'Synthetic isolated tariff\r\ncommission includes regulatory fees; transfer separate.',
        'confirmed': True, **changes}


def test_source_bound_cost_registration_is_immutable_and_never_grants_capability(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        submit(client, baseline(), 'baseline')
        assert client.post('/api/funding/confirm', json=funding()).status_code == 200
        response = client.post('/api/actions/broker-costs/confirm', json=contract())
        assert response.status_code == 201, response.text
        first = response.json()
        assert first['version'] == 1 and first['system_usable'] is False
        raw = client.get('/api/data/archives/'+first['source_archive']['sha256'])
        assert raw.content == contract()['source_text'].encode('utf-8')
        assert client.post('/api/actions/broker-costs/confirm', json=contract()).json() == first
        assert client.post('/api/actions/broker-costs/confirm', json=contract(source_text='changed')).status_code == 409
        assert client.get('/api/capabilities').json()['allowed_actions'] == []
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/actions/broker-costs/versions/1').json() == first
        assert client.get('/api/actions/broker-costs').json()['current'] == first


def test_actual_capture_tracks_cost_revision_and_keeps_validity_ungranted(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        submit(client, baseline(), 'baseline')
        client.post('/api/funding/confirm', json=funding())
        before = client.post('/api/actions/evaluate', json={}).json()
        registered = client.post('/api/actions/broker-costs/confirm', json=contract()).json()
        after = client.post('/api/actions/evaluate', json={}).json()
        assert before['evaluation_id'] != after['evaluation_id']
        inputs = client.get('/api/data/archives/'+after['input_archive']['sha256']).json()
        assert inputs['broker_cost_state']['current'] == registered
        assert 'PRODUCTION_ACTION_VALIDITY_POLICY_NOT_FROZEN' in after['limitations']
        assert after['decisions'] == []
        assert client.post('/api/actions/evaluations/'+after['evaluation_id']+'/replay').json()['matches_original'] is True


def test_current_cost_facts_and_fee_estimate_restrict_scope_interval_and_changed_versions(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        submit(client, baseline(), 'baseline')
        client.post('/api/funding/confirm', json=funding())
        client.post('/api/actions/broker-costs/confirm', json=contract())
        status = client.get('/api/actions/broker-costs').json()
        assert status['current_status'] == 'CONFIRMED_COST_FACTS_ONLY'
        assert client.post('/api/market/identities', json={'instrument':'SSE:600000', 'exchange':'SSE',
            'board':'MAIN', 'instrument_type':'STOCK', 'name':'Isolated stock', 'basis':'Synthetic identity',
            'effective_at':'2026-10-07T00:00:00+08:00'}).status_code == 200
        command = {'instrument':'SSE:600000','price_upper_yuan':'100.00','quantity':'200',
                   'required_as_of':datetime.now(timezone.utc).isoformat()}
        estimated = client.post('/api/actions/broker-costs/estimate', json=command).json()
        assert estimated['fees_yuan'] == '6.20'
        assert estimated['cost_binding']['version'] == 1
        assert estimated['limitations'] == ['PRODUCTION_ACTION_VALIDITY_POLICY_NOT_FROZEN']
        assert estimated['system_usable'] is False
        outside = client.post('/api/actions/broker-costs/estimate', json={**command,'instrument':'SZSE:300001'}).json()
        assert outside['fees_yuan'] is None and 'BROKER_COST_SCOPE_MISMATCH' in outside['limitations']
        past = client.post('/api/actions/broker-costs/estimate', json={**command,'required_as_of':'2026-09-01T00:00:00+08:00'}).json()
        assert past['fees_yuan'] is None and 'BROKER_COST_OUTSIDE_EFFECTIVE_INTERVAL' in past['limitations']
        client.post('/api/funding/confirm', json=funding(1, single_exposure='5000.00'))
        assert client.get('/api/actions/broker-costs').json()['current_status'] == 'RESTRICTED'
        changed = client.post('/api/actions/broker-costs/estimate', json=command).json()
        assert changed['fees_yuan'] is None and 'BROKER_COST_ACCOUNT_OR_FUNDING_VERSION_CHANGED' in changed['limitations']


def test_source_corruption_restricts_current_contract_without_rewriting_history(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        submit(client, baseline(), 'baseline')
        client.post('/api/funding/confirm', json=funding())
        first = client.post('/api/actions/broker-costs/confirm', json=contract()).json()
        # External loss of an isolated archive, identified through public metadata.
        source = tmp_path / first['source_archive']['path']
        source.write_bytes(b'corrupt isolated source')
        listing = client.get('/api/actions/broker-costs').json()
        assert listing['current_status'] == 'RESTRICTED'
        assert 'BROKER_COST_SOURCE_UNAVAILABLE_OR_CORRUPT' in listing['current_reasons']
        assert client.get('/api/actions/broker-costs/versions/1').json() == first
