import json
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
