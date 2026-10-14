import json
import httpx
from fastapi.testclient import TestClient
from roll.app import create_app


def test_status_evidence_preserves_reported_listing_and_historical_unknown(tmp_path,monkeypatch):
    stamp='2026-10-11T18:00:00+08:00'
    for module in ['roll.market.post_close_packet','roll.market.sse_company_contract','roll.research.prospective','roll.market.evidence']:
        monkeypatch.setattr(module+'.now',lambda:stamp)
    snap={'code':'600362','date':20261009,'time':150004,'snap':['江西铜业',44.01,1,.44,1234567.89,12345,43,43.57,[],[],45,42,' E1 ',125,0,3,0,48,39,None,0,'opaque-status','opaque-limit','']}
    company={'sqlId':'COMMON_SSE_CP_GPJCTPZ_GPLB_GPGK_GSGK_C','isPagination':'false','result':[{'COMPANY_CODE':'600362','A_STOCK_CODE':'600362','SEC_TYPE':'主板A','STATE_CODE_A_DESC':'上市','A_LIST_DATE':'2002-01-11','STATUS_A':'opaque'}]}
    calls=[]
    def source(request):
        calls.append(request)
        return httpx.Response(200,content=json.dumps(snap if request.url.host=='yunhq.sse.com.cn' else company,ensure_ascii=False).encode())
    transport=httpx.MockTransport(source)
    with TestClient(create_app(tmp_path,market_transport=transport,runtime_role='API')) as client:
        plan=client.post('/api/research/collections',json={'instrument':'SSE:600362','basis':'Isolated state query'}).json()
        base='/api/research/collections/'+plan['plan_id']
        receipt=client.post(base+'/sse-company-contract',json={'basis':'Pinned state evidence fixture'}).json()
        query=client.get(base+'/status-evidence',params={'known_by':stamp})
        assert query.status_code==200,query.text
        value=query.json()
        assert value['state']=='UNKNOWN' and not value['negative_coverage_verified']
        assert value['company_observations'][0]['company_state_reported']=='上市'
        assert value['company_observations'][0]['effective_at'] is None
        assert value['receipt_ids']==[receipt['receipt_id']]
        assert value['network_calls']==0 and value['capability']=='NOT_GRANTED'
        earlier=client.get(base+'/status-evidence',params={'known_by':'2026-10-11T17:59:59+08:00'}).json()
        assert earlier['receipt_ids']==[] and earlier['state']=='UNKNOWN'
        assert len(calls)==2
        current=client.get(base+'/status-evidence')
        assert current.status_code==200,current.text
        assert current.json()['company_observations'][0]['company_state_reported']=='上市'
    with TestClient(create_app(tmp_path,market_transport=transport,runtime_role='API')) as client:
        assert client.get(base+'/status-evidence',params={'known_by':stamp}).json()==value
        assert client.get('/api/account').json()['version']==0
    assert len(calls)==2


def test_reported_suspension_dates_do_not_certify_resumption_or_full_status(tmp_path,monkeypatch):
    from test_sse_current_suspension import page,clocks
    stamp='2026-10-12T15:06:00+08:00'
    clocks(monkeypatch,stamp)
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,json=page())),runtime_role='API')) as client:
        plan=client.post('/api/research/collections',json={'instrument':'SSE:600362','basis':'Isolated suspension query'}).json()
        base='/api/research/collections/'+plan['plan_id']
        captured=client.post(base+'/sse-suspension',json={'basis':'Explicit METHOD suspension query'})
        assert captured.status_code==201,captured.text
        query=client.get(base+'/status-evidence',params={'known_by':stamp}).json()
        assert query['state']=='UNKNOWN'
        event=query['suspension_observations'][0]
        assert event['suspension'] is True
        assert event['reported_start_date']=='2026-10-12' and event['reported_end_date']=='2026-10-20'
        assert event['resume_date'] is None
