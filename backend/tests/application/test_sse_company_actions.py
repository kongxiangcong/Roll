"""Finite raw-first action source receipt, without guessed response/lifecycle semantics."""
import hashlib
import httpx
import asyncio
import time
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from roll.app import create_app
from test_sse_company_contract import clock, start

FH='COMMON_SSE_CP_GPJCTPZ_GPLB_LRFP_FH_L'
SG='COMMON_SSE_CP_GPJCTPZ_GPLB_LRFP_SG_L'

def actual_bodies():
    reference=Path(__file__).resolve().parents[2]/'src/roll/market/reference/sse-company-action-contract'
    expected={FH:('20243b376bad269c47fffb63cd38034caa0c619eadaf85e9532741ec9a0aa91e',5548),
              SG:('b498844359a5f0bd6b2dbddaa1b02b1a9d55e04f708cdb93b14cfb776d553f52',496)}
    bodies={}
    for sql,(sha,size) in expected.items():
        body=(reference/(sha+'.raw')).read_bytes()
        assert hashlib.sha256(body).hexdigest()==sha and len(body)==size
        bodies[sql]=body
    return bodies

def method_clock(monkeypatch):
    clock(monkeypatch,'2026-10-11T21:00:00+08:00')
    monkeypatch.setattr('roll.market.sse_company_actions.now',lambda:'2026-10-11T21:00:00+08:00')
    monkeypatch.setattr('roll.market.sse_action_assessments.now',lambda:'2026-10-11T21:00:00+08:00')
    # This is only the pre-agreed METHOD clock; Host/registry clocks remain unchanged.

def test_observed_first_pages_become_explicit_candidates_with_unknown_complete_coverage(tmp_path,monkeypatch):
    method_clock(monkeypatch)
    bodies=actual_bodies();calls=[]
    def supplier(request):
        calls.append(request)
        return httpx.Response(200,content=bodies[request.url.params['sqlId']])
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(supplier),runtime_role='API')) as client:
        base=start(client)
        raw=client.post(base+'/sse-company-actions',json={'basis':'Offline exact newly captured public originals'}).json()
        response=client.post(base+'/sse-action-assessments',json={'source_receipt_id':raw['receipt_id'],'basis':'Explicit observed response schema assessment'})
        assert response.status_code==201,response.text
        assessment=response.json()
        dividend=assessment['role_audits']['dividend'];empty=assessment['role_audits']['send_share']
        assert dividend['returned_count']==5 and dividend['total_reported']==6 and dividend['page_count_reported']==2
        assert dividend['pagination_state']=='FIRST_PAGE_INCOMPLETE'
        assert empty['returned_count']==empty['total_reported']==0 and empty['pagination_state']=='EMPTY_FINITE_RESPONSE_SCOPE_UNKNOWN'
        assert len(assessment['candidates'])==5 and assessment['network_calls']==0
        first=assessment['candidates'][0]
        assert first['company_code']=='600362' and first['stock_code']=='600362'
        assert first['record_date_original']=='20260716' and first['record_date_reported']=='2026-07-16'
        assert first['dividend_date_original']=='20260717' and first['dividend_date_reported']=='2026-07-17'
        assert first['cash_before_tax_original']=='0.6' and first['cash_before_tax_exact']=='0.6'
        assert first['reported_date_precision']=='DATE' and first['source_row_pointer']=='/result/0'
        assert first['raw_hash']=='20243b376bad269c47fffb63cd38034caa0c619eadaf85e9532741ec9a0aa91e'
        assert first['authoritative_event_id'] is None and first['lifecycle_state']=='UNKNOWN'
        assert first['payment_fulfilled'] is None and first['cash_per_share_unit']=='UNKNOWN'
        assert not assessment['complete_action_coverage'] and not assessment['pending_older_obligations_complete']
        assert assessment['query_date_scope']=='UNKNOWN' and not assessment['system_usable']
        assert client.get(base+'/sse-action-assessments').json()==[assessment]
        current=client.get(base+'/sse-action-assessments/current').json()
        assert current['assessment_id']==assessment['assessment_id'] and not current['current_complete_action_coverage']
        assert client.get(base+'/source-gaps').json()['action_assessments']==[assessment]
        assert len(calls)==2

def test_action_successor_keeps_fixed_empty_and_nonempty_ids_after_same_cutoff_append_and_restart(tmp_path,monkeypatch):
    method_clock(monkeypatch);bodies=actual_bodies();calls=[]
    def supplier(request):
        calls.append(request);return httpx.Response(200,content=bodies[request.url.params['sqlId']])
    transport=httpx.MockTransport(supplier)
    with TestClient(create_app(tmp_path,market_transport=transport,runtime_role='API')) as client:
        base=start(client)
        original=client.post(base+'/post-close-packets',json={'basis':'Original daily packet keeps old parser and input identity'}).json()
        empty_command={'source_receipt_id':None,'assessment_ids':[],'predecessor_packet_id':original['packet_id'],
                       'basis':'Explicit empty action successor before any source receipt'}
        response=client.post(base+'/sse-action-packets',json=empty_command)
        assert response.status_code==201,response.text
        empty=response.json()
        raw=client.post(base+'/sse-company-actions',json={'basis':'Offline recorded first pages'}).json()
        command={'source_receipt_id':raw['receipt_id'],'basis':'First explicit partial action assessment'}
        first=client.post(base+'/sse-action-assessments',json=command).json()
        response=client.post(base+'/sse-action-packets',json={**empty_command,'source_receipt_id':raw['receipt_id'],
            'assessment_ids':[first['assessment_id']],'basis':'Fixed IDs explicit action consumer'})
        assert response.status_code==201,response.text
        packet=response.json()
        assert packet['packet_type']=='ACTION_SUCCESSOR' and packet['predecessor']==original
        assert packet['assessment_ids']==[first['assessment_id']] and len(packet['action_candidates'])==5
        assert packet['source_receipt_ids']==[raw['receipt_id']]
        assert not packet['forward_admissible'] and not packet['complete_action_coverage']
        second=client.post(base+'/sse-action-assessments',json=command).json()
        assert second['assessment_id']!=first['assessment_id']
        for saved in [empty,packet]:
            assert client.get(base+'/sse-action-packets/'+saved['packet_id']).json()==saved
            replay=client.post('/api/research/post-close-packets/'+saved['packet_id']+'/replay').json()
            assert replay['matches_original'] and replay['network_calls']==0
        assert empty['assessment_ids']==[] and empty['source_receipt_ids']==[]
        assert client.post('/api/research/post-close-packets/'+original['packet_id']+'/replay').json()['matches_original']
        assert client.post(base+'/sse-action-packets',json={**empty_command,'complete_action_coverage':True}).status_code==422
    with TestClient(create_app(tmp_path,market_transport=transport,runtime_role='API')) as client:
        for saved in [empty,packet]:assert client.get(base+'/sse-action-packets/'+saved['packet_id']).json()==saved
        assert client.post(base+'/sse-company-actions',json={'basis':'Repeat after restart returns existing source receipt'}).json()==raw
    assert len(calls)==2

@pytest.mark.parametrize('defect',['security','pagination','sql','date','share_row'])
def test_raw_is_retained_but_unproved_identity_page_or_row_schema_is_refused(tmp_path,monkeypatch,defect):
    method_clock(monkeypatch);bodies=actual_bodies()
    role=SG if defect=='share_row' else FH
    value=json.loads(bodies[role])
    if defect=='security':value['result'][0]['A_STOCK_CODE']='600000'
    if defect=='pagination':value['pageHelp']['pageNo']=2
    if defect=='sql':value['sqlId']=SG
    if defect=='date':value['result'][0]['A_REG_DATE']='20261340'
    if defect=='share_row':
        value['result']=[{'SECURITY_CODE_A':'600362'}];value['pageHelp'].update(total=1,pageCount=1)
    value['pageHelp']['data']=value['result']
    bodies[role]=json.dumps(value,ensure_ascii=False).encode()
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,content=bodies[r.url.params['sqlId']])),runtime_role='API')) as client:
        base=start(client);raw=client.post(base+'/sse-company-actions',json={'basis':'METHOD invalid supplier observation retained'}).json()
        response=client.post(base+'/sse-action-assessments',json={'source_receipt_id':raw['receipt_id'],'basis':'Invalid observation cannot become facts'})
        assert response.status_code==409,response.text
        assert client.get(base+'/sse-company-action-receipts').json()==[raw]
        assert client.get(base+'/sse-action-assessments').json()==[]

@pytest.mark.parametrize('dependency',['raw','mapping','assessment','plan'])
def test_damaged_archived_dependencies_refuse_current_query_and_fixed_packet_replay(tmp_path,monkeypatch,dependency):
    method_clock(monkeypatch);bodies=actual_bodies()
    app=create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,content=bodies[r.url.params['sqlId']])),runtime_role='API')
    with TestClient(app) as client:
        base=start(client);original=client.post(base+'/post-close-packets',json={'basis':'Original predecessor retains identity'}).json()
        raw=client.post(base+'/sse-company-actions',json={'basis':'Offline fixed raw dependency originals'}).json()
        assessed=client.post(base+'/sse-action-assessments',json={'source_receipt_id':raw['receipt_id'],'basis':'Explicit dependency-bound assessment'}).json()
        packet=client.post(base+'/sse-action-packets',json={'source_receipt_id':raw['receipt_id'],
            'assessment_ids':[assessed['assessment_id']],'predecessor_packet_id':original['packet_id'],'basis':'Fixed source and assessment IDs'}).json()
        sha={'raw':raw['responses']['dividend']['archive']['sha256'],'mapping':assessed['schema_mapping_hash'],
             'assessment':assessed['archive']['sha256'],'plan':raw['capture_plan_archive']['sha256']}[dependency]
        # Pre-agreed narrow archive damage seam; only the isolated test's archived file.
        app.state.evidence.raw(sha).write_bytes(b'corrupt isolated archive')
        assert client.get(base+'/sse-action-assessments/current').status_code==409
        assert client.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay').status_code==409

def test_action_successor_consumes_price_predecessor_without_changing_quote_or_ungranted_caller(tmp_path,monkeypatch):
    from test_sse_company_contract import snap,company
    method_clock(monkeypatch)
    monkeypatch.setattr('roll.market.sse_price_quotes.now',lambda:'2026-10-11T21:00:00+08:00')
    bodies=actual_bodies();calls=[]
    def supplier(request):
        calls.append(request)
        if request.url.path=='/commonQuery.do':return httpx.Response(200,content=bodies[request.url.params['sqlId']])
        return httpx.Response(200,json=snap() if request.url.host=='yunhq.sse.com.cn' else company())
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(supplier),runtime_role='API')) as client:
        base=start(client)
        source=client.post(base+'/sse-company-contract',json={'basis':'Existing company client METHOD source'}).json()
        original=client.post(base+'/post-close-packets',json={'basis':'Existing original daily source packet'}).json()
        quote=client.post(base+'/sse-price-quotes',json={'source_receipt_id':source['receipt_id'],'basis':'Existing explicit quote successor'}).json()
        price=client.post(base+'/sse-price-packets',json={'source_receipt_id':source['receipt_id'],
            'assessment_ids':[quote['assessment_id']],'predecessor_packet_id':original['packet_id'],'basis':'Existing fixed price consumer'}).json()
        raw=client.post(base+'/sse-company-actions',json={'basis':'Offline action source observation'}).json()
        action=client.post(base+'/sse-action-assessments',json={'source_receipt_id':raw['receipt_id'],'basis':'Explicit finite action observation'}).json()
        response=client.post(base+'/sse-action-packets',json={'source_receipt_id':raw['receipt_id'],
            'assessment_ids':[action['assessment_id']],'predecessor_packet_id':price['packet_id'],'basis':'Explicit action successor on saved price packet'})
        assert response.status_code==201,response.text
        packet=response.json()
        assert packet['predecessor']==price and price['predecessor']==original
        assert not packet['forward_admissible'] and not packet['system_usable']
        for saved in [original,price,packet]:
            assert client.post('/api/research/post-close-packets/'+saved['packet_id']+'/replay').json()['matches_original']
        assert client.get(base+'/sse-price-packets/'+price['packet_id']).json()==price
        current=client.get('/api/actions/current?instrument=SSE:600362').json()
        assert current['decisions']==[] and current['evaluation'] is None
        assert client.get(base+'/source-gaps').json()['action_assessments']==[action]
        assert len(calls)==4

def test_action_packet_refuses_duplicate_missing_future_and_mismatched_assessment_ids(tmp_path,monkeypatch):
    method_clock(monkeypatch);bodies=actual_bodies()
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,content=bodies[r.url.params['sqlId']])),runtime_role='API')) as client:
        base=start(client);original=client.post(base+'/post-close-packets',json={'basis':'Original fixed predecessor'}).json()
        raw=client.post(base+'/sse-company-actions',json={'basis':'Offline raw source observation'}).json()
        assessment_command={'source_receipt_id':raw['receipt_id'],'basis':'Known finite action assessment'}
        known=client.post(base+'/sse-action-assessments',json=assessment_command).json()
        command={'source_receipt_id':raw['receipt_id'],'assessment_ids':[known['assessment_id']],
                 'predecessor_packet_id':original['packet_id'],'basis':'Exact known source and assessment selection'}
        for ids in [[known['assessment_id'],known['assessment_id']],['missing']]:
            assert client.post(base+'/sse-action-packets',json={**command,'assessment_ids':ids}).status_code==409
        assert client.post(base+'/sse-action-packets',json={**command,'source_receipt_id':None}).status_code==409
        monkeypatch.setattr('roll.market.sse_action_assessments.now',lambda:'2026-10-11T22:00:00+08:00')
        future=client.post(base+'/sse-action-assessments',json=assessment_command).json()
        method_clock(monkeypatch)
        assert client.post(base+'/sse-action-packets',json={**command,'assessment_ids':[future['assessment_id']]}).status_code==409
        assert client.get(base+'/sse-action-assessments').json()==[known]

def test_raw_first_two_exact_requests_are_archived_without_claiming_action_semantics(tmp_path,monkeypatch):
    method_clock(monkeypatch)
    calls=[];bodies={FH:b'{"opaque":"fixed supplier, no event schema claim"}',SG:b'[]'}
    def supplier(request):
        calls.append(request)
        return httpx.Response(200,content=bodies[request.url.params['sqlId']])
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(supplier),runtime_role='API')) as client:
        base=start(client)
        response=client.post(base+'/sse-company-actions',json={'basis':'METHOD exact bounded documentary requests'})
        assert response.status_code==201,response.text
        receipt=response.json()
        assert receipt['evidence_kind']=='METHOD_CASE' and receipt['network_calls']==2
        assert receipt['request_budget_calls']==2 and len(calls)==2
        assert {r.url.path for r in calls}=={'/commonQuery.do'} and {r.url.host for r in calls}=={'query.sse.com.cn'}
        shared={'isPagination':'true','pageHelp.pageSize':'5','pageHelp.pageNo':'1','pageHelp.beginPage':'1',
                'pageHelp.cacheSize':'1','pageHelp.endPage':'1','COMPANY_CODE':'600362','IS_STAR':'0'}
        assert dict(calls[0].url.params)=={**shared,'sqlId':FH,'CONDITION_ZBA':'1','CONDITION_ZBB':''}
        assert dict(calls[1].url.params)=={**shared,'sqlId':SG}
        assert receipt['query_date_scope']=='UNKNOWN' and receipt['assessment_state']=='RAW_ONLY_UNASSESSED'
        assert receipt['action_events']==[] and not receipt['complete_action_coverage'] and not receipt['system_usable']
        assert receipt['forward_started_at'] is None and receipt['capability']=='NOT_GRANTED'
        for role,sql in [('dividend',FH),('send_share',SG)]:
            archive=receipt['responses'][role]['archive']
            assert archive['sha256']==hashlib.sha256(bodies[sql]).hexdigest()
            assert client.get('/api/data/archives/'+archive['sha256']).content==bodies[sql]
        assert client.get(base+'/sse-company-action-receipts').json()==[receipt]
        assert client.post(base+'/sse-company-actions',json={'basis':'Repeated trigger must reuse original receipt'}).json()==receipt
        assert len(calls)==2 and client.get('/api/account').json()['version']==0

def test_error_body_is_complete_raw_but_never_an_action_assessment(tmp_path,monkeypatch):
    method_clock(monkeypatch)
    calls=[]
    def supplier(request):
        calls.append(request)
        return httpx.Response(503 if request.url.params['sqlId']==FH else 200,content=b'upstream error' if request.url.params['sqlId']==FH else b'[]')
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(supplier),runtime_role='API')) as client:
        base=start(client)
        receipt=client.post(base+'/sse-company-actions',json={'basis':'Retain actual HTTP error bytes'}).json()
        raw=receipt['responses']['dividend']
        assert raw['archive']['status_code']==503 and raw['error']=='HTTPStatusError'
        assert raw['original_complete'] and raw['archive']['original_complete']
        assert client.get('/api/data/archives/'+raw['archive']['sha256']).content==b'upstream error'
        assert receipt['status']=='REFUSED_RAW_PARTIAL' and receipt['action_events']==[]
        assert len(calls)==2 and not receipt['complete_action_coverage']

class SlowExternalBody(httpx.SyncByteStream,httpx.AsyncByteStream):
    def __iter__(self):
        yield b'prefix';time.sleep(20);yield b'late'
    async def __aiter__(self):
        yield b'prefix';await asyncio.sleep(20);yield b'late'

def test_fifteen_second_attempt_deadline_keeps_prefix_and_has_no_retry(tmp_path,monkeypatch):
    method_clock(monkeypatch)
    calls=[]
    def supplier(request):
        calls.append(request)
        return httpx.Response(200,stream=SlowExternalBody()) if request.url.params['sqlId']==FH else httpx.Response(200,content=b'[]')
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(supplier),runtime_role='API')) as client:
        base=start(client);began=time.monotonic()
        receipt=client.post(base+'/sse-company-actions',json={'basis':'Bound a slow external stream by elapsed deadline'}).json()
        elapsed=time.monotonic()-began
        assert elapsed<18,elapsed
        first=receipt['responses']['dividend']
        assert first['error'] in ['TimeoutError','ReadTimeout'] and not first['original_complete']
        assert first['cancelled'] and first['original_completeness']=='UNKNOWN_AFTER_CANCELLATION'
        assert first['archive']['original_completeness']=='UNKNOWN_AFTER_CANCELLATION'
        assert client.get('/api/data/archives/'+first['archive']['sha256']).content==b'prefix'
        assert receipt['network_calls']==2 and len(calls)==2
