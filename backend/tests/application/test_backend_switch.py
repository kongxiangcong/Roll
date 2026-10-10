import json
import time
import httpx
import pytest

from fastapi.testclient import TestClient

from roll.app import create_app
from test_codex_evidence import WORKER, request_data, terminal
from test_market_directory import establish
from test_deepseek_evidence import model_server, response, call, message, terminal as deep_terminal


def test_backend_settings_are_versioned_persistent_and_do_not_change_authority(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        before=client.get('/api/account').json()
        settings=client.get('/api/agents/settings')
        assert settings.status_code==200
        assert settings.json()['backend']=='CODEX'
        changed=client.post('/api/agents/settings',json={'expected_version':0,'backend':'DEEPSEEK'})
        assert changed.status_code==200,changed.text
        assert changed.json()['version']==1
        assert client.post('/api/agents/settings',json={'expected_version':0,'backend':'CODEX'}).status_code==409
        assert client.post('/api/agents/settings',json={'expected_version':1,'backend':'CODEX','model':'invented'}).status_code==422
        assert client.get('/api/account').json()==before
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/agents/settings').json()==changed.json()
        assert len(client.get('/api/agents/settings/history').json())==2


def test_running_task_keeps_its_selection_and_all_routes_share_concurrency(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test')
    monkeypatch.delenv('DEEPSEEK_API_KEY',raising=False)
    monkeypatch.delenv('ROLL_DEEPSEEK_API_KEY_FILE',raising=False)
    credential=tmp_path/'chatgpt.json'
    credential.write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'METHOD_CASE_ONLY'}}))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE',str(credential))
    worker=tmp_path/'worker.py';worker.write_text(WORKER,encoding='utf-8')
    with TestClient(create_app(tmp_path/'data',codex_worker=worker)) as client:
        establish(client,['SSE:600519']);identifier=request_data(client)
        started=client.post(f'/api/data/requests/{identifier}/agent',json={'question':'WAIT'})
        assert started.status_code==202,started.text
        first=started.json()
        assert first['backend']=='CODEX' and first['backend_settings']['version']==0
        assert client.post('/api/agents/settings',json={'expected_version':0,'backend':'DEEPSEEK'}).status_code==200
        assert client.post(f'/api/data/requests/{identifier}/deepseek',json={'question':'other'}).status_code==409
        assert client.post(f'/api/data/requests/{identifier}/agent',json={'question':'other'}).status_code==409
        current=client.get('/api/data/runs/'+first['run_id']).json()
        for field in ['backend','model','config_fingerprint','sdk_runtime_version','backend_settings','limits']:
            assert current[field]==first[field]
        client.post('/api/data/runs/'+first['run_id']+'/cancel',json={})
        old=terminal(client,first['run_id'])
        next_run=client.post(f'/api/data/requests/{identifier}/agent',json={'question':'WAIT','retry_of':first['run_id']})
        assert next_run.status_code==202,next_run.text
        second=terminal(client,next_run.json()['run_id'])
        assert second['backend']=='DEEPSEEK' and second['backend_settings']['version']==1
        assert second['retry_of']==old['run_id']
        assert second['run_id']!=old['run_id']
        assert client.get('/api/data/runs/'+old['run_id']).json()==old
        assert client.post(f'/api/data/requests/{identifier}/agent',json={'question':'changed','retry_of':old['run_id']}).status_code==409


def test_cross_backend_retry_reuses_verified_source_bytes_and_original_times(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test');monkeypatch.setenv('DEEPSEEK_API_KEY','ROLL_METHOD_CASE_ONLY')
    credential=tmp_path/'auth.json';credential.write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'METHOD_CASE_ONLY'}}))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE',str(credential))
    worker=tmp_path/'worker.py';worker.write_text(WORKER,encoding='utf-8')
    source_calls=[]
    def source(request):
        source_calls.append(str(request.url))
        return httpx.Response(200,text='<p>贵州茅台公开材料</p>',headers={'content-type':'text/html'})
    def model(body,number):
        if number==1:return 200,response([call('roll_read_source',{'instrument':'SSE:600519','source_id':'MOUTAI_OFFICIAL'},1)])
        material=json.loads(next(v['output'] for v in body['input'] if v.get('type')=='function_call_output'))
        return 200,response([message(json.dumps({'candidates':[{'instrument':'SSE:600519','group':'QUOTE','raw_hash':material['archive']['sha256'],
            'assertion':'公开材料','evidence_quote':'贵州茅台公开材料','time_basis':'UNKNOWN'}],'gaps':[]}))])
    with model_server(model) as (endpoint,_),TestClient(create_app(tmp_path/'data',codex_worker=worker,
            deepseek_endpoint=endpoint,market_transport=httpx.MockTransport(source))) as client:
        establish(client,['SSE:600519']);identifier=request_data(client)
        first=client.post(f'/api/data/requests/{identifier}/codex',json={'question':'READ_SOURCE'}).json()
        original=terminal(client,first['run_id']);calls_before=len(source_calls)
        client.post('/api/agents/settings',json={'expected_version':0,'backend':'DEEPSEEK'})
        retry=client.post(f'/api/data/requests/{identifier}/agent',json={'question':' READ_SOURCE ','retry_of':original['run_id']})
        assert retry.status_code==202,retry.text
        actual=deep_terminal(client,retry.json()['run_id'])
        assert actual['status']=='PARTIAL',actual
        assert len(source_calls)==calls_before
        assert actual['acquisition_usage']['http_calls']==0
        assert actual['tools'][0]['status']=='REUSED_ARCHIVE'
        assert actual['tools'][0]['reused_from_run_id']==original['run_id']
        assert actual['archives'][0]['received_at']==original['archives'][0]['received_at']
        assert actual['candidates'][0]['available_at']==original['archives'][0]['available_at']
        assert client.get('/api/data/runs/'+original['run_id']).json()==original


def test_other_live_host_cannot_bypass_shared_concurrency_after_switch(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test')
    credential=tmp_path/'auth.json';credential.write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'METHOD_CASE_ONLY'}}))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE',str(credential))
    worker=tmp_path/'worker.py';worker.write_text(WORKER,encoding='utf-8')
    with TestClient(create_app(tmp_path/'data',codex_worker=worker)) as first:
        establish(first,['SSE:600519']);identifier=request_data(first)
        run=first.post(f'/api/data/requests/{identifier}/codex',json={'question':'WAIT'}).json()
        with TestClient(create_app(tmp_path/'data',codex_worker=worker)) as second:
            assert second.post('/api/agents/settings',json={'expected_version':0,'backend':'DEEPSEEK'}).status_code==200
            refused=second.post(f'/api/data/requests/{identifier}/agent',json={'question':'WAIT'})
            assert refused.status_code==409,refused.text
            assert refused.json()['detail']['code']=='AGENT_CONCURRENCY_LIMIT'
            assert second.get('/api/data/runs/'+run['run_id']).json()['status']=='RUNNING'
        first.post('/api/data/runs/'+run['run_id']+'/cancel',json={})
        assert terminal(first,run['run_id'])['status']=='CANCELLED'


def test_deepseek_running_selection_survives_reverse_switch_and_cancel(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test');monkeypatch.setenv('DEEPSEEK_API_KEY','ROLL_METHOD_CASE_ONLY')
    monkeypatch.delenv('ROLL_CODEX_AUTH_FILE',raising=False)
    def waiting(body,number):
        time.sleep(3)
        return 200,response([message(json.dumps({'candidates':[],'gaps':['no source']}))])
    with model_server(waiting) as (endpoint,bodies),TestClient(create_app(tmp_path,deepseek_endpoint=endpoint)) as client:
        establish(client,['SSE:600519']);identifier=request_data(client)
        client.post('/api/agents/settings',json={'expected_version':0,'backend':'DEEPSEEK'})
        started=client.post(f'/api/data/requests/{identifier}/agent',json={'question':'source'}).json()
        deadline=time.monotonic()+15
        while not bodies and time.monotonic()<deadline:time.sleep(.05)
        assert bodies
        client.post('/api/agents/settings',json={'expected_version':1,'backend':'CODEX'})
        assert client.post(f'/api/data/requests/{identifier}/codex',json={'question':'source'}).status_code==409
        current=client.get('/api/data/runs/'+started['run_id']).json()
        for field in ['backend','model','config_fingerprint','sdk_runtime_version','backend_settings','limits']:
            assert current[field]==started[field]
        client.post('/api/data/runs/'+started['run_id']+'/cancel',json={})
        assert deep_terminal(client,started['run_id'])['status']=='CANCELLED'
        next_run=client.post(f'/api/data/requests/{identifier}/agent',json={'question':'source','retry_of':started['run_id']})
        assert next_run.status_code==202
        assert terminal(client,next_run.json()['run_id'])['backend']=='CODEX'


def test_corrupt_retry_archive_is_a_gap_and_is_never_researched_again(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test');monkeypatch.setenv('DEEPSEEK_API_KEY','ROLL_METHOD_CASE_ONLY')
    credential=tmp_path/'auth.json';credential.write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'METHOD_CASE_ONLY'}}))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE',str(credential))
    worker=tmp_path/'worker.py';worker.write_text(WORKER,encoding='utf-8')
    calls=[]
    def source(request):
        calls.append(str(request.url))
        return httpx.Response(200,text='<p>公开材料</p>',headers={'content-type':'text/html'})
    def model(body,number):
        if number==1:return 200,response([call('roll_read_source',{'instrument':'SSE:600519','source_id':'MOUTAI_OFFICIAL'},1)])
        return 200,response([message(json.dumps({'candidates':[],'gaps':['archive unavailable']}))])
    with model_server(model) as (endpoint,_),TestClient(create_app(tmp_path/'data',codex_worker=worker,
            deepseek_endpoint=endpoint,market_transport=httpx.MockTransport(source))) as client:
        establish(client,['SSE:600519']);identifier=request_data(client)
        original=terminal(client,client.post(f'/api/data/requests/{identifier}/codex',json={'question':'READ_SOURCE'}).json()['run_id'])
        (tmp_path/'data'/original['archives'][0]['path']).write_bytes(b'corrupted')
        count=len(calls)
        retry=client.post(f'/api/data/requests/{identifier}/deepseek',json={'question':'READ_SOURCE','retry_of':original['run_id']}).json()
        result=deep_terminal(client,retry['run_id'])
        assert len(calls)==count
        assert any(g['code']=='ARCHIVE_MISSING_OR_CORRUPT' for g in result['gaps']),result
        assert not result['candidates']
