"""Seventh independent public API fresh METHOD only; saved raw are immutable inputs."""
import json,time
from pathlib import Path
from datetime import datetime,timedelta
import httpx
from fastapi.testclient import TestClient
from roll.app import create_app

SOURCE=Path('D:/dsh-proj/Roll/.scratch/worktrees/ticket30-producer')
RAW=SOURCE/'.scratch/roll-p0/evidence/30-sse-company-contract/runtime/source-assessment'
SNAP=(RAW/'bc0971238819277c2b9d6773e341c6d12496adb7991fc897000974cbb2942403.raw').read_bytes()
COMPANY=(RAW/'4e4bd76727f03b989b98f923c65c2d3d99816f6683172dba4ab7e148b6c2fb7a.raw').read_bytes()
def clock(mp):
    for m in ['roll.market.post_close_packet','roll.market.sse_company_contract','roll.research.prospective','roll.market.evidence']:
        mp.setattr(m+'.now',lambda:'2026-10-11T19:00:00+08:00')
def start(c):
    r=c.post('/api/research/collections',json={'instrument':'SSE:600362','basis':'Independent isolated METHOD contract'})
    assert r.status_code==201,r.text
    return '/api/research/collections/'+r.json()['plan_id']
def record(p,n,v):(p/(n+'.json')).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def test_actual_literals_pinned_ids_restart_and_damage(tmp_path,monkeypatch):
    clock(monkeypatch);calls=[];data=tmp_path/'data'
    def supply(r):
        calls.append(str(r.url));return httpx.Response(200,content=SNAP if r.url.host=='yunhq.sse.com.cn' else COMPANY)
    with TestClient(create_app(data,market_transport=httpx.MockTransport(supply),runtime_role='API')) as c:
        base=start(c)
        old=c.post(base+'/post-close-packets',json={'basis':'Pin original empty IDs'}).json()
        assert old['company_contract_receipts']==[]
        job=c.post(base+'/sse-company-contract/check',json={'basis':'Bounded original assessment METHOD'}).json()
        receipt=c.get(base+'/sse-company-contract-receipts').json()[0];q=receipt['quote_fact'];s=receipt['company_fact']
        assert receipt['evidence_kind']=='METHOD_CASE' and len(calls)==receipt['network_calls']==2
        assert q['volume_raw']=='31419158' and q['amount_raw']=='1314805240'
        assert q['display_volume_hands_exact']=='314191.58' and q['display_amount_10000_cny_exact']=='131480.524'
        assert q['tradephase_original']=='E110    ' and q['tradephase_compact']=='E110' and q['tradephase_display']=='闭市'
        assert q['fp_volume_raw']=='30600' and q['fp_amount_raw']=='1300806.000' and q['fp_phase_original']=='D0      '
        assert q['trade_date']=='2026-10-09' and q['time_display']=='16:29:05'
        for k in ['source_timezone','turnover_scope','completion_state','tradephase_full_semantics','fp_phase_semantics']:assert q[k]=='UNKNOWN'
        assert s['listing_date_reported']=='2002-01-11' and s['status_a_original']=='   D  F  N          '
        for k in ['listing_stage','risk_warning','st_subtype','suspension','resume_date','ex_rights']:assert s[k] is None
        assert s['source_reported_date'] is None and not s['negative_coverage_verified']
        assert not receipt['system_usable'] and not receipt['complete_status_verified'] and not receipt['no_event_authority']
        assert receipt['forward_started_at'] is None and receipt['capability']=='NOT_GRANTED'
        packet=c.post(base+'/post-close-packets',json={'basis':'Fixed original nonempty selection'}).json()
        assert packet['company_contract_receipts']==[receipt] and len(packet['source_contract_facts'])==2
        assert 'SSE_CLIENT_QUOTE_NOT_CURRENT_HOST_DATE' in packet['gaps'] and not packet['forward_admissible']
        later=c.post(base+'/sse-company-contract',json={'basis':'Append same cutoff without reselection'}).json()
        assert later['receipt_id']!=receipt['receipt_id']
        for p in [old,packet]:assert c.post('/api/research/post-close-packets/'+p['packet_id']+'/replay').json()['matches_original']
        assert c.post(base+'/sse-company-contract/check',json={'basis':'Once cache'}).json()==job and len(calls)==4
        assert c.get('/api/account').json()['version']==0
        record(tmp_path,'literals',{'receipt':receipt,'later':later,'old':old,'packet':packet,'job':job,'mock_requests':calls})
    def forbidden(r):raise AssertionError('Restart and replay cannot fetch')
    app=create_app(data,market_transport=httpx.MockTransport(forbidden),runtime_role='API')
    with TestClient(app) as c:
        assert c.post(base+'/sse-company-contract/check',json={'basis':'Restart same job'}).json()==job
        for sha in [receipt['responses']['snap']['archive']['sha256'],receipt['mapping_hash'],receipt['capture_plan_archive']['sha256']]:
            p=app.state.evidence.raw(sha);raw=p.read_bytes()
            try:
                p.write_bytes(b'Independent METHOD damaged original')
                assert c.get(base+'/sse-company-contract-receipts').status_code==409
                assert c.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay').status_code==409
            finally:p.write_bytes(raw)
        assert c.post('/api/research/post-close-packets/'+old['packet_id']+'/replay').json()['matches_original']

def test_exact_decimal_prefix_budget_client_authority_and_disabled(tmp_path,monkeypatch):
    clock(monkeypatch);reports=[]
    for fault in ['precision','future','prefix','disabled']:
        calls=[]
        class Broken(httpx.SyncByteStream):
            def __iter__(self):
                yield b'{"code":"600362","snap":['
                raise httpx.ReadTimeout('Independent METHOD prefix')
        def supply(r):
            calls.append(str(r.url))
            if r.url.host!='yunhq.sse.com.cn':return httpx.Response(200,content=COMPANY)
            if fault=='prefix':return httpx.Response(200,stream=Broken())
            raw=SNAP.replace(b'1314805240',b'12345678901234567890.123456') if fault=='precision' else SNAP.replace(b'20261009',b'20261012')
            return httpx.Response(200,content=raw)
        with TestClient(create_app(tmp_path/fault,market_transport=httpx.MockTransport(supply),runtime_role='API')) as c:
            base=start(c)
            if fault=='disabled':assert c.post('/api/research/collection-sources/sse-company-client-contract/policy',json={'enabled':False,'expected_revision':1,'basis':'Independent source off'}).status_code==200
            for f in ['complete_status_verified','system_usable','actual_forward_start']:
                assert c.post(base+'/sse-company-contract',json={'basis':'Client cannot assert authority',f:True}).status_code==422
            job=c.post(base+'/sse-company-contract/check',json={'basis':'Independent bounded job'}).json()
            r=c.get(base+'/sse-company-contract-receipts').json()[0]
            assert r['network_calls']==len(calls)==(0 if fault=='disabled' else 2)
            assert r['capture_plan']['retries']==r['capture_plan']['fallbacks']==0 and r['request_budget_calls']==2
            assert not r['system_usable'] and not r['complete_status_verified'] and r['forward_started_at'] is None
            if fault=='precision':
                assert r['quote_fact']['amount_raw']=='12345678901234567890.123456'
                assert r['quote_fact']['display_amount_10000_cny_exact']=='1234567890123456.7890123456'
            else:assert r['errors'] and r['quote_fact'] is None
            if fault=='prefix':
                a=r['responses']['snap']['archive'];assert not a['original_complete'] and a['stream_error']=='ReadTimeout'
                assert c.get('/api/data/archives/'+a['sha256']).content==b'{"code":"600362","snap":['
            assert c.post(base+'/sse-company-contract/check',json={'basis':'Cached no new attempt'}).json()==job
            assert len(calls)==(0 if fault=='disabled' else 2) and c.get('/api/account').json()['version']==0
            reports.append({'fault':fault,'job':job,'receipt':r,'mock_requests':calls})
    record(tmp_path,'refusals',reports)

def test_after27_actual_paused_worker_no_capture_existing_company_ids_readable(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test');clock(monkeypatch);data=tmp_path/'data'
    def supply(r):return httpx.Response(200,content=SNAP if r.url.host=='yunhq.sse.com.cn' else COMPANY)
    with TestClient(create_app(data,market_transport=httpx.MockTransport(supply),runtime_role='API')) as c:
        base=start(c);receipt=c.post(base+'/sse-company-contract',json={'basis':'Preserved METHOD facts'}).json()
        packet=c.post(base+'/post-close-packets',json={'basis':'Pin existing IDs'}).json()
        queued=c.post('/api/reviews/tasks',json={'refresh_missing':False});assert queued.status_code==202
        assert c.post('/api/capabilities/lifecycle',json={'scope':'ALL_MONITOR','state':'SUSPENDED','reason_code':'USER_PAUSE','reason':'Independent paused automatic worker','expected_version':0,'idempotency_key':'company-pause'}).status_code==200
        assert c.get('/api/reviews/tasks/'+queued.json()['task_id']).json()['status']=='CANCELLED'
    attempts=[];stamp=[datetime.fromisoformat('2026-10-12T15:31:00+08:00')]
    def forbidden(r):attempts.append(str(r.url));raise AssertionError('Paused loop must not fetch')
    with TestClient(create_app(data,market_transport=httpx.MockTransport(forbidden),runtime_role='WORKER',review_clock=lambda:stamp[0])) as c:
        for _ in range(3):
            stamp[0]+=timedelta(minutes=2);deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                cov=c.get('/api/reviews/coverage').json()
                if cov['sessions'][-1]['last_seen_at']==stamp[0].isoformat():break
                time.sleep(.05)
            assert cov['sessions'][-1]['last_seen_at']==stamp[0].isoformat(),cov
        assert attempts==[] and c.get(base+'/sse-company-contract-receipts').json()==[receipt]
        assert c.get(base+'/source-gaps').json()['company_contract_jobs']==[]
        assert c.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay').json()['matches_original']
        assert c.post('/api/reviews/tasks',json={'refresh_missing':False}).status_code==409
        assert c.get('/api/account').json()['version']==0
        record(tmp_path,'paused-worker',{'coverage':cov,'new_mock_requests':attempts,'registered_forward_plan':False})
