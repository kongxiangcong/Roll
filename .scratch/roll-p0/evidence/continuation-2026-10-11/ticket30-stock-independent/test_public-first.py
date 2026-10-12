"""Independent offline METHOD API/SQLite checks, no new external requests or fits."""
import json,time
from pathlib import Path
from datetime import datetime,timedelta
import httpx
from fastapi.testclient import TestClient
from roll.app import create_app
from test_sse_stock_suspension import clock,interval,start
from test_sse_current_suspension import test_existing_worker_job_records_one_bounded_suspension_receipt_without_hidden_retries as worker_case

SOURCE=Path('D:/dsh-proj/Roll/.scratch/worktrees/ticket30-producer')
RAW=SOURCE/'.scratch/roll-p0/evidence/30-sse-stock-suspension/runtime/source-assessment'
DAY=(RAW/'f45a2a21a972c1150d69db7a60e8506932974bc1bdd216d3f6d052a5cdc7fc22.raw').read_bytes()
EMPTY=(RAW/'7fd45879b5af75c7e0cb7f4c92ce9ad6fa31ddca8ad472deb83b66f3bbfd1c6f.raw').read_bytes()
def record(path,name,value):(path/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def test_actual_raw_unknown_fixed_empty_and_nonempty_ids_restart_and_tamper(tmp_path,monkeypatch):
    clock(monkeypatch);calls=[];interval_count=[0]
    def supply(r):
        calls.append(str(r.url))
        if r.url.params['sqlId'].endswith('TRADEDAY'):return httpx.Response(200,content=DAY)
        interval_count[0]+=1
        return httpx.Response(200,content=EMPTY) if interval_count[0]==1 else httpx.Response(200,json=interval())
    data=tmp_path/'data';app=create_app(data,market_transport=httpx.MockTransport(supply),runtime_role='API')
    with TestClient(app) as c:
        pid=start(c);base=f'/api/research/collections/{pid}'
        old=c.post(base+'/post-close-packets',json={'basis':'独立原空ID列表'}).json()
        assert old['stock_suspension_receipts']==[]
        first=c.post(base+'/sse-stock-suspension',json={'basis':'归档实际raw只作离线METHOD'}).json()
        assert first['status']=='REPORTED_PARTIAL' and first['evidence_kind']=='METHOD_CASE'
        assert first['network_calls']==2 and first['request_budget_calls']==3
        assert first['reported_before_trade_day']=='2026-10-09'
        assert first['requested_interval']['start_date']=='2026-10-09'
        assert first['requested_interval']['end_date']=='2026-10-11'
        assert first['events']==[] and first['declared_total']==first['reported_page_count']==0
        assert not first['latest_trade_day_verified'] and not first['no_event_authority'] and not first['complete_status_verified']
        assert first['system_usable'] is False and first['forward_started_at'] is None
        assert first['trade_day_page']['reported_metadata']['response_date_reported']==''
        assert first['capture_plan']['created_at']<=first['trade_day_page']['archive']['received_at']
        assert c.get('/api/data/archives/'+first['capture_plan_archive']['sha256']).json()==first['capture_plan']
        frozen=c.post(base+'/post-close-packets',json={'basis':'冻结第一次receipt ID'}).json()
        second=c.post(base+'/sse-stock-suspension',json={'basis':'同cutoff追加reported事件，不改旧选择'}).json()
        assert second['events'][0]['resume_date'] is None and second['events'][0]['suspension'] is None
        new=c.post(base+'/post-close-packets',json={'basis':'新选择保留两个IDs'}).json()
        assert [r['receipt_id'] for r in frozen['stock_suspension_receipts']]==[first['receipt_id']]
        assert [r['receipt_id'] for r in new['stock_suspension_receipts']]==[first['receipt_id'],second['receipt_id']]
        for packet in [old,frozen,new]:
            assert packet['forward_started_at'] is None and not packet['forward_admissible']
            assert c.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay').json()['matches_original']
        assert c.get('/api/account').json()['version']==0
        assert len(calls)==4
        record(tmp_path,'literal-receipts',{'first':first,'second':second,'old':old,'frozen':frozen,'new':new,'mock_requests':calls})
    def forbidden(r):raise AssertionError('Offline restart/replay must not fetch')
    app=create_app(data,market_transport=httpx.MockTransport(forbidden),runtime_role='API')
    with TestClient(app) as c:
        assert [r['receipt_id'] for r in c.get(base+'/sse-stock-suspension-receipts').json()]==[first['receipt_id'],second['receipt_id']]
        for dependency in [first['trade_day_page']['archive']['sha256'],first['capture_plan_archive']['sha256'],first['schema_mapping_hash']]:
            p=app.state.evidence.raw(dependency);original=p.read_bytes()
            try:
                p.write_bytes(b'independent METHOD damaged dependency')
                assert c.get(base+'/sse-stock-suspension-receipts').status_code==409
                assert c.post('/api/research/post-close-packets/'+frozen['packet_id']+'/replay').status_code==409
            finally:p.write_bytes(original)
        assert c.post('/api/research/post-close-packets/'+frozen['packet_id']+'/replay').json()['matches_original']

def test_date_security_page_budget_refusals_and_source_off_zero_calls(tmp_path,monkeypatch):
    clock(monkeypatch);reports=[]
    for fault in ['missing','security','page','budget','disabled']:
        calls=[]
        def supply(r):
            calls.append(str(r.url))
            if r.url.params['sqlId'].endswith('TRADEDAY'):
                return httpx.Response(200,json={'sqlId':'GW_PL_JYTS_TFPXX_TRADEDAY','result':[]}) if fault=='missing' else httpx.Response(200,content=DAY)
            n=int(r.url.params['pageHelp.pageNo']);v=interval(total=3,n=n,pages=3) if fault=='budget' else interval()
            if fault=='security':v['result'][0]['productCode']='600000'
            if fault=='page':v['pageHelp']['pageSize']=1000
            if fault=='budget':v['result'][0]['stopTime']='WH' if n==1 else 'AM'
            return httpx.Response(200,json=v)
        with TestClient(create_app(tmp_path/fault,market_transport=httpx.MockTransport(supply),runtime_role='API')) as c:
            pid=start(c);base=f'/api/research/collections/{pid}'
            if fault=='disabled':
                assert c.post('/api/research/collection-sources/sse-stock-suspension-interval/policy',json={'enabled':False,'expected_revision':1,'basis':'独立关闭本来源'}).status_code==200
            response=c.post(base+'/sse-stock-suspension/check',json={'basis':'独立持久有界任务'});assert response.status_code==201,response.text
            job=response.json();receipt=c.get(base+'/sse-stock-suspension-receipts').json()[0]
            assert receipt['network_calls']==len(calls)==({'missing':1,'security':2,'page':2,'budget':3,'disabled':0}[fault])
            assert receipt['system_usable'] is False and not receipt['complete_status_verified']
            assert c.post(base+'/sse-stock-suspension/check',json={'basis':'重试不增预算'}).json()==job
            if fault=='budget':
                assert receipt['status']=='REPORTED_PARTIAL' and len(receipt['events'])==2
                assert receipt['declared_total']==3 and 'SSE_STOCK_PAGE_BUDGET_EXHAUSTED' in receipt['gaps']
            else:
                assert receipt['status']=='REFUSED' and receipt['events']==[]
                if fault=='disabled':assert 'SOURCE_DISABLED' in receipt['errors']
                else:assert c.get('/api/data/archives/'+receipt['trade_day_page']['archive']['sha256']).status_code==200
            for extra in [{'latest_trade_day_verified':True},{'system_usable':True},{'startStopDate':'20130101'}]:
                assert c.post(base+'/sse-stock-suspension',json={'basis':'不接受客户端权限/日期',**extra}).status_code==422
            assert c.get('/api/account').json()['version']==0
            reports.append({'fault':fault,'job':job,'receipt':receipt,'mock_requests':calls})
    record(tmp_path,'refusals',reports)

def test_shared_worker_and_restart_cache(tmp_path,monkeypatch):
    worker_case(tmp_path,monkeypatch)
    def forbidden(r):raise AssertionError('Cached source worker must not refetch')
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(forbidden),runtime_role='API')) as c:
        pid=c.get('/api/research/collections').json()[0]['plan_id'];base=f'/api/research/collections/{pid}'
        receipt=c.get(base+'/sse-stock-suspension-receipts').json()[0]
        job=c.post(base+'/sse-stock-suspension/check',json={'basis':'独立重启读取已存once job'}).json()
        assert job['receipt_id']==receipt['receipt_id'] and job['state']=='RECORDED'
        assert c.get('/api/account').json()['version']==0
        record(tmp_path,'worker-cache',{'receipt':receipt,'job':job})

def test_after27_real_worker_paused_loop_keeps_fixed_facts_without_capture(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test');clock(monkeypatch);data=tmp_path/'data'
    def source(r):return httpx.Response(200,content=DAY if r.url.params['sqlId'].endswith('TRADEDAY') else EMPTY)
    with TestClient(create_app(data,market_transport=httpx.MockTransport(source),runtime_role='API')) as c:
        pid=start(c);base=f'/api/research/collections/{pid}'
        receipt=c.post(base+'/sse-stock-suspension',json={'basis':'先保存独立METHOD事实'}).json()
        packet=c.post(base+'/post-close-packets',json={'basis':'固定先前事实IDs'}).json()
        queued=c.post('/api/reviews/tasks',json={'refresh_missing':False});assert queued.status_code==202,queued.text
        pause=c.post('/api/capabilities/lifecycle',json={'scope':'ALL_MONITOR','state':'SUSPENDED','reason_code':'USER_PAUSE','reason':'独立暂停自动观察','expected_version':0,'idempotency_key':'pause-auto'})
        assert pause.status_code==200,pause.text
        assert c.get('/api/reviews/tasks/'+queued.json()['task_id']).json()['status']=='CANCELLED'
    attempts=[]
    def forbidden(r):attempts.append(str(r.url));raise AssertionError('Paused automatic worker cannot capture')
    observed=[datetime.fromisoformat('2026-10-12T15:31:00+08:00')]
    with TestClient(create_app(data,market_transport=httpx.MockTransport(forbidden),runtime_role='WORKER',review_clock=lambda:observed[0])) as c:
        for pulse in range(3):
            observed[0]+=timedelta(minutes=2);deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                coverage=c.get('/api/reviews/coverage').json()
                if coverage['sessions'][-1]['last_seen_at']==observed[0].isoformat():break
                time.sleep(.05)
            assert coverage['sessions'][-1]['last_seen_at']==observed[0].isoformat(),coverage
        assert attempts==[]
        assert c.get(base+'/sse-stock-suspension-receipts').json()==[receipt]
        assert c.get(base+'/source-gaps').json()['stock_suspension_jobs']==[]
        assert c.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay').json()['matches_original']
        assert c.post('/api/reviews/tasks',json={'refresh_missing':False}).status_code==409
        assert c.get('/api/account').json()['version']==0 and c.post('/api/runtime/backups').status_code==201
        record(tmp_path,'paused-real-worker',{'coverage':coverage,'source_receipt_id':receipt['receipt_id'],'mock_requests':attempts,'registered_forward_plan':False})
