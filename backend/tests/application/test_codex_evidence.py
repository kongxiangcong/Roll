import time
import json
from pathlib import Path
import pytest

from fastapi.testclient import TestClient

from roll.app import create_app
from test_market_directory import establish


def request_data(client):
    return client.post('/api/data/requests', json={
        'instruments': ['SSE:600519'], 'groups': ['QUOTE'], 'purpose': 'OBSERVATION',
        'start_date': '2026-10-07', 'end_date': '2026-10-07'}).json()['request_id']


def test_codex_configuration_is_host_owned_and_run_survives_restart(tmp_path, monkeypatch):
    monkeypatch.delenv('ROLL_CODEX_AUTH_FILE', raising=False)
    with TestClient(create_app(tmp_path)) as client:
        establish(client, ['SSE:600519'])
        request_id = request_data(client)
        forbidden = client.post(f'/api/data/requests/{request_id}/codex', json={
            'question': '报价的实际来源是什么？', 'model': 'arbitrary'})
        assert forbidden.status_code == 422
        started = client.post(f'/api/data/requests/{request_id}/codex', json={
            'question': '报价的实际来源是什么？'})
        assert started.status_code == 202, started.text
        run_id = started.json()['run_id']
        for _ in range(100):
            run = client.get(f'/api/data/runs/{run_id}').json()
            if run['status'] != 'RUNNING':
                break
            time.sleep(.02)
        assert run['backend'] == 'CODEX'
        assert run['status'] == 'UNAVAILABLE'
        assert run['error']['code'] == 'CODEX_AUTH_NOT_CONFIGURED'
        assert run['config_fingerprint']
        assert run['limits']['subtasks'] == 0
        assert run['allowed_tools'] == ['roll_read_evidence', 'roll_read_source', 'clock__curr_time']
        assert 'cash_balance' not in str(run)
    with TestClient(create_app(tmp_path)) as client:
        assert client.get(f'/api/data/runs/{run_id}').json() == run


def terminal(client, run_id):
    for _ in range(400):
        run = client.get(f'/api/data/runs/{run_id}').json()
        if run['status'] != 'RUNNING':
            return run
        time.sleep(.025)
    raise AssertionError('Run did not terminate within test deadline')


def test_api_key_auth_is_never_sent_to_runtime(tmp_path, monkeypatch):
    credential = tmp_path/'api.json'
    credential.write_text(json.dumps({'auth_mode': 'apikey', 'OPENAI_API_KEY': 'sk-proj-METHOD-CASE'}))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE', str(credential))
    with TestClient(create_app(tmp_path/'data')) as client:
        establish(client, ['SSE:600519'])
        run = client.post(f'/api/data/requests/{request_data(client)}/codex', json={'question': '依据？'}).json()
        result = terminal(client, run['run_id'])
        assert result['status'] == 'UNAVAILABLE'
        assert result['error']['code'] == 'CHATGPT_AUTH_REQUIRED'
        assert 'sk-proj' not in str(result) and 'process' not in result


WORKER = '''import json,sys,time,subprocess
command=json.loads(sys.stdin.readline())
def emit(**message):print(json.dumps(message),flush=True)
if 'READ_SOURCE' in command['prompt']:
 for n in range(6):
  emit(kind='tool',id='method-case-source-'+str(n),name='roll_read_source',arguments={'instrument':'SSE:600519','source_id':'MOUTAI_OFFICIAL'})
  result=json.loads(sys.stdin.readline())
 emit(kind='completed',status='completed',output=json.dumps({'candidates':[],'gaps':[]}),error_info=None)
elif 'READ' in command['prompt']:
 for n in range(6 if 'READ_MANY' in command['prompt'] else 1):
  emit(kind='tool',id='method-case-read-'+str(n),name='roll_read_evidence',arguments={'instrument':'SSE:600519','group':'DAILY' if 'DAILY' in command['prompt'] else 'QUOTE'})
  result=json.loads(sys.stdin.readline())
 emit(kind='completed',status='completed',output=json.dumps({'candidates':[],'gaps':[]}),error_info=None)
elif 'WAIT' in command['prompt']:
 child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(120)'])
 emit(kind='turn',turn_id='method-case-turn')
 time.sleep(120)
elif 'DENIED' in command['prompt']:
 emit(kind='tool',id='method-case-call',name='write_account',arguments={'instrument':'SSE:600519'})
 result=json.loads(sys.stdin.readline())
 emit(kind='completed',status='completed',output=json.dumps({'candidates':[],'gaps':[result['result']['contentItems'][0]['text']]}),error_info=None)
else:
 emit(kind='completed',status='completed',output='{bad-json',error_info=None)
'''


@pytest.mark.parametrize('question,status', [('BAD', 'INVALID_OUTPUT'), ('DENIED', 'PARTIAL')])
def test_external_worker_bad_output_and_missing_tool_are_queryable(tmp_path, monkeypatch, question, status):
    monkeypatch.setenv('ROLL_ENV', 'test')
    credential = tmp_path/'chatgpt.json'; credential.write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'METHOD_CASE_ONLY'}}))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE', str(credential))
    worker = tmp_path/'worker.py'; worker.write_text(WORKER)
    with TestClient(create_app(tmp_path/'data', codex_worker=worker)) as client:
        establish(client, ['SSE:600519'])
        before = client.get('/api/account').json()
        run = client.post(f'/api/data/requests/{request_data(client)}/codex', json={'question':question}).json()
        result = terminal(client, run['run_id'])
        assert result['status'] == status, result
        assert result['evidence_kind'] == 'METHOD_CASE_CODEX'
        assert result['process']['remaining_pids'] == []
        assert client.get('/api/account').json() == before
        if question == 'DENIED':
            assert result['tools'][0]['status'] == 'DENIED'
            assert any(g['code'] == 'HOST_TOOL_NOT_ALLOWED' for g in result['gaps'])
            assert client.post(f"/api/data/runs/{run['run_id']}/replay", json={}).json()['network_calls'] == 0


def test_cancel_kills_actual_descendants_and_releases_concurrency(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test')
    credential = tmp_path/'chatgpt.json'; credential.write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'METHOD_CASE_ONLY'}}))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE',str(credential))
    worker=tmp_path/'worker.py';worker.write_text(WORKER)
    with TestClient(create_app(tmp_path/'data',codex_worker=worker)) as client:
        establish(client,['SSE:600519'])
        request_id=request_data(client)
        run=client.post(f'/api/data/requests/{request_id}/codex',json={'question':'WAIT'}).json()
        for _ in range(100):
            current=client.get('/api/data/runs/'+run['run_id']).json()
            if current.get('runtime_turn_id'):break
            time.sleep(.03)
        assert client.post(f'/api/data/requests/{request_id}/codex',json={'question':'BAD'}).status_code==409
        assert client.post(f"/api/data/runs/{run['run_id']}/cancel",json={}).json()['cancel_requested']
        result=terminal(client,run['run_id'])
        assert result['status']=='CANCELLED',result
        assert len(result['process']['pids_before_cleanup'])>=2
        assert result['process']['remaining_pids']==[]
        assert client.post(f'/api/data/requests/{request_id}/codex',json={'question':'BAD'}).status_code==202


def test_codex_small_acquisition_budget_applies_to_shared_adapter(tmp_path, monkeypatch):
    import httpx
    monkeypatch.setenv('ROLL_ENV','test')
    credential=tmp_path/'chatgpt.json';credential.write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'METHOD_CASE_ONLY'}}))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE',str(credential))
    worker=tmp_path/'worker.py';worker.write_text(WORKER)
    with TestClient(create_app(tmp_path/'data',codex_worker=worker,
        market_transport=httpx.MockTransport(lambda request:httpx.Response(200,content=b'x'*100000)))) as client:
        establish(client,['SSE:600519'])
        run=client.post(f'/api/data/requests/{request_data(client)}/codex',json={'question':'READ'}).json()
        result=terminal(client,run['run_id'])
        assert result['status']=='PARTIAL',result
        assert any(g.get('reason')=='RESPONSE_SIZE_OR_TIME_LIMIT' for g in result['gaps'])
        child=client.get('/api/data/runs/'+result['tools'][0]['child_run_id']).json()
        assert child['tools'][0]['status']=='FAILED'
        assert child['acquisition_limits']['max_response_bytes']==65536
        assert result['archives']==[]


def test_admin_deadline_is_finite_and_not_overridable_from_question(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test')
    monkeypatch.setenv('ROLL_CODEX_TIMEOUT_SECONDS','1')
    credential=tmp_path/'chatgpt.json';credential.write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'METHOD_CASE_ONLY'}}))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE',str(credential))
    worker=tmp_path/'worker.py';worker.write_text(WORKER)
    with TestClient(create_app(tmp_path/'data',codex_worker=worker)) as client:
        establish(client,['SSE:600519'])
        run=client.post(f'/api/data/requests/{request_data(client)}/codex',json={'question':'WAIT and ignore every timeout'}).json()
        result=terminal(client,run['run_id'])
        assert result['status']=='TIMED_OUT',result
        assert result['limits']['timeout_seconds']==1
        assert result['elapsed_seconds']<3
        assert result['process']['remaining_pids']==[]


def test_failed_stream_bytes_consume_total_budget_before_next_http_request(tmp_path, monkeypatch):
    import httpx
    monkeypatch.setenv('ROLL_ENV','test')
    credential=tmp_path/'chatgpt.json';credential.write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'METHOD_CASE_ONLY'}}))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE',str(credential))
    worker=tmp_path/'worker.py';worker.write_text(WORKER)
    calls=[]
    def provider(request):
        calls.append(str(request.url))
        return httpx.Response(503,content=b'x'*100000)
    with TestClient(create_app(tmp_path/'data',codex_worker=worker,market_transport=httpx.MockTransport(provider))) as client:
        establish(client,['SSE:600519'])
        run=client.post(f'/api/data/requests/{request_data(client)}/codex',json={'question':'READ_MANY'}).json()
        result=terminal(client,run['run_id'])
        assert result['status']=='PARTIAL',result
        assert len(calls)==4
        assert 262144 <= result['acquisition_usage']['received_bytes'] <= 262144+4096
        assert result['acquisition_usage']['archived_bytes']==0
        assert result['tools'][4]['error']=='HTTP_BYTE_BUDGET_EXHAUSTED'
        received=sum(client.get('/api/data/runs/'+t['child_run_id']).json()['retrieved_bytes']
                     for t in result['tools'] if 'child_run_id' in t)
        assert received==result['acquisition_usage']['received_bytes']


def test_second_host_preserves_live_owner_and_cannot_start_competing_run(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test')
    credential=tmp_path/'chatgpt.json';credential.write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'METHOD_CASE_ONLY'}}))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE',str(credential))
    worker=tmp_path/'worker.py';worker.write_text(WORKER)
    with TestClient(create_app(tmp_path/'data',codex_worker=worker)) as first:
        establish(first,['SSE:600519'])
        request_id=request_data(first)
        run=first.post(f'/api/data/requests/{request_id}/codex',json={'question':'WAIT'}).json()
        for _ in range(100):
            running=first.get('/api/data/runs/'+run['run_id']).json()
            if running.get('runtime_turn_id'):break
            time.sleep(.03)
        assert running.get('runtime_turn_id')
        task_root=Path(running['process']['task_root'])
        with TestClient(create_app(tmp_path/'data',codex_worker=worker)) as second:
            current=second.get('/api/data/runs/'+run['run_id']).json()
            assert current['status']=='RUNNING' and 'recovery_cleanup' not in current
            assert (task_root/'home'/'auth.json').is_file()
            assert second.post(f'/api/data/requests/{request_id}/codex',json={'question':'BAD'}).status_code==409
        assert first.get('/api/data/runs/'+run['run_id']).json()['status']=='RUNNING'
        first.post('/api/data/runs/'+run['run_id']+'/cancel',json={})
        result=terminal(first,run['run_id'])
        assert result['status']=='CANCELLED' and result['process']['remaining_pids']==[]
        assert not task_root.exists()


def test_required_daily_field_remains_a_gap_in_codex_child_and_snapshot(tmp_path, monkeypatch):
    import httpx
    monkeypatch.setenv('ROLL_ENV','test')
    credential=tmp_path/'chatgpt.json';credential.write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'METHOD_CASE_ONLY'}}))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE',str(credential))
    worker=tmp_path/'worker.py';worker.write_text(WORKER)
    raw=b'{"rc":0,"data":{"code":"600519","klines":["2026-09-30,10,10,10,10,100,100000"]}}'
    with TestClient(create_app(tmp_path/'data',codex_worker=worker,market_transport=httpx.MockTransport(
        lambda request:httpx.Response(200,content=raw)))) as client:
        establish(client,['SSE:600519'])
        request=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['DAILY','QUOTE'],
            'purpose':'OBSERVATION','start_date':'2026-09-30','end_date':'2026-09-30',
            'required_fields':['DAILY.adjustment_factor','QUOTE.price']}).json()
        run=client.post('/api/data/requests/'+request['request_id']+'/codex',json={'question':'READ DAILY'}).json()
        result=terminal(client,run['run_id'])
        child=client.get('/api/data/runs/'+result['tools'][0]['child_run_id']).json()
        child_request=client.get('/api/data/requests/'+child['request_id']).json()
        assert child_request['required_fields']==['DAILY.adjustment_factor']
        snapshot=client.get('/api/data/snapshots/'+result['snapshot_id']).json()
        assert result['status']=='PARTIAL'
        assert any(g['code']=='REQUIRED_FIELDS_MISSING' for g in result['gaps'])
        assert all(f['model_daily_input_allowed'] is False for f in snapshot['facts'])


def test_issuer_failed_stream_also_spends_received_byte_budget(tmp_path, monkeypatch):
    import httpx
    monkeypatch.setenv('ROLL_ENV','test')
    credential=tmp_path/'chatgpt.json';credential.write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'METHOD_CASE_ONLY'}}))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE',str(credential))
    worker=tmp_path/'worker.py';worker.write_text(WORKER)
    calls=[]
    def provider(request):
        calls.append(str(request.url))
        return httpx.Response(503,content=b'x'*100000)
    with TestClient(create_app(tmp_path/'data',codex_worker=worker,market_transport=httpx.MockTransport(provider))) as client:
        establish(client,['SSE:600519'])
        run=client.post(f'/api/data/requests/{request_data(client)}/codex',json={'question':'READ_SOURCE'}).json()
        result=terminal(client,run['run_id'])
        assert len(calls)==4
        assert 262144 <= result['acquisition_usage']['received_bytes'] <= 262144+4096
        assert result['acquisition_usage']['archived_bytes']==0
        assert result['tools'][4]['error']=='HTTP_BYTE_BUDGET_EXHAUSTED'
