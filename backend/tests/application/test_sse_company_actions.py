"""Finite raw-first action source receipt, without guessed response/lifecycle semantics."""
import hashlib
import httpx
import asyncio
import time
import pytest
from fastapi.testclient import TestClient
from roll.app import create_app
from test_sse_company_contract import clock, start

FH='COMMON_SSE_CP_GPJCTPZ_GPLB_LRFP_FH_L'
SG='COMMON_SSE_CP_GPJCTPZ_GPLB_LRFP_SG_L'

def method_clock(monkeypatch):
    clock(monkeypatch,'2026-10-11T21:00:00+08:00')
    monkeypatch.setattr('roll.market.sse_company_actions.now',lambda:'2026-10-11T21:00:00+08:00')
    # This is only the pre-agreed METHOD clock; Host/registry clocks remain unchanged.

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
