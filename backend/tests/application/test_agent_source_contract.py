import json
from contextlib import contextmanager

import httpx
import pytest
from fastapi.testclient import TestClient

from roll.app import create_app
from test_deepseek_evidence import call, message, model_server, response, terminal
from test_fuyao_evidence import millis
from test_market_directory import establish
from test_source_resolution import completed, quote_bytes


@contextmanager
def method_agent_client(tmp_path, monkeypatch, source, group, backend='DEEPSEEK'):
    monkeypatch.setenv('ROLL_ENV', 'test')
    credential = tmp_path / 'method-auth.json'
    credential.write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'METHOD_CASE_ONLY'}}))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE', str(credential))
    worker = tmp_path / 'method-worker.py'
    worker.write_text('''import json,sys
command=json.loads(sys.stdin.readline())
print(json.dumps({'kind':'tool','id':'method-source','name':'roll_read_evidence','arguments':{'instrument':'SSE:600519','group':''' + repr(group) + '''}}),flush=True)
result=json.loads(sys.stdin.readline())
print(json.dumps({'kind':'completed','status':'completed','output':json.dumps({'candidates':[],'gaps':[]}), 'error_info':None}),flush=True)
''', encoding='utf-8')

    if backend=='CODEX':
        with TestClient(create_app(tmp_path/'data',market_transport=httpx.MockTransport(source),codex_worker=worker)) as client:
            establish(client,['SSE:600519'])
            yield client
        return

    # Historical cross-provider tests retain their original adapter; current collection excludes them.
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'ROLL_METHOD_CASE_ONLY')
    def model(body, number):
        if not any(item.get('type') == 'function_call_output' for item in body['input']):
            return 200, response([call('roll_read_evidence', {'instrument':'SSE:600519','group':group}, number)])
        return 200, response([message('{"candidates":[],"gaps":[]}')])

    with model_server(model) as (endpoint, bodies), TestClient(create_app(tmp_path / 'data',
            market_transport=httpx.MockTransport(source), codex_worker=worker, deepseek_endpoint=endpoint)) as client:
        establish(client, ['SSE:600519'])
        yield client


@pytest.mark.parametrize('backend', ['CODEX'])
def test_agent_child_preserves_explicit_fuyao_adjustment_source(tmp_path, monkeypatch, backend):
    monkeypatch.setenv('FUYAO_API_KEY', 'METHOD_SECRET_NOT_REAL')
    calls = []

    def source(request):
        calls.append(str(request.url))
        if request.url.host != 'fuyao.aicubes.cn':
            return httpx.Response(503, content=b'METHOD denies unintended provider')
        return httpx.Response(200, json={'code':0,'data':{'thscode':'600519.SH','ticker':'600519',
            'item':[{'ticker':'600519','ex_date_ms':millis('2026-06-26'),'dividend_per_share':'28.02423','per_share_bonus':0}]}})

    with method_agent_client(tmp_path, monkeypatch, source, 'ADJUSTMENTS', backend) as client:
        parent = client.post('/api/data/requests', json={'instruments':['SSE:600519'],'groups':['ADJUSTMENTS'],
            'purpose':'OBSERVATION','start_date':'2026-01-01','end_date':'2026-09-30',
            'daily_source':'FUYAO','quote_source':'FUYAO','adjustment_source':'FUYAO','required_fields':['ADJUSTMENTS.cash_per_share']}).json()
        account = client.get('/api/account').json()
        client.post('/api/agents/settings', json={'expected_version':0,'backend':backend}).raise_for_status()
        launched = client.post(f'/api/data/requests/{parent["request_id"]}/agent', json={'question':'method explicit adjustment source'})
        assert launched.status_code == 202, launched.text
        run = terminal(client, launched.json()['run_id'])
        child = client.get('/api/data/runs/' + run['tools'][0]['child_run_id']).json()
        child_request = client.get('/api/data/requests/' + child['request_id']).json()
        for field in ['daily_source','quote_source','adjustment_source','required_fields']:
            assert child_request[field] == parent[field]
        snapshot = client.get('/api/data/snapshots/' + child['snapshot_id']).json()
        assert snapshot['facts'][0]['source_id'] == 'fuyao-actions'
        assert snapshot['facts'][0]['cash_per_share'] == '28.02423'
        assert len(calls) == 1 and calls[0].startswith('https://fuyao.aicubes.cn/api/a-share/corporate-actions/adjustment-factors')
        assert client.get('/api/account').json() == account


def test_codex_retry_rejects_revised_archive_and_preserves_original(tmp_path,monkeypatch):
    """Current same-Codex retry; historical cross-provider tuples below stay excluded."""
    price=['1258.620'];calls=[]
    def source(request):
        calls.append(str(request.url))
        return httpx.Response(200,content=quote_bytes(price[0]))
    with method_agent_client(tmp_path,monkeypatch,source,'QUOTE','CODEX') as client:
        parent=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['QUOTE'],
            'purpose':'OBSERVATION','start_date':'2026-09-30','end_date':'2026-09-30',
            'quote_source':'SINA','required_fields':['QUOTE.last']}).json()
        account=client.get('/api/account').json()
        path=f'/api/data/requests/{parent["request_id"]}/agent'
        launched=client.post(path,json={'question':'method revised source'})
        assert launched.status_code==202,launched.text
        original=terminal(client,launched.json()['run_id'])
        assert original['backend']=='CODEX' and original['tools'][0]['status']=='ARCHIVED'
        tool=original['tools'][0];old=client.get('/api/data/snapshots/'+tool['snapshot_id']).json()
        child=client.get('/api/data/runs/'+tool['child_run_id']).json()
        resolve=f'/api/data/requests/{child["request_id"]}/resolve'
        first=completed(client,client.post(resolve,json={'usage':'HISTORICAL_RESEARCH','allow_fallback':False,
            'basis_run_id':tool['child_run_id']}).json()['resolution_id'])
        price[0]='1390.000'
        revised=completed(client,client.post(resolve,json={'usage':'HISTORICAL_RESEARCH','allow_fallback':False,
            'use_cache':False,'revision_of':first['resolution_id']}).json()['resolution_id'])
        assert old['facts'][0]['raw_hash'] in revised['revision']['changed_raw_hashes']
        assert client.get('/api/data/resolutions/'+first['resolution_id']).json()['dependency_status']=='INVALIDATED'
        before=len(calls)
        launched=client.post(path,json={'question':'method revised source','retry_of':original['run_id']})
        assert launched.status_code==202,launched.text
        retry=terminal(client,launched.json()['run_id']);retry_tool=retry['tools'][0]
        assert retry['backend']=='CODEX' and retry['retry_of']==original['run_id']
        assert retry['backend_settings']==original['backend_settings']
        assert retry_tool['reuse_rejected']=='SOURCE_REVISED_RECHECK_REQUIRED' and retry_tool['status']=='ARCHIVED'
        assert retry['acquisition_usage']['http_calls']==1 and len(calls)==before+1
        new=client.get('/api/data/snapshots/'+retry_tool['snapshot_id']).json()
        assert new['facts'][0]['last']=='1390.000' and new['facts'][0]['raw_hash']!=old['facts'][0]['raw_hash']
        assert client.get('/api/data/runs/'+original['run_id']).json()==original
        assert client.get('/api/data/snapshots/'+tool['snapshot_id']).json()==old
        assert client.post('/api/data/runs/'+tool['child_run_id']+'/replay').json()['facts']==old['facts']
        assert len(calls)==before+1 and client.get('/api/account').json()==account


@pytest.mark.parametrize('first_backend,retry_backend', [('CODEX','DEEPSEEK'), ('DEEPSEEK','CODEX')])
def test_cross_backend_retry_rejects_revised_archive_and_preserves_original(tmp_path, monkeypatch, first_backend, retry_backend):
    price = ['1258.620']
    calls = []

    def source(request):
        calls.append(str(request.url))
        return httpx.Response(200, content=quote_bytes(price[0]))

    with method_agent_client(tmp_path, monkeypatch, source, 'QUOTE') as client:
        parent = client.post('/api/data/requests', json={'instruments':['SSE:600519'],'groups':['QUOTE'],
            'purpose':'OBSERVATION','start_date':'2026-09-30','end_date':'2026-09-30',
            'quote_source':'SINA','required_fields':['QUOTE.last']}).json()
        account = client.get('/api/account').json()
        client.post('/api/agents/settings', json={'expected_version':0,'backend':first_backend}).raise_for_status()
        launched = client.post(f'/api/data/requests/{parent["request_id"]}/agent', json={'question':'method revised source'})
        assert launched.status_code == 202, launched.text
        original = terminal(client, launched.json()['run_id'])
        tool = original['tools'][0]
        assert tool['status'] == 'ARCHIVED', original
        old_snapshot = client.get('/api/data/snapshots/' + tool['snapshot_id']).json()
        original_fact = old_snapshot['facts'][0]
        child = client.get('/api/data/runs/' + tool['child_run_id']).json()
        resolution_url = f'/api/data/requests/{child["request_id"]}/resolve'
        first = completed(client, client.post(resolution_url,
            json={'usage':'HISTORICAL_RESEARCH','allow_fallback':False,'basis_run_id':tool['child_run_id']}).json()['resolution_id'])
        assert first['status'] == 'COMPLETED', first
        price[0] = '1390.000'
        revised = completed(client, client.post(resolution_url,
            json={'usage':'HISTORICAL_RESEARCH','allow_fallback':False,'use_cache':False,
                  'revision_of':first['resolution_id']}).json()['resolution_id'])
        assert original_fact['raw_hash'] in revised['revision']['changed_raw_hashes']
        assert client.get('/api/data/resolutions/' + first['resolution_id']).json()['dependency_status'] == 'INVALIDATED'
        calls_before = len(calls)
        version = client.get('/api/agents/settings').json()['version']
        client.post('/api/agents/settings', json={'expected_version':version,'backend':retry_backend}).raise_for_status()
        retry = client.post(f'/api/data/requests/{parent["request_id"]}/agent',
            json={'question':'method revised source','retry_of':original['run_id']})
        assert retry.status_code == 202, retry.text
        actual = terminal(client, retry.json()['run_id'])
        retry_tool = actual['tools'][0]
        assert retry_tool.get('reuse_rejected') == 'SOURCE_REVISED_RECHECK_REQUIRED', actual
        assert retry_tool['status'] == 'ARCHIVED'
        assert len(calls) == calls_before + 1
        assert actual['acquisition_usage']['http_calls'] == 1
        new_snapshot = client.get('/api/data/snapshots/' + retry_tool['snapshot_id']).json()
        assert new_snapshot['facts'][0]['last'] == '1390.000'
        assert new_snapshot['facts'][0]['raw_hash'] != original_fact['raw_hash']
        assert client.get('/api/data/runs/' + original['run_id']).json() == original
        assert client.get('/api/data/snapshots/' + tool['snapshot_id']).json() == old_snapshot
        assert client.post('/api/data/runs/' + tool['child_run_id'] + '/replay').json()['facts'] == old_snapshot['facts']
        assert len(calls) == calls_before + 1
        assert client.get('/api/account').json() == account
