"""Public notification lifecycle, real SQLite; external delivery remains unproven."""
from fastapi.testclient import TestClient
from roll.app import create_app
from capability_method_app import save_package
from test_actions import action_package, prepare
from test_intents import intent_command
import httpx
import time
import threading
import pytest
from test_account import baseline
from test_funding import funding


def pause(client, key='pause'):
    return client.post('/api/capabilities/lifecycle', json={
        'scope': 'ALL_MONITOR', 'state': 'SUSPENDED', 'reason_code': 'USER_PAUSE',
        'reason': '用户暂停监控；事实同步继续', 'expected_version': 0, 'idempotency_key': key})


def test_persisted_pause_creates_one_station_notice_explicit_read_survives_restart(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    directory = tmp_path / 'data'
    with TestClient(create_app(directory, runtime_role='API')) as client:
        receipt = pause(client)
        assert receipt.status_code == 200, receipt.text
        assert pause(client).json() == receipt.json()
        response = client.get('/api/notifications')
        assert response.status_code == 200, response.text
        notices = response.json()['notifications']
        assert len(notices) == 1
        notice = notices[0]
        assert notice['category'] == 'NEED_SYNC_RECOVERY'
        assert notice['source']['id'] == receipt.json()['event_id']
        assert notice['read_at'] is None and notice['delivered_at'] is None
        assert notice['external_status'] == 'CHANNEL_DISABLED'
        current = client.get('/api/notifications/' + notice['notification_id'] + '/current').json()
        assert current['notification']['message'] == notice['message']
        assert current['read_at'] is None
        read = client.post('/api/notifications/' + notice['notification_id'] + '/read', json={'idempotency_key': 'read'})
        assert read.status_code == 200, read.text
        assert read.json()['read_source'] == 'EXPLICIT_STATION_READ'
        assert client.post('/api/notifications/' + notice['notification_id'] + '/read', json={'idempotency_key': 'read'}).json() == read.json()
    with TestClient(create_app(directory, runtime_role='API')) as client:
        notices = client.get('/api/notifications').json()['notifications']
        assert len(notices) == 1 and notices[0]['read_at'] == read.json()['read_at']
        assert notices[0]['delivered_at'] is None
        assert client.get('/api/notifications/audit').json()['business_notifications'] == 1


def test_new_immutable_evaluation_after_ordinary_quote_merges_notice_but_old_link_cannot_prepare(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    package = action_package()
    qualification = save_package(tmp_path / 'qualification.json', package)
    quote = [''] * 60
    for index, value in {2:'600000',3:'136',4:'135',5:'135',6:'100',30:'20261009103000',33:'137',34:'134'}.items(): quote[index] = value
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=('v_sh600000="' + '~'.join(quote) + '";').encode('gbk')))
    with TestClient(create_app(tmp_path / 'data', runtime_role='API', capability_method_file=qualification, market_transport=transport)) as client:
        prepare(client, package)
        first = client.post('/api/actions/evaluate', json={}).json()
        assert [(d['action'],d['quantity']) for d in first['decisions']] == [('BUY','200')]
        notices = client.get('/api/notifications').json()['notifications']
        action = next(n for n in notices if n['category'] == 'NEED_ACTION')
        original_message = action['message']
        request = client.post('/api/data/requests', json={'instruments':['SSE:600000'],'groups':['QUOTE'],
            'purpose':'OBSERVATION','start_date':'2026-10-09','end_date':'2026-10-09'}).json()
        retrieved = client.post('/api/data/requests/' + request['request_id'] + '/retrieve')
        assert retrieved.status_code == 200, retrieved.text
        second = client.post('/api/actions/evaluate', json={}).json()
        assert second['evaluation_id'] != first['evaluation_id']
        assert [(d['action'],d['quantity']) for d in second['decisions']] == [('BUY','200')]
        assert second['decisions'][0]['decision_id'] != first['decisions'][0]['decision_id']
        notices = client.get('/api/notifications').json()['notifications']
        actions = [n for n in notices if n['category'] == 'NEED_ACTION']
        assert len(actions) == 1, actions
        assert actions[0]['message'] == original_message
        current = client.get('/api/notifications/' + action['notification_id'] + '/current').json()
        assert current['current_state'] == 'SUPERSEDED'
        assert current['prepare_allowed'] is False
        assert len(current['source_links']) == 2
        assert client.post('/api/intents/prepare', json=intent_command(first)).status_code == 409
        assert client.get('/api/actions/evaluations/' + first['evaluation_id']).json() == first


def test_invalid_config_unknown_fields_and_storage_failure_never_echo_synthetic_secret(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    canary = 'SYNTHETIC_CHANNEL_FAILURE_CANARY'
    with TestClient(create_app(tmp_path / 'data', runtime_role='API')) as client:
        for body in [{'expected_version':0,'enabled':False,'token':{'bad':canary}},
                     {'expected_version':0,'enabled':False,canary:canary}]:
            result = client.post('/api/notification-channel', json=body)
            assert result.status_code == 422 and canary not in result.text
        result = client.post('/api/notification-channel', content='{"token":"' + canary)
        assert result.status_code == 422 and canary not in result.text
        def broken_storage(*args): raise OSError(canary)
        monkeypatch.setattr('roll.runtime.notification_channel.persist', broken_storage)
        result = client.post('/api/notification-channel', json={'expected_version':0,'enabled':False,'token':canary})
        assert result.status_code == 503 and canary not in result.text
        assert client.get('/api/notification-channel').json()['auth_configured'] is False


def test_unexpected_transport_error_is_sanitized_unknown_not_worker_exception_or_auto_retry(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    canary, requests = 'SYNTHETIC_TRANSPORT_SECRET_CANARY', []
    def publish(request):
        requests.append(request.url.path)
        raise RuntimeError(canary)
    app = create_app(tmp_path / 'data', runtime_role='API', notification_transport=httpx.MockTransport(publish))
    with TestClient(app) as client:
        pause(client)
        client.post('/api/notification-channel', json={'expected_version':0,'enabled':True,
            'server':'https://ntfy.example.test','topic':'method-only','app_base_url':'http://127.0.0.1:5173','token':canary})
        app.state.notifications.work('owned-test-worker')
        notice = client.get('/api/notifications').json()['notifications'][0]
        assert notice['external_status'] == 'RESULT_UNKNOWN'
        current = client.get('/api/notifications/' + notice['notification_id'] + '/current').json()
        assert canary not in str(current)
        app.state.notifications.work('owned-test-worker')
        assert len(requests) == 1


def test_permission_change_after_claim_before_http_is_not_dispatched_and_short_writer_is_released(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    package, requests = action_package(), []
    qualification = save_package(tmp_path / 'qualification.json', package)
    app = create_app(tmp_path / 'data', runtime_role='API', capability_method_file=qualification,
        notification_transport=httpx.MockTransport(lambda request: requests.append(request.content) or httpx.Response(200,json={'id':'method','event':'message'})))
    with TestClient(app) as client:
        prepare(client, package)
        client.post('/api/actions/evaluate', json={})
        notice = next(n for n in client.get('/api/notifications').json()['notifications'] if n['category'] == 'NEED_ACTION')
        client.post('/api/notification-channel', json={'expected_version':0,'enabled':True,
            'server':'https://ntfy.example.test','topic':'method-only','app_base_url':'http://127.0.0.1:5173'})
        def at_boundary(point):
            if point == 'notification_after_claim':
                response = pause(client)
                assert response.status_code == 200, response.text
        monkeypatch.setattr(app.state.ledger, 'crash_point', at_boundary)
        app.state.notifications.work('owned-test-worker')
        current = client.get('/api/notifications/' + notice['notification_id'] + '/current').json()
        assert requests == []
        assert current['attempts'][0]['result']['status'] == 'NOT_DISPATCHED'
        assert not any(e['event_type'] == 'DISPATCH_STARTED' for e in current['attempts'][0]['events'])


def test_two_distinct_retry_commands_before_worker_claim_share_one_retry_attempt(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    app = create_app(tmp_path / 'data', runtime_role='API', notification_transport=httpx.MockTransport(
        lambda request: (_ for _ in ()).throw(httpx.ReadTimeout('controlled-timeout',request=request))))
    with TestClient(app) as client:
        pause(client)
        client.post('/api/notification-channel', json={'expected_version':0,'enabled':True,
            'server':'https://ntfy.example.test','topic':'method-only','app_base_url':'http://127.0.0.1:5173'})
        app.state.notifications.work('owned-test-worker')
        notice = client.get('/api/notifications').json()['notifications'][0]
        path = '/api/notifications/' + notice['notification_id'] + '/retry'
        assert client.post(path, json={'idempotency_key':'one'}).status_code == 200
        assert client.post(path, json={'idempotency_key':'two'}).status_code == 409
        assert client.get('/api/notifications/audit').json()['possible_duplicate_attempts'] == 1


def test_default_disabled_private_channel_masked_retains_same_origin_rejects_secret_errors(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    directory = tmp_path / 'data'
    canary = 'SYNTHETIC_NOTIFICATION_SECRET_DO_NOT_EXPORT'
    with TestClient(create_app(directory, runtime_role='API')) as client:
        state = client.get('/api/notification-channel')
        assert state.status_code == 200, state.text
        assert state.json()['enabled'] is False and state.json()['auth_configured'] is False
        command = {'expected_version':0,'enabled':False,'server':'https://ntfy.example.test','topic':'method-private-topic',
                   'app_base_url':'http://127.0.0.1:5173','token':canary}
        saved = client.post('/api/notification-channel', json=command)
        assert saved.status_code == 200, saved.text
        assert canary not in saved.text and saved.json()['auth_configured'] is True
        invalid = client.post('/api/notification-channel', json={**command,'expected_version':1,'enabled':{'bad':canary}})
        assert invalid.status_code == 422 and canary not in invalid.text
        retained = client.post('/api/notification-channel', json={'expected_version':1,'enabled':False,'token':''})
        assert retained.status_code == 200 and retained.json()['auth_configured'] is True
        changed = client.post('/api/notification-channel', json={'expected_version':2,'enabled':False,'server':'https://other.example.test'})
        assert changed.status_code == 409 and changed.json()['detail'] == 'CHANNEL_ORIGIN_CHANGE_REQUIRES_NEW_OR_CLEARED_AUTH'
        cleared = client.post('/api/notification-channel', json={'expected_version':2,'enabled':False,'server':'https://other.example.test','clear_auth':True})
        assert cleared.status_code == 200 and cleared.json()['auth_configured'] is False
        assert client.get('/api/notifications/audit').json()['transmission_attempts'] == 0
        backup = client.post('/api/runtime/backups').json()
        bundle = client.get('/api/runtime/backups/' + backup['backup_id'] + '/export').content
        import io, zipfile
        with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
            assert not any('notification-private' in p for p in archive.namelist())
            assert all(canary.encode() not in archive.read(p) for p in archive.namelist())
    with TestClient(create_app(directory, runtime_role='API')) as client:
        assert client.get('/api/notification-channel').json()['version'] == 3
        assert client.get('/api/notification-channel').json()['enabled'] is False


def test_worker_channel_acceptance_not_delivery_or_read_and_single_business_attempt(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    received = []
    def publish(request):
        import json
        received.append({'path':request.url.path,'body':json.loads(request.content),'authorization_present':'authorization' in request.headers})
        return httpx.Response(200, json={'id':'method-accepted-1','event':'message','time':1791700000})
    with TestClient(create_app(tmp_path / 'data', notification_transport=httpx.MockTransport(publish))) as client:
        assert pause(client).status_code == 200
        configured = client.post('/api/notification-channel', json={'expected_version':0,'enabled':True,
            'server':'https://ntfy.example.test','topic':'synthetic-method-only','app_base_url':'http://127.0.0.1:5173','token':'METHOD_CANARY_AUTH'})
        assert configured.status_code == 200, configured.text
        for _ in range(200):
            notices = client.get('/api/notifications').json()['notifications']
            if notices[0]['external_status'] == 'CHANNEL_ACCEPTED': break
            time.sleep(.05)
        else: raise AssertionError(notices)
        notice = notices[0]
        assert notice['delivered_at'] is None and notice['read_at'] is None
        assert notice['sent_at'] is None
        assert notice['dispatch_started_at'] and notice['publish_confirmed_at']
        assert notice['accepted_occurred_at'] == '2026-10-11T06:26:40+00:00'
        assert notice['accepted_known_at']
        assert len(received) == 1 and received[0]['path'] == '/'
        assert received[0]['body']['topic'] == 'synthetic-method-only'
        assert received[0]['authorization_present'] is True
        assert received[0]['body']['click'].endswith('#notification=' + notice['notification_id'])
        assert client.get('/api/notifications/audit').json()['transmission_attempts'] == 1
        current = client.get('/api/notifications/' + notice['notification_id'] + '/current').json()
        assert len(current['attempts']) == 1 and current['attempts'][0]['result']['provider_id'] == 'method-accepted-1'
        assert 'METHOD_CANARY_AUTH' not in str(current)


def test_uncertain_publish_has_no_automatic_retry_one_explicit_retry_and_sanitized_history(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    requests = []
    def publish(request):
        requests.append(request.url.path)
        if len(requests) == 1: raise httpx.ReadTimeout('SECRET_IN_TRANSPORT_EXCEPTION', request=request)
        return httpx.Response(200, json={'id':'method-accepted-retry','event':'message'})
    with TestClient(create_app(tmp_path / 'data', notification_transport=httpx.MockTransport(publish))) as client:
        pause(client)
        client.post('/api/notification-channel', json={'expected_version':0,'enabled':True,
            'server':'https://ntfy.example.test','topic':'method-only','app_base_url':'http://127.0.0.1:5173'})
        for _ in range(200):
            notice = client.get('/api/notifications').json()['notifications'][0]
            if notice['external_status'] == 'RESULT_UNKNOWN': break
            time.sleep(.05)
        else: raise AssertionError(notice)
        identifier = notice['notification_id']
        time.sleep(.2)
        assert len(requests) == 1
        old = client.get('/api/notifications/' + identifier + '/current').json()
        assert old['attempts'][0]['result']['error_code'] == 'CHANNEL_REQUEST_UNCERTAIN'
        assert 'SECRET_IN_TRANSPORT_EXCEPTION' not in str(old)
        command = {'idempotency_key':'retry-once'}
        retry = client.post('/api/notifications/' + identifier + '/retry', json=command)
        assert retry.status_code == 200, retry.text
        assert retry.json()['possible_duplicate'] is True
        assert client.post('/api/notifications/' + identifier + '/retry', json=command).json() == retry.json()
        for _ in range(200):
            notice = client.get('/api/notifications').json()['notifications'][0]
            if notice['external_status'] == 'CHANNEL_ACCEPTED': break
            time.sleep(.05)
        else: raise AssertionError(notice)
        current = client.get('/api/notifications/' + identifier + '/current').json()
        assert current['attempts'][0] == old['attempts'][0]
        assert len(current['attempts']) == 2 and len(requests) == 2
        assert client.post('/api/notifications/' + identifier + '/retry', json={'idempotency_key':'third'}).status_code == 409
        assert client.get('/api/notifications/audit').json()['possible_duplicate_attempts'] == 1


def test_notification_time_chain_augments_intent_query_without_rewriting_original_unknowns(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    package = action_package()
    qualification = save_package(tmp_path / 'qualification.json', package)
    transport = httpx.MockTransport(lambda request:httpx.Response(200, json={'id':'method-timechain','event':'message'}))
    with TestClient(create_app(tmp_path / 'data', capability_method_file=qualification, notification_transport=transport)) as client:
        prepare(client, package)
        evaluation = client.post('/api/actions/evaluate', json={}).json()
        intent = client.post('/api/intents/prepare', json=intent_command(evaluation)).json()
        configured = client.post('/api/notification-channel', json={'expected_version':0,'enabled':True,
            'server':'https://ntfy.example.test','topic':'method-only','app_base_url':'http://127.0.0.1:5173'})
        assert configured.status_code == 200
        for _ in range(200):
            notice = next(n for n in client.get('/api/notifications').json()['notifications'] if n['category'] == 'NEED_ACTION')
            if notice['external_status'] == 'CHANNEL_ACCEPTED': break
            time.sleep(.05)
        else: raise AssertionError(notice)
        query = '/api/notifications/time-chain?decision_id=' + intent['decision_id'] + '&evaluation_id=' + intent['evaluation_id'] + '&intent_id=' + intent['intent_id']
        response = client.get(query)
        assert response.status_code == 200, response.text
        chain = response.json()
        assert chain['time_chain']['prepared_at'] == intent['time_chain']['prepared_at']
        assert chain['time_chain']['sent_at'] is None and chain['time_chain']['delivered_at'] is None
        assert chain['time_chain']['read_at'] is None
        assert chain['notification_timeline'][0]['publish_confirmed_at']
        assert chain['notification_timeline'][0]['accepted_occurred_at'] is None
        client.post('/api/notifications/' + notice['notification_id'] + '/read', json={'idempotency_key':'explicit-read'})
        known = client.get(query).json()
        assert known['time_chain']['read_at'] and known['time_chain']['read_source'] == 'EXPLICIT_STATION_READ'
        assert known['time_chain']['occurred_at'] is None and known['time_chain']['reported_at'] is None
        assert client.get('/api/intents').json()['intents'][0] == intent
        # A later user declaration has its own occurrence and host knowledge,
        # independent of the channel's earlier/unknown receive evidence.
        declaration = client.post('/api/intents/' + intent['intent_id'] + '/declare', json={
            'state':'OPERATION_PENDING','external_order_id':'METHOD-late-report','occurred_at':'2026-10-09T10:00:00+08:00',
            'idempotency_key':'late-report'})
        assert declaration.status_code == 200, declaration.text
        late = client.get(query).json()
        assert late['time_chain']['occurred_at'] == declaration.json()['time_chain']['occurred_at']
        assert late['time_chain']['reported_at'] == declaration.json()['time_chain']['reported_at']
        assert late['time_chain']['occurred_at'] != late['time_chain']['reported_at']
        assert late['time_chain']['delivered_at'] is None
        assert late['notification_timeline'] == known['notification_timeline']


def test_revoke_inflight_preserves_accepted_body_appends_critical_invalidation_without_writer_wait(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    package = action_package()
    qualification = save_package(tmp_path / 'qualification.json', package)
    entered, release = threading.Event(), threading.Event()
    received = []
    def publish(request):
        received.append(request.content)
        if len(received) == 1:
            entered.set(); assert release.wait(timeout=10)
        return httpx.Response(200, json={'id':'method-inflight','event':'message'})
    with TestClient(create_app(tmp_path / 'data', capability_method_file=qualification, notification_transport=httpx.MockTransport(publish))) as client:
        prepare(client, package)
        evaluation = client.post('/api/actions/evaluate', json={}).json()
        client.post('/api/notification-channel', json={'expected_version':0,'enabled':True,
            'server':'https://ntfy.example.test','topic':'method-only','app_base_url':'http://127.0.0.1:5173'})
        assert entered.wait(timeout=10)
        original = next(n for n in client.get('/api/notifications').json()['notifications'] if n['category'] == 'NEED_ACTION')
        try:
            started = time.monotonic()
            receipt = client.post('/api/capabilities/lifecycle', json={'scope':'NEW_RISK','state':'SUSPENDED','reason_code':'USER_PAUSE',
                'reason':'暂停新增风险','expected_version':0,'idempotency_key':'pause-inflight'})
            assert receipt.status_code == 200, receipt.text
            assert time.monotonic() - started < 2
            assert client.post('/api/intents/prepare', json=intent_command(evaluation)).status_code == 409
        finally: release.set()
        for _ in range(200):
            current = client.get('/api/notifications/' + original['notification_id'] + '/current').json()
            if current['external_status'] == 'CHANNEL_ACCEPTED': break
            time.sleep(.05)
        else: raise AssertionError(current)
        assert current['notification']['message'] == original['message']
        assert current['current_state'] == 'INVALIDATED' and current['prepare_allowed'] is False
        assert current['attempts'][0]['result']['status'] == 'CHANNEL_ACCEPTED'
        assert any(e['event_type'] == 'SOURCE_INVALIDATED' and e['inflight'] for e in current['source_links'])
        notices = client.get('/api/notifications').json()['notifications']
        assert any(n['severity'] == 'CRITICAL' and n['category'] == 'NEED_SYNC_RECOVERY' for n in notices)
        assert client.get('/api/actions/evaluations/' + evaluation['evaluation_id']).json() == evaluation


def test_actual_local_review_stage_summary_is_optional_bounded_and_no_research_action_push(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    with TestClient(create_app(tmp_path / 'data')) as client:
        assert client.get('/api/notifications').json()['notifications'] == []
        completed = []
        for _ in range(2):
            task = client.post('/api/reviews/tasks', json={'refresh_missing':False}).json()
            for _ in range(200):
                result = client.get('/api/reviews/tasks/' + task['task_id']).json()
                if result.get('result'): break
                time.sleep(.05)
            else: raise AssertionError(result)
            completed.append(result)
        notices = client.get('/api/notifications').json()['notifications']
        summaries = [n for n in notices if n['category'] == 'STAGE_SUMMARY']
        assert len(summaries) == 1
        assert not any(n['category'] == 'NEED_ACTION' for n in notices)
        current = client.get('/api/notifications/' + summaries[0]['notification_id'] + '/current').json()
        assert len(current['source_links']) == 2
        assert current['prepare_allowed'] is False
        audit = client.get('/api/reviews/audits/' + completed[-1]['audit_id']).json()
        assert audit['metrics']['duplicate_notifications']['status'] == 'CHECKED'
        assert audit['metrics']['duplicate_notifications']['business_notifications'] >= 1


def test_same_permission_state_new_reason_words_merge_immutable_sources_but_escalation_is_new(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    package = action_package()
    qualification = save_package(tmp_path / 'qualification.json', package)
    with TestClient(create_app(tmp_path / 'data', runtime_role='API', capability_method_file=qualification)) as client:
        grant = prepare(client, package)
        first = pause(client).json()
        original = client.get('/api/notifications').json()['notifications'][0]
        second = client.post('/api/capabilities/lifecycle', json={'scope':'ALL_MONITOR','state':'SUSPENDED','reason_code':'USER_PAUSE',
            'reason':'同一暂停，仅说明文字改变','expected_version':1,'idempotency_key':'new-words'}).json()
        assert second['event_id'] != first['event_id']
        notices = client.get('/api/notifications').json()['notifications']
        assert len(notices) == 1
        assert notices[0]['message'] == original['message']
        current = client.get('/api/notifications/' + original['notification_id'] + '/current').json()
        assert len(current['source_links']) == 2 and current['current_state'] == 'SUPERSEDED'
        escalated = client.post('/api/capabilities/lifecycle', json={'scope':'MODEL','state':'REVOKED','reason_code':'USER_REVOKE',
            'grant_id':grant['grant_id'],'reason':'撤回当前资格，旧授权不能复活','expected_version':2,'idempotency_key':'major-risk'})
        assert escalated.status_code == 200
        notices = client.get('/api/notifications').json()['notifications']
        assert len(notices) == 2 and notices[0]['severity'] == 'CRITICAL'
        assert client.get('/api/notifications/audit').json()['merged_sources'] == 1


def test_pending_account_fact_notice_does_not_need_model_grant_or_monitoring_and_resolves_current_link(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    with TestClient(create_app(tmp_path / 'data', runtime_role='API')) as client:
        draft = client.post('/api/account/drafts', json=baseline()).json()
        notices = client.get('/api/notifications').json()['notifications']
        notice = next(n for n in notices if n['source']['kind'] == 'ACCOUNT_DRAFT')
        assert notice['category'] == 'NEED_SYNC_RECOVERY'
        pause(client)
        assert client.get('/api/notifications/' + notice['notification_id'] + '/current').json()['current_state'] == 'CURRENT'
        assert client.get('/api/capabilities').json()['state'] == 'UNGRANTED'
        confirmation = client.post('/api/account/confirm', json={'draft_id':draft['draft_id'],'idempotency_key':'fact'})
        assert confirmation.status_code == 200, confirmation.text
        current = client.get('/api/notifications/' + notice['notification_id'] + '/current').json()
        assert current['current_state'] == 'RESOLVED'
        assert current['notification']['message'] == notice['message']
        assert current['prepare_allowed'] is False


def test_external_operation_pending_sync_notice_survives_revoke_and_original_intent_is_preserved(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    package = action_package()
    qualification = save_package(tmp_path / 'qualification.json', package)
    with TestClient(create_app(tmp_path / 'data', runtime_role='API', capability_method_file=qualification)) as client:
        prepare(client, package)
        evaluation = client.post('/api/actions/evaluate', json={}).json()
        intent = client.post('/api/intents/prepare', json=intent_command(evaluation)).json()
        declaration = client.post('/api/intents/' + intent['intent_id'] + '/declare', json={
            'state':'OPERATION_PENDING','idempotency_key':'pending'})
        assert declaration.status_code == 200, declaration.text
        pending = declaration.json()
        pause(client)
        notices = client.get('/api/notifications').json()['notifications']
        notice = next(n for n in notices if n['source']['kind'] == 'EXTERNAL_OPERATION_PENDING')
        assert notice['category'] == 'NEED_SYNC_RECOVERY'
        assert client.get('/api/notifications/' + notice['notification_id'] + '/current').json()['current_state'] == 'CURRENT'
        assert client.get('/api/intents').json()['intents'][0] == pending
        assert client.post('/api/intents/prepare', json=intent_command(evaluation)).status_code == 409


def test_expired_action_is_archived_before_send_without_blocking_live_fact_notice(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    from datetime import datetime, timedelta
    package, requests = action_package(), []
    qualification = save_package(tmp_path / 'qualification.json', package)
    app = create_app(tmp_path / 'data', runtime_role='API', capability_method_file=qualification,
        notification_transport=httpx.MockTransport(lambda request: requests.append(request.content) or httpx.Response(200,json={'id':'live-fact','event':'message'})))
    with TestClient(app) as client:
        prepare(client, package)
        client.post('/api/actions/evaluate', json={})
        notice = next(n for n in client.get('/api/notifications').json()['notifications'] if n['category'] == 'NEED_ACTION')
        expired_clock = (datetime.fromisoformat(notice['expires_at']) + timedelta(seconds=1)).isoformat()
        monkeypatch.setattr('roll.decisions.notifications.now', lambda:expired_clock)
        monkeypatch.setattr('roll.decisions.actions.now', lambda:expired_clock)
        pause(client)
        client.post('/api/notification-channel', json={'expected_version':0,'enabled':True,
            'server':'https://ntfy.example.test','topic':'method-only','app_base_url':'http://127.0.0.1:5173'})
        app.state.notifications.work('owned-test-worker')
        current = client.get('/api/notifications/' + notice['notification_id'] + '/current').json()
        assert current['current_state'] == 'EXPIRED' and current['attempts'] == []
        assert client.get('/api/notifications').json()['notifications'][-1]['external_status'] == 'OUTBOUND_CLOSED'
        assert len(requests) == 1 and b'BUY' not in requests[0]


def test_public_restoration_creates_recovery_notice_without_restoring_grant_or_channel_secret(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test')
    with TestClient(create_app(tmp_path / 'source',runtime_role='API')) as client:
        draft = client.post('/api/account/drafts',json=baseline()).json()
        assert client.post('/api/account/confirm',json={'draft_id':draft['draft_id'],'idempotency_key':'baseline'}).status_code == 200
        backup = client.post('/api/runtime/backups').json()
        bundle = client.get('/api/runtime/backups/' + backup['backup_id'] + '/export').content
    with TestClient(create_app(tmp_path / 'target',runtime_role='API')) as client:
        assert client.post('/api/runtime/restores',content=bundle,headers={'content-type':'application/zip'}).status_code == 202
    with TestClient(create_app(tmp_path / 'target',runtime_role='API')) as client:
        notices = client.get('/api/notifications').json()['notifications']
        notice = next(n for n in notices if n['source']['kind'] == 'RECOVERY_LOCK')
        assert notice['category'] == 'NEED_SYNC_RECOVERY' and notice['severity'] == 'CRITICAL'
        assert client.get('/api/capabilities').json()['runtime_state'] == 'RECOVERY_LOCK'
        assert client.get('/api/notification-channel').json()['enabled'] is False
        assert client.get('/api/notifications/' + notice['notification_id'] + '/current').json()['current_state'] == 'CURRENT'
        closed = client.post('/api/formal/evaluate',json={})
        assert closed.status_code == 403 and closed.json()['detail']['code'] == 'RECOVERY_LOCK'
        assert len([n for n in client.get('/api/notifications').json()['notifications'] if n['source']['kind'] == 'RECOVERY_LOCK']) == 1


@pytest.mark.parametrize('response_kind,status,error',[
    ('rejected','FAILED','CHANNEL_HTTP_REJECTED'),
    ('redirect','FAILED','CHANNEL_HTTP_REJECTED'),
    ('malformed','RESULT_UNKNOWN','CHANNEL_RECEIPT_INVALID'),
    ('oversized','RESULT_UNKNOWN','CHANNEL_RESPONSE_LIMIT'),
])
def test_http_failure_receipts_are_bounded_sanitized_no_auto_retry(tmp_path,monkeypatch,response_kind,status,error):
    monkeypatch.setenv('ROLL_ENV','test')
    canary,requests='SYNTHETIC_RECEIPT_FAILURE_CANARY',[]
    def publish(request):
        requests.append(request.url.host)
        if response_kind == 'rejected': return httpx.Response(401,text=canary)
        if response_kind == 'redirect': return httpx.Response(302,headers={'location':'https://other.example.test/'+canary},text=canary)
        if response_kind == 'oversized': return httpx.Response(200,content=(canary*3000).encode())
        return httpx.Response(200,json={'event':'unexpected','id':canary})
    app=create_app(tmp_path/'data',runtime_role='API',notification_transport=httpx.MockTransport(publish))
    with TestClient(app) as client:
        pause(client)
        client.post('/api/notification-channel',json={'expected_version':0,'enabled':True,'server':'https://ntfy.example.test',
            'topic':'method-only','app_base_url':'http://127.0.0.1:5173','token':canary})
        app.state.notifications.work('owned-test-worker')
        notice=client.get('/api/notifications').json()['notifications'][0]
        current=client.get('/api/notifications/'+notice['notification_id']+'/current').json()
        assert notice['external_status'] == status and notice['delivered_at'] is None
        assert current['attempts'][0]['result']['error_code'] == error and canary not in str(current)
        app.state.notifications.work('owned-test-worker')
        assert requests == ['ntfy.example.test']


def test_repeated_current_reads_after_same_funding_failure_do_not_duplicate_major_notice(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test')
    package=action_package()
    qualification=save_package(tmp_path/'qualification.json',package)
    with TestClient(create_app(tmp_path/'data',runtime_role='API',capability_method_file=qualification)) as client:
        prepare(client,package)
        evaluation=client.post('/api/actions/evaluate',json={}).json()
        action=next(n for n in client.get('/api/notifications').json()['notifications'] if n['category']=='NEED_ACTION')
        changed=client.post('/api/funding/confirm',json=funding(2,total_exposure='10000.00',single_exposure='10000.00',cash_reserve='90000.00'))
        assert changed.status_code == 200,changed.text
        for _ in range(4):
            assert client.get('/api/actions/current').json()['decisions'] == []
            assert client.get('/api/notifications/'+action['notification_id']+'/current').json()['current_state'] == 'INVALIDATED'
        notifications=client.get('/api/notifications').json()['notifications']
        critical=[n for n in notifications if n['source']['kind']=='ACTION_INVALIDATION']
        assert len(critical) == 1
        assert critical[0]['reasons'] == ['FUNDING_VERSION_CHANGE','GRANT_RESTRICTED']
        assert next(n for n in notifications if n['notification_id']==action['notification_id'])['message'] == action['message']
        assert client.get('/api/actions/evaluations/'+evaluation['evaluation_id']).json() == evaluation


def test_valid_long_station_message_uses_bounded_external_projection_without_blocking_next_fact(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test')
    import json
    received=[]
    def publish(request):
        received.append(json.loads(request.content))
        return httpx.Response(200,json={'id':'method-length-'+str(len(received)),'event':'message'})
    app=create_app(tmp_path/'data',runtime_role='API',notification_transport=httpx.MockTransport(publish))
    with TestClient(app) as client:
        reason='界'*1600
        result=client.post('/api/capabilities/lifecycle',json={'scope':'ALL_MONITOR','state':'SUSPENDED',
            'reason_code':'USER_PAUSE','reason':reason,'expected_version':0,'idempotency_key':'long'})
        assert result.status_code == 200,result.text
        assert client.post('/api/account/drafts',json=baseline()).status_code == 201
        original=client.get('/api/notifications').json()['notifications']
        assert len(original)==2
        client.post('/api/notification-channel',json={'expected_version':0,'enabled':True,'server':'https://ntfy.example.test',
            'topic':'method-only','app_base_url':'http://127.0.0.1:5173'})
        app.state.notifications.work('owned-test-worker')
        app.state.notifications.work('owned-test-worker')
        assert len(received)==2 and all(len(v['message'].encode())<=4096 for v in received)
        after=client.get('/api/notifications').json()['notifications']
        assert next(n for n in after if n['source']['kind']=='CAPABILITY_SCOPE_CHANGED')['message']==reason
        assert all(n['external_status']=='CHANNEL_ACCEPTED' for n in after)
