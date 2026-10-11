"""Current provider scope via public API; legacy fixtures are closed old SQLite."""
import json
import sqlite3
from fastapi.testclient import TestClient
from roll.app import create_app
from test_market_directory import establish
from test_codex_evidence import request_data, WORKER, terminal


def legacy_settings(directory):
    with TestClient(create_app(directory)):
        pass
    # A closed prior profile supplies its old saved setting before reopening the writer.
    with sqlite3.connect(directory/'roll.sqlite3') as db:
        value={'version':1,'backend':'DEEPSEEK','saved_at':'2026-10-08T00:00:00+00:00'}
        db.execute('INSERT INTO agent_settings VALUES(1,?)',(json.dumps(value),))
    return value


def test_new_deepseek_selection_is_refused_without_creating_settings_or_runs(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        before=client.get('/api/agents/settings/history').json()
        response=client.post('/api/agents/settings',json={'expected_version':0,'backend':'DEEPSEEK'})
        assert response.status_code==403,response.text
        assert response.json()['detail']['code']=='BACKEND_OUTSIDE_CURRENT_SCOPE'
        assert client.get('/api/agents/settings/history').json()==before
        assert client.get('/api/data/runs').json()==[]


def test_legacy_deepseek_admission_is_refused_before_request_retry_or_material_lookup(tmp_path):
    legacy=legacy_settings(tmp_path)
    with TestClient(create_app(tmp_path)) as client:
        history=client.get('/api/agents/settings/history').json()
        account=client.get('/api/account').json()
        # Missing identifiers prove refusal precedes lookup and any credential/runtime dispatch.
        commands=[('/api/data/requests/missing/deepseek',{'question':'依据？','retry_of':'missing'}),
                  ('/api/data/requests/missing/agent',{'question':'依据？'}),
                  ('/api/research/review-materials/missing/reviews',{'expected_material_fingerprint':'missing','retry_of':'missing'})]
        for url,command in commands:
            response=client.post(url,json=command)
            assert response.status_code==403,response.text
            assert response.json()['detail']['code']=='BACKEND_OUTSIDE_CURRENT_SCOPE'
        settings=client.get('/api/agents/settings').json()
        assert {key:settings[key] for key in legacy}==legacy
        assert settings['supported_backends']==['CODEX']
        assert settings['resave_required'] is True
        assert client.get('/api/agents/settings/history').json()==history
        assert client.get('/api/data/runs').json()==[]
        assert client.get('/api/account').json()==account


def test_explicit_codex_works_with_legacy_settings_and_resave_preserves_history(tmp_path,monkeypatch):
    directory=tmp_path/'data'
    legacy=legacy_settings(directory)
    credential=tmp_path/'auth.json'
    credential.write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'METHOD_CASE_ONLY'}}))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE',str(credential))
    worker=tmp_path/'worker.py';worker.write_text(WORKER,encoding='utf-8')
    with TestClient(create_app(directory,codex_worker=worker)) as client:
        establish(client,['SSE:600519'])
        request_id=request_data(client)
        history=client.get('/api/agents/settings/history').json()
        for route in ['deepseek','agent']:
            refused=client.post(f'/api/data/requests/{request_id}/{route}',json={'question':'BAD'})
            assert refused.status_code==403,refused.text
        assert client.get('/api/data/runs').json()==[]
        explicit=client.post(f'/api/data/requests/{request_id}/codex',json={'question':'BAD'})
        assert explicit.status_code==202,explicit.text
        original=terminal(client,explicit.json()['run_id'])
        assert original['backend']=='CODEX' and original['status']=='INVALID_OUTPUT'
        assert original['selection_kind']=='EXPLICIT_BACKEND'
        assert original['backend_settings']==legacy
        assert client.get('/api/agents/settings/history').json()==history
        saved=client.post('/api/agents/settings',json={'expected_version':1,'backend':'CODEX'})
        assert saved.status_code==200,saved.text
        assert saved.json()['version']==2
        assert client.post('/api/agents/settings',json={'expected_version':1,'backend':'CODEX'}).status_code==409
        retry=client.post(f'/api/data/requests/{request_id}/agent',json={'question':'BAD','retry_of':original['run_id']})
        assert retry.status_code==202,retry.text
        result=terminal(client,retry.json()['run_id'])
        assert result['backend']=='CODEX' and result['status']=='INVALID_OUTPUT'
        assert result['selection_kind']=='SAVED_BACKEND'
        assert result['backend_settings']['version']==2
        assert client.get(f"/api/data/runs/{original['run_id']}").json()==original
        assert client.get('/api/agents/settings/history').json()[1:]==history
    with TestClient(create_app(directory)) as client:
        assert client.get('/api/agents/settings').json()['resave_required'] is False
        assert client.get(f"/api/data/runs/{original['run_id']}").json()==original
        assert client.get(f"/api/data/runs/{result['run_id']}").json()==result
        assert client.get('/api/agents/settings/history').json()[1:]==history


def test_legacy_selection_cannot_create_a_review_run_for_valid_frozen_material(tmp_path):
    directory=tmp_path/'data';legacy_settings(directory)
    fixture=tmp_path/'review.json'
    fixture.write_text(json.dumps({'cases':[{'case_id':'scope-refusal','gates':{'G4':'FAIL'},
        'checks_complete':True,'endpoint_reached':True,'observed_value':-1}]}))
    with TestClient(create_app(directory,technical_review_method_file=fixture)) as client:
        material=client.get('/api/research/method-review-materials').json()[0]
        url='/api/research/review-materials/'+material['material_id']
        before=client.get(url).json()
        assert client.get(url+'/reviews').json()==[]
        response=client.post(url+'/reviews',json={'expected_material_fingerprint':material['material_fingerprint']})
        assert response.status_code==403,response.text
        assert response.json()['detail']['code']=='BACKEND_OUTSIDE_CURRENT_SCOPE'
        assert client.get(url+'/reviews').json()==[]
        assert client.get(url).json()==before
        assert client.get('/api/data/runs').json()==[]
