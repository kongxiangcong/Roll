"""Current scope/publication contracts on isolated host-bound METHOD inputs."""
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import time
import pytest
from fastapi.testclient import TestClient
from roll.app import create_app
from capability_method_app import package, save_package
from test_capabilities import ready, method_command
from test_funding import funding
from test_actions import action_package, prepare
from test_intents import intent_command


def risk_package():
    clock = package()['required_as_of']
    p = package()
    gates = ['DATA', 'RULE_QUANTITY', 'AUTHORIZATION', 'STRESS_EXECUTION', 'ONLINE_CONSISTENCY']
    p.update(candidate_kind='RISK_POLICY', gates={g: 'PASS' for g in gates}, required_gates=gates, allowed_actions=['REDUCE', 'EXIT'])
    p['deployment_fingerprints'] = {'policy': 'e' * 64}
    rule_id = 'SSE-MAIN-A-2026-07-06'
    p['action_packet'] = {'namespace': 'METHOD_ENGINEERING', 'as_of': p['required_as_of'], 'expires_at': p['expires_at'],
        'opportunities': [], 'loss_facts': p['loss_facts'], 'risk_inputs': {
            'policy': {'policy_id': 'risk-method', 'policy_fingerprint': 'e' * 64, 'authorization': {**funding()['authorization'], 'version': 1, 'loss_origin_at': '2026-10-07T02:00:00+00:00'},
                       'scope': p['scope'], 'rule_ids': {'SSE:600000': rule_id}},
            'required_as_of': p['required_as_of'], 'consumer_knowledge_cutoff': clock,
            'quotes': {'SSE:600000': {'last': '100', 'adjustment': 'RAW', 'currency': 'CNY', 'errors': [], 'upstream_at': p['required_as_of'],
                    'available_at': p['required_as_of'], 'method_status': 'NORMAL', 'evidence_kind': 'METHOD_CASE'}},
            'identities': {'SSE:600000': {'exchange': 'SSE', 'board': 'MAIN', 'instrument_type': 'STOCK'}},
            'rules': {'SSE:600000': {'implementation_status': 'ADAPTED', 'rule_id': rule_id, 'normal_price_limit_percent': '10', 'price_tick_yuan': '.01'}},
            'calendars': {'SSE:600000': {'is_trading_day': True}}, 'evidence_kind': 'METHOD_CASE'}}
    return p


@pytest.mark.parametrize('scope,allowed', [('NEW_RISK', True), ('MODEL', True), ('ALL_MONITOR', False)])
def test_scope_keeps_independently_qualified_risk_reduction_and_known_holdings(tmp_path, monkeypatch, scope, allowed):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = risk_package()
    file = save_package(tmp_path/'qualification.json', p)
    client = TestClient(create_app(tmp_path/'data', capability_method_file=file))
    try:
        positions = [{'instrument':'SSE:600000','quantity':'300','sellable_quantity':'300','reference_cost':'100'}]
        ready(client, permission_status='NOT_OPEN', positions=positions)
        original = client.post('/api/capabilities/grants', json={**method_command(), 'allowed_actions':['REDUCE','EXIT'], 'deployment_fingerprints':p['deployment_fingerprints']})
        assert original.status_code == 201, original.text
        pause = client.post('/api/capabilities/lifecycle', json={'scope':scope,'state':'SUSPENDED','reason_code':'USER_PAUSE','reason':'单独控制本范围','expected_version':0,'idempotency_key':'pause'})
        assert pause.status_code == 200
        result = client.post('/api/actions/evaluate', json={}).json()
        assert [(d['action'],d['quantity']) for d in result['decisions']] == ([('REDUCE','100')] if allowed else []), result
        assert result['holdings'] == positions or result['holdings'][0]['quantity']=='300'
        assert client.get('/api/account').json()['positions'][0]['sellable_quantity']=='300'
        assert client.get('/api/capabilities/grants').json() == [original.json()]
    finally: client.close()


def test_revoke_interleaved_after_capture_refuses_publication_and_original_prepare(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test')
    p=action_package()
    p['action_packet']['method_publish_delay_ms']=1500
    file=save_package(tmp_path/'qualification.json',p)
    with TestClient(create_app(tmp_path/'data',capability_method_file=file)) as client:
        grant=prepare(client,p)
        old=client.post('/api/actions/evaluate',json={}).json()
        with ThreadPoolExecutor(max_workers=2) as pool:
            computing=pool.submit(client.post,'/api/actions/evaluate',json={})
            time.sleep(.4)
            revoked=client.post('/api/capabilities/lifecycle',json={'grant_id':grant['grant_id'],'scope':'MODEL','state':'REVOKED','reason_code':'USER_REVOKE','reason':'计算期间撤回原授权','expected_version':0,'idempotency_key':'revoke'})
            assert revoked.status_code==200,revoked.text
            result=computing.result().json()
        assert result['decisions']==[],result
        assert result['publication_check']['refusal'],result
        assert client.get('/api/actions/current').json()['decisions']==[]
        assert client.post('/api/intents/prepare',json=intent_command(old)).status_code==409
        assert client.get('/api/actions/evaluations/'+old['evaluation_id']).json()==old
        assert client.post('/api/actions/evaluations/'+result['evaluation_id']+'/replay').json()['matches_original'] is True


def test_required_risk_policy_monitoring_source_unknown_restricts_its_actual_purpose(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test')
    p=risk_package()
    file=save_package(tmp_path/'qualification.json',p)
    client=TestClient(create_app(tmp_path/'data',capability_method_file=file))
    try:
        ready(client,permission_status='NOT_OPEN',positions=[{'instrument':'SSE:600000','quantity':'300','sellable_quantity':'300','reference_cost':'100'}])
        response=client.post('/api/capabilities/grants',json={**method_command(),'allowed_actions':['REDUCE','EXIT'],'deployment_fingerprints':p['deployment_fingerprints']})
        assert response.status_code==201,response.text
        grant=response.json()
        old=client.post('/api/actions/evaluate',json={}).json()
        assert len(old['decisions'])==1
        monitor=client.post('/api/capabilities/monitoring/check',json={'grant_id':grant['grant_id'],'basis':'必需风险政策运行监测原归档缺失，不得继续放行此目的'})
        assert monitor.status_code==201,monitor.text
        check=monitor.json()
        assert check['status']=='RESTRICTED'
        assert 'REQUIRED_MONITORING_SOURCE_UNVERIFIED' in check['reasons']
        assert client.get('/api/capabilities/grants/'+grant['grant_id']+'/status').json()['allowed_actions']==[]
        assert client.get('/api/actions/current').json()['decisions']==[]
        assert client.get('/api/actions/evaluations/'+old['evaluation_id']).json()==old
        assert client.get('/api/account').json()['positions'][0]['quantity']=='300'
    finally: client.close()
