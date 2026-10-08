from fastapi.testclient import TestClient

from roll.app import create_app
from test_deepseek_evidence import model_server, request, terminal


def test_explicit_environment_file_configures_runtime_and_preserves_process_overrides(tmp_path, monkeypatch):
    data = tmp_path / 'runtime'
    env_file = tmp_path / 'runtime.env'
    env_file.write_text(f'ROLL_DATA_DIR="{data}"\nexport DEEPSEEK_API_KEY="ROLL_METHOD_CASE_ONLY" # local only\n', encoding='utf-8')
    monkeypatch.setenv('ROLL_ENV', 'test')
    monkeypatch.setenv('ROLL_ENV_FILE', str(env_file))
    monkeypatch.setenv('ROLL_DATA_DIR', str(data))
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    monkeypatch.delenv('ROLL_DEEPSEEK_API_KEY_FILE', raising=False)
    with model_server(lambda body, n: (401, {'error': {'message': 'method unauthorized'}})) as (endpoint, bodies):
        with TestClient(create_app(deepseek_endpoint=endpoint)) as client:
            parent = request(client)
            run = terminal(client, client.post(f'/api/data/requests/{parent}/deepseek', json={'question': '核对来源'}).json()['run_id'])
            assert run['error']['code'] == 'DEEPSEEK_AUTH_REJECTED'
            assert 'ROLL_METHOD_CASE_ONLY' not in str(run)
        assert len(bodies) == 1
    assert (data / 'roll.sqlite3').exists()
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'PROCESS_OVERRIDE')
    with TestClient(create_app(deepseek_endpoint=endpoint)) as client:
        persisted = client.get('/api/data/runs/' + run['run_id']).json()
        assert persisted == run
        next_run = terminal(client, client.post(f'/api/data/requests/{parent}/deepseek', json={'question': '核对来源'}).json()['run_id'])
        assert next_run['error']['code'] == 'METHOD_ENDPOINT_REQUIRES_SYNTHETIC_CREDENTIAL'


def test_isolated_application_directory_never_reads_runtime_credentials(tmp_path, monkeypatch):
    env_file = tmp_path / 'not-for-this-test.env'
    env_file.write_text('DEEPSEEK_API_KEY=SHOULD_NEVER_LOAD\n', encoding='utf-8')
    monkeypatch.setenv('ROLL_ENV_FILE', str(env_file))
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    monkeypatch.delenv('ROLL_DEEPSEEK_API_KEY_FILE', raising=False)
    with TestClient(create_app(tmp_path / 'isolated')) as client:
        parent = request(client)
        run = terminal(client, client.post(f'/api/data/requests/{parent}/deepseek', json={'question': '核对来源'}).json()['run_id'])
        assert run['error']['code'] == 'DEEPSEEK_AUTH_NOT_CONFIGURED'


def test_test_factory_does_not_load_checkout_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_DATA_DIR', str(tmp_path / 'isolated'))
    monkeypatch.setenv('ROLL_ENV', 'test')
    monkeypatch.delenv('ROLL_ENV_FILE', raising=False)
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    monkeypatch.delenv('ROLL_DEEPSEEK_API_KEY_FILE', raising=False)
    with TestClient(create_app()) as client:
        parent = request(client)
        run = terminal(client, client.post(f'/api/data/requests/{parent}/deepseek', json={'question': '核对来源'}).json()['run_id'])
        assert run['error']['code'] == 'DEEPSEEK_AUTH_NOT_CONFIGURED'
