import copy
import json

from fastapi.testclient import TestClient
from roll.app import create_app
from test_account import baseline, submit
from test_funding import funding
from capability_method_app import package, save_package
import pytest


def command():
    return {"material_id": "unknown", "review_run_id": "unknown", "expected_material_fingerprint": "a" * 64,
            "deployment_fingerprints": {}, "scope": {"instruments": ["SSE:600000"], "market": "SSE", "board": "MAIN", "frequency": "DAILY", "horizon": 20},
            "allowed_actions": ["BUY"], "expected_account_version": 0, "expected_funding_version": 0,
            "required_as_of": "2026-10-11T00:00:00+00:00", "effective_at": "2026-10-11T00:00:00+00:00",
            "expires_at": "2026-10-12T00:00:00+00:00", "idempotency_key": "grant-1", "basis": "isolated engineering"}


def test_unknown_evidence_is_refused_and_audited_across_restart(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        result = client.post('/api/capabilities/grants', json=command())
        assert result.status_code == 409
        assert 'EVIDENCE_UNAVAILABLE' in result.json()['detail']['reasons']
        assert client.get('/api/capabilities').json()['state'] == 'UNGRANTED'
        assert client.get('/api/capabilities/events').json()[0]['event_type'] == 'GRANT_REFUSED'
    with TestClient(create_app(tmp_path)) as client:
        assert len(client.get('/api/capabilities/events').json()) == 1
        assert client.post('/api/capabilities/grants', json=command()).json() == result.json()


def test_isolated_complete_method_evidence_grants_bounded_scope_and_survives_restart(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    file = save_package(tmp_path / 'qualification.json', package())
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        ready(client)
        value = method_command()
        result = client.post('/api/capabilities/grants', json=value)
        assert result.status_code == 201, result.text
        grant = result.json()
        assert grant['evidence_kind'] == 'METHOD_ENGINEERING' and grant['system_usable'] is False
        assert grant['scope']['horizon'] == 20 and grant['allowed_actions'] == ['BUY']
        assert grant['human_review_label'] == '经自动验证与模型技术审阅，未经人工独立复核'
        assert client.get('/api/capabilities').json()['state'] == 'METHOD_GRANTED'
        assert client.post('/api/formal/evaluate', json={}).status_code == 403
        assert client.post('/api/capabilities/grants', json=value).json() == grant
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        assert client.get('/api/capabilities/grants').json() == [grant]


def ready(client, permission_status='OPEN', positions=None):
    value = baseline()
    value['payload']['positions'] = positions or []
    value['payload']['permission_profile'][0]['status'] = permission_status
    submit(client, value, 'baseline')
    submit(client, {'kind': 'ACCOUNT_DECLARATION', 'expected_account_version': 1, 'payload': {
        'effective_at': package()['required_as_of'], 'source': 'METHOD fixture user', 'record_id': 'declaration',
        'scope': ['TRADES', 'ORDERS', 'CASH', 'EQUITY'], 'changes': 'NONE', 'basis': 'isolated facts'}}, 'declaration')
    assert client.post('/api/funding/confirm', json=funding()).status_code == 200


def method_command():
    p = package()
    return {**command(), 'material_id': p['material_id'], 'review_run_id': p['review_run_id'],
            'expected_material_fingerprint': p['material_fingerprint'], 'deployment_fingerprints': p['deployment_fingerprints'],
            'scope': p['scope'], 'expected_account_version': 2, 'expected_funding_version': 1,
            'effective_at': p['effective_at'], 'expires_at': p['expires_at'], 'required_as_of': p['required_as_of']}


def test_old_required_time_cannot_bypass_current_facts(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    file = save_package(tmp_path / 'qualification.json', package())
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        ready(client)
        value = method_command()
        value['required_as_of'] = '2026-10-07T10:00:00+08:00'
        result = client.post('/api/capabilities/grants', json=value)
        assert result.status_code == 409
        assert 'CURRENT_CUTOFF_NOT_BOUND' in result.json()['detail']['reasons']


@pytest.mark.parametrize('change,reason', [
    ({'gates': {'G1': 'PASS'}}, 'REQUIRED_GATES_NOT_PASS'),
    ({'gates': {**package()['gates'], 'G7': 'INCONCLUSIVE'}}, 'REQUIRED_GATES_NOT_PASS'),
    ({'preliminary': True}, 'QUALIFICATION_EVIDENCE_INCOMPLETE'),
    ({'experiment_status': 'RUNNING_DIAGNOSTIC'}, 'QUALIFICATION_EVIDENCE_INCOMPLETE'),
    ({'incomplete_checks': ['FORWARD_NOT_MATURE']}, 'QUALIFICATION_EVIDENCE_INCOMPLETE'),
    ({'review': {**package()['review'], 'backend': 'DEEPSEEK'}}, 'CODEX_REVIEW_INCOMPLETE'),
    ({'review': {**package()['review'], 'host_unresolved_gate_evidence': ['G7']}}, 'REVIEW_BLOCKERS_UNRESOLVED'),
    ({'review': {**package()['review'], 'blocking_issues_resolved': False}}, 'REVIEW_BLOCKERS_UNRESOLVED'),
    ({'review': {**package()['review'], 'material_id': 'another'}}, 'REVIEW_MATERIAL_BINDING_MISMATCH'),
    ({'review': {**package()['review'], 'reproduction': {'matches_original': False, 'network_calls': 0}}}, 'HOST_REPRODUCTION_NOT_VERIFIED'),
    ({'review_due_at': None}, 'VALIDATED_EXPIRY_MISSING'),
])
def test_host_derived_evidence_deficits_cannot_be_self_signed(tmp_path, monkeypatch, change, reason):
    monkeypatch.setenv('ROLL_ENV', 'test')
    file = save_package(tmp_path / 'qualification.json', {**package(), **change})
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        ready(client)
        result = client.post('/api/capabilities/grants', json=method_command())
        assert result.status_code == 409, result.text
        assert reason in result.json()['detail']['reasons']
        assert client.get('/api/capabilities/grants').json() == []
        assert client.get('/api/capabilities/events').json()[-1]['event_type'] == 'GRANT_REFUSED'
        assert client.post('/api/capabilities/grants', json={**method_command(), 'gates': {'G1': 'PASS'}, 'self_signed': True}).status_code == 422


@pytest.mark.parametrize('changes,reason', [
    ({'deployment_fingerprints': {'model': 'f' * 64}}, 'DEPLOYMENT_FINGERPRINT_MISMATCH'),
    ({'scope': {**package()['scope'], 'instruments': ['SSE:600001']}}, 'SCOPE_NOT_VALIDATED'),
    ({'scope': {**package()['scope'], 'horizon': 30}}, 'SCOPE_NOT_VALIDATED'),
    ({'scope': {**package()['scope'], 'frequency': 'INTRADAY'}}, 'SCOPE_NOT_VALIDATED'),
    ({'allowed_actions': ['TRADE']}, 'ACTIONS_NOT_VALIDATED'),
    ({'expected_account_version': 1}, 'ACCOUNT_VERSION_CONFLICT'),
    ({'expected_funding_version': 0}, 'FUNDING_VERSION_CONFLICT'),
    ({'expires_at': '2099-10-12T00:00:00+00:00'}, 'GRANT_TIME_OUTSIDE_VALIDATED_BOUNDARY'),
])
def test_deployment_scope_versions_and_expiry_reject_direct_calls(tmp_path, monkeypatch, changes, reason):
    monkeypatch.setenv('ROLL_ENV', 'test')
    file = save_package(tmp_path / 'qualification.json', package())
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        ready(client)
        response = client.post('/api/capabilities/grants', json={**method_command(), **changes})
        assert response.status_code == 409 and reason in response.json()['detail']['reasons']


def test_parallel_idempotency_and_funding_revocation_restrict_stored_grant(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    monkeypatch.setenv('ROLL_ENV', 'test')
    file = save_package(tmp_path / 'qualification.json', package())
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        ready(client)
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(pool.map(lambda _: client.post('/api/capabilities/grants', json=method_command()), range(4)))
        assert all(r.status_code == 201 for r in responses)
        assert len({r.json()['grant_id'] for r in responses}) == 1
        assert len(client.get('/api/capabilities/events').json()) == 1
        assert client.post('/api/capabilities/grants', json={**method_command(), 'basis': 'changed'}).status_code == 409
        assert client.post('/api/funding/confirm', json=funding(1, enabled=False)).status_code == 200
        current = client.get('/api/capabilities').json()
        assert current['state'] == 'RESTRICTED' and current['allowed_actions'] == []
        assert 'FUNDING_NOT_ENABLED' in current['reasons']
        assert len(client.get('/api/capabilities/grants').json()) == 1


def test_production_constructor_and_reopening_refuse_synthetic_authority(tmp_path, monkeypatch):
    file = save_package(tmp_path / 'qualification.json', package())
    monkeypatch.delenv('ROLL_ENV', raising=False)
    with pytest.raises(ValueError, match='CAPABILITY_METHOD_HOST_TEST_ONLY'):
        create_app(tmp_path / 'prod', capability_method_file=file)
    monkeypatch.setenv('ROLL_ENV', 'test')
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        ready(client)
        assert client.post('/api/capabilities/grants', json=method_command()).status_code == 201
    monkeypatch.delenv('ROLL_ENV', raising=False)
    with TestClient(create_app(tmp_path / 'data')) as client:
        assert client.get('/api/capabilities').json()['state'] == 'RESTRICTED'
        value = {**method_command(), 'idempotency_key': 'prod'}
        assert client.post('/api/capabilities/grants', json=value).status_code == 409


def test_explicit_risk_policy_uses_own_five_gates_without_profit_model_requirement(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    gates = ['DATA', 'RULE_QUANTITY', 'AUTHORIZATION', 'STRESS_EXECUTION', 'ONLINE_CONSISTENCY']
    value = {**package(), 'candidate_kind': 'RISK_POLICY', 'required_gates': gates, 'gates': {g: 'PASS' for g in gates}, 'allowed_actions': ['REDUCE', 'EXIT']}
    file = save_package(tmp_path / 'qualification.json', value)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        ready(client)
        response = client.post('/api/capabilities/grants', json={**method_command(), 'allowed_actions': ['REDUCE']})
        assert response.status_code == 201, response.text
        assert response.json()['candidate_kind'] == 'RISK_POLICY'


def test_unconfirmed_funding_pending_drafts_and_archive_changes_remain_closed(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    file = save_package(tmp_path / 'qualification.json', package())
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        response = client.post('/api/capabilities/grants', json=method_command())
        assert 'FUNDING_NOT_ENABLED' in response.json()['detail']['reasons']
        ready(client)
        draft = client.post('/api/account/drafts', json={'kind': 'ACCOUNT_DECLARATION', 'expected_account_version': 2,
            'payload': {'effective_at': package()['required_as_of'], 'source': 'pending', 'record_id': 'pending',
                        'scope': ['TRADES'], 'changes': 'UNRECORDED', 'basis': 'unresolved'}})
        assert draft.status_code == 201
        response = client.post('/api/capabilities/grants', json={**method_command(), 'idempotency_key': 'pending'})
        assert 'ACCOUNT_FACTS_NOT_RECONCILED' in response.json()['detail']['reasons']


def test_method_file_content_hash_is_verified_before_host_start(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    file = save_package(tmp_path / 'qualification.json', package())
    envelope = json.loads(file.read_text(encoding='utf-8'))
    envelope['package']['gates']['G7'] = 'FAIL'
    file.write_text(json.dumps(envelope), encoding='utf-8')
    with pytest.raises(ValueError, match='CAPABILITY_METHOD_PACKAGE_INVALID'):
        create_app(tmp_path / 'data', capability_method_file=file)


def test_final_ended_protocol_is_accepted_without_extra_human_review_gate(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    file = save_package(tmp_path / 'qualification.json', {**package(), 'experiment_status': 'ENDED'})
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        ready(client)
        response = client.post('/api/capabilities/grants', json=method_command())
        assert response.status_code == 201, response.text
        assert response.json()['human_review_label'].endswith('未经人工独立复核')


def test_each_grant_scope_remains_queryable_when_a_second_scope_is_registered(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = package()
    p['scope']['instruments'] = ['SSE:600000', 'SSE:600001']
    p['current_data']['instruments'] = ['SSE:600000', 'SSE:600001']
    file = save_package(tmp_path / 'qualification.json', p)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        ready(client)
        first = client.post('/api/capabilities/grants', json=method_command()).json()
        second = client.post('/api/capabilities/grants', json={**method_command(), 'scope': {**method_command()['scope'], 'instruments': ['SSE:600001']}, 'idempotency_key': 'second'}).json()
        result = client.get('/api/capabilities').json()
        assert {s['grant']['grant_id'] for s in result['grant_statuses']} == {first['grant_id'], second['grant_id']}
        own = client.get(f"/api/capabilities/grants/{first['grant_id']}/status").json()
        assert own['state'] == 'METHOD_GRANTED' and own['grant']['scope']['instruments'] == ['SSE:600000']


def test_missing_complete_protocol_fingerprint_cannot_create_versionless_grant(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    file = save_package(tmp_path / 'qualification.json', {**package(), 'complete_protocol_fingerprint': None})
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        ready(client)
        response = client.post('/api/capabilities/grants', json=method_command())
        assert response.status_code == 409
        assert 'COMPLETE_PROTOCOL_FINGERPRINT_MISSING' in response.json()['detail']['reasons']


@pytest.mark.parametrize('permission_status', ['NOT_OPEN', 'UNKNOWN'])
def test_independent_reduction_does_not_require_new_purchase_permission(tmp_path, monkeypatch, permission_status):
    monkeypatch.setenv('ROLL_ENV', 'test')
    gates = ['DATA', 'RULE_QUANTITY', 'AUTHORIZATION', 'STRESS_EXECUTION', 'ONLINE_CONSISTENCY']
    p = {**package(), 'candidate_kind': 'RISK_POLICY', 'required_gates': gates, 'gates': {g: 'PASS' for g in gates}, 'allowed_actions': ['REDUCE', 'EXIT']}
    file = save_package(tmp_path / 'qualification.json', p)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        ready(client, permission_status, [{'instrument': 'SSE:600000', 'quantity': '300', 'sellable_quantity': '300', 'reference_cost': '10.00'}])
        response = client.post('/api/capabilities/grants', json={**method_command(), 'allowed_actions': ['REDUCE']})
        assert response.status_code == 201, response.text
        for action in ['BUY', 'ADD']:
            rejected = client.post('/api/capabilities/grants', json={**method_command(), 'allowed_actions': [action], 'idempotency_key': action})
            assert rejected.status_code == 409 and 'MARKET_PERMISSION_NOT_OPEN' in rejected.json()['detail']['reasons']


def test_reduction_with_unknown_sellable_quantity_stays_closed(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    gates = ['DATA', 'RULE_QUANTITY', 'AUTHORIZATION', 'STRESS_EXECUTION', 'ONLINE_CONSISTENCY']
    p = {**package(), 'candidate_kind': 'RISK_POLICY', 'required_gates': gates, 'gates': {g: 'PASS' for g in gates}, 'allowed_actions': ['REDUCE', 'EXIT']}
    file = save_package(tmp_path / 'qualification.json', p)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        ready(client, 'NOT_OPEN', [{'instrument': 'SSE:600000', 'quantity': '300', 'sellable_quantity': None, 'reference_cost': '10.00'}])
        rejected = client.post('/api/capabilities/grants', json={**method_command(), 'allowed_actions': ['REDUCE']})
        assert rejected.status_code == 409 and 'ACCOUNT_FACTS_NOT_RECONCILED' in rejected.json()['detail']['reasons']


def test_queries_reuse_one_immutable_host_proof_without_new_reproduction(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    file = save_package(tmp_path / 'qualification.json', package())
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        ready(client)
        grant = client.post('/api/capabilities/grants', json=method_command())
        assert grant.status_code == 201
        before = client.get('/api/capabilities/proofs')
        assert before.status_code == 200
        assert len(before.json()) == 1 and before.json()[0]['status'] == 'VERIFIED'
        for _ in range(3):
            assert client.get('/api/capabilities').json()['state'] == 'METHOD_GRANTED'
            assert client.get(f"/api/capabilities/grants/{grant.json()['grant_id']}/status").json()['state'] == 'METHOD_GRANTED'
        assert client.get('/api/capabilities/proofs').json() == before.json()


def test_slow_host_reproduction_does_not_lock_account_writer_and_rechecks_revocation(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import time
    monkeypatch.setenv('ROLL_ENV', 'test')
    file = save_package(tmp_path / 'qualification.json', {**package(), 'method_reproduction_delay_ms': 2000})
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        ready(client)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(client.post, '/api/capabilities/grants', json=method_command())
            for _ in range(100):
                proof = client.get('/api/capabilities/proofs')
                if proof.status_code == 200 and proof.json() and proof.json()[-1]['status'] == 'RUNNING': break
                time.sleep(.01)
            else: raise AssertionError('host proof did not start')
            start = time.monotonic()
            confirmed = client.post('/api/funding/confirm', json=funding(1, enabled=False))
            assert confirmed.status_code == 200
            assert time.monotonic() - start < 1.0
            result = future.result()
        assert result.status_code == 409
        assert 'FUNDING_VERSION_CONFLICT' in result.json()['detail']['reasons']
        assert client.get('/api/capabilities/grants').json() == []


def test_archived_review_producer_proof_reuse_detects_changed_original_input(tmp_path, monkeypatch):
    from test_technical_review import WORKER, terminal
    monkeypatch.setenv('ROLL_ENV', 'test')
    auth = tmp_path / 'auth.json'
    auth.write_text(json.dumps({'auth_mode': 'chatgpt', 'tokens': {'access_token': 'METHOD_CASE_ONLY'}}))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE', str(auth))
    worker = tmp_path / 'review.py'
    worker.write_text(WORKER)
    fixture = tmp_path / 'review-case.json'
    fixture.write_text(json.dumps({'cases': [{'case_id': 'proof', 'gates': {'G4': 'INCONCLUSIVE'},
        'checks_complete': True, 'endpoint_reached': True, 'observed_value': 1}]}))
    directory = tmp_path / 'data'
    with TestClient(create_app(directory, codex_worker=worker, technical_review_method_file=fixture)) as client:
        ready(client)
        material = client.get('/api/research/method-review-materials').json()[0]
        started = client.post('/api/research/review-materials/' + material['material_id'] + '/reviews', json={
            'expected_material_fingerprint': material['material_fingerprint']})
        assert started.status_code == 202, started.text
        review = terminal(client, started.json()['run_id'])
        assert review['status'] == 'COMPLETE', review
        value = {**method_command(), 'material_id': material['material_id'], 'review_run_id': review['run_id'],
                 'expected_material_fingerprint': material['material_fingerprint']}
        response = client.post('/api/capabilities/grants', json=value)
        assert response.status_code == 409  # Completed METHOD review is not actual qualification.
        proofs = client.get('/api/capabilities/proofs').json()
        assert len(proofs) == 1 and proofs[0]['status'] == 'VERIFIED'
        identifier = proofs[0]['proof_id']
        assert client.get('/api/capabilities/proofs/' + identifier + '/check').json()['reproduction_reused'] is True
        assert client.get('/api/capabilities/proofs').json() == proofs
        (directory / material['method_case_archive']['path']).write_bytes(b'changed original input')
        assert client.get('/api/capabilities/proofs/' + identifier + '/check').status_code == 409
        assert client.get('/api/capabilities/grants').json() == []
