"""Independent bounded METHOD HTTP/SQLite checks; no fit or actual qualification."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import json
import pytest
from fastapi.testclient import TestClient
from roll.app import create_app
from capability_method_app import save_package
from test_actions import action_package, prepare
from test_capabilities import ready, method_command
from test_intents import intent_command
from test_funding import funding
from test_lifecycle_composition import risk_package
from test_capability_monitoring import monitored_package
from test_monitoring_recovery import test_data_drift_resume_requires_a_later_bound_healthy_check_and_new_action as later_health_case
from test_capability_monitoring import test_actual_26_partial_fill_keeps_exact_fee_time_and_unknown_scenario_components as partial_case
from test_lifecycle_recovery import test_recovery_requires_current_source_bound_proof_and_new_broker_reconciliation as current_backup_case
from test_lifecycle_loss import test_trusted_method_loss_event_latches_new_risk_and_funding_expansion_cannot_resume as loss_case

def record(tmp_path,name,value):
    (tmp_path/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

@pytest.mark.parametrize('scope,control,risk_allowed',[
    ('NEW_RISK',(True,True,False),True),('MODEL',(True,False,False),True),('ALL_MONITOR',(False,False,False),False)])
def test_independent_scope_profit_and_risk(tmp_path,monkeypatch,scope,control,risk_allowed):
    monkeypatch.setenv('ROLL_ENV','test')
    p=action_package();file=save_package(tmp_path/'profit.json',p);data=tmp_path/'profit'
    with TestClient(create_app(data,capability_method_file=file)) as c:
        grant=prepare(c,p);old=c.post('/api/actions/evaluate',json={}).json()
        cmd={'scope':scope,'state':'SUSPENDED','reason_code':'USER_PAUSE','reason':'独立范围验收','expected_version':0,'idempotency_key':'scope-pause'}
        paused=c.post('/api/capabilities/lifecycle',json=cmd);assert paused.status_code==200,paused.text
        v=c.get('/api/capabilities/lifecycle').json()
        assert (v['observations_allowed'],v['model_judgments_allowed'],v['new_risk_allowed'])==control
        assert c.post('/api/capabilities/lifecycle',json=cmd).json()==paused.json()
        assert c.get('/api/actions/current').json()['decisions']==[]
        assert c.post('/api/intents/prepare',json=intent_command(old)).status_code==409
        assert c.get('/api/actions/evaluations/'+old['evaluation_id']).json()==old
        assert c.get('/api/capabilities/grants').json()==[grant]
        record(tmp_path,'profit-scope',{'old':old,'paused':paused.json(),'control':v})
    with TestClient(create_app(data,capability_method_file=file)) as c:
        assert c.get('/api/capabilities/lifecycle').json()['scopes'][scope]['state']=='SUSPENDED'
        assert c.post('/api/intents/prepare',json=intent_command(old)).status_code==409
    p=risk_package();file=save_package(tmp_path/'risk.json',p)
    with TestClient(create_app(tmp_path/'risk',capability_method_file=file)) as c:
        ready(c,permission_status='NOT_OPEN',positions=[{'instrument':'SSE:600000','quantity':'300','sellable_quantity':'300','reference_cost':'100'}])
        response=c.post('/api/capabilities/grants',json={**method_command(),'allowed_actions':['REDUCE','EXIT'],'deployment_fingerprints':p['deployment_fingerprints']})
        assert response.status_code==201,response.text
        risk=response.json();assert c.post('/api/capabilities/lifecycle',json=cmd).status_code==200
        result=c.post('/api/actions/evaluate',json={}).json()
        assert [(d['action'],d['quantity']) for d in result['decisions']]==([('REDUCE','100')] if risk_allowed else [])
        assert c.get('/api/account').json()['positions'][0]['sellable_quantity']=='300'
        assert c.get('/api/capabilities/grants').json()==[risk]
        assert c.post('/api/formal/evaluate',json={}).status_code==403
        record(tmp_path,'risk-scope',result)

def test_concurrent_current_monitor_and_permission_writer(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test');p=monitored_package(20);file=save_package(tmp_path/'qualification.json',p)
    with TestClient(create_app(tmp_path/'data',capability_method_file=file)) as c:
        grant=prepare(c,p);barrier=Barrier(3)
        def reader():
            barrier.wait();values=[]
            for _ in range(10):
                response=c.get('/api/capabilities');assert response.status_code==200,response.text
                values.append(response.json()['runtime_state'])
                assert c.get('/api/actions/current').status_code==200
            return values
        with ThreadPoolExecutor(max_workers=2) as pool:
            tasks=[pool.submit(reader) for _ in range(2)];barrier.wait()
            checks=[]
            for i in range(3):
                pause=c.post('/api/capabilities/lifecycle',json={'scope':'NEW_RISK','state':'SUSPENDED','reason_code':'USER_PAUSE','reason':'独立并发','expected_version':2*i,'idempotency_key':f'p{i}'})
                assert pause.status_code==200,pause.text
                m=c.post('/api/capabilities/monitoring/check',json={'grant_id':grant['grant_id'],'basis':'独立健康检查'})
                assert m.status_code==201,m.text
                assert m.json()['status']=='CHECKED',m.text;checks.append(m.json())
                resume=c.post('/api/capabilities/lifecycle',json={'scope':'NEW_RISK','state':'ACTIVE','reason_code':'USER_PAUSE','reason':'同原因恢复','expected_version':2*i+1,'resume_event_id':pause.json()['event_id'],'idempotency_key':f'r{i}'})
                assert resume.status_code==200,resume.text
            states=[v for task in tasks for v in task.result()]
        assert len(states)==20 and 'RECOVERY_LOCK' not in states
        assert c.get('/api/capabilities/recovery').json()['state']=='NOT_RESTORED'
        assert not (tmp_path/'data/backups/recovery-lock.json').exists()
        assert c.get('/api/capabilities/grants').json()==[grant]
        assert len([e for e in c.get('/api/capabilities/events').json() if e.get('scope')=='NEW_RISK'])==6
        record(tmp_path,'concurrent',{'states':states,'checks':checks})

def test_later_health_and_old_card_nonrevival(tmp_path,monkeypatch):
    later_health_case(tmp_path,monkeypatch)

def test_checkpoint_consumed_once_and_no_extra_pass(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test');p=monitored_package(30)
    p['monitoring_basis']['results']=[{'known_at':p['required_as_of'],'mature_at':p['required_as_of'],'mature':True,'label':1},
        {'known_at':p['required_as_of'],'mature':False,'label':None}]
    file=save_package(tmp_path/'qualification.json',p)
    with TestClient(create_app(tmp_path/'data',capability_method_file=file)) as c:
        grant=prepare(c,p);command={'grant_id':grant['grant_id'],'basis':'固定登记点独立验收'}
        first=c.post('/api/capabilities/monitoring/check',json=command).json()
        assert first['maturity']['mature_count']==1 and first['maturity']['excluded_unmatured']==1
        assert first['statistical_verdict']=='INCONCLUSIVE' and first['confirmation_pass_look'] is False
        second=c.post('/api/capabilities/monitoring/check',json=command).json()
        assert second['maturity']['review_status']=='REGISTERED_CHECKPOINT_ALREADY_CONSUMED'
        assert second['maturity']['original_check_id']==first['check_id']
        assert second['statistical_verdict']=='NOT_REVIEWED' and second['mature_review'] is None
        assert c.post('/api/capabilities/monitoring/'+first['check_id']+'/replay').json()['matches_original'] is True
        record(tmp_path,'checkpoint',{'first':first,'second':second})

def test_partial_execution_unknowns_and_correction(tmp_path,monkeypatch):
    partial_case(tmp_path,monkeypatch)
    with TestClient(create_app(tmp_path/'data',capability_method_file=tmp_path/'qualification.json')) as c:
        checks=c.get('/api/capabilities/monitoring').json();check=checks[-1]
        assert check['correction_class']=='EXECUTION_ASSUMPTION'
        command={'monitoring_check_id':check['check_id'],'category':'EXECUTION_ASSUMPTION',
            'error_source':'实际METHOD部分成交超出冻结价窗且费用/时间口径未知','expected_improvement':'单独核对执行条件',
            'affected_modules':['decisions/intents'],'validation_plan':'核对原成交与冻结价窗及未知时间字段',
            'changes_frozen':False,'idempotency_key':'independent-correction'}
        response=c.post('/api/capabilities/corrections',json=command)
        assert response.status_code==201,response.text
        value=response.json()
        assert value['source_check_archive_sha256']==check['archive']['sha256']
        assert value['qualification_verdict_changed'] is False
        assert value['validation_plan']==command['validation_plan']
        assert c.post('/api/capabilities/corrections',json=command).json()==value
        unproven=c.post('/api/capabilities/corrections',json={**command,'category':'USER_DELAY','idempotency_key':'unproven-user-delay'})
        assert unproven.status_code==409 and unproven.json()['detail']=='USER_DELAY_NOT_ESTABLISHED_BY_SOURCE'
        record(tmp_path,'execution-correction',value)

def test_loss_rebound_expansion_wrong_reason_and_no_policy_resume(tmp_path,monkeypatch):
    loss_case(tmp_path,monkeypatch)
    file=tmp_path/'qualification.json'
    with TestClient(create_app(tmp_path/'data',capability_method_file=file)) as c:
        control=c.get('/api/capabilities/lifecycle').json()
        event=next(e for e in c.get('/api/capabilities/events').json() if e.get('reason_code')=='LOSS_BOUNDARY')
        response=c.post('/api/capabilities/lifecycle',json={'scope':'NEW_RISK','state':'ACTIVE','reason_code':'LOSS_BOUNDARY','reason':'无冻结恢复证据不能解除','expected_version':control['version'],'resume_event_id':event['event_id'],'idempotency_key':'unregistered-positive'})
        assert response.status_code==409,response.text
        assert c.get('/api/capabilities/lifecycle').json()['new_risk_allowed'] is False
        record(tmp_path,'loss-refusal',{'event':event,'refusal':response.json()})

def test_current_proof_backup_recovery_and_relock(tmp_path,monkeypatch):
    current_backup_case(tmp_path,monkeypatch)

def test_targeted_all_monitor_and_terminal_have_no_new_check(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test');p=monitored_package(20);file=save_package(tmp_path/'qualification.json',p)
    with TestClient(create_app(tmp_path/'data',capability_method_file=file)) as c:
        grant=prepare(c,p);old=c.post('/api/actions/evaluate',json={}).json()
        cmd={'grant_id':grant['grant_id'],'scope':'ALL_MONITOR','state':'SUSPENDED','reason_code':'USER_PAUSE','reason':'目标监测暂停','expected_version':0,'idempotency_key':'target-pause'}
        response=c.post('/api/capabilities/lifecycle',json=cmd);assert response.status_code==200,response.text
        checks=c.get('/api/capabilities/monitoring').json()
        assert c.post('/api/capabilities/monitoring/check',json={'grant_id':grant['grant_id'],'basis':'不得偷跑'}).json()['detail']=='ALL_MONITOR_SUSPENDED'
        resume={**cmd,'state':'ACTIVE','expected_version':1,'resume_event_id':response.json()['event_id'],'idempotency_key':'target-resume'}
        assert c.post('/api/capabilities/lifecycle',json=resume).status_code==200
        revoke=c.post('/api/capabilities/lifecycle',json={**cmd,'scope':'MODEL','state':'REVOKED','reason_code':'USER_REVOKE','expected_version':2,'idempotency_key':'terminal'})
        assert revoke.status_code==200,revoke.text
        refused=c.post('/api/capabilities/monitoring/check',json={'grant_id':grant['grant_id'],'basis':'撤回后不得偷跑'})
        assert refused.status_code==409 and refused.json()['detail']=='TERMINAL_GRANT_MONITORING_CLOSED'
        assert c.get('/api/capabilities/monitoring').json()==checks
        assert c.post('/api/intents/prepare',json=intent_command(old)).status_code==409
        assert c.get('/api/actions/evaluations/'+old['evaluation_id']).json()==old
        assert c.get('/api/account').status_code==200
        record(tmp_path,'terminal',{'revoke':revoke.json(),'refused':refused.json()})
