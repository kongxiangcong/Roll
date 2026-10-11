"""Public bounded source receipt API; injected current raw is explicit METHOD."""
import hashlib
import json
import httpx
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app
from test_post_close_packet import setup


def page(rows=None,total=1,page_no=1,page_count=1):
    if rows is None:rows=[{'PRODUCT_CODE':'600362','PRODUCT_NAME':'江西铜业','CONTROLTYPE':'TR',
        'SHOW_START_DATE':'2026-10-12','SHOW_END_DATE':'2026-10-20','STOP_DATE':'-',
        'STOP_TIME':'自2026-10-12起连续停牌','STOP_REASON':'METHOD explicit suspension input',
        'BULLETIN_TYPE':'3','NUM':'1'}]
    return {'sqlId':'COMMON_SSE_XXPL_JYTS_TFPXX_L','actionErrors':[],'fieldErrors':{},
        'isPagination':'true','queryDate':'','result':rows,'pageHelp':{'data':rows,'total':total,
        'pageNo':page_no,'pageCount':page_count,'pageSize':100,'beginPage':page_no,
        'endPage':page_no,'cacheSize':1,'searchDate':None}}


def clocks(monkeypatch,stamp='2026-10-12T15:06:00+08:00'):
    for module in ['roll.market.post_close_packet','roll.research.prospective','roll.market.evidence']:
        monkeypatch.setattr(module+'.now',lambda:stamp)


def test_bounded_receipt_keeps_reported_suspension_original_without_resume_or_full_status(tmp_path,monkeypatch):
    clocks(monkeypatch)
    raw=json.dumps(page(),ensure_ascii=False).encode();calls=[]
    def supplier(request):
        calls.append(request)
        assert request.url.host=='query.sse.com.cn' and request.url.path=='/sseQuery/commonQuery.do'
        return httpx.Response(200,content=raw)
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(supplier))) as client:
        pid=setup(client)
        response=client.post(f'/api/research/collections/{pid}/sse-suspension',json={'basis':'Explicit METHOD current source receipt'})
        assert response.status_code==201,response.text
        receipt=response.json()
        assert receipt['query_date']=='2026-10-12' and receipt['network_calls']==1
        assert len(calls)==1 and calls[0].url.params['SEARCH_DATE']=='2026-10-12'
        assert receipt['request_budget_pages']==2 and not receipt['system_usable']
        assert receipt['evidence_kind']=='METHOD_CASE' and not receipt['complete_status_verified']
        assert receipt['pages'][0]['archive']['sha256']==hashlib.sha256(raw).hexdigest()
        assert client.get('/api/data/archives/'+receipt['pages'][0]['archive']['sha256']).content==raw
        fact=receipt['events'][0]
        assert fact['instrument']=='SSE:600362' and fact['suspension'] is True
        assert fact['reported_end_date']=='2026-10-20' and fact['date_precision']=='DATE'
        assert fact['resume_date'] is None and fact['risk_warning'] is None
        assert fact['listing_stage'] is None and fact['ex_rights'] is None
        assert fact['query_js_hash']=='32fc98ea41e599f457609247ba68defb82e6d855aa2551da6923dbf7e44153a7'
        assert 'SSE_SUSPENSION_RESPONSE_DATE_ECHO_UNPROVEN' in receipt['gaps']
        assert client.get(f'/api/research/collections/{pid}/sse-suspension-receipts').json()==[receipt]


def test_packet_consumer_retains_conflicting_sources_and_old_empty_receipt_ids(tmp_path,monkeypatch):
    clocks(monkeypatch);calls=[]
    closing=json.dumps({'date':20261012,'time':150005,'list':[['600362','江西铜业',100,101,99,100,1234,123400,100]]}).encode()
    suspension=json.dumps(page(),ensure_ascii=False).encode()
    def supplier(request):
        calls.append(str(request.url))
        return httpx.Response(200,content=closing if request.url.host=='yunhq.sse.com.cn' else suspension)
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(supplier))) as client:
        pid=setup(client);base=f'/api/research/collections/{pid}'
        account=client.get('/api/account').json()
        response=client.post(base+'/post-close',json={'basis':'Original METHOD closing packet before suspension receipt'})
        assert response.status_code==201,response.text
        old=response.json()
        assert old['suspension_receipts']==[] and old['rows'][0]['suspension_receipt_ids']==[]
        response=client.post(base+'/sse-suspension',json={'basis':'Explicit later same-cutoff source assessment'})
        assert response.status_code==201,response.text
        receipt=response.json()
        packet=client.post(base+'/post-close-packets',json={'basis':'Both conflicting original source observations'}).json()
        assert packet['suspension_receipts']==[receipt]
        assert packet['rows'][0]['suspension_receipt_ids']==[receipt['receipt_id']]
        assert len(packet['status_facts'])==2
        assert {s['suspension'] for s in packet['status_facts']}=={True,False}
        assert 'UNRESOLVED_CURRENT_STATUS_CONFLICT:2026-10-12' in packet['gaps']
        assert not packet['forward_admissible'] and packet['forward_started_at'] is None
        for original in [old,packet]:
            replay=client.post('/api/research/post-close-packets/'+original['packet_id']+'/replay')
            assert replay.status_code==200 and replay.json()['matches_original'],replay.text
        assert client.get(base+'/source-gaps').json()['suspension_receipts']==[receipt]
        assert len(calls)==2


def test_existing_worker_job_records_one_bounded_suspension_receipt_without_hidden_retries(tmp_path,monkeypatch):
    clocks(monkeypatch);calls=[]
    closing=json.dumps({'date':20261012,'time':150005,'list':[['600362','江西铜业',100,101,99,100,1234,123400,100]]}).encode()
    suspension=json.dumps(page(rows=[],total=0,page_count=0)).encode()
    def supplier(request):
        calls.append(request.url.host)
        return httpx.Response(200,content=closing if request.url.host=='yunhq.sse.com.cn' else suspension)
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(supplier))) as client:
        pid=setup(client);base=f'/api/research/collections/{pid}'
        account=client.get('/api/account').json()
        response=client.post(base+'/post-close/check',json={'basis':'Same worker owns both bounded current source jobs'})
        assert response.status_code==201,response.text
        job=response.json()
        assert job['state']=='RECORDED' and job['suspension_receipt_id']
        receipts=client.get(base+'/sse-suspension-receipts').json()
        assert len(receipts)==1 and receipts[0]['receipt_id']==job['suspension_receipt_id']
        assert receipts[0]['events']==[] and not receipts[0]['no_event_authority']
        assert client.post(base+'/post-close/check',json={'basis':'Same checkpoint retry cannot expand source budget'}).json()==job
        bounded=client.post(base+'/sse-suspension/check',json={'basis':'Explicit cached status-source job'}).json()
        assert bounded['state']=='RECORDED' and bounded['receipt_id']==job['suspension_receipt_id']
        assert sorted(calls)==['query.sse.com.cn','yunhq.sse.com.cn']
        assert client.get('/api/account').json()==account


@pytest.mark.parametrize('fault,expected',[
    ('date','SSE_SUSPENSION_MATCHED_SECURITY_DATE_RANGE_INVALID'),
    ('echo','SSE_SUSPENSION_RESPONSE_DATE_MISMATCH'),
    ('security','SSE_SUSPENSION_ROW_SECURITY_UNPROVEN'),
    ('page','SSE_SUSPENSION_PAGE_REQUEST_RESPONSE_MISMATCH'),
])
def test_refused_response_keeps_original_and_literal_reported_metadata(tmp_path,monkeypatch,fault,expected):
    clocks(monkeypatch);value=page()
    if fault=='date':value['result'][0]['SHOW_END_DATE']='2026-10-11'
    if fault=='echo':value['queryDate']='2016-02-16'
    if fault=='security':value['result'][0]['PRODUCT_CODE']='600362?'
    if fault=='page':value['pageHelp']['pageNo']=2
    raw=json.dumps(value).encode();calls=[]
    def supplier(request):
        calls.append(request);return httpx.Response(200,content=raw)
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(supplier))) as client:
        pid=setup(client);base=f'/api/research/collections/{pid}'
        response=client.post(base+'/sse-suspension',json={'basis':'METHOD malformed authoritative fields, keep raw first'})
        assert response.status_code==201,response.text
        receipt=response.json()
        assert receipt['status']=='REFUSED' and expected in receipt['errors']
        assert receipt['network_calls']==1 and len(calls)==1 and receipt['events']==[]
        saved=receipt['pages'][0]
        assert saved['reported_metadata']['declared_total']==1
        assert saved['reported_metadata']['page_no']==value['pageHelp']['pageNo']
        assert saved['reported_metadata']['response_date_reported']==value['queryDate']
        assert client.get('/api/data/archives/'+saved['archive']['sha256']).content==raw
        assert client.get(base+'/sse-suspension-receipts').json()==[receipt]
        packet=client.post(base+'/post-close-packets',json={'basis':'Refused source remains a concrete input gap'}).json()
        assert not packet['forward_admissible'] and packet['suspension_receipts']==[receipt]
        assert client.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay').json()['matches_original']


def test_two_page_budget_retains_truncation_and_second_page_security_without_completeness(tmp_path,monkeypatch):
    clocks(monkeypatch);calls=[];originals=[]
    def supplier(request):
        n=int(request.url.params['pageHelp.pageNo']);calls.append(n)
        rows=[{'PRODUCT_CODE':str(600000+i+100*(n-1))} for i in range(100)]
        if n==2:rows[-1]=page()['result'][0]
        raw=json.dumps(page(rows,total=201,page_no=n,page_count=3)).encode();originals.append(raw)
        return httpx.Response(200,content=raw)
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(supplier))) as client:
        pid=setup(client);base=f'/api/research/collections/{pid}'
        receipt=client.post(base+'/sse-suspension',json={'basis':'METHOD two bounded pages, third is deliberately unavailable'}).json()
        assert calls==[1,2] and receipt['network_calls']==2
        assert receipt['declared_total']==201 and receipt['returned_count']==200
        assert not receipt['returned_count_matches_positive_total']
        assert 'SSE_SUSPENSION_PAGE_BUDGET_EXHAUSTED' in receipt['gaps']
        assert receipt['events'][0]['source_page_no']==2 and receipt['events'][0]['row_ordinal']==99
        assert not receipt['complete_status_verified'] and not receipt['no_event_authority']
        for saved,raw in zip(receipt['pages'],originals):
            assert client.get('/api/data/archives/'+saved['archive']['sha256']).content==raw
        assert client.get(base+'/sse-suspension-receipts').json()==[receipt]


@pytest.mark.parametrize('fault',['duplicate','changed_total'])
def test_second_page_inconsistency_is_refused_with_both_raws_retained(tmp_path,monkeypatch,fault):
    clocks(monkeypatch);calls=[]
    def supplier(request):
        n=int(request.url.params['pageHelp.pageNo']);calls.append(n)
        value=page(total=2 if n==1 or fault=='duplicate' else 3,page_no=n,page_count=2)
        return httpx.Response(200,json=value)
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(supplier))) as client:
        pid=setup(client);base=f'/api/research/collections/{pid}'
        receipt=client.post(base+'/sse-suspension',json={'basis':'METHOD contradictory pages'}).json()
        assert calls==[1,2] and receipt['status']=='REFUSED' and len(receipt['pages'])==2
        assert receipt['events']==[] and not receipt['system_usable']
        expected='MATCHED_SECURITY_DUPLICATED' if fault=='duplicate' else 'PAGINATION_CHANGED_BETWEEN_PAGES'
        assert any(expected in e for e in receipt['errors'])
        assert client.get(base+'/sse-suspension-receipts').json()==[receipt]


@pytest.mark.parametrize('dependency',['page','query_js','mapping','receipt'])
def test_receipt_and_packet_replay_refuse_tampered_original_dependencies(tmp_path,monkeypatch,dependency):
    clocks(monkeypatch)
    app=create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,json=page())))
    with TestClient(app) as client:
        pid=setup(client);base=f'/api/research/collections/{pid}'
        receipt=client.post(base+'/sse-suspension',json={'basis':'METHOD immutable linked source dependencies'}).json()
        packet=client.post(base+'/post-close-packets',json={'basis':'Freeze exact input receipt'}).json()
        hashes={'page':receipt['pages'][0]['archive']['sha256'],'query_js':receipt['query_js_hash'],
            'mapping':receipt['schema_mapping_hash'],'receipt':receipt['archive']['sha256']}
        app.state.evidence.raw(hashes[dependency]).write_bytes(b'owned METHOD archive corruption')
        assert client.get(base+'/sse-suspension-receipts').status_code==409
        assert client.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay').status_code==409


def test_disabled_source_and_caller_flags_cannot_trigger_network_or_certify_status(tmp_path,monkeypatch):
    clocks(monkeypatch);calls=[]
    def supplier(request):calls.append(request);return httpx.Response(200,json=page())
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(supplier))) as client:
        pid=setup(client);base=f'/api/research/collections/{pid}'
        for extra in [{'query_date':'2016-02-16'},{'complete_status_verified':True},{'evidence_kind':'REAL'}]:
            assert client.post(base+'/sse-suspension',json={'basis':'Client cannot supply authority',**extra}).status_code==422
        changed=client.post('/api/research/collection-sources/sse-suspension-date/policy',json={
            'enabled':False,'expected_revision':1,'basis':'METHOD persistent source shutdown'})
        assert changed.status_code==200,changed.text
        job=client.post(base+'/sse-suspension/check',json={'basis':'Respect source shutdown without hidden retries'}).json()
        assert job['state']=='RECORDED' and 'SOURCE_DISABLED' in job['gaps']
        receipt=client.get(base+'/sse-suspension-receipts').json()[0]
        assert receipt['status']=='REFUSED' and receipt['network_calls']==0 and receipt['pages']==[]
        assert client.post(base+'/sse-suspension/check',json={'basis':'No hidden retry'}).json()==job
        assert calls==[]


def test_oversized_source_keeps_bounded_prefix_and_refuses_original_completeness(tmp_path,monkeypatch):
    clocks(monkeypatch);raw=b'x'*(8*1024*1024+1)
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,content=raw)))) as client:
        pid=setup(client);base=f'/api/research/collections/{pid}'
        receipt=client.post(base+'/sse-suspension',json={'basis':'METHOD byte ceiling retains bounded diagnostic prefix'}).json()
        assert receipt['status']=='REFUSED' and receipt['network_calls']==1
        assert 'SSE_SUSPENSION_DECODED_BYTE_LIMIT_PREFIX_ONLY' in receipt['errors']
        saved=receipt['pages'][0]
        assert saved['original_complete'] is False
        assert client.get('/api/data/archives/'+saved['archive']['sha256']).content==raw[:8*1024*1024]
        assert not receipt['no_event_authority'] and receipt['events']==[]
        assert client.get(base+'/sse-suspension-receipts').json()==[receipt]


def test_saved_actual_public_response_remains_partial_in_offline_packet_and_replay(tmp_path,monkeypatch):
    clocks(monkeypatch,'2026-10-11T16:14:06+08:00')
    proof=Path(__file__).resolve().parents[3]/'.scratch/roll-p0/evidence/30-sse-current-suspension/runtime/source-assessment'
    raw=(proof/'986c403e89bf4aab9f260034f1d301126daa0de9ff62926f90cf798768eeb958.raw').read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='986c403e89bf4aab9f260034f1d301126daa0de9ff62926f90cf798768eeb958'
    calls=[]
    def supplier(request):calls.append(request);return httpx.Response(200,content=raw)
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(supplier),runtime_role='API')) as client:
        pid=client.post('/api/research/collections',json={'instrument':'SSE:600362','basis':'METHOD offline public raw replay'}).json()['plan_id']
        base=f'/api/research/collections/{pid}'
        receipt=client.post(base+'/sse-suspension',json={'basis':'Saved actual raw supplied offline; transport evidence stays METHOD'}).json()
        assert receipt['evidence_kind']=='METHOD_CASE' and receipt['events']==[]
        assert receipt['returned_count']==receipt['declared_total']==26
        assert receipt['returned_count_matches_positive_total'] and not receipt['no_event_authority']
        assert receipt['page_audits'][0]['response_date_verified'] is False
        packet=client.post(base+'/post-close-packets',json={'basis':'No security return cannot prove ordinary status'}).json()
        assert packet['suspension_receipts']==[receipt] and not packet['forward_admissible']
        assert packet['forward_started_at'] is None
        assert client.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay').json()['matches_original']
        assert client.get(base+'/source-gaps').json()['suspension_receipts']==[receipt]
        assert len(calls)==1 and client.get('/api/account').json()['version']==0
