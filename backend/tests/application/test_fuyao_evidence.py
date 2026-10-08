import hashlib
import json
from datetime import datetime, timezone, timedelta
import httpx
import pytest
from fastapi.testclient import TestClient
from roll.app import create_app
from test_market_directory import establish
from test_source_resolution import completed


def millis(day):
    return int(datetime.fromisoformat(day).replace(tzinfo=timezone(timedelta(hours=8))).timestamp()*1000)


def test_fuyao_real_contract_daily_preserves_units_raw_adjustment_and_replay(tmp_path, monkeypatch):
    monkeypatch.setenv('FUYAO_API_KEY', 'METHOD_SECRET_NOT_REAL')
    calls=[]
    def provider(request):
        assert request.url.host=='fuyao.aicubes.cn'
        assert request.headers['X-api-key']=='METHOD_SECRET_NOT_REAL'
        calls.append(str(request.url))
        return httpx.Response(200,json={'code':0,'data':{'thscode':'600519.SH','interval':'1d',
            'adjust':request.url.params['adjust'],'timestamp':millis('2026-09-30T15:00:00'),
            'item':[{'date_ms':millis('2026-09-30'),'open_price':'10','high_price':'12','low_price':'9',
                'close_price':'11','volume':1000,'turnover':11000}]}})
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        establish(client,['SSE:600519'])
        command={'instruments':['SSE:600519'],'groups':['DAILY'],'purpose':'OBSERVATION',
            'start_date':'2026-09-30','end_date':'2026-09-30','daily_source':'FUYAO'}
        request=client.post('/api/data/requests',json=command)
        assert request.status_code==201,request.text
        run=client.post('/api/data/requests/'+request.json()['request_id']+'/retrieve').json()
        assert run['status']=='COMPLETE',run
        snapshot=client.get('/api/data/snapshots/'+run['snapshot_id']).json()
        raw=next(f for f in snapshot['facts'] if f['adjustment']=='RAW')
        assert raw['volume_shares']=='1000' and raw['amount_yuan']=='11000'
        assert raw['volume_unit']=='SHARE' and raw['source_volume_unit']=='SHARE'
        assert raw['model_daily_input_allowed'] is True
        assert raw['historical_limitations'] and not raw['point_in_time_input_allowed']
        assert {f['adjustment'] for f in snapshot['facts']}=={'RAW','FORWARD_CURRENT_VERSION'}
        assert len(calls)==2
        replay=client.post('/api/data/runs/'+run['run_id']+'/replay').json()
        assert replay['network_calls']==0 and len(calls)==2
        assert 'METHOD_SECRET_NOT_REAL' not in json.dumps(run)
        for archive in snapshot['archives']:
            data=client.get('/api/data/archives/'+archive['sha256']).content
            assert hashlib.sha256(data).hexdigest()==archive['sha256']
            assert b'METHOD_SECRET_NOT_REAL' not in data


def test_fuyao_corporate_action_retains_date_only_and_unproven_coverage(tmp_path,monkeypatch):
    monkeypatch.setenv('FUYAO_API_KEY','METHOD_SECRET_NOT_REAL')
    calls=[]
    def provider(request):
        assert request.url.path=='/api/a-share/corporate-actions/adjustment-factors'
        calls.append(str(request.url))
        return httpx.Response(200,json={'code':0,'data':{'thscode':'600519.SH','ticker':'600519',
            'item':[{'ticker':'600519','ex_date_ms':millis('2026-06-26'),'dividend_per_share':'28.02423','per_share_bonus':0}]}})
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        establish(client,['SSE:600519'])
        request=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['ADJUSTMENTS'],
            'purpose':'RESEARCH','start_date':'2026-01-01','end_date':'2026-09-30','adjustment_source':'FUYAO'})
        assert request.status_code==201,request.text
        run=client.post('/api/data/requests/'+request.json()['request_id']+'/retrieve').json()
        assert run['status']=='COMPLETE',run
        snapshot=client.get('/api/data/snapshots/'+run['snapshot_id']).json()
        fact=snapshot['facts'][0]
        assert fact['cash_per_share']=='28.02423' and fact['ex_date']=='2026-06-26'
        assert fact['published_at'] is None and fact['disclosure_date'] is None
        assert fact['time_precision']=='DATE' and not fact['point_in_time_input_allowed']
        assert fact['historical_complete_actions_verified'] is False
        observation=next(o for o in snapshot['observations'] if o['kind']=='PENDING_ACCOUNT_RECONCILIATION')
        assert observation['event_date']=='2026-06-26' and '原始除权事项' in observation['message']
        assert len(calls)==1 and len(client.get('/api/account').json()['positions'])==1


def test_fuyao_quote_never_turns_batch_latest_time_into_security_freshness(tmp_path,monkeypatch):
    monkeypatch.setenv('FUYAO_API_KEY','METHOD_SECRET_NOT_REAL')
    def provider(request):
        return httpx.Response(200,json={'code':0,'data':{'timestamp':millis('2026-09-30T15:01:00'),'total':1,
            'item':[{'thscode':'600519.SH','ticker':'600519','last_price':11,'volume':1000,'turnover':11000}]}})
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        establish(client,['SSE:600519'])
        request=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['QUOTE','STATUS'],
            'purpose':'OBSERVATION','start_date':'2026-09-30','end_date':'2026-09-30','quote_source':'FUYAO'})
        assert request.status_code==201,request.text
        run=client.post('/api/data/requests/'+request.json()['request_id']+'/retrieve').json()
        assert run['status']=='PARTIAL',run
        facts=client.get('/api/data/snapshots/'+run['snapshot_id']).json()['facts']
        quote=next(f for f in facts if f['group']=='QUOTE')
        assert quote['last']=='11' and quote['volume_shares']=='1000'
        assert quote['upstream_at'] is None and quote['trade_date'] is None and quote['age_seconds'] is None
        assert quote['source_snapshot_ready_at'] is not None
        assert not quote['current_monitoring_input_allowed']
        assert next(f for f in facts if f['group']=='STATUS')['state']=='UNKNOWN'
        assert {g['code'] for g in run['gaps']}=={'QUOTE_PER_INSTRUMENT_TIME_UNKNOWN','CURRENT_STATUS_UNKNOWN'}
        resolution=completed(client,client.post('/api/data/requests/'+request.json()['request_id']+'/resolve',
            json={'usage':'CURRENT_MONITORING','allow_fallback':False,'basis_run_id':run['run_id']}).json()['resolution_id'])
        assert resolution['status']=='COMPLETED',resolution
        assert resolution['capabilities']['current_monitoring']=='MONITORING_UNAVAILABLE'
        assert all(f['group']!='QUOTE' for f in resolution['facts'])
        basis=client.get('/api/account/valuation-basis').json()
        valuation=client.post('/api/account/valuations',json={k:basis[k] for k in ['baseline_account_version','origin_at','as_of','scope_kind','scope_id']})
        assert valuation.status_code==201,valuation.text
        assert valuation.json()['facts']['net_assets'] is None

        assert client.post('/api/data/runs/'+run['run_id']+'/replay').json()['network_calls']==0


@pytest.mark.parametrize('case,expected',[
    ('missing','FUYAO_CREDENTIAL_NOT_CONFIGURED'),('permission','FUYAO_BUSINESS_ERROR_2003'),
    ('rate','FUYAO_BUSINESS_ERROR_4001'),('echo','FUYAO_SECRET_REFLECTED_RESPONSE_REJECTED'),
    ('escaped_echo','FUYAO_SECRET_REFLECTED_RESPONSE_REJECTED'),('object','FUYAO_SOURCE_OBJECT_MISMATCH'),('badcode','FUYAO_BUSINESS_CODE_INVALID'),('boolcode','FUYAO_BUSINESS_CODE_INVALID')])
def test_fuyao_failure_is_bounded_audited_and_never_echoes_credentials(tmp_path,monkeypatch,case,expected):
    secret='METHOD_SECRET_NOT_REAL'
    if case=='missing':monkeypatch.delenv('FUYAO_API_KEY',raising=False)
    else:monkeypatch.setenv('FUYAO_API_KEY',secret)
    calls=[]
    def provider(request):
        calls.append(str(request.url))
        if case in {'permission','rate'}:return httpx.Response(200,json={'code':2003 if case=='permission' else 4001,'data':None})
        if case in {'badcode','boolcode'}:return httpx.Response(200,json={'code':'untrusted_provider_text' if case=='badcode' else False,'data':{'item':[]}})
        if case=='escaped_echo':return httpx.Response(200,content=b'{"code":2003,"message":"\\u004dETHOD_SECRET_NOT_REAL","data":null}')
        if case=='echo':return httpx.Response(200,json={'code':2003,'message':secret,'data':None})
        return httpx.Response(200,json={'code':0,'data':{'timestamp':millis('2026-09-30'),'item':[{'thscode':'000001.SZ','last_price':11}]}})
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        establish(client,['SSE:600519'])
        request=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['QUOTE'],
            'purpose':'OBSERVATION','start_date':'2026-09-30','end_date':'2026-09-30','quote_source':'FUYAO'}).json()
        run=client.post('/api/data/requests/'+request['request_id']+'/retrieve').json()
        assert run['status']=='FAILED' and len(calls)==(0 if case=='missing' else 1),run
        assert any(g.get('reason')==expected for g in run['gaps']),run
        assert secret not in json.dumps(run)
        snapshot=client.get('/api/data/snapshots/'+run['snapshot_id']).json()
        assert snapshot['facts']==[]
        if case in {'echo','escaped_echo','missing'}:assert snapshot['archives']==[]



def test_fuyao_index_does_not_compare_aggregate_turnover_with_index_points(tmp_path,monkeypatch):
    monkeypatch.setenv('FUYAO_API_KEY','METHOD_SECRET_NOT_REAL')
    def provider(request):
        assert 'adjust' not in request.url.params
        return httpx.Response(200,json={'code':0,'data':{'adjust':None,'item':[{'date_ms':millis('2026-09-30'),
            'open_price':3500,'close_price':3510,'high_price':3530,'low_price':3490,'volume':1000000,'turnover':15000000}]}})
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        request=client.post('/api/data/requests',json={'instruments':['SSE:000001'],'groups':['DAILY'],
            'purpose':'BACKGROUND','start_date':'2026-09-30','end_date':'2026-09-30','daily_source':'FUYAO'}).json()
        run=client.post('/api/data/requests/'+request['request_id']+'/retrieve').json()
        fact=client.get('/api/data/snapshots/'+run['snapshot_id']).json()['facts'][0]
        assert fact['errors']==[] and fact['close']=='3510'
        assert fact['model_daily_input_allowed'] is False
        assert 'INDEX_POINTS_NOT_SHARE_PRICE' in fact['limitations']


def test_fuyao_two_added_fixed_backgrounds_use_verified_sh_codes_and_archive(tmp_path,monkeypatch):
    monkeypatch.setenv('FUYAO_API_KEY','METHOD_SECRET_NOT_REAL')
    calls=[]
    def provider(request):
        assert request.url.path=='/api/a-share-index/prices/historical'
        assert 'adjust' not in request.url.params
        calls.append(request.url.params['thscode'])
        return httpx.Response(200,json={'code':0,'data':{'thscode':request.url.params['thscode'],
            'item':[{'date_ms':millis('2026-09-30'),'open_price':3500,'close_price':3510,
                'high_price':3530,'low_price':3490,'volume':1000000,'turnover':15000000}]}})
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        before=client.get('/api/account').json()
        response=client.post('/api/data/requests',json={'instruments':['SSE:000300','SSE:000905'],
            'groups':['DAILY'],'purpose':'BACKGROUND','start_date':'2026-09-30',
            'end_date':'2026-09-30','daily_source':'FUYAO'})
        assert response.status_code==201,response.text
        run=client.post('/api/data/requests/'+response.json()['request_id']+'/retrieve').json()
        assert run['status']=='COMPLETE' and calls==['000300.SH','000905.SH'],run
        snapshot=client.get('/api/data/snapshots/'+run['snapshot_id']).json()
        assert {f['instrument'] for f in snapshot['facts']}=={'SSE:000300','SSE:000905'}
        assert all(not f['model_daily_input_allowed'] for f in snapshot['facts'])
        replay=client.post('/api/data/runs/'+run['run_id']+'/replay').json()
        assert replay['facts']==snapshot['facts'] and replay['network_calls']==0 and len(calls)==2
        assert client.get('/api/account').json()==before
