from fastapi.testclient import TestClient
from roll.app import create_app
from capability_method_app import save_package
from test_actions import action_package,prepare
from test_funding import funding
from test_capability_monitoring import monitored_package


def prepared_loss(client,p):
    original=prepare(client,p);decline=client.post('/api/actions/evaluate',json={}).json()
    pause=next(e for e in client.get('/api/capabilities/events').json() if e.get('reason_code')=='LOSS_BOUNDARY')
    assert decline['joint_budget']['loss']['peak_loss']=='6000.00'
    assert client.post('/api/funding/confirm',json=funding(2,loss_threshold='10000.00',single_exposure='40000.00')).status_code==200
    lifecycle=client.get('/api/capabilities/lifecycle').json()
    retired=client.post('/api/capabilities/lifecycle',json={'grant_id':original['grant_id'],'scope':'MODEL','state':'REVOKED','reason_code':'USER_REVOKE','reason':'Retire original grant for explicit loss successor','expected_version':lifecycle['version'],'idempotency_key':'retire'})
    assert retired.status_code==200,retired.text
    proposal=client.get('/api/capabilities/proposal',params={'material_id':p['material_id'],'review_run_id':p['review_run_id']}).json()
    successor=client.post('/api/capabilities/grants',json={**proposal,'allowed_actions':['BUY'],'predecessor_grant_id':original['grant_id'],'idempotency_key':'new-grant','basis':'Fresh current qualification after explicit boundary reconfirmation'})
    assert successor.status_code==201,successor.text
    successor=successor.json();control=client.get('/api/capabilities/lifecycle').json()
    command={'pause_event_id':pause['event_id'],'successor_grant_id':successor['grant_id'],'expected_funding_version':3,'expected_account_version':2,'expected_lifecycle_version':control['version'],'idempotency_key':'check','basis':'User chose reconfirmed boundary plus successor, preserving peak/history'}
    return original,decline,pause,successor,command


def test_explicit_boundary_and_successor_recover_loss_without_resetting_peak_or_old_grant(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test')
    p=monitored_package();p['action_packet']['loss_facts']={**p['loss_facts'],'facts_version':'method-loss6000','net_assets':'94000.10','realized_pnl':'-6000.00'}
    file=save_package(tmp_path/'qualification.json',p);directory=tmp_path/'data'
    with TestClient(create_app(directory,capability_method_file=file)) as client:
        original,decline,pause,successor,command=prepared_loss(client,p)
        response=client.post('/api/funding/loss-recovery/checks',json=command);assert response.status_code==201,response.text
        check=response.json();assert check['status']=='READY' and check['gaps']==[],check['gaps']
        route='/api/funding/loss-recovery/checks/'+check['check_id']+'/activate'
        activate={'idempotency_key':'activate','acknowledge_preserved_peak':True,'basis':'Explicit activation after inspecting preserved peak 6000 and threshold 10000'}
        response=client.post(route,json=activate);assert response.status_code==201,response.text
        receipt=response.json();assert receipt['preserved_peak_loss']=='6000.00'
        assert client.post(route,json=activate).json()==receipt
        assert client.get('/api/capabilities/grants/'+original['grant_id']+'/status').json()['state']=='REVOKED'
        current=client.post('/api/actions/evaluate',json={}).json();loss=current['joint_budget']['loss']
        assert loss['status']=='WITHIN_BOUNDARY' and loss['peak_loss']=='6000.00'
        assert loss['historical_triggered'] is True and loss['triggered'] is False
        assert len(current['decisions'])==1 and current['decisions'][0]['grant_id']==successor['grant_id']
        assert client.get('/api/actions/evaluations/'+decline['evaluation_id']).json()==decline
        assert client.post('/api/actions/evaluations/'+decline['evaluation_id']+'/replay').json()['matches_original']
        assert client.get('/api/funding/loss-recovery/receipts').json()==[receipt]
        assert client.get('/api/account').json()['version']==2
        # Literal financial contract: a later breach latches anew; rebound or
        # enlarged boundary cannot acknowledge it with the old recovery id.
        from roll.decisions.funding import LossFacts,evaluate_loss
        auth=client.get('/api/funding').json()
        assert 'loss_recovery' not in client.get('/api/funding/versions/3').json()
        again=LossFacts(**{**p['action_packet']['loss_facts'],'facts_version':'method-loss11000','net_assets':'89000.10','realized_pnl':'-11000.00'})
        next_loss=evaluate_loss(auth,again,loss)
        assert next_loss['status']=='PAUSED' and next_loss['peak_loss']=='11000.00'
        rebound=LossFacts(**{**p['loss_facts'],'facts_version':'method-rebound'})
        assert evaluate_loss(auth,rebound,next_loss)['status']=='PAUSED'
        assert evaluate_loss({**auth,'loss_threshold':'20000.00'},rebound,next_loss)['status']=='PAUSED'
        for pointer in (check['archive'],check['rule']):
            raw=client.app.state.evidence.raw(pointer['sha256']);body=raw.read_bytes()
            try:
                raw.write_bytes(b'corrupt recovery prerequisite')
                assert client.get('/api/funding').status_code==409
                assert client.get('/api/funding/loss-recovery/receipts').status_code==409
                assert client.post(route,json=activate).status_code==409
            finally:raw.write_bytes(body)

    with TestClient(create_app(directory,capability_method_file=file)) as client:
        assert client.get('/api/funding/loss-recovery/receipts').json()==[receipt]
        assert client.get('/api/capabilities/grants/'+original['grant_id']+'/status').json()['state']=='REVOKED'
        assert client.post('/api/actions/evaluate',json={}).json()['joint_budget']['loss']['peak_loss']=='6000.00'


def test_pending_account_change_after_capture_refuses_activation(tmp_path,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    monkeypatch.setenv('ROLL_ENV','test')
    p=monitored_package();p['action_packet']['loss_facts']={**p['loss_facts'],'facts_version':'method-loss6000','net_assets':'94000.10','realized_pnl':'-6000.00'}
    file=save_package(tmp_path/'qualification.json',p)
    with TestClient(create_app(tmp_path/'data',capability_method_file=file)) as client:
        original,decline,pause,successor,command=prepared_loss(client,p)
        checked=client.post('/api/funding/loss-recovery/checks',json=command).json();assert checked['status']=='READY',checked
        captured=Event();release=Event();real_capture=client.app.state.actions.capture
        # Synchronization only: retain the real capture result; no substituted
        # account, valuation or authorization evidence.
        def barrier(command):
            value=real_capture(command);captured.set();assert release.wait(10);return value
        monkeypatch.setattr(client.app.state.actions,'capture',barrier)
        with ThreadPoolExecutor(max_workers=1) as pool:
            running=pool.submit(client.post,'/api/funding/loss-recovery/checks/'+checked['check_id']+'/activate',json={'idempotency_key':'raced','acknowledge_preserved_peak':True,'basis':'Must not accept a stale account capture'})
            assert captured.wait(10)
            try:
                draft=client.post('/api/account/drafts',json={'kind':'ACCOUNT_DECLARATION','expected_account_version':2,'payload':{'effective_at':p['required_as_of'],'source':'METHOD pending user facts','record_id':'new-pending','scope':['TRADES','ORDERS','CASH','EQUITY'],'changes':'NONE','basis':'Isolated draft inserted between capture and recovery commit'}})
                assert draft.status_code==201,draft.text
                assert client.get('/api/account').json()['version']==2
            finally:release.set()
            refused=running.result()
        assert refused.status_code==409,refused.text
        assert 'CURRENT_ACCOUNT_USE_CHANGED' in refused.text
        assert client.get('/api/funding/loss-recovery/receipts').json()==[]
        assert client.get('/api/capabilities/lifecycle').json()['new_risk_allowed'] is False


def test_recovery_history_survives_a_later_peak_within_the_new_boundary():
    from roll.decisions.funding import evaluate_loss,LossFacts
    from test_funding import loss_facts
    auth={**funding()['authorization'],'version':3,'baseline_account_version':1,'loss_origin_at':'2026-10-07T02:00:00+00:00','loss_threshold':'10000.00'}
    auth['loss_recovery']={'recovery_id':'fixed-recovery','funding_version':3,'acknowledged_peak_loss':'6000.00','loss_scope':{'scope_kind':'ACCOUNT','scope_id':'account-1','baseline_account_version':1,'origin_at':auth['loss_origin_at']}}
    previous={'peak_loss':'6000.00','triggered':False,'historical_triggered':True,'loss_recovery_id':'fixed-recovery','as_of':'2026-10-07T03:00:00+00:00','baseline_assets':'100000.00'}
    facts=LossFacts(**loss_facts(net_assets='93000.00',external_in='0.00',external_out='0.00',realized_pnl='-7000.00',unrealized_pnl='0.00',income='0.00',fees='0.00'))
    first=evaluate_loss(auth,facts,previous)
    assert first['peak_loss']=='7000.00' and first['historical_triggered'] is True and first['loss_recovery_id']=='fixed-recovery'
    second=evaluate_loss(auth,facts,first)
    assert second['status']=='WITHIN_BOUNDARY' and second['historical_triggered'] is True and second['loss_recovery_id']=='fixed-recovery'
