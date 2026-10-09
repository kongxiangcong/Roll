"""Read-only metadata checks are not training, source qualification or support evidence."""
from fastapi.testclient import TestClient
from roll.app import create_app
import httpx
import sqlite3
from test_research_acquisition_import import acquire, provider


def protocol(client, predecessor=None, dataset=None):
    response = client.post('/api/research/protocols', json={
        'predecessor_id': predecessor, 'dataset_id': dataset,
        'basis': 'Explicit engineering metadata fixture; no real research claim'})
    assert response.status_code == 201, response.text
    return response.json()['protocol_id']


def attempt(client, pid, category='PRIMARY_FIT', status='FAILED'):
    response = client.post('/api/research/protocols/' + pid + '/attempts', json={
        'category': category,
        'partition': 'CALIBRATION' if category == 'CALIBRATION' else 'DEVELOPMENT',
        'configuration': {'candidate': 'PRICE_VOLUME_LOGIT_V1'},
        'basis': 'Explicit bounded engineering attempt'})
    assert response.status_code == 201, response.text
    identifier = response.json()['attempt_id']
    if status:
        finished = client.post('/api/research/attempts/' + identifier + '/finish', json={
            'status': status, 'reason': 'Retain engineering terminal state'})
        assert finished.status_code == 200, finished.text
    return identifier


def public_state(client, pids):
    return {
        'protocols': client.get('/api/research/protocols').json(),
        'datasets': client.get('/api/research/datasets').json(),
        'account': client.get('/api/account').json(),
        'account_audit': client.get('/api/account/audit').json(),
        'capabilities': client.get('/api/capabilities').json(),
        'family': {pid: {
            suffix: client.get('/api/research/protocols/' + pid + '/' + suffix).json()
            for suffix in ['audit', 'attempt-manifest', 'models']}
            for pid in pids}}


def test_preflight_preserves_two_old_failures_and_shares_family_budget_without_writes(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        root = protocol(client)
        first = attempt(client, root)
        second = attempt(client, root)
        successor = protocol(client, root)
        sibling = protocol(client, root)
        pids = [root, successor, sibling]
        before = public_state(client, pids)
        replies = []
        for pid in pids:
            response = client.get('/api/research/protocols/' + pid + '/training-preflight')
            assert response.status_code == 200, response.text
            result = response.json()
            assert result['purpose'] == 'RESEARCH'
            assert result['assessment'] == 'METADATA_ONLY'
            assert result['ready_to_fit'] is False
            assert result['budget']['primary_and_neighbors'] == {
                'categories': ['PRIMARY_FIT', 'G5_NEIGHBOR'], 'limit': 5,
                'used': 2, 'remaining': 3, 'exhausted': False}
            assert result['budget']['calibration']['used'] == 0
            assert result['budget']['calibration']['remaining'] == 1
            assert set(result['attempt_manifest']['family_protocol_ids']) == set(pids)
            assert set(result['attempt_manifest']['attempt_ids']) == {first, second}
            assert all(a['status'] == 'FAILED' for a in result['attempt_manifest']['attempts'])
            assert all('configuration' not in a for a in result['attempt_manifest']['attempts'])
            assert 'DATASET_NOT_REGISTERED' in result['blockers']
            assert 'REAL_TRAINING_PATH_NOT_IMPLEMENTED' in result['blockers']
            assert result['checks']['training_inputs_labels_and_support'] == 'NOT_CHECKED'
            assert result['checks']['source_artifact_integrity'] == 'NOT_CHECKED'
            assert client.get('/api/research/protocols/' + pid + '/training-preflight').json() == result
            replies.append(result)
        assert public_state(client, pids) == before
    with TestClient(create_app(tmp_path)) as client:
        assert public_state(client, pids) == before
        for pid, expected in zip(pids, replies):
            assert client.get('/api/research/protocols/' + pid + '/training-preflight').json() == expected
        assert public_state(client, pids) == before


def test_blocked_host_acquisition_preflight_reads_metadata_without_sources_labels_or_fits(tmp_path):
    calls = []

    def fixed_source(request):
        calls.append(str(request.url))
        return provider(request)

    # Public source format uses a fixed external response, not an actual qualified research sample.
    with TestClient(create_app(tmp_path, market_transport=httpx.MockTransport(fixed_source))) as client:
        run = acquire(client)
        response = client.post('/api/research/datasets', json={
            'source_run_id': run['run_id'], 'basis': 'Host format fixture; coverage is not historical PIT'})
        assert response.status_code == 201, response.text
        dataset = response.json()
        pid = protocol(client, dataset=dataset['dataset_id'])
        before = public_state(client, [pid])
        source_calls = list(calls)
        # Damage only this test's archived source and Parquet. A metadata GET cannot validate or decode them.
        for original in dataset['original_archives']:
            (tmp_path / original['path']).write_bytes(b'Unreadable source fixture for metadata-only preflight')
        for purpose in ['RESEARCH', 'METHOD_VALIDATION']:
            response = client.get('/api/research/protocols/' + pid + '/training-preflight',
                                  params={'purpose': purpose})
            assert response.status_code == 200, response.text
            result = response.json()
            assert result['source']['evidence_kind'] == dataset['source_evidence_kind']
            assert result['source']['registered_training_readiness'] == 'BLOCKED'
            assert result['checks']['historical_point_in_time'] == 'NOT_PROVEN_IN_REGISTRATION'
            assert result['checks']['source_artifact_integrity'] == 'NOT_CHECKED'
            assert result['checks']['training_inputs_labels_and_support'] == 'NOT_CHECKED'
            assert result['checks']['real_training_path'] == 'NOT_IMPLEMENTED'
            assert result['registered_windows'] == {
                'DEVELOPMENT': {'state': 'NOT_PREREGISTERED', 'rows': 0},
                'CALIBRATION': {'state': 'NOT_PREREGISTERED', 'rows': 0}}
            for blocker in ['HISTORICAL_POINT_IN_TIME_NOT_PROVEN',
                            'COMPLETE_CORPORATE_ACTION_TREATMENT_NOT_PROVEN',
                            'COMPLETE_HISTORICAL_EXECUTION_STATUS_NOT_PROVEN',
                            'HISTORICAL_RULE_COVERAGE_REQUIRES_VALIDATION',
                            'RESEARCH_WINDOWS_NOT_PREREGISTERED', 'REAL_TRAINING_PATH_NOT_IMPLEMENTED']:
                assert blocker in result['blockers']
            assert 'HISTORICAL_SEAL_INDEPENDENCE_UNPROVEN' not in result['blockers']
            assert 'REAL_MODEL_AND_CALIBRATOR_NOT_FROZEN' not in result['blockers']
            assert result['source']['evidence_kind'] == 'METHOD_CASE'
            assert 'METHOD_CASE_NOT_REAL_RESEARCH_DATA' in result['blockers']
            assert result['ready_to_fit'] is False
            assert result['budget']['primary_and_neighbors']['used'] == 0
            assert result['budget']['calibration']['used'] == 0
            assert client.get('/api/research/protocols/' + pid + '/training-preflight',
                              params={'purpose': purpose}).json() == result
        assert calls == source_calls
        assert public_state(client, [pid]) == before
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/research/protocols/' + pid + '/training-preflight').json()['ready_to_fit'] is False
        assert public_state(client, [pid]) == before


def test_preflight_counts_neighbors_abort_and_interruption_at_shared_budget_boundary(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        root = protocol(client)
        attempt(client, root)
        attempt(client, root, category='G5_NEIGHBOR')
        successor = protocol(client, root)
        sibling = protocol(client, root)
        attempt(client, successor, status='ABORTED')
        attempt(client, successor, status='SUCCEEDED')
        interrupted = attempt(client, sibling, status=None)
        attempt(client, successor, category='CALIBRATION', status='ABORTED')
        pending = client.get('/api/research/protocols/' + root + '/attempt-manifest').json()
        assert next(a for a in pending['attempts'] if a['attempt_id'] == interrupted)['status'] == 'RUNNING'
    # Existing lifecycle records an unfinished attempt on close. GET itself never ends it.
    with TestClient(create_app(tmp_path)) as client:
        pids = [root, successor, sibling]
        before = public_state(client, pids)
        for pid in pids:
            response = client.get('/api/research/protocols/' + pid + '/training-preflight')
            assert response.status_code == 200, response.text
            result = response.json()
            assert result['budget']['primary_and_neighbors'] == {
                'categories': ['PRIMARY_FIT', 'G5_NEIGHBOR'], 'limit': 5,
                'used': 5, 'remaining': 0, 'exhausted': True}
            assert result['budget']['calibration'] == {
                'categories': ['CALIBRATION'], 'limit': 1,
                'used': 1, 'remaining': 0, 'exhausted': True}
            assert 'PRIMARY_FIT_BUDGET_EXHAUSTED' in result['blockers']
            assert 'CALIBRATION_BUDGET_EXHAUSTED' in result['blockers']
            fits = [a for a in result['attempt_manifest']['attempts'] if a['category'] != 'CALIBRATION']
            assert [a['status'] for a in fits] == ['FAILED', 'FAILED', 'ABORTED', 'SUCCEEDED', 'INTERRUPTED']
        assert client.get('/api/research/protocols/unknown/training-preflight').status_code == 404
        assert client.get('/api/research/protocols/' + root + '/training-preflight',
                          params={'purpose': 'UNKNOWN'}).status_code == 422
        assert public_state(client, pids) == before
    with TestClient(create_app(tmp_path)) as client:
        assert public_state(client, pids) == before


def test_preflight_reads_legacy_ownerless_attempt_without_rewriting_it(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        pid = protocol(client)
        identifier = attempt(client, pid, status=None)
    # External persisted-state fixture: old versions lack host_owner. Assertions use only public APIs.
    with sqlite3.connect(tmp_path / 'roll.sqlite3') as database:
        database.execute("UPDATE research_attempts SET value=json_remove(value,'$.host_owner') WHERE id=?",
                         (identifier,))
    with TestClient(create_app(tmp_path)) as client:
        before = public_state(client, [pid])
        response = client.get('/api/research/protocols/' + pid + '/training-preflight')
        assert response.status_code == 200, response.text
        result = response.json()
        metadata = result['attempt_manifest']['attempts'][0]
        assert metadata['attempt_id'] == identifier
        assert metadata['status'] == 'INTERRUPTED'
        assert metadata.get('host_owner') is None
        assert result['budget']['primary_and_neighbors']['used'] == 1
        assert result['budget']['primary_and_neighbors']['remaining'] == 4
        assert public_state(client, [pid]) == before


def test_research_model_admission_preserves_budget_and_old_failures_without_reading_inputs(tmp_path):
    with TestClient(create_app(tmp_path, market_transport=httpx.MockTransport(provider))) as client:
        run = acquire(client)
        dataset = client.post('/api/research/datasets', json={
            'source_run_id': run['run_id'], 'basis': 'Unqualified archived source; no historical proof'}).json()
        pid = protocol(client, dataset=dataset['dataset_id'])
        attempt(client, pid)
        attempt(client, pid)
        before = public_state(client, [pid])
        # Admission must not try to decode even DEV/CAL when metadata already forbids training.
        for original in dataset['original_archives']:
            (tmp_path / original['path']).write_bytes(b'Unreadable archived source for admission test')
        response = client.post('/api/research/protocols/' + pid + '/models', json={
            'purpose': 'RESEARCH', 'basis': 'Do not consume a third fit to rediscover known gaps'})
        assert response.status_code == 409, response.text
        detail = response.json()['detail']
        assert detail['code'] == 'TRAINING_ADMISSION_BLOCKED'
        assert 'HISTORICAL_POINT_IN_TIME_NOT_PROVEN' in detail['blockers']
        assert 'RESEARCH_WINDOWS_NOT_PREREGISTERED' in detail['blockers']
        assert detail['budget']['primary_and_neighbors']['remaining'] == 3
        assert detail['budget']['calibration']['remaining'] == 1
        assert detail['attempt_started'] is False
        assert public_state(client, [pid]) == before
    with TestClient(create_app(tmp_path)) as client:
        assert public_state(client, [pid]) == before


def test_exhausted_calibration_prevents_starting_another_method_primary_fit(tmp_path):
    from test_execution_labels import method_archive, register
    method_archive(tmp_path, unknown=True)
    with TestClient(create_app(tmp_path)) as client:
        _, registered = register(client)
        pid = registered['protocol_id']
        attempt(client, pid, category='CALIBRATION', status='ABORTED')
        before = public_state(client, [pid])
        response = client.post('/api/research/protocols/' + pid + '/models', json={
            'purpose': 'METHOD_VALIDATION', 'basis': 'Calibration cannot be retried under a new primary'})
        assert response.status_code == 409, response.text
        assert response.json()['detail']['code'] == 'CALIBRATION_BUDGET_EXHAUSTED'
        assert response.json()['detail']['attempt_started'] is False
        assert public_state(client, [pid]) == before
