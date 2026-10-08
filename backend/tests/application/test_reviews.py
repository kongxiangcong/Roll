from datetime import datetime
import time
from fastapi.testclient import TestClient
from roll.app import create_app
import httpx
import threading
import sqlite3
from test_market_directory import establish


def wait_result(client, identifier):
    for _ in range(200):
        response=client.get('/api/reviews/tasks/'+identifier)
        assert response.status_code==200,response.text
        value=response.json()
        if value['status'] in {'COMPLETE','PARTIAL','CANCELLED','FAILED','TIMED_OUT'}:
            return value
        time.sleep(.02)
    raise AssertionError('review did not finish')


def test_closed_exchange_on_demand_is_a_complete_fact_flow_without_model_or_daily_check_in(tmp_path):
    clock=lambda:datetime.fromisoformat('2026-10-07T10:00:00+08:00')
    with TestClient(create_app(tmp_path,review_clock=clock)) as client:
        response=client.post('/api/reviews/tasks',json={'mode':'ON_DEMAND'})
        assert response.status_code==202,response.text
        task=wait_result(client,response.json()['task_id'])
        observation=task['result']
        assert observation['calendar']['phase']=='CLOSED'
        assert observation['calendar']['reason']=='HOLIDAY'
        assert observation['account_version']==0
        assert observation['formal_judgment']=='DISABLED'
        assert observation['forecast'] is None
        assert observation['forward_sample_created'] is False
        assert observation['coverage']['intraday_observed'] is False
        assert client.post('/api/reviews/tasks',json={'mode':'ON_DEMAND'}).json()['task_id']==task['task_id']
        assert client.post('/api/reviews/tasks',json={'mode':'ON_DEMAND','cutoff':'2026-10-07T02:00:00+00:00'}).json()['task_id']==task['task_id']
        assert len(client.get('/api/reviews/history').json())==1
    with TestClient(create_app(tmp_path,review_clock=clock)) as client:
        assert client.get('/api/reviews/tasks/'+task['task_id']).json()==task


def test_intraday_current_bar_cannot_replace_last_complete_daily_or_refresh_old_quote_time(tmp_path, method_market_timeline):
    raw=b'{"rc":0,"data":{"code":"600519","market":1,"klines":["2026-09-30,10,10,10,10,100,100000","2026-10-08,10,11,11,10,100,110000"]}}'
    fields=['']*60
    for index,value in {2:'600519',3:'12',4:'10',5:'10',6:'100',30:'20260930161458',33:'12',34:'10',35:'12/100/120000',47:'13.2',48:'10.8'}.items():fields[index]=value
    def provider(request):
        return httpx.Response(200,content=raw if 'kline' in request.url.path else ('v_sh600519="'+'~'.join(fields)+'";').encode())
    consume=method_market_timeline('2026-10-08T10:00:00+08:00')
    clock=lambda:datetime.fromisoformat('2026-10-08T10:00:00+08:00')
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider),review_clock=clock)) as client:
        establish(client,['SSE:600519'])
        client.post('/api/market/identities',json={'instrument':'SSE:600519','exchange':'SSE','board':'MAIN','instrument_type':'STOCK',
            'name':'合成普通股','basis':'合成证券身份','effective_at':'2026-10-07T00:00:00+08:00'})
        request=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['DAILY','QUOTE'],
            'purpose':'OBSERVATION','start_date':'2026-09-30','end_date':'2026-10-08'}).json()
        run=client.post('/api/data/requests/'+request['request_id']+'/retrieve').json()
        before=client.get('/api/account').json()
        consume()  # Advance the recording clock only after the fixed-source acquisition.
        task=wait_result(client,client.post('/api/reviews/tasks',json={'mode':'ON_DEMAND'}).json()['task_id'])
        item=next(i for i in task['result']['instruments'] if i['instrument']=='SSE:600519')
        assert item['last_complete_daily']['trade_date']=='2026-09-30'
        assert item['incomplete_daily']['trade_date']=='2026-10-08'
        assert item['incomplete_daily']['model_daily_input_allowed'] is False
        assert item['quote']['upstream_at']=='2026-09-30T16:14:58+08:00'
        assert item['quote_status']=='STALE_PREVIOUS_SESSION'
        assert datetime.fromisoformat(before['confirmed_at']) < datetime.fromisoformat(request['created_at'])
        assert datetime.fromisoformat(request['created_at']) < datetime.fromisoformat(item['quote']['available_at']) < datetime.fromisoformat(task['result']['knowledge_cutoff'])
        assert task['result']['calendar']['phase']=='CONTINUOUS'
        assert task['result']['data_versions']==[run['snapshot_id']]
        assert task['result']['forecast'] is None
        assert client.get('/api/account').json()==before
        assert any(g['code']=='CURRENT_STATUS_UNKNOWN' for g in task['result']['gaps'])


def test_persistent_worker_retries_with_backoff_once_per_identity_and_preserves_partial_facts(tmp_path):
    def unavailable(request):raise httpx.ConnectTimeout('controlled source timeout')
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(unavailable))) as client:
        establish(client,['SSE:600519'])
        response=client.post('/api/reviews/tasks',json={'mode':'ON_DEMAND','refresh_missing':True})
        assert response.status_code==202,response.text
        identifier=response.json()['task_id']
        health=client.get('/api/reviews/health').json()
        assert health['worker_limit']==1
        assert health['technical_limits']['attempts']==3
        for _ in range(200):
            task=client.get('/api/reviews/tasks/'+identifier).json()
            if task['status']=='RETRY_WAIT':break
            time.sleep(.01)
        assert task['status']=='RETRY_WAIT',task
        assert task['attempts']==1 and task['retry_at']>task['last_attempt_at']
        assert task['result'] is None
        task=wait_result(client,identifier)
        assert task['status']=='PARTIAL' and task['attempts']==3
        assert task['result']['forecast'] is None and task['result']['gaps']
        assert task['timing']['network_seconds']>=0
        assert task['timing']['local_seconds']>=0
        assert len(task['retrieval_runs'])==3
        assert client.post('/api/reviews/tasks',json={'mode':'ON_DEMAND','cutoff':task['inputs']['cutoff'],'refresh_missing':True}).json()['task_id']==identifier
        assert client.get('/api/account').json()['version']==1
        assert client.get('/api/reviews/audits/'+task['audit_id']).json()['metrics']['duplicate_notifications']['value'] is None
        assert client.get('/api/reviews/audits/'+task['audit_id']).json()['metrics']['module_errors']['value']>=3
        assert any(e['code']=='ConnectTimeout' for e in client.get('/api/reviews/audits/'+task['audit_id']).json()['metrics']['module_errors']['errors'])


def test_cancelled_network_task_never_publishes_and_second_host_cannot_duplicate_worker(tmp_path):
    entered=threading.Event();release=threading.Event()
    def delayed(request):
        entered.set();release.wait(2)
        return httpx.Response(503,content=b'controlled unavailable')
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(delayed))) as first:
        establish(first,['SSE:600519'])
        queued=first.post('/api/reviews/tasks',json={'mode':'ON_DEMAND','refresh_missing':True}).json()
        assert entered.wait(2)
        with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(delayed))) as second:
            assert second.get('/api/reviews/health').json()['running']==1
            assert second.get('/api/data/runs').json()[0]['status']=='RUNNING'
            queued_other=second.post('/api/reviews/tasks',json={'mode':'ON_DEMAND'}).json()
            assert second.get('/api/reviews/health').json()['running']==1
            cancel=second.post('/api/reviews/tasks/'+queued['task_id']+'/cancel')
            assert cancel.status_code==200,cancel.text
            assert cancel.json()['status']=='CANCELLED'
            release.set()
            assert wait_result(second,queued_other['task_id'])['result'] is not None
            assert second.get('/api/reviews/tasks/'+queued['task_id']).json()['result'] is None
            assert second.get('/api/account').json()['version']==1
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/reviews/tasks/'+queued['task_id']).json()['status']=='CANCELLED'


def test_successive_actual_observations_link_without_rebuilding_missing_trigger_sequence(tmp_path):
    clock=lambda:datetime.fromisoformat('2026-10-08T10:30:00+08:00')
    with TestClient(create_app(tmp_path,review_clock=clock)) as client:
        first=wait_result(client,client.post('/api/reviews/tasks',json={'mode':'ON_DEMAND','cutoff':'2026-10-08T10:00:00+08:00'}).json()['task_id'])
        second=wait_result(client,client.post('/api/reviews/tasks',json={'mode':'ON_DEMAND','cutoff':'2026-10-08T10:30:00+08:00'}).json()['task_id'])
        assert second['result']['previous_snapshot_id']==first['result']['snapshot_id']
        assert second['result']['change']=='NO_SUBSTANTIAL_CHANGE'
        assert second['result']['coverage']['unobserved_trigger_sequence']=='NOT_RECONSTRUCTED'
        assert second['result']['forward_sample_created'] is False


def test_normal_close_keeps_actual_gap_and_overdue_calendar_maintenance_checked_once_on_resume(tmp_path):
    clock=[datetime.fromisoformat('2026-10-08T16:00:00+08:00')]
    with TestClient(create_app(tmp_path,review_clock=lambda:clock[0])) as client:
        registration=client.post('/api/reviews/maintenance',json={'kind':'WEEKLY','exchange':'SSE',
            'first_due_at':'2026-10-09T16:00:00+08:00'})
        assert registration.status_code==201,registration.text
        schedule=registration.json()
        assert schedule['next_due_at']=='2026-10-09T16:00:00+08:00'
        assert client.get('/api/reviews/maintenance/checks').json()==[]
    clock[0]=datetime.fromisoformat('2026-10-12T10:00:00+08:00')
    with TestClient(create_app(tmp_path,review_clock=lambda:clock[0])) as client:
        response=client.post('/api/reviews/recover')
        assert response.status_code==202,response.text
        recovered=wait_result(client,response.json()['task_id'])
        coverage=client.get('/api/reviews/coverage').json()
        gap=coverage['gaps'][-1]
        assert gap['start']=='2026-10-08T16:00:00+08:00'
        assert gap['end']=='2026-10-12T10:00:00+08:00'
        assert gap['reason']=='NORMAL_OFFLINE_NO_COVERAGE_PROMISED'
        assert recovered['result']['forward_sample_created'] is False
        checks=client.post('/api/reviews/maintenance/check').json()
        assert len(checks)==1
        assert checks[0]['schedule_id']==schedule['schedule_id']
        assert checks[0]['scheduled_at']=='2026-10-09T16:00:00+08:00'
        assert checks[0]['checked_at']=='2026-10-12T10:00:00+08:00'
        assert checks[0]['status']=='OVERDUE_CHECKED'
        assert checks[0]['business_checks']['mature_labels']['status']=='NOT_CONNECTED'
        assert checks[0]['business_checks']['qualification_expiry']['value'] is None
        assert client.post('/api/reviews/maintenance/check').json()==checks
        assert client.get('/api/reviews/maintenance').json()[0]['next_due_at']=='2026-10-16T16:00:00+08:00'


def test_shutdown_keeps_lease_until_actual_network_worker_stops_before_peer_takes_over(tmp_path):
    entered=threading.Event();release=threading.Event();closed=threading.Event()
    calls=[]
    def delayed(request):
        calls.append(str(request.url));entered.set();release.wait(10)
        return httpx.Response(503,content=b'controlled blocked network boundary')
    first=TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(delayed)))
    first.__enter__()
    establish(first,['SSE:600519'])
    first.post('/api/reviews/tasks',json={'mode':'ON_DEMAND','refresh_missing':True})
    assert entered.wait(2)
    original_owner=first.get('/api/reviews/health').json()['worker']['host_owner']
    def close_first():
        first.__exit__(None,None,None);closed.set()
    closing=threading.Thread(target=close_first)
    closing.start()
    try:
        # Specifically crosses the original unsafe three-second join boundary.
        time.sleep(3.2)
        with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(delayed))) as peer:
            assert peer.get('/api/reviews/health').json()['worker']['host_owner']==original_owner
            assert not closed.is_set()
            queued=peer.post('/api/reviews/tasks',json={'mode':'ON_DEMAND'}).json()
            assert queued['status']=='QUEUED'
            assert len(calls)==1
            release.set();closing.join(5)
            assert closed.is_set()
            assert wait_result(peer,queued['task_id'])['result'] is not None
    finally:
        release.set();closing.join(10)


def test_on_demand_refresh_records_later_actual_knowledge_without_backdating_newly_acquired_fact(tmp_path):
    fields=['']*60
    for index,value in {2:'600519',3:'12',4:'10',5:'10',6:'100',30:'20260930161458',33:'12',34:'10',35:'12/100/120000',47:'13.2',48:'10.8'}.items():fields[index]=value
    def provider(request):
        if 'kline' in request.url.path:
            return httpx.Response(200,json={'rc':0,'data':{'code':'600519','market':1,'klines':['2026-09-30,10,10,10,10,100,100000']}})
        if 'qt.gtimg' in request.url.host:return httpx.Response(200,content=('v_sh600519="'+'~'.join(fields)+'";').encode())
        return httpx.Response(503,content=b'controlled missing company response')
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        establish(client,['SSE:600519'])
        client.post('/api/market/identities',json={'instrument':'SSE:600519','exchange':'SSE','board':'MAIN','instrument_type':'STOCK',
            'name':'合成普通股','basis':'合成证券身份','effective_at':'2026-10-07T00:00:00+08:00'})
        queued=client.post('/api/reviews/tasks',json={'mode':'ON_DEMAND','refresh_missing':True}).json()
        task=wait_result(client,queued['task_id'])
        item=next(i for i in task['result']['instruments'] if i['instrument']=='SSE:600519')
        assert item['quote'] is not None,task
        assert datetime.fromisoformat(item['quote']['available_at'])>datetime.fromisoformat(task['inputs']['cutoff'])
        assert datetime.fromisoformat(task['result']['knowledge_cutoff'])>=datetime.fromisoformat(item['quote']['available_at'])
        assert task['result']['knowledge_basis']=='ACTUAL_COMPLETION_NO_BACKDATED_KNOWLEDGE'
        assert task['result']['cutoff']==task['inputs']['cutoff']
        assert task['result']['forward_sample_created'] is False


def test_real_sqlite_lock_worker_failure_is_not_relabelled_as_normal_close(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        locked=threading.Event()
        def storage_lock():
            # Actual storage-boundary fault, no private schema inspection or writes.
            with sqlite3.connect(tmp_path/'roll.sqlite3',timeout=10,isolation_level=None) as db:
                db.execute('BEGIN IMMEDIATE');locked.set();time.sleep(12.5);db.rollback()
        blocker=threading.Thread(target=storage_lock)
        blocker.start();assert locked.wait(2);blocker.join(15)
        for _ in range(100):
            health=client.get('/api/reviews/health').json()
            if health.get('last_worker_error'):break
            time.sleep(.02)
        assert health['last_worker_error']['code']=='OperationalError',health
        assert client.get('/api/reviews/coverage').json()['sessions'][-1]['close_reason']=='WORKER_EXCEPTION'
        recovered=client.post('/api/reviews/recover')
        assert recovered.status_code==202,recovered.text
        assert wait_result(client,recovered.json()['task_id'])['result'] is not None
        assert client.get('/api/reviews/health').json()['worker_state']=='RUNNING'
    with TestClient(create_app(tmp_path)) as client:
        coverage=client.get('/api/reviews/coverage').json()
        assert coverage['sessions'][-3]['close_reason']=='WORKER_EXCEPTION'
        assert coverage['sessions'][-2]['close_reason']=='NORMAL_CLOSE_NO_ALWAYS_ON_REQUIREMENT'
        assert any(g['reason']=='MODULE_FAILURE_COVERAGE_GAP' for g in coverage['gaps'])


def test_sleep_gap_and_holiday_rolled_weekly_maintenance_keep_actual_checks_and_nominal_week(tmp_path):
    clock=[datetime.fromisoformat('2026-09-30T16:00:00+08:00')]
    with TestClient(create_app(tmp_path,review_clock=lambda:clock[0])) as client:
        registration=client.post('/api/reviews/maintenance',json={'kind':'WEEKLY','exchange':'SSE','first_due_at':'2026-10-07T16:00:00+08:00'})
        assert registration.json()['next_due_at']=='2026-10-08T16:00:00+08:00'
        clock[0]=datetime.fromisoformat('2026-10-09T10:00:00+08:00')
        time.sleep(.15)
        gaps=client.get('/api/reviews/coverage').json()['gaps']
        assert len(gaps)==1 and gaps[0]['reason']=='RUNNING_HEARTBEAT_GAP_UNOBSERVED'
        assert gaps[0]['monitoring_fault'] is False
        checks=client.post('/api/reviews/maintenance/check').json()
        assert len(checks)==1 and checks[0]['status']=='OVERDUE_CHECKED'
        assert checks[0]['checked_at']==clock[0].isoformat()
        assert client.get('/api/reviews/maintenance').json()[0]['next_due_at']=='2026-10-14T16:00:00+08:00'


def test_phase_guard_historical_label_and_public_immutable_replay(tmp_path):
    clock=lambda:datetime.fromisoformat('2026-10-08T10:00:00+08:00')
    with TestClient(create_app(tmp_path,review_clock=clock)) as client:
        assert client.post('/api/reviews/tasks',json={'mode':'POST_CLOSE'}).status_code==422
        task=wait_result(client,client.post('/api/reviews/tasks',json={'mode':'HISTORICAL','cutoff':'2026-09-30T16:00:00+08:00'}).json()['task_id'])
        assert task['result']['account_basis']=='CURRENT_CONFIRMED_ACCOUNT_NOT_PAST_ACCOUNT_PROOF'
        replay=client.post('/api/reviews/tasks/'+task['task_id']+'/replay')
        assert replay.status_code==200,replay.text
        assert replay.json()['result']==task['result'] and replay.json()['network_calls']==0


def test_explicit_critical_review_freezes_decisive_original_reference_without_upgrading_routine_audit(tmp_path):
    def source(request):return httpx.Response(200,json={'rc':0,'data':{'code':'600519','market':1,'klines':['2026-09-30,10,10,10,10,100,100000']}})
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(source))) as client:
        establish(client,['SSE:600519'])
        req=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['DAILY'],'purpose':'OBSERVATION','start_date':'2026-09-30','end_date':'2026-09-30'}).json()
        run=client.post('/api/data/requests/'+req['request_id']+'/retrieve').json()
        task=wait_result(client,client.post('/api/reviews/tasks',json={'mode':'ON_DEMAND'}).json()['task_id'])
        audit=client.get('/api/reviews/audits/'+task['audit_id']).json()
        assert audit['critical_review']['status']=='NOT_REQUIRED'
        command={'trigger':'USER_SELECTED','knowledge_cutoff':task['result']['knowledge_cutoff'],'reason':'重点核对收盘原价，影响复盘归因','facts':[{'fact_id':'decisive-close','field':'close','references':[{'snapshot_id':run['snapshot_id'],'fact_index':0}]}]}
        selected=client.post('/api/reviews/tasks/'+task['task_id']+'/verification-request',json=command)
        assert selected.status_code==201,selected.text
        value=selected.json()
        assert value['task_id']==task['task_id'] and value['status']=='PENDING_CONSUMER_14'
        assert value['original_fact_values'][0]['value']=='10'
        assert value['request']==command
        assert client.get('/api/reviews/verification-requests/'+value['request_id']).json()==value
        assert client.post('/api/reviews/tasks/'+task['task_id']+'/verification-request',json=command).json()==value
        assert client.get('/api/reviews/audits/'+task['audit_id']).json()['critical_review']['request_id']==value['request_id']
        wrong={**command,'facts':[{'fact_id':'wrong','field':'close','references':[{'snapshot_id':'missing','fact_index':0}]}]}
        assert client.post('/api/reviews/tasks/'+task['task_id']+'/verification-request',json=wrong).status_code==422


def test_empty_account_can_refresh_fixed_backgrounds_with_shared_budget_and_no_account_write(tmp_path):
    def background(request):
        symbol=request.url.params['param'].split(',')[0]
        return httpx.Response(200,json={'code':0,'data':{symbol:{'day':[['2026-09-30','3800','3830','3840','3790','400000000']]}}})
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(background))) as client:
        before=client.get('/api/account').json()
        task=wait_result(client,client.post('/api/reviews/tasks',json={'mode':'ON_DEMAND','refresh_missing':True}).json()['task_id'])
        assert task['retrieval_runs'],task
        assert len(task['result']['instruments'])==2
        assert all(i['last_complete_daily'] and i['last_complete_daily']['trade_date']=='2026-09-30' for i in task['result']['instruments'])
        run=client.get('/api/data/runs/'+task['retrieval_runs'][0]).json()
        assert len(run['tools'])<=4
        assert client.get('/api/account').json()==before


def test_real_public_source_revision_changes_new_review_but_keeps_published_old_review_and_replay(tmp_path):
    price=['10']
    def source(request):return httpx.Response(200,json={'rc':0,'data':{'code':'600519','market':1,'klines':[f'2026-09-30,{price[0]},{price[0]},{price[0]},{price[0]},100,{int(price[0])*10000}']}})
    def resolve(client,request_id,prior=None):
        command={'usage':'POST_MARKET_RECORD','use_cache':False,'allow_fallback':False}
        if prior:command['revision_of']=prior
        response=client.post('/api/data/requests/'+request_id+'/resolve',json=command)
        assert response.status_code==202,response.text
        identifier=response.json()['resolution_id']
        for _ in range(100):
            value=client.get('/api/data/resolutions/'+identifier).json()
            if value['status']=='COMPLETED':return value
            time.sleep(.02)
        raise AssertionError(value)
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(source))) as client:
        establish(client,['SSE:600519'])
        client.post('/api/market/identities',json={'instrument':'SSE:600519','exchange':'SSE','board':'MAIN','instrument_type':'STOCK','name':'合成普通股','basis':'合成身份','effective_at':'2026-10-07T00:00:00+08:00'})
        req=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['DAILY'],'purpose':'OBSERVATION','start_date':'2026-09-30','end_date':'2026-09-30'}).json()
        first_resolution=resolve(client,req['request_id'])
        first=wait_result(client,client.post('/api/reviews/tasks',json={'mode':'ON_DEMAND'}).json()['task_id'])
        price[0]='11'
        second_resolution=resolve(client,req['request_id'],first_resolution['resolution_id'])
        second=wait_result(client,client.post('/api/reviews/tasks',json={'mode':'ON_DEMAND'}).json()['task_id'])
        first_item=next(i for i in first['result']['instruments'] if i['instrument']=='SSE:600519')
        second_item=next(i for i in second['result']['instruments'] if i['instrument']=='SSE:600519')
        assert first_item['last_complete_daily']['close']=='10' and second_item['last_complete_daily']['close']=='11'
        assert second['result']['previous_snapshot_id']==first['result']['snapshot_id']
        assert second['result']['change']=='NEW_INFORMATION'
        assessments={r['resolution_id']:r for r in second['result']['source_assessments']}
        assert assessments[first_resolution['resolution_id']]['dependency_status']=='INVALIDATED'
        assert assessments[second_resolution['resolution_id']]['dependency_status']=='CURRENT'
        assert client.get('/api/reviews/tasks/'+first['task_id']).json()==first
        assert client.post('/api/reviews/tasks/'+first['task_id']+'/replay').json()['result']==first['result']


def test_running_day_audit_records_only_actual_seen_days_without_creating_observations(tmp_path):
    clock=[datetime.fromisoformat('2026-10-08T10:00:00+08:00')]
    with TestClient(create_app(tmp_path,review_clock=lambda:clock[0])) as client:
        for _ in range(100):
            response=client.get('/api/reviews/audits')
            if response.status_code==200 and response.json():break
            time.sleep(.02)
        assert response.status_code==200,response.text
        first=response.json();assert [a['trade_date'] for a in first]==['2026-10-08']
        assert first[0]['task_id'] is None and first[0]['snapshot_id'] is None
        assert first[0]['origin']=='RUNNING_DAY_CHECK'
        assert first[0]['metrics']['unfinished_execution_intents']['value'] is None
        clock[0]=datetime.fromisoformat('2026-10-12T10:00:00+08:00');time.sleep(.15)
        audits=client.get('/api/reviews/audits').json()
        assert {a['trade_date'] for a in audits}=={'2026-10-08','2026-10-12'}
        assert client.get('/api/reviews/history').json()==[]


def test_actual_elapsed_deadline_stops_at_one_attempt_and_keeps_timeout_audit(tmp_path):
    entered=threading.Event()
    def delayed(request):
        entered.set();time.sleep(8.1)
        return httpx.Response(503,content=b'controlled deadline boundary')
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(delayed))) as client:
        response=client.post('/api/reviews/tasks',json={'mode':'ON_DEMAND','refresh_missing':True})
        assert entered.wait(2)
        for _ in range(500):
            task=client.get('/api/reviews/tasks/'+response.json()['task_id']).json()
            if task['status']=='TIMED_OUT':break
            time.sleep(.02)
        assert task['status']=='TIMED_OUT' and task['attempts']==1,task
        assert task['timing']['acquisition_seconds']>=8
        assert task['result']['gaps']
        assert client.get('/api/reviews/audits/'+task['audit_id']).status_code==200
