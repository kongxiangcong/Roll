import hashlib,json,httpx
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app
from test_post_close_packet import setup
from test_sse_current_suspension import page,clocks
from test_sse_current_suspension import test_existing_worker_job_records_one_bounded_suspension_receipt_without_hidden_retries as worker_case

PROOF=Path('D:/dsh-proj/Roll/.scratch/worktrees/ticket30-producer/.scratch/roll-p0/evidence/30-sse-current-suspension/runtime/source-assessment')
SHA='986c403e89bf4aab9f260034f1d301126daa0de9ff62926f90cf798768eeb958'
def test_saved_real_raw_is_method_partial_empty_ids_restart_and_corruption(tmp_path,monkeypatch):
    clocks(monkeypatch,'2026-10-11T16:14:06+08:00')
    raw=(PROOF/(SHA+'.raw')).read_bytes();assert len(raw)==13367 and hashlib.sha256(raw).hexdigest()==SHA
    original=json.loads(raw);assert original['queryDate']=='' and original['pageHelp']['searchDate'] is None
    assert original['pageHelp']['total']==26 and len(original['result'])==26
    assert all(row['PRODUCT_CODE']!='600362' and row['SHOW_END_DATE']=='-' for row in original['result'])
    calls=[]
    def supplier(r):calls.append(r);return httpx.Response(200,content=raw)
    app=create_app(tmp_path,market_transport=httpx.MockTransport(supplier),runtime_role='API')
    with TestClient(app) as c:
        plan=c.post('/api/research/collections',json={'instrument':'SSE:600362','basis':'Independent offline METHOD'});assert plan.status_code==201,plan.text
        base='/api/research/collections/'+plan.json()['plan_id'];account=c.get('/api/account').json()
        old=c.post(base+'/post-close-packets',json={'basis':'Original no receipt packet'});assert old.status_code==201,old.text
        old=old.json();assert old['suspension_receipts']==[]
        receipt=c.post(base+'/sse-suspension',json={'basis':'Archived actual public body supplied METHOD'});assert receipt.status_code==201,receipt.text
        r=receipt.json();assert r['status']=='REPORTED_PARTIAL' and r['evidence_kind']=='METHOD_CASE'
        assert r['query_date']=='2026-10-11' and r['network_calls']==1 and r['request_budget_pages']==2
        assert calls[0].url.params['SEARCH_DATE']=='2026-10-11'
        assert calls[0].url.params['pageHelp.pageNo']=='1'
        assert r['returned_count']==r['declared_total']==26 and r['events']==[] and r['returned_count_matches_positive_total']
        assert not r['no_event_authority'] and not r['complete_status_verified'] and not r['system_usable']
        assert not r['page_audits'][0]['response_date_verified'] and r['forward_started_at'] is None and r['capability']=='NOT_GRANTED'
        assert r['pages'][0]['archive']['sha256']==SHA and c.get('/api/data/archives/'+SHA).content==raw
        new=c.post(base+'/post-close-packets',json={'basis':'Bind exact source ID'}).json();assert new['suspension_receipts']==[r]
        assert not new['forward_admissible'] and new['forward_started_at'] is None
        assert c.post(base+'/sse-suspension',json={'basis':'Same cutoff new explicit assessment'}).status_code==201
        replay='/api/research/post-close-packets/'+new['packet_id']+'/replay'
        oldreplay='/api/research/post-close-packets/'+old['packet_id']+'/replay'
        assert c.post(replay).json()['matches_original'] and c.post(oldreplay).json()['matches_original']
        assert len(calls)==2
        for sha in [SHA,r['query_js_hash'],r['schema_mapping_hash'],r['archive']['sha256']]:
            path=app.state.evidence.raw(sha);body=path.read_bytes();path.write_bytes(b'own corrupt fixture')
            assert c.get(base+'/sse-suspension-receipts').status_code==409
            assert c.post(replay).status_code==409
            assert c.post(oldreplay).status_code==200
            path.write_bytes(body);assert c.post(replay).json()['matches_original']
        gaps=c.get(base+'/source-gaps').json();assert len(gaps['suspension_receipts'])==2 and gaps['capability']=='NOT_GRANTED'
        assert c.get('/api/account').json()==account and account['version']==0
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:(_ for _ in ()).throw(AssertionError('offline restart'))),runtime_role='API')) as c:
        assert c.post(replay).json()['matches_original'] and c.post(oldreplay).json()['matches_original']
        assert c.get('/api/account').json()['version']==0

def test_literal_refusals_raw_first_budget_and_source_disabled(tmp_path,monkeypatch):
    clocks(monkeypatch);mode=['date'];calls=[]
    def supplier(r):
        n=int(r.url.params['pageHelp.pageNo']);calls.append((mode[0],n))
        value=page()
        if mode[0]=='date':value['result'][0]['SHOW_END_DATE']='2026-10-11'
        elif mode[0]=='security':value['result'][0]['PRODUCT_CODE']='600362?'
        elif mode[0]=='page':value['pageHelp']['pageNo']=2
        elif mode[0]=='echo':value['queryDate']='2016-02-16'
        elif mode[0]=='budget':
            rows=[{'PRODUCT_CODE':str(600000+i+100*(n-1))} for i in range(100)]
            if n==2:rows[-1]=page()['result'][0]
            value=page(rows,total=201,page_no=n,page_count=3)
        return httpx.Response(200,json=value)
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(supplier),runtime_role='API')) as c:
        pid=setup(c);base='/api/research/collections/'+pid
        for fault in ['date','security','page','echo']:
            mode[0]=fault;r=c.post(base+'/sse-suspension',json={'basis':'Independent explicit refusal '+fault});assert r.status_code==201,r.text
            r=r.json();assert r['status']=='REFUSED' and r['events']==[]
            if fault=='echo':
                assert r['network_calls']==0 and r['pages']==[] and 'SOURCE_COOLDOWN' in r['errors']
                continue
            assert r['network_calls']==1
            p=r['pages'][0];assert p['reported_metadata']['declared_total']==1
            original=c.get('/api/data/archives/'+p['archive']['sha256']);assert original.status_code==200
            assert hashlib.sha256(original.content).hexdigest()==p['archive']['sha256']
            assert c.get(base+'/sse-suspension-receipts').status_code==200
    # Three prior failures correctly cooled down that source. A separate fresh
    # fixture tests the remaining response-date parser and bounded page budget.
    with TestClient(create_app(tmp_path/'remaining',market_transport=httpx.MockTransport(supplier),runtime_role='API')) as c:
        pid=setup(c);base='/api/research/collections/'+pid
        mode[0]='echo';r=c.post(base+'/sse-suspension',json={'basis':'Fresh date echo mismatch'}).json()
        assert r['status']=='REFUSED' and r['network_calls']==1 and 'SSE_SUSPENSION_RESPONSE_DATE_MISMATCH' in r['errors']
        assert r['pages'][0]['reported_metadata']['response_date_reported']=='2016-02-16'
        mode[0]='budget';r=c.post(base+'/sse-suspension',json={'basis':'At most two pages'}).json()
        assert calls[-2:]==[('budget',1),('budget',2)] and r['network_calls']==2
        assert r['declared_total']==201 and r['returned_count']==200
        assert 'SSE_SUSPENSION_PAGE_BUDGET_EXHAUSTED' in r['gaps']
        assert r['events'][0]['source_page_no']==2 and r['events'][0]['row_ordinal']==99
        assert r['events'][0]['reported_end_date']=='2026-10-20' and r['events'][0]['resume_date'] is None
        assert not r['complete_status_verified'] and not r['no_event_authority']
        for field in ['query_date','complete_status_verified','evidence_kind']:
            assert c.post(base+'/sse-suspension',json={'basis':'Reject client authority',field:True}).status_code==422
        count=len(calls)
        assert c.post('/api/research/collection-sources/sse-suspension-date/policy',json={'enabled':False,'expected_revision':1,'basis':'Independent source off'}).status_code==200
        job=c.post(base+'/sse-suspension/check',json={'basis':'No network when disabled'}).json()
        assert job['state']=='RECORDED' and 'SOURCE_DISABLED' in job['gaps']
        assert c.post(base+'/sse-suspension/check',json={'basis':'Repeat cached'}).json()==job
        assert len(calls)==count

def test_existing_worker_loop_bounded_same_day_source_composition(tmp_path,monkeypatch):
    worker_case(tmp_path,monkeypatch)
