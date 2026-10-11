"""Independent finite station/outbox/report caller tests. All ntfy responses are METHOD mocks."""
import json
import httpx
from fastapi.testclient import TestClient
from roll.app import create_app
from capability_method_app import save_package
from test_actions import action_package,prepare
from test_intents import intent_command
from test_account import baseline
from test_funding import funding
def record(p,n,v):(p/(n+'.json')).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def pause(c,reason='Independent METHOD暂停；事实同步继续'):
    r=c.post('/api/capabilities/lifecycle',json={'scope':'ALL_MONITOR','state':'SUSPENDED','reason_code':'USER_PAUSE','reason':reason,'expected_version':0,'idempotency_key':'pause'})
    assert r.status_code==200,r.text;return r.json()
def channel(c,enabled):
    r=c.post('/api/notification-channel',json={'expected_version':0,'enabled':enabled,'server':'https://ntfy.example.test','topic':'independent-method','app_base_url':'http://127.0.0.1:5173'})
    assert r.status_code==200,r.text;return r.json()

def test_first_invalidation_audit_and_notice_once_immutable_restart(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test');p=action_package();file=save_package(tmp_path/'qualification.json',p);data=tmp_path/'data'
    with TestClient(create_app(data,capability_method_file=file,runtime_role='API')) as c:
        prepare(c,p);old=c.post('/api/actions/evaluate',json={}).json();assert len(old['decisions'])==1
        original=next(n for n in c.get('/api/notifications').json()['notifications'] if n['category']=='NEED_ACTION')
        assert original['source']['id']==old['decisions'][0]['decision_id'] and original['read_at'] is None
        assert c.post('/api/funding/confirm',json=funding(2,total_exposure='10000.00',single_exposure='10000.00',cash_reserve='90000.00')).status_code==200
        first=c.get('/api/actions/current').json();assert first['decisions']==[]
        events=[e for e in c.get('/api/actions/events').json() if e['event_type']=='ACTION_INVALIDATED'];assert len(events)==1
        notices=c.get('/api/notifications').json()['notifications'];critical=[n for n in notices if n['source']['kind']=='ACTION_INVALIDATION'];assert len(critical)==1
        assert critical[0]['source']['id']==events[0]['event_id'] and critical[0]['reasons']==['FUNDING_VERSION_CHANGE','GRANT_RESTRICTED']
        nid=original['notification_id'];current=c.get('/api/notifications/'+nid+'/current').json()
        assert current['current_state']=='INVALIDATED' and current['prepare_allowed'] is False
        assert len([s for s in current['source_links'] if s['event_type']=='SOURCE_INVALIDATED'])==1
        for _ in range(2):
            assert c.get('/api/actions/current').json()['decisions']==[]
            assert c.get('/api/notifications/'+nid+'/current').json()['notification']==current['notification']
        assert [e for e in c.get('/api/actions/events').json() if e['event_type']=='ACTION_INVALIDATED']==events
        assert c.get('/api/notifications').json()['notifications']==notices
        assert c.post('/api/intents/prepare',json=intent_command(old)).status_code==409
        assert c.get('/api/actions/evaluations/'+old['evaluation_id']).json()==old
        assert c.post('/api/actions/evaluations/'+old['evaluation_id']+'/replay').json()['matches_original']
        audit=c.get('/api/notifications/audit').json();assert audit['business_notifications']==2 and audit['transmission_attempts']==0 and audit['delivered'] is None
        record(tmp_path,'first-transition',{'old':old,'events':events,'notices':notices,'current':current,'audit':audit})
    with TestClient(create_app(data,capability_method_file=file,runtime_role='API')) as c:
        assert c.get('/api/notifications').json()['notifications']==notices
        assert c.get('/api/notifications/audit').json()==audit

def test_long_chinese_projection_preserves_station_and_next_fact(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test');requests=[]
    def publish(r):requests.append(json.loads(r.content));return httpx.Response(200,json={'event':'message','id':'method-'+str(len(requests))})
    app=create_app(tmp_path/'data',runtime_role='API',notification_transport=httpx.MockTransport(publish))
    with TestClient(app) as c:
        reason='界'*1600;pause(c,reason)
        assert c.post('/api/account/drafts',json=baseline()).status_code==201
        prior=c.get('/api/notifications').json()['notifications'];long=next(n for n in prior if n['source']['kind']=='CAPABILITY_SCOPE_CHANGED')
        assert long['message']==reason and len(reason.encode())==4800
        channel(c,True);app.state.notifications.work('independent-finite-worker');app.state.notifications.work('independent-finite-worker')
        assert len(requests)==2 and all(len(r['message'].encode())<=4096 for r in requests)
        after=c.get('/api/notifications').json()['notifications'];assert all(n['external_status']=='CHANNEL_ACCEPTED' for n in after)
        current=c.get('/api/notifications/'+long['notification_id']+'/current').json()
        attempt=current['attempts'][0];assert attempt['message_projection']=='SUMMARY_FOR_CHANNEL_BYTE_LIMIT'
        assert attempt['body']['message']!=reason and current['notification']['message']==reason
        assert attempt['result']['status']=='CHANNEL_ACCEPTED'
        for n in after:
            assert n['sent_at'] is None and n['sent_source']=='UNKNOWN' and n['delivered_at'] is None and n['delivery_source']=='UNKNOWN' and n['read_at'] is None
            assert n['dispatch_started_at'] and n['publish_confirmed_at'] and n['accepted_occurred_at'] is None
        record(tmp_path,'long-projection',{'requests':requests,'current':current,'after':after})

def test_readonly_report_chain_unknown_no_intent_advance_and_late_report(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test');p=action_package();file=save_package(tmp_path/'qualification.json',p);requests=[]
    def timeout(r):requests.append(str(r.url));raise httpx.ReadTimeout('Independent METHOD acceptance unknown',request=r)
    app=create_app(tmp_path/'data',capability_method_file=file,runtime_role='API',notification_transport=httpx.MockTransport(timeout))
    with TestClient(app) as c:
        prepare(c,p);evaluation=c.post('/api/actions/evaluate',json={}).json()
        r=c.post('/api/intents/prepare',json=intent_command(evaluation));assert r.status_code==201,r.text;intent=r.json()
        nid=next(n for n in c.get('/api/notifications').json()['notifications'] if n['category']=='NEED_ACTION')['notification_id']
        channel(c,True);app.state.notifications.work('independent-finite-worker')
        query='/api/notifications/time-chain?decision_id='+intent['decision_id']+'&evaluation_id='+intent['evaluation_id']+'&intent_id='+intent['intent_id']
        intents_before=c.get('/api/intents').json();events_before=c.get('/api/actions/events').json();audit=c.get('/api/notifications/audit').json()
        r=c.get(query);assert r.status_code==200,r.text;chain=r.json()
        assert chain['original_intent_mutated'] is False and chain['time_chain']['prepared_at']==intent['time_chain']['prepared_at']
        assert chain['time_chain']['sent_at'] is chain['time_chain']['delivered_at'] is chain['time_chain']['read_at'] is None
        assert chain['time_chain']['sent_source']=='UNKNOWN' and chain['time_chain']['delivery_source']=='UNKNOWN'
        assert chain['notification_timeline'][0]['external_status']=='RESULT_UNKNOWN' and chain['notification_timeline'][0]['publish_confirmed_at'] is None
        assert chain['notification_timeline'][0]['original_source_binding'] is True
        assert c.get(query).json()==chain and c.get('/api/intents').json()==intents_before and c.get('/api/actions/events').json()==events_before and c.get('/api/notifications/audit').json()==audit
        assert audit['unknown_attempts']==1 and audit['transmission_attempts']==1 and audit['delivered'] is None
        app.state.notifications.work('independent-finite-worker');assert len(requests)==1
        read=c.post('/api/notifications/'+nid+'/read',json={'idempotency_key':'station-read'});assert read.status_code==200
        known=c.get(query).json();assert known['time_chain']['read_source']=='EXPLICIT_STATION_READ' and known['time_chain']['read_at']==read.json()['read_at']
        assert c.get('/api/intents').json()==intents_before
        declare=c.post('/api/intents/'+intent['intent_id']+'/declare',json={'state':'OPERATION_PENDING','external_order_id':'METHOD-only','occurred_at':'2026-10-09T10:00:00+08:00','idempotency_key':'late-report'})
        assert declare.status_code==200,declare.text
        late=c.get(query).json();assert late['time_chain']['occurred_at']==declare.json()['time_chain']['occurred_at'] and late['time_chain']['reported_at']==declare.json()['time_chain']['reported_at']
        assert late['time_chain']['occurred_at']!=late['time_chain']['reported_at'] and late['notification_timeline']==known['notification_timeline'] and late['time_chain']['delivered_at'] is None
        record(tmp_path,'report-chain',{'original':chain,'read':known,'late':late,'audit':audit,'intent_before':intent,'new_report':declare.json(),'mock_requests':requests})

def test_disabled_local_config_no_send_station_read_explicit_restart(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test');data=tmp_path/'data';attempts=[]
    def forbidden(r):attempts.append(str(r.url));raise AssertionError('Disabled configuration cannot send')
    app=create_app(data,runtime_role='API',notification_transport=httpx.MockTransport(forbidden))
    with TestClient(app) as c:
        initial=c.get('/api/notification-channel').json();assert initial['enabled'] is False and initial['real_channel_acceptance']=='PENDING_USER_CONFIGURATION'
        saved=channel(c,False);assert not saved['enabled'] and saved['version']==1 and saved['topic']=='' and saved['topic_configured']
        pause(c);notices=c.get('/api/notifications').json()['notifications'];assert len(notices)==1 and notices[0]['read_at'] is None
        nid=notices[0]['notification_id'];assert c.get('/api/notifications/'+nid+'/current').json()['read_at'] is None
        app.state.notifications.work('independent-finite-worker');assert attempts==[] and c.get('/api/notifications/audit').json()['transmission_attempts']==0
        read=c.post('/api/notifications/'+nid+'/read',json={'idempotency_key':'read'}).json()
        assert read['read_source']=='EXPLICIT_STATION_READ' and c.post('/api/notifications/'+nid+'/read',json={'idempotency_key':'read'}).json()==read
        record(tmp_path,'disabled-channel',{'masked_configuration':saved,'notices':notices,'read':read,'mock_requests':attempts})
    with TestClient(create_app(data,runtime_role='API',notification_transport=httpx.MockTransport(forbidden))) as c:
        assert c.get('/api/notification-channel').json()==saved
        notice=c.get('/api/notifications').json()['notifications'][0];assert notice['read_at']==read['read_at'] and notice['delivered_at'] is None and notice['external_status']=='CHANNEL_DISABLED'
