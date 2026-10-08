import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app
from test_market_directory import establish


def test_baostock_raw_status_are_archived_and_offline_replayed(tmp_path, monkeypatch):
    monkeypatch.setenv('BAOSTOCK_API_KEY','METHOD_CREDENTIAL')
    worker=tmp_path/'source.py'
    worker.write_text('import sys,json,base64\nc=json.load(sys.stdin)\nprint(json.dumps({"error_code":"0","calls":3,"received_bytes":10,"wire_b64":base64.b64encode(b"source-wire").decode(),"received_at":"2026-10-09T00:00:00+00:00","fields":["date","code","open","high","low","close","preclose","volume","amount","adjustflag","tradestatus","isST"],"rows":[["2026-09-30","sh.600519","10.0000","12.0000","9.0000","11.0000","10.0000","1000","11000.0000","3","1","0"]]}))',encoding='utf-8')
    with TestClient(create_app(tmp_path/'data',baostock_worker=worker)) as client:
        establish(client,['SSE:600519'])
        req=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['DAILY','STATUS'], 'purpose':'RESEARCH','start_date':'2026-09-30','end_date':'2026-09-30','daily_source':'BAOSTOCK','status_source':'BAOSTOCK'})
        assert req.status_code==201,req.text
        run=client.post('/api/data/requests/'+req.json()['request_id']+'/retrieve').json()
        assert run['status']=='COMPLETE',run
        snap=client.get('/api/data/snapshots/'+run['snapshot_id']).json()
        bar=next(f for f in snap['facts'] if f['group']=='DAILY')
        assert (bar['close'],bar['volume_shares'],bar['amount_yuan'])==('11.0000','1000','11000.0000')
        state=next(f for f in snap['facts'] if f['group']=='STATUS')
        assert state['state']=='NORMAL_REPORTED' and state['reported_tradestatus']=='1' and state['reported_is_st']=='0'
        assert state['listing_stage']=='UNKNOWN' and not state['historical_complete_status_verified']
        assert bar['historical_limitations'] and not bar['point_in_time_input_allowed']
        raw=next(a for a in snap['archives'] if a['kind']=='RAW_SOCKET_RESPONSE')
        assert client.get('/api/data/archives/'+raw['sha256']).content==b'source-wire'
        replay=client.post('/api/data/runs/'+run['run_id']+'/replay').json()
        assert replay['facts']==snap['facts'] and replay['network_calls']==0
        assert 'METHOD_CREDENTIAL' not in json.dumps(snap)

def test_baostock_reflected_secret_in_compressed_query_is_rejected_before_archive(tmp_path,monkeypatch):
    import base64,zlib
    monkeypatch.setenv('BAOSTOCK_API_KEY','METHOD_CREDENTIAL')
    worker=tmp_path/'source.py'
    worker.write_text('import json,sys\njson.load(sys.stdin)\nprint('+repr(json.dumps({'error_code':'0','calls':2,'received_bytes':40,'wire_b64':base64.b64encode(b'00.9.40\x0196\x010000000040'+zlib.compress(b'0\x01METHOD_CREDENTIAL\x01success')+b'<![CDATA[]]>\n').decode(),'received_at':'2026-10-09T00:00:00+00:00','fields':[],'rows':[]}))+')',encoding='utf-8')
    with TestClient(create_app(tmp_path/'data',baostock_worker=worker)) as client:
        establish(client,['SSE:600519'])
        req=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['DAILY'],'purpose':'RESEARCH','start_date':'2026-09-30','end_date':'2026-09-30','daily_source':'BAOSTOCK'}).json()
        run=client.post('/api/data/requests/'+req['request_id']+'/retrieve').json()
        assert any(g.get('reason')=='BAOSTOCK_SECRET_REFLECTED_RESPONSE_REJECTED' for g in run['gaps']),run
        snap=client.get('/api/data/snapshots/'+run['snapshot_id']).json()
        assert snap['archives']==[] and snap['facts']==[]

def test_baostock_rejects_impossible_action_date_order_without_account_changes(tmp_path,monkeypatch):
    monkeypatch.setenv('BAOSTOCK_API_KEY','METHOD_CREDENTIAL')
    worker=tmp_path/'source.py'
    worker.write_text('import json,sys,base64\njson.load(sys.stdin)\nprint(json.dumps({"error_code":"0","calls":2,"received_bytes":4,"wire_b64":base64.b64encode(b"wire").decode(),"received_at":"2026-10-09T00:00:00+00:00","fields":["code","dividPlanDate","dividRegistDate","dividOperateDate","dividPayDate","dividCashPsBeforeTax"],"rows":[["sh.600519","2026-09-20","2026-09-30","2026-09-29","2026-09-29","0.7"]]}))',encoding='utf-8')
    with TestClient(create_app(tmp_path/'data',baostock_worker=worker)) as client:
        establish(client,['SSE:600519'])
        before=client.get('/api/account').json()
        req=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['ADJUSTMENTS'],'purpose':'RESEARCH','start_date':'2026-09-01','end_date':'2026-09-30','adjustment_source':'BAOSTOCK'}).json()
        run=client.post('/api/data/requests/'+req['request_id']+'/retrieve').json()
        assert any(g.get('reason')=='BAOSTOCK_ACTION_DATE_ORDER_INVALID' for g in run['gaps']),run
        assert client.get('/api/data/snapshots/'+run['snapshot_id']).json()['facts']==[]
        assert client.get('/api/account').json()==before

def test_baostock_public_mode_is_explicit_and_child_receives_no_api_key(tmp_path,monkeypatch):
    monkeypatch.setenv('BAOSTOCK_API_KEY','METHOD_CREDENTIAL')
    worker=tmp_path/'public.py'
    worker.write_text('import sys,json,os,base64\nc=json.load(sys.stdin)\nassert c["auth_mode"]=="PUBLIC" and "BAOSTOCK_API_KEY" not in os.environ\nprint(json.dumps({"error_code":"0","calls":2,"received_bytes":4,"wire_b64":base64.b64encode(b"wire").decode(),"received_at":"2026-10-09T00:00:00+00:00","fields":["calendar_date","is_trading_day"],"rows":[["2026-09-30","1"]]}))',encoding='utf-8')
    with TestClient(create_app(tmp_path/'data',baostock_worker=worker)) as client:
        establish(client,['SSE:600519'])
        req=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['CALENDAR'],'purpose':'RESEARCH','start_date':'2026-09-30','end_date':'2026-09-30','baostock_auth_mode':'PUBLIC'})
        assert req.status_code==201,req.text
        assert req.json()['baostock_auth_mode']=='PUBLIC'
        run=client.post('/api/data/requests/'+req.json()['request_id']+'/retrieve').json()
        assert run['status']=='COMPLETE',run
        snap=client.get('/api/data/snapshots/'+run['snapshot_id']).json()
        fact=snap['facts'][0]
        assert fact['is_trading_day'] is True and fact['official_exchange_calendar_verified'] is False
        assert fact['source_url']=='tcp://public-api.baostock.com:10030'
        assert all(a['auth_mode']=='PUBLIC' for a in snap['archives'])

def test_baostock_two_compressed_frames_share_one_decoded_budget(tmp_path):
    import base64,zlib
    wire=b''.join(b'00.9.40\x0196\x010000000020'+zlib.compress(b'x'*40)+b'<![CDATA[]]>\n' for _ in range(2))
    worker=tmp_path/'frames.py'
    worker.write_text('import json,sys\njson.load(sys.stdin)\nprint('+repr(json.dumps({'error_code':'0','calls':2,'received_bytes':len(wire),'wire_b64':base64.b64encode(wire).decode(),'received_at':'2026-10-09T00:00:00+00:00','fields':[],'rows':[]}))+')',encoding='utf-8')
    with TestClient(create_app(tmp_path/'data',baostock_worker=worker)) as client:
        establish(client,['SSE:600519'])
        req=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['CALENDAR'],'purpose':'RESEARCH','start_date':'2026-09-30','end_date':'2026-09-30','baostock_auth_mode':'PUBLIC','max_decoded_bytes':64})
        assert req.status_code==201,req.text
        run=client.post('/api/data/requests/'+req.json()['request_id']+'/retrieve').json()
        assert any(g.get('reason')=='BAOSTOCK_DECODED_BYTE_LIMIT' for g in run['gaps']),run
        assert client.get('/api/data/snapshots/'+run['snapshot_id']).json()['archives']==[]

def production_sdk_worker(tmp_path,query_body,external_setup=""):
    worker=tmp_path/'sdk_boundary.py'
    implementation=Path(__file__).resolve().parents[2]/'src/roll/market/baostock_process.py'
    worker.write_text('import sys,types,runpy,zlib,socket\n'+external_setup+
        'sdk=types.ModuleType("baostock");common=types.ModuleType("baostock.common")\n'
        'context=types.ModuleType("baostock.common.context");context.default_socket=types.SimpleNamespace(close=lambda:None)\n'
        'constants=types.ModuleType("baostock.common.contants");constants.BAOSTOCK_CLIENT_VERSION="00.9.40"\n'
        'sdk.login=lambda:types.SimpleNamespace(error_code="0")\n'
        'def query(*args,**kwargs):\n'+''.join('    '+line+'\n' for line in query_body.splitlines())+
        'sdk.query_trade_dates=query\n'
        'sys.modules.update({"baostock":sdk,"baostock.common":common,"baostock.common.context":context,"baostock.common.contants":constants})\n'
        'runpy.run_path('+repr(str(implementation))+',run_name="__main__")',encoding='utf-8')
    return worker


def test_baostock_production_sdk_decoder_accumulates_across_pages(tmp_path):
    worker=production_sdk_worker(tmp_path,'zlib.decompress(zlib.compress(b"x"*40))\nzlib.decompress(zlib.compress(b"y"*40))\nreturn types.SimpleNamespace(error_code="0",fields=[],next=lambda:False)')
    with TestClient(create_app(tmp_path/'data',baostock_worker=worker)) as client:
        establish(client,['SSE:600519'])
        req=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['CALENDAR'],'purpose':'RESEARCH','start_date':'2026-09-30','end_date':'2026-09-30','baostock_auth_mode':'PUBLIC','max_decoded_bytes':64}).json()
        run=client.post('/api/data/requests/'+req['request_id']+'/retrieve').json()
        assert any(g.get('reason')=='BAOSTOCK_DECODED_BYTE_LIMIT' for g in run['gaps']),run
        assert client.get('/api/data/snapshots/'+run['snapshot_id']).json()['archives']==[]

def test_baostock_request_shares_decoded_budget_across_queries(tmp_path):
    import base64,zlib
    wire=b'00.9.40\x0196\x010000000020'+zlib.compress(b'x'*40)+b'<![CDATA[]]>\n'
    value={'error_code':'0','calls':2,'received_bytes':len(wire),'decoded_bytes':40,'wire_b64':base64.b64encode(wire).decode(),'received_at':'2026-10-09T00:00:00+00:00','fields':['calendar_date','is_trading_day'],'rows':[['2026-09-30','1']]}
    worker=tmp_path/'queries.py'
    worker.write_text('import json,sys\nc=json.load(sys.stdin)\nv='+repr(value)+'\nif c["group"]!="CALENDAR":v.update(fields=[],rows=[])\nprint(json.dumps(v))',encoding='utf-8')
    with TestClient(create_app(tmp_path/'data',baostock_worker=worker)) as client:
        establish(client,['SSE:600519'])
        req=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['CALENDAR','ADJUSTMENTS'],'purpose':'RESEARCH','start_date':'2026-09-01','end_date':'2026-09-30','adjustment_source':'BAOSTOCK','baostock_auth_mode':'PUBLIC','max_decoded_bytes':64,'max_total_decoded_bytes':64}).json()
        run=client.post('/api/data/requests/'+req['request_id']+'/retrieve').json()
        assert any(g.get('reason')=='BAOSTOCK_DECODED_BYTE_LIMIT' for g in run['gaps']),run
        assert run['retrieved_decoded_bytes']==40
        assert next(g for g in run['gaps'] if g.get('reason')=='BAOSTOCK_DECODED_BYTE_LIMIT')['failure_audit']['decoded_bytes']==25
        snap=client.get('/api/data/snapshots/'+run['snapshot_id']).json()
        assert len(snap['facts'])==1 and snap['facts'][0]['group']=='CALENDAR'
        assert all(a['decoded_bytes']==40 for a in snap['archives'])


@pytest.mark.parametrize('phase,kind',[('SDK_IMPORT','ModuleNotFoundError'),('ROW_ITERATION','TypeError')])
def test_baostock_unknown_failure_retains_safe_location_without_values(tmp_path,monkeypatch,phase,kind):
    monkeypatch.setenv('BAOSTOCK_API_KEY','METHOD_CREDENTIAL')
    if phase=='ROW_ITERATION':
        worker=production_sdk_worker(tmp_path,'return types.SimpleNamespace(error_code="0",fields=[],next=lambda:(_ for _ in ()).throw(TypeError("METHOD_CREDENTIAL")))')
    else:
        worker=tmp_path/'sdk_import_failure.py'
        implementation=Path(__file__).resolve().parents[2]/'src/roll/market/baostock_process.py'
        worker.write_text('import runpy,builtins\noriginal=builtins.__import__\ndef importing(name,*args,**kwargs):\n    if name=="baostock":raise ModuleNotFoundError("METHOD_CREDENTIAL")\n    return original(name,*args,**kwargs)\nbuiltins.__import__=importing\nrunpy.run_path('+repr(str(implementation))+',run_name="__main__")',encoding='utf-8')
    with TestClient(create_app(tmp_path/'data',baostock_worker=worker)) as client:
        establish(client,['SSE:600519'])
        req=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['CALENDAR'],'purpose':'RESEARCH','start_date':'2026-09-30','end_date':'2026-09-30','baostock_auth_mode':'PUBLIC'}).json()
        run=client.post('/api/data/requests/'+req['request_id']+'/retrieve').json()
        gap=next(g for g in run['gaps'] if g['code']=='BAOSTOCK_ACQUISITION_FAILED')
        assert gap['reason']=='BAOSTOCK_PROCESS_OR_TRANSPORT_FAILURE'
        assert gap['diagnostic']['phase']==phase and gap['diagnostic']['exception_type']==kind
        assert gap['diagnostic']['line']>0 and '/' not in gap['diagnostic']['file'] and '\\' not in gap['diagnostic']['file']
        assert 'METHOD_CREDENTIAL' not in json.dumps(run)
        assert client.get('/api/data/snapshots/'+run['snapshot_id']).json()['archives']==[]

def test_baostock_unserializable_sdk_row_shape_has_safe_diagnostic(tmp_path):
    worker=production_sdk_worker(tmp_path,'return types.SimpleNamespace(error_code="0",fields=[object()],next=lambda:False)')
    with TestClient(create_app(tmp_path/'data',baostock_worker=worker)) as client:
        establish(client,['SSE:600519'])
        req=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['CALENDAR'],'purpose':'RESEARCH','start_date':'2026-09-30','end_date':'2026-09-30','baostock_auth_mode':'PUBLIC'}).json()
        run=client.post('/api/data/requests/'+req['request_id']+'/retrieve').json()
        gap=next(g for g in run['gaps'] if g['code']=='BAOSTOCK_ACQUISITION_FAILED')
        assert gap['reason']=='BAOSTOCK_PROCESS_OR_TRANSPORT_FAILURE',run
        assert gap['diagnostic']['phase']=='RESULT_ENCODING' and gap['diagnostic']['exception_type']=='TypeError'

def test_baostock_production_worker_archives_received_compressed_socket_frame(tmp_path):
    import socket,threading,zlib
    frame=b'00.9.40\x0196\x010000000020'+zlib.compress(b'x'*40)+b'<![CDATA[]]>\n'
    with socket.socket() as server:
        server.bind(('127.0.0.1',0));server.listen(1);server.settimeout(10)
        port=server.getsockname()[1]
        def provide():
            with server.accept()[0] as connection:
                connection.recv(4096)
                connection.sendall(frame)
        thread=threading.Thread(target=provide,daemon=True);thread.start()
        setup='native_socket=socket.socket\nclass SourceSocket(native_socket):\n    def connect(self,address):return super().connect(("127.0.0.1",'+str(port)+'))\nsocket.socket=SourceSocket\n'
        query='transport=socket.socket()\ntransport.connect(("public-api.baostock.com",10030))\ntransport.send(b"query")\nwire=b""\nwhile not wire.endswith(b"<![CDATA[]]>\\n"):wire+=transport.recv(8192)\nzlib.decompress(wire[21:-13])\ntransport.close()\nready=iter([True,False])\nreturn types.SimpleNamespace(error_code="0",fields=["calendar_date","is_trading_day"],next=lambda:next(ready),get_row_data=lambda:["2026-09-30","1"])'
        worker=production_sdk_worker(tmp_path,query,setup)
        with TestClient(create_app(tmp_path/'data',baostock_worker=worker)) as client:
            establish(client,['SSE:600519'])
            req=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['CALENDAR'],'purpose':'RESEARCH','start_date':'2026-09-30','end_date':'2026-09-30','baostock_auth_mode':'PUBLIC'}).json()
            run=client.post('/api/data/requests/'+req['request_id']+'/retrieve').json()
            assert run['status']=='COMPLETE',run
            assert run['retrieved_decoded_bytes']==40
            snap=client.get('/api/data/snapshots/'+run['snapshot_id']).json()
            raw=next(a for a in snap['archives'] if a['kind']=='RAW_SOCKET_RESPONSE')
            assert client.get('/api/data/archives/'+raw['sha256']).content==frame
            assert raw['decoded_bytes']==40 and snap['facts'][0]['is_trading_day'] is True
        thread.join(timeout=5)
