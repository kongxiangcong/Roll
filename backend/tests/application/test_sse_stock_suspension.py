"""Specific new-stock SSE interval receipt through public HTTP and own genuine archives."""
import hashlib
import json
import httpx
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app


def clock(monkeypatch):
    for module in ['roll.market.sse_stock_suspension','roll.market.post_close_packet','roll.research.prospective','roll.market.evidence']:
        monkeypatch.setattr(module+'.now',lambda:'2026-10-11T16:20:00+08:00')


def interval(rows=None,total=1,n=1,pages=1):
    rows=rows if rows is not None else [{'productCode':'600362','productName':'江西铜业',
        'startStopDate':'20261009','endStopDate':'','controlType':'TR','stopTime':'WH',
        'stopReason':'METHOD scheduled notice','endStopReason':'','type':'LSTP'}]
    return {'sqlId':'GW_PL_JYTS_TFPXX','isPagination':'true','queryDate':'','actionErrors':[],
        'fieldErrors':{},'result':rows,'pageHelp':{'data':rows,'total':total,'pageCount':pages,
        'pageSize':25,'pageNo':n,'beginPage':n,'endPage':n,'cacheSize':1,'searchDate':None}}


def start(client):
    return client.post('/api/research/collections',json={'instrument':'SSE:600362','basis':'METHOD no account source assessment'}).json()['plan_id']


def test_stock_interval_receipt_binds_trade_day_then_fixed_interval_without_resumption_authority(tmp_path,monkeypatch):
    clock(monkeypatch);calls=[]
    day=json.dumps({'sqlId':'GW_PL_JYTS_TFPXX_TRADEDAY','result':[{'beforeTradeDay':'20261009'}]}).encode()
    body=json.dumps(interval()).encode()
    def supplier(request):
        calls.append(request)
        return httpx.Response(200,content=day if request.url.params['sqlId'].endswith('TRADEDAY') else body)
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(supplier),runtime_role='API')) as client:
        pid=start(client);base=f'/api/research/collections/{pid}'
        response=client.post(base+'/sse-stock-suspension',json={'basis':'METHOD explicit finite new-stock source receipt'})
        assert response.status_code==201,response.text
        receipt=response.json()
        assert receipt['evidence_kind']=='METHOD_CASE' and not receipt['system_usable']
        assert receipt['request_budget_calls']==3 and receipt['network_calls']==2
        assert calls[0].url.params['bizDate']=='20261011'
        assert calls[1].url.params['productCode']=='600362'
        assert calls[1].url.params['startStopDate']=='20261009' and calls[1].url.params['endStopDate']=='20261011'
        assert calls[1].url.params['pageHelp.pageSize']=='25'
        assert receipt['reported_before_trade_day']=='2026-10-09' and not receipt['latest_trade_day_verified']
        selected=receipt['events'][0]
        assert selected['reported_start_date']=='2026-10-09' and selected['reported_end_date'] is None
        assert selected['end_date_precision']=='UNKNOWN' and selected['resume_date'] is None
        assert selected['suspension'] is None and not selected['complete_status_verified']
        assert receipt['reference_empty_audit']['declared_total']==10
        assert receipt['reference_empty_audit']['returned_count']==0
        assert receipt['reference_empty_audit']['request_page_size']==100
        assert receipt['reference_empty_audit']['response_page_size']==1000
        assert not receipt['reference_empty_audit']['no_event_authority']
        for saved,raw in [(receipt['trade_day_page'],day),(receipt['pages'][0],body)]:
            assert saved['archive']['sha256']==hashlib.sha256(raw).hexdigest()
            assert client.get('/api/data/archives/'+saved['archive']['sha256']).content==raw
        assert client.get(base+'/sse-stock-suspension-receipts').json()==[receipt]
        assert client.get('/api/account').json()['version']==0


def test_interval_receipts_enter_packet_gap_query_worker_and_pin_old_empty_ids(tmp_path,monkeypatch):
    clock(monkeypatch);calls=[]
    def supplier(request):
        calls.append(request.url.params['sqlId'])
        return httpx.Response(200,json={'sqlId':'GW_PL_JYTS_TFPXX_TRADEDAY','result':[{'beforeTradeDay':'20261009'}]}
            if request.url.params['sqlId'].endswith('TRADEDAY') else interval())
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(supplier),runtime_role='API')) as client:
        pid=start(client);base=f'/api/research/collections/{pid}'
        old=client.post(base+'/post-close-packets',json={'basis':'Immutable old packet before interval source'}).json()
        assert old['stock_suspension_receipts']==[]
        job_response=client.post(base+'/sse-stock-suspension/check',json={'basis':'One concrete persisted source job'})
        assert job_response.status_code==201,job_response.text
        job=job_response.json()
        assert job['state']=='RECORDED' and job['receipt_id']
        assert client.post(base+'/sse-stock-suspension/check',json={'basis':'No retry budget expansion'}).json()==job
        receipts=client.get(base+'/sse-stock-suspension-receipts').json()
        assert len(receipts)==1 and receipts[0]['receipt_id']==job['receipt_id']
        packet=client.post(base+'/post-close-packets',json={'basis':'Current interval facts and exact receipt identity'}).json()
        assert packet['stock_suspension_receipts']==receipts
        assert packet['status_facts'][0]['stock_receipt_id']==job['receipt_id']
        assert packet['status_facts'][0]['suspension'] is None and not packet['forward_admissible']
        query=client.get(base+'/source-gaps').json()
        assert query['stock_suspension_receipts']==receipts and query['stock_suspension_jobs']==[job]
        for original in [old,packet]:
            response=client.post('/api/research/post-close-packets/'+original['packet_id']+'/replay')
            assert response.status_code==200 and response.json()['matches_original'],response.text
        assert calls==['GW_PL_JYTS_TFPXX_TRADEDAY','GW_PL_JYTS_TFPXX']


@pytest.mark.parametrize('fault',['missing_day','future_day','wrong_security','wrong_interval','wrong_page','fixed_empty'])
def test_specific_refusals_keep_trade_day_and_interval_originals_without_fallback(tmp_path,monkeypatch,fault):
    clock(monkeypatch);calls=[]
    from pathlib import Path
    historical=(Path(__file__).resolve().parents[2]/'src/roll/market/reference/sse-history/15a1180483592fa133cc4da6907ad84428fe0bb56ffd672241c456d14a715066.raw').read_bytes()
    def supplier(request):
        calls.append(request.url.params['sqlId'])
        if calls[-1].endswith('TRADEDAY'):
            result=[] if fault=='missing_day' else [{'beforeTradeDay':'20261012' if fault=='future_day' else '20261009'}]
            return httpx.Response(200,json={'sqlId':'GW_PL_JYTS_TFPXX_TRADEDAY','result':result})
        if fault=='fixed_empty':return httpx.Response(200,content=historical)
        value=interval()
        if fault=='wrong_security':value['result'][0]['productCode']='600000'
        if fault=='wrong_interval':value['result'][0]['startStopDate']='20261012'
        if fault=='wrong_page':value['pageHelp']['pageSize']=1000
        return httpx.Response(200,json=value)
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(supplier),runtime_role='API')) as client:
        pid=start(client);base=f'/api/research/collections/{pid}'
        receipt=client.post(base+'/sse-stock-suspension',json={'basis':'METHOD known malformed source contract, no fallback'}).json()
        assert receipt['status']=='REFUSED' and receipt['events']==[] and not receipt['system_usable']
        assert receipt['network_calls']==(1 if fault in {'missing_day','future_day'} else 2)
        assert len(calls)==receipt['network_calls'] and all('GW_PL_JYTS_TFPXX' in s for s in calls)
        assert receipt['trade_day_page']['archive']['sha256']
        assert client.get(base+'/sse-stock-suspension-receipts').json()==[receipt]
        if fault=='fixed_empty':
            page=receipt['pages'][0]
            assert page['reported_metadata']['declared_total']==10 and page['reported_metadata']['returned_count']==0
            assert page['reported_metadata']['page_size']==1000
            assert client.get('/api/data/archives/'+page['archive']['sha256']).content==historical
        packet=client.post(base+'/post-close-packets',json={'basis':'Refused source retained as input gap'}).json()
        assert packet['stock_suspension_receipts']==[receipt] and not packet['forward_admissible']
        assert client.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay').json()['matches_original']


@pytest.mark.parametrize('dependency',['day','page','js','mapping','empty','receipt','capture_plan'])
def test_original_dependencies_refuse_read_and_replay_after_owned_damage(tmp_path,monkeypatch,dependency):
    clock(monkeypatch)
    def supplier(request):
        return httpx.Response(200,json={'sqlId':'GW_PL_JYTS_TFPXX_TRADEDAY','result':[{'beforeTradeDay':'20261009'}]}
            if request.url.params['sqlId'].endswith('TRADEDAY') else interval())
    app=create_app(tmp_path,market_transport=httpx.MockTransport(supplier),runtime_role='API')
    with TestClient(app) as client:
        pid=start(client);base=f'/api/research/collections/{pid}'
        receipt=client.post(base+'/sse-stock-suspension',json={'basis':'METHOD concrete raw dependency integrity'}).json()
        packet=client.post(base+'/post-close-packets',json={'basis':'Archive exact raw bindings'}).json()
        hashes={'day':receipt['trade_day_page']['archive']['sha256'],'page':receipt['pages'][0]['archive']['sha256'],
            'js':receipt['query_js_hash'],'mapping':receipt['schema_mapping_hash'],
            'empty':receipt['reference_empty_audit']['raw_hash'],'receipt':receipt['archive']['sha256'],
            'capture_plan':receipt['capture_plan_archive']['sha256']}
        app.state.evidence.raw(hashes[dependency]).write_bytes(b'owned METHOD corruption')
        assert client.get(base+'/sse-stock-suspension-receipts').status_code==409
        assert client.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay').status_code==409


def test_two_interval_pages_keep_budget_gap_and_distinct_events(tmp_path,monkeypatch):
    clock(monkeypatch);calls=[]
    def supplier(request):
        calls.append(request)
        if request.url.params['sqlId'].endswith('TRADEDAY'):
            return httpx.Response(200,json={'sqlId':'GW_PL_JYTS_TFPXX_TRADEDAY','result':[{'beforeTradeDay':'20261009'}]})
        n=int(request.url.params['pageHelp.pageNo']);value=interval(total=3,n=n,pages=3)
        value['result'][0]['stopTime']='WH' if n==1 else 'AM'
        return httpx.Response(200,json=value)
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(supplier),runtime_role='API')) as client:
        pid=start(client);base=f'/api/research/collections/{pid}'
        receipt=client.post(base+'/sse-stock-suspension',json={'basis':'METHOD third interval page exceeds new independent budget'}).json()
        assert receipt['network_calls']==3 and len(calls)==3 and len(receipt['events'])==2
        assert receipt['returned_count']==2 and receipt['declared_total']==3
        assert 'SSE_STOCK_PAGE_BUDGET_EXHAUSTED' in receipt['gaps']
        assert not receipt['returned_count_matches_positive_total'] and not receipt['complete_status_verified']
        assert client.get(base+'/sse-stock-suspension-receipts').json()==[receipt]


def test_stream_interruption_retains_received_prefix_without_date_fallback(tmp_path,monkeypatch):
    clock(monkeypatch);prefix=b'{"sqlId":"GW_PL_JYTS_TFPXX_TRADEDAY","result":'
    class Interrupted(httpx.SyncByteStream):
        def __iter__(self):
            yield prefix
            raise httpx.ReadTimeout('METHOD interrupted response stream')
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,stream=Interrupted())),runtime_role='API')) as client:
        pid=start(client);base=f'/api/research/collections/{pid}'
        receipt=client.post(base+'/sse-stock-suspension',json={'basis':'METHOD preserve observed bytes on transport failure'}).json()
        assert receipt['status']=='REFUSED' and receipt['network_calls']==1 and 'ReadTimeout' in receipt['errors']
        saved=receipt['trade_day_page']
        assert saved['original_complete'] is False
        assert client.get('/api/data/archives/'+saved['archive']['sha256']).content==prefix
        assert receipt['pages']==[] and receipt['reported_before_trade_day'] is None
        assert client.get(base+'/sse-stock-suspension-receipts').json()==[receipt]


def test_empty_and_disabled_source_do_not_claim_normal_or_expand_cached_budget(tmp_path,monkeypatch):
    clock(monkeypatch);calls=[]
    def supplier(request):
        calls.append(request)
        return httpx.Response(200,json={'sqlId':'GW_PL_JYTS_TFPXX_TRADEDAY','result':[{'beforeTradeDay':'20261009'}]}
            if request.url.params['sqlId'].endswith('TRADEDAY') else interval(rows=[],total=0,pages=0))
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(supplier),runtime_role='API')) as client:
        pid=start(client);base=f'/api/research/collections/{pid}'
        receipt=client.post(base+'/sse-stock-suspension',json={'basis':'METHOD empty selected interval'}).json()
        assert receipt['events']==[] and not receipt['no_event_authority'] and not receipt['returned_count_matches_positive_total']
        assert client.post('/api/research/collection-sources/sse-stock-suspension-interval/policy',json={
            'enabled':False,'expected_revision':1,'basis':'Disable this specific source independently'}).status_code==200
        job=client.post(base+'/sse-stock-suspension/check',json={'basis':'Do not acquire disabled source'}).json()
        assert 'SOURCE_DISABLED' in job['gaps']
        assert client.post(base+'/sse-stock-suspension/check',json={'basis':'Cached task stays bounded'}).json()==job
        assert len(calls)==2
        for extra in [{'startStopDate':'20130101'},{'latest_trade_day_verified':True},{'system_usable':True}]:
            assert client.post(base+'/sse-stock-suspension',json={'basis':'No client authority flags',**extra}).status_code==422


def test_capture_plan_is_archived_before_raws_and_bound_to_the_new_three_call_budget(tmp_path,monkeypatch):
    clock(monkeypatch)
    def supplier(request):
        return httpx.Response(200,json={'sqlId':'GW_PL_JYTS_TFPXX_TRADEDAY','result':[{'beforeTradeDay':'20261009'}]}
            if request.url.params['sqlId'].endswith('TRADEDAY') else interval(rows=[],total=0,pages=0))
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(supplier),runtime_role='API')) as client:
        pid=start(client);base=f'/api/research/collections/{pid}'
        receipt=client.post(base+'/sse-stock-suspension',json={'basis':'Independent source-plan audit before HTTP'}).json()
        planned=receipt['capture_plan']
        assert planned['capture_id']==receipt['receipt_id'] and planned['collection_plan_id']==pid
        assert planned['host_date']=='2026-10-11' and planned['request_budget_calls']==3
        assert planned['trade_day_parameters']=={'sqlId':'GW_PL_JYTS_TFPXX_TRADEDAY','bizDate':'20261011'}
        assert planned['interval_page_budget']==2 and planned['no_fallback'] and planned['no_retries']
        assert planned['created_at']<=receipt['trade_day_page']['archive']['received_at']
        archived=client.get('/api/data/archives/'+receipt['capture_plan_archive']['sha256'])
        assert archived.status_code==200 and archived.json()==planned
        assert client.get(base+'/sse-stock-suspension-receipts').json()==[receipt]


def test_saved_actual_empty_interval_stays_unknown_and_old_nonempty_ids_survive_append(tmp_path,monkeypatch):
    clock(monkeypatch);calls=[]
    proof=Path(__file__).resolve().parents[3]/'.scratch/roll-p0/evidence/30-sse-stock-suspension/runtime/source-assessment'
    day=(proof/'f45a2a21a972c1150d69db7a60e8506932974bc1bdd216d3f6d052a5cdc7fc22.raw').read_bytes()
    raw=(proof/'7fd45879b5af75c7e0cb7f4c92ce9ad6fa31ddca8ad472deb83b66f3bbfd1c6f.raw').read_bytes()
    assert hashlib.sha256(day).hexdigest()=='f45a2a21a972c1150d69db7a60e8506932974bc1bdd216d3f6d052a5cdc7fc22'
    assert hashlib.sha256(raw).hexdigest()=='7fd45879b5af75c7e0cb7f4c92ce9ad6fa31ddca8ad472deb83b66f3bbfd1c6f'
    def supplier(request):
        calls.append(request)
        return httpx.Response(200,content=day if request.url.params['sqlId'].endswith('TRADEDAY') else raw)
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(supplier),runtime_role='API')) as client:
        pid=start(client);base=f'/api/research/collections/{pid}'
        first=client.post(base+'/sse-stock-suspension',json={'basis':'Saved actual public originals supplied strictly offline METHOD'}).json()
        assert first['evidence_kind']=='METHOD_CASE' and first['reported_before_trade_day']=='2026-10-09'
        assert first['events']==[] and first['declared_total']==0 and not first['latest_trade_day_verified']
        assert not first['no_event_authority'] and not first['complete_status_verified']
        old=client.post(base+'/post-close-packets',json={'basis':'Freeze first exact stock source receipt'}).json()
        second=client.post(base+'/sse-stock-suspension',json={'basis':'Explicit later same-cutoff receipt, no old ID replacement'}).json()
        new=client.post(base+'/post-close-packets',json={'basis':'Both actual raw METHOD receipt IDs'}).json()
        assert [r['receipt_id'] for r in old['stock_suspension_receipts']]==[first['receipt_id']]
        assert [r['receipt_id'] for r in new['stock_suspension_receipts']]==[first['receipt_id'],second['receipt_id']]
        for original in [old,new]:
            replay=client.post('/api/research/post-close-packets/'+original['packet_id']+'/replay')
            assert replay.status_code==200 and replay.json()['matches_original'],replay.text
            assert not original['forward_admissible'] and original['forward_started_at'] is None
        gaps=client.get(base+'/source-gaps').json()
        assert len(gaps['stock_suspension_receipts'])==2
        assert 'SSE_STOCK_EMPTY_NOT_NORMAL_OR_NO_EVENT_AUTHORITY' in gaps['stock_suspension_source_gaps']
        assert len(calls)==4 and client.get('/api/account').json()['version']==0
