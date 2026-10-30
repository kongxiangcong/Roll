"""Host configuration isolation, without invoking a retired model backend."""
import os
from fastapi.testclient import TestClient

from roll.app import create_app


def test_explicit_environment_file_configures_runtime_and_preserves_process_overrides(tmp_path,monkeypatch):
    data=tmp_path/'runtime'
    env_file=tmp_path/'runtime.env'
    env_file.write_text(f'ROLL_DATA_DIR="{data}"\nexport FUYAO_API_KEY="ROLL_METHOD_CASE_ONLY" # local only\nROLL_DATA_SOURCE_POLICY=OFFICIAL_FIRST\n',encoding='utf-8')
    monkeypatch.setenv('ROLL_ENV','test')
    monkeypatch.setenv('ROLL_ENV_FILE',str(env_file))
    monkeypatch.setenv('ROLL_DATA_DIR',str(data))
    # Register restoration even when a variable was originally absent: the loader
    # mutates os.environ outside monkeypatch and must not leak into later tests.
    monkeypatch.setenv('FUYAO_API_KEY','BEFORE_LOAD')
    monkeypatch.delenv('FUYAO_API_KEY')
    monkeypatch.setenv('ROLL_DATA_SOURCE_POLICY','LEGACY')
    monkeypatch.delenv('ROLL_DATA_SOURCE_POLICY')
    with TestClient(create_app()) as client:
        policy=client.get('/api/data/source-policy').json()
        assert policy['default']=='OFFICIAL_FIRST'
        assert os.environ['FUYAO_API_KEY']=='ROLL_METHOD_CASE_ONLY'
        assert 'ROLL_METHOD_CASE_ONLY' not in str(policy)
    assert (data/'roll.sqlite3').exists()
    monkeypatch.setenv('FUYAO_API_KEY','PROCESS_OVERRIDE')
    monkeypatch.setenv('ROLL_DATA_SOURCE_POLICY','LEGACY')
    with TestClient(create_app()) as client:
        assert client.get('/api/data/source-policy').json()['default']=='LEGACY'
        assert os.environ['FUYAO_API_KEY']=='PROCESS_OVERRIDE'


def test_isolated_application_directory_never_reads_runtime_credentials(tmp_path,monkeypatch):
    env_file=tmp_path/'not-for-this-test.env'
    env_file.write_text('FUYAO_API_KEY=SHOULD_NEVER_LOAD\nROLL_DATA_SOURCE_POLICY=OFFICIAL_FIRST\n',encoding='utf-8')
    monkeypatch.setenv('ROLL_ENV_FILE',str(env_file))
    monkeypatch.delenv('FUYAO_API_KEY',raising=False)
    monkeypatch.setenv('ROLL_DATA_SOURCE_POLICY','LEGACY')
    with TestClient(create_app(tmp_path/'isolated')) as client:
        assert client.get('/api/data/source-policy').json()['default']=='LEGACY'
        assert 'FUYAO_API_KEY' not in os.environ


def test_test_factory_does_not_load_checkout_credentials(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_DATA_DIR',str(tmp_path/'isolated'))
    monkeypatch.setenv('ROLL_ENV','test')
    monkeypatch.delenv('ROLL_ENV_FILE',raising=False)
    monkeypatch.delenv('FUYAO_API_KEY',raising=False)
    monkeypatch.delenv('EM_API_KEY',raising=False)
    monkeypatch.setenv('ROLL_DATA_SOURCE_POLICY','LEGACY')
    with TestClient(create_app()) as client:
        assert client.get('/api/data/source-policy').json()['default']=='LEGACY'
        assert 'FUYAO_API_KEY' not in os.environ and 'EM_API_KEY' not in os.environ
