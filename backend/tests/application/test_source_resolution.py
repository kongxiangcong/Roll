import hashlib
import time
from datetime import datetime, timezone

import httpx
from fastapi.testclient import TestClient

from roll.app import create_app
from test_market_directory import establish


def quote_bytes(price='1258.620', day='2026-09-30', symbol='sh600519'):
    fields=['贵州茅台','1239.530','1235.580',price,'1268.000','1236.050','1258.620','1258.650','3833098','4797246636.000']
    fields += ['0']*20 + [day,'15:34:59','00']
    return ('var hq_str_'+symbol+'="'+','.join(fields)+'";\n').encode('gbk')


def tencent_bytes():
    fields=['']*55
    for n,v in {0:'1',1:'贵州茅台',2:'600519',3:'1258.62',4:'1235.58',5:'1239.53',6:'38331',
        30:'20260930161458',33:'1268.00',34:'1236.05',35:'1258.62/38331/4797246636',47:'1359.14',48:'1112.02'}.items():fields[n]=v
    return ('v_sh600519="'+'~'.join(fields)+'";\n').encode('gbk')


def setup_request(client, **changes):
    establish(client,['SSE:600519'])
    client.post('/api/market/identities',json={'instrument':'SSE:600519','exchange':'SSE','board':'MAIN',
        'instrument_type':'STOCK','name':'贵州茅台','basis':'隔离合成身份核对','effective_at':'2026-10-07T00:00:00+08:00'})
    command={'instruments':['SSE:600519'],'groups':['QUOTE'],'purpose':'OBSERVATION',
        'start_date':'2026-09-30','end_date':'2026-09-30',**changes}
    response=client.post('/api/data/requests',json=command)
    assert response.status_code==201,response.text
    return response.json()


def test_sina_quote_uses_same_fact_contract_and_archived_supplier_unit_definition(tmp_path):
    calls=[]
    raw=quote_bytes()
    def provider(request):
        calls.append(request)
        return httpx.Response(200,content=raw)
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        request=setup_request(client,quote_source='SINA')
        run=client.post('/api/data/requests/'+request['request_id']+'/retrieve').json()
        fact=client.get('/api/data/snapshots/'+run['snapshot_id']).json()['facts'][0]
        assert fact['instrument']=='SSE:600519' and fact['source_id']=='sina-quote'
        assert fact['trade_date']=='2026-09-30' and fact['upstream_at']=='2026-09-30T15:34:59+08:00'
        assert fact['last']=='1258.620' and fact['amount_yuan']=='4797246636.000'
        assert fact['volume_shares']=='3833098' and fact['volume_unit']=='SHARE'
        assert fact['adjustment']=='RAW' and fact['currency']=='CNY'
        assert calls[0].url.host=='hq.sinajs.cn' and calls[0].headers['referer']=='https://finance.sina.com.cn/'
        assert client.get('/api/data/archives/'+fact['raw_hash']).content==raw
        assert hashlib.sha256(raw).hexdigest()==fact['raw_hash']
        before=len(calls)
        assert client.post('/api/data/runs/'+run['run_id']+'/replay').json()['facts']==[fact]
        assert len(calls)==before


def test_revised_price_invalidates_existing_observation_without_overwriting_original(tmp_path):
    close=['1000']
    def provider(request):
        mode=request.url.params['param'].split(',')[-1]
        return httpx.Response(200,json={'code':0,'data':{'sh600519':{('qfqday' if mode else 'day'):
            [['2026-09-29','1400','1400','1400','1400','100'],['2026-09-30',close[0],close[0],close[0],close[0],'100']]}}})
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        request=setup_request(client,groups=['DAILY'],daily_source='TENCENT',start_date='2026-09-29',required_fields=['DAILY.close'])
        first=completed(client,client.post('/api/data/requests/'+request['request_id']+'/resolve',
            json={'usage':'HISTORICAL_RESEARCH','allow_fallback':False}).json()['resolution_id'])
        observation=next(o for o in client.get('/api/data/observations').json() if o['kind']=='PRICE_MOVE_OBSERVATION')
        assert observation['dependency_status']=='CURRENT' and observation['event_date']=='2026-09-30'
        close[0]='1390'
        revised=completed(client,client.post('/api/data/requests/'+request['request_id']+'/resolve',
            json={'usage':'HISTORICAL_RESEARCH','allow_fallback':False,'use_cache':False,'revision_of':first['resolution_id']}).json()['resolution_id'])
        assert revised['revision']['changed_fact_keys']
        after=next(o for o in client.get('/api/data/observations').json() if o['observation_id']==observation['observation_id'])
        assert after['dependency_status']=='INVALIDATED' and after['observed_raw_return']==observation['observed_raw_return']
        replay=client.post('/api/data/resolutions/'+first['resolution_id']+'/replay').json()
        assert any(o['observation_id']==observation['observation_id'] and o['observed_raw_return']==observation['observed_raw_return'] for o in replay['observations'])
        assert replay['network_calls']==0


def completed(client, resolution_id):
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        response=client.get('/api/data/resolutions/'+resolution_id)
        assert response.status_code==200,response.text
        result=response.json()
        if result['status']!='RUNNING':return result
        time.sleep(.02)
    raise AssertionError('bounded resolution did not finish')


def test_reported_quote_outside_requested_window_remains_archived_but_cannot_satisfy_usage(tmp_path):
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,content=quote_bytes())))) as client:
        request=setup_request(client,quote_source='SINA',start_date='2026-09-29',end_date='2026-09-29')
        value=completed(client,client.post('/api/data/requests/'+request['request_id']+'/resolve',
            json={'usage':'HISTORICAL_RESEARCH','allow_fallback':False}).json()['resolution_id'])
        assert not value['facts']
        assert value['capabilities']['required_inputs']=='BLOCKED_NEW_RISK'
        assert any(g['code']=='REPORTED_SESSION_OUTSIDE_REQUEST' for g in value['gaps'])
        run=client.get('/api/data/runs/'+value['attempts'][0]['run_id']).json()
        assert client.get('/api/data/snapshots/'+run['snapshot_id']).json()['facts'][0]['trade_date']=='2026-09-30'


def test_declared_exchange_mismatch_is_archived_as_normalization_failure(tmp_path):
    raw=tencent_bytes().replace(b'v_sh600519',b'v_sz600519')
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,content=raw)))) as client:
        request=setup_request(client)
        run=client.post('/api/data/requests/'+request['request_id']+'/retrieve').json()
        assert any(g['code']=='NORMALIZATION_ERROR' and 'OBJECT' in g['reason'] for g in run['gaps'])
        assert client.get('/api/data/snapshots/'+run['snapshot_id']).json()['facts']==[]
        assert client.get('/api/data/archives/'+run['tools'][0]['raw_hash']).content==raw


def test_failed_primary_gets_bounded_alternate_and_preserves_same_daily_fact_format(tmp_path):
    def provider(request):
        if request.url.host=='push2his.eastmoney.com':return httpx.Response(503,content=b'fixed upstream unavailable')
        mode=request.url.params['param'].split(',')[-1]
        return httpx.Response(200,json={'code':0,'data':{'sh600519':{('qfqday' if mode else 'day'):
            [['2026-09-30','1239.53','1258.62','1268','1236.05','38331']]}}})
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        request=setup_request(client,groups=['DAILY'],required_fields=['DAILY.close'],max_calls=4)
        response=client.post('/api/data/requests/'+request['request_id']+'/resolve',json={'usage':'HISTORICAL_RESEARCH'})
        assert response.status_code==202,response.text
        result=completed(client,response.json()['resolution_id'])
        assert result['status']=='COMPLETED' and len(result['attempts'])==2,result
        assert {f['source_id'] for f in result['facts']}=={'tencent-daily'}
        assert {f['adjustment'] for f in result['facts']}=={'RAW','FORWARD_CURRENT_VERSION'}
        assert all(f['close']=='1258.62' and f['amount_yuan'] is None for f in result['facts'])
        assert result['attempts'][0]['role']=='PRIMARY' and result['attempts'][1]['role']=='ALTERNATE'
        primary=client.get('/api/data/runs/'+result['attempts'][0]['run_id']).json()
        assert primary['status']=='FAILED' and all(g['code']=='HTTPStatusError' for g in primary['gaps'])
        assert result['network_calls']==4 and result['state']=='DEGRADED'
        assert result['capabilities']['complete_daily_model']=='BLOCKED_NEW_RISK'
        assert result['model_qualification']=='NOT_GRANTED'
        assert any(c['decision']=='ACCEPTED' for c in result['source_checks'])


def test_cache_preserves_real_receipt_and_rechecks_own_knowledge_cutoff_and_session_usage(tmp_path):
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,content=quote_bytes())),
        market_clock=lambda:'2026-10-08T08:30:00+08:00')) as client:
        request=setup_request(client,quote_source='SINA',required_fields=['QUOTE.last'])
        first=completed(client,client.post('/api/data/requests/'+request['request_id']+'/resolve',
            json={'usage':'PRE_MARKET_RECORD'}).json()['resolution_id'])
        assert first['state']=='HEALTHY' and first['facts'][0]['point_in_time_input_allowed'] is False
        cached=completed(client,client.post('/api/data/requests/'+request['request_id']+'/resolve',
            json={'usage':'PRE_MARKET_RECORD'}).json()['resolution_id'])
        assert cached['network_calls']==0 and cached['cache']['reused_resolution_id']==first['resolution_id']
        assert cached['facts'][0]['received_at']==first['facts'][0]['received_at']
        assert cached['facts'][0]['available_at']==first['facts'][0]['available_at']
        assert cached['capabilities']['complete_daily_model']=='NOT_REQUESTED'
        assert cached['freshness'][0]['expected_session']=='2026-09-30'
        past=completed(client,client.post('/api/data/requests/'+request['request_id']+'/resolve',
            json={'usage':'HISTORICAL_RESEARCH','knowledge_cutoff':'2026-09-30T17:00:00+08:00'}).json()['resolution_id'])
        assert past['network_calls']==0 and past['facts']==[]
        assert any(g['code']=='NOT_AVAILABLE_AT_CONSUMER_CUTOFF' for g in past['gaps'])


def test_old_quote_blocks_current_monitoring_but_optional_status_gap_only_degrades_record(tmp_path):
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,content=quote_bytes())),
        market_clock=lambda:'2026-10-08T10:00:00+08:00')) as client:
        request=setup_request(client,quote_source='SINA',groups=['QUOTE','STATUS'])
        monitored=completed(client,client.post('/api/data/requests/'+request['request_id']+'/resolve',
            json={'usage':'CURRENT_MONITORING','allow_fallback':False}).json()['resolution_id'])
        assert monitored['state']=='MONITORING_UNAVAILABLE'
        assert any(g['code']=='STALE_FOR_CURRENT_SESSION' for g in monitored['gaps'])
        assert monitored['capabilities']['observation']=='DEGRADED' and monitored['facts']
        historical=completed(client,client.post('/api/data/requests/'+request['request_id']+'/resolve',
            json={'usage':'HISTORICAL_RESEARCH','allow_fallback':False}).json()['resolution_id'])
        assert historical['state']=='DEGRADED'
        assert any(g['code']=='CURRENT_STATUS_UNKNOWN' for g in historical['gaps'])
        newrisk=completed(client,client.post('/api/data/requests/'+request['request_id']+'/resolve',
            json={'usage':'NEW_RISK','allow_fallback':False}).json()['resolution_id'])
        assert newrisk['state']=='BLOCKED_NEW_RISK' and newrisk['formal_judgment']=='DISABLED'


def test_noncomparable_alternate_blocks_switch_and_keeps_known_primary_price(tmp_path):
    def provider(request):
        return httpx.Response(200,content=tencent_bytes() if request.url.host=='qt.gtimg.cn' else quote_bytes(price='1200.00'))
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        request=setup_request(client,required_fields=['QUOTE.volume_shares'])
        result=completed(client,client.post('/api/data/requests/'+request['request_id']+'/resolve',
            json={'usage':'HISTORICAL_RESEARCH'}).json()['resolution_id'])
        assert len(result['attempts'])==2
        assert result['source_checks'][0]['decision']=='BLOCKED'
        assert 'CONFLICT_LAST' in result['source_checks'][0]['reasons']
        assert result['facts'][0]['last']=='1258.62' and result['facts'][0]['volume_shares'] is None
        assert result['capabilities']['required_inputs']=='BLOCKED_NEW_RISK'
        assert any(g['code']=='SOURCE_SWITCH_NOT_COMPARABLE' for g in result['gaps'])
        assert result['state']=='DEGRADED'


def test_revision_invalidates_original_derived_resolution_and_replay_keeps_original_input(tmp_path):
    price=['1258.620']
    calls=[]
    def provider(request):
        calls.append(str(request.url))
        return httpx.Response(200,content=quote_bytes(price=price[0]))
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        request=setup_request(client,quote_source='SINA',required_fields=['QUOTE.last'])
        first=completed(client,client.post('/api/data/requests/'+request['request_id']+'/resolve',
            json={'usage':'HISTORICAL_RESEARCH'}).json()['resolution_id'])
        first_run=client.get('/api/data/runs/'+first['attempts'][0]['run_id']).json()
        original_snapshot=client.get('/api/data/snapshots/'+first_run['snapshot_id']).json()
        price[0]='1259.00'
        response=client.post('/api/data/requests/'+request['request_id']+'/resolve',
            json={'usage':'HISTORICAL_RESEARCH','use_cache':False,'revision_of':first['resolution_id']})
        assert response.status_code==202,response.text
        revised=completed(client,response.json()['resolution_id'])
        assert revised['facts'][0]['last']=='1259.00' and revised['revision']['prior_resolution_id']==first['resolution_id']
        assert revised['facts'][0]['available_at']>first['facts'][0]['available_at']
        assert client.get('/api/data/resolutions/'+first['resolution_id']).json()['dependency_status']=='INVALIDATED'
        dependencies=client.get('/api/data/dependencies',params={'resolution_id':first['resolution_id']}).json()
        assert any(d['reason']=='FACT_VALUE_OR_SEMANTICS_REVISED' for d in dependencies)
        assert client.get('/api/data/snapshots/'+first_run['snapshot_id']).json()==original_snapshot
        before=len(calls)
        replay=client.post('/api/data/resolutions/'+first['resolution_id']+'/replay').json()
        assert replay['network_calls']==0 and replay['original_state']==first['state']
        assert replay['facts']==first['facts'] and replay['current_dependency_status']=='INVALIDATED'
        assert client.get('/api/data/replays/'+replay['replay_id']).json()==replay
        assert len(calls)==before


def test_invalid_revision_id_does_not_hold_resolution_slot_or_start_external_work(tmp_path):
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,content=quote_bytes())))) as client:
        request=setup_request(client,quote_source='SINA')
        bad=client.post('/api/data/requests/'+request['request_id']+'/resolve',
            json={'usage':'HISTORICAL_RESEARCH','use_cache':False,'revision_of':'missing'})
        assert bad.status_code==404
        assert client.get('/api/data/runs').json()==[]
        good=client.post('/api/data/requests/'+request['request_id']+'/resolve',json={'usage':'HISTORICAL_RESEARCH'})
        assert good.status_code==202,good.text
        assert completed(client,good.json()['resolution_id'])['status']=='COMPLETED'


def test_missing_raw_variant_triggers_alternate_but_adjusted_versions_never_splice(tmp_path):
    def provider(request):
        if request.url.host=='push2his.eastmoney.com':
            if request.url.params['fqt']=='0':return httpx.Response(503,content=b'fixed raw path failure')
            return httpx.Response(200,json={'rc':0,'data':{'code':'600519','market':1,'klines':['2026-09-30,10,10,10,10,100,100000']}})
        mode=request.url.params['param'].split(',')[-1]
        return httpx.Response(200,json={'code':0,'data':{'sh600519':{('qfqday' if mode else 'day'):[['2026-09-30','10','10','10','10','100']]}}})
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        request=setup_request(client,groups=['DAILY'],required_fields=['DAILY.close'])
        result=completed(client,client.post('/api/data/requests/'+request['request_id']+'/resolve',
            json={'usage':'HISTORICAL_RESEARCH'}).json()['resolution_id'])
        assert len(result['attempts'])==2,result
        assert next(f for f in result['facts'] if f['adjustment']=='RAW')['source_id']=='tencent-daily'
        adjusted=next(f for f in result['facts'] if f['adjustment']=='FORWARD_CURRENT_VERSION')
        assert adjusted['source_id']=='eastmoney-daily'
        assert any(c['decision']=='BLOCKED' and 'ADJUSTED_PROVIDER_VERSION_NOT_COMPARABLE' in c['reasons'] for c in result['source_checks'])
        assert result['state']=='DEGRADED'


def test_existing_archived_primary_is_reused_without_refreshing_its_clock_and_real_quote_unit_gap_triggers_alternate(tmp_path):
    def provider(request):
        return httpx.Response(200,content=tencent_bytes() if request.url.host=='qt.gtimg.cn' else quote_bytes())
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        request=setup_request(client,required_fields=['QUOTE.volume_shares'])
        primary=client.post('/api/data/requests/'+request['request_id']+'/retrieve').json()
        snapshot=client.get('/api/data/snapshots/'+primary['snapshot_id']).json()
        response=client.post('/api/data/requests/'+request['request_id']+'/resolve',
            json={'usage':'HISTORICAL_RESEARCH','basis_run_id':primary['run_id']})
        assert response.status_code==202,response.text
        result=completed(client,response.json()['resolution_id'])
        assert result['network_calls']==1 and result['attempts'][0]['cached'] is True
        assert result['attempts'][0]['run_id']==primary['run_id']
        assert result['facts'][0]['source_id']=='sina-quote' and result['facts'][0]['volume_shares']=='3833098'
        assert result['capabilities']['required_inputs']=='SATISFIED'
        assert result['source_checks'][0]['unit_comparison']=='UNKNOWN_PRIMARY_VOLUME_NOT_EXTRAPOLATED'
        assert client.get('/api/data/snapshots/'+primary['snapshot_id']).json()==snapshot


def test_resolution_total_budget_preserves_all_twenty_one_holdings_and_visible_stop(tmp_path):
    instruments=['SSE:'+str(600519+n) for n in range(21)]
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(503,content=b'fixed failure')))) as client:
        establish(client,instruments)
        request=client.post('/api/data/requests',json={'instruments':instruments,'groups':['QUOTE'],'purpose':'OBSERVATION',
            'start_date':'2026-09-30','end_date':'2026-09-30','max_calls':1,'timeout_seconds':1}).json()
        result=completed(client,client.post('/api/data/requests/'+request['request_id']+'/resolve',
            json={'usage':'CURRENT_MONITORING'}).json()['resolution_id'])
        assert result['requested_instruments']==instruments and result['network_calls']==1
        assert len(result['attempts'])==1 and result['stop_reason']=='CALL_BUDGET_EXHAUSTED'
        assert any(g['instrument']==instruments[-1] and not g['resolved'] for g in result['gaps'])
        assert result['state']=='MONITORING_UNAVAILABLE'
