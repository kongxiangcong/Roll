"""Independent finite literal callers. Test-only METHOD; no real qualification or model fitting."""
import json
from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from roll.app import create_app
from capability_method_app import save_package
from action_order_method import paired_package,grant_command
from test_action_risk_priority import setup,method_clock
from test_actions import action_package,prepare
from test_account import submit
from test_funding import funding
def record(p,name,value):(p/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def qualify(c,p,profit=True):
    setup(c,p);grants=[]
    for v,k in ([(p,'profit')] if profit else [])+[(p['risk_qualification'],'risk')]:
        r=c.post('/api/capabilities/grants',json=grant_command(v,k));assert r.status_code==201,r.text;grants.append(r.json())
    return grants
def test_risk_then_buy_literal_budget_own_grants_and_replay(tmp_path,monkeypatch):
    method_clock(monkeypatch);p=paired_package();file=save_package(tmp_path/'qualification.json',p)
    with TestClient(create_app(tmp_path/'data',capability_method_file=file,runtime_role='API')) as c:
        grants=qualify(c,p);account=c.get('/api/account').json()
        r=c.post('/api/actions/evaluate',json={});assert r.status_code==201,r.text;v=r.json()
        assert [(d['instrument'],d['action'],d['quantity'],d['target_quantity']) for d in v['decisions']]==[('SSE:600000','REDUCE','100','200'),('SSE:600001','BUY','200','200')]
        risk,buy=v['decisions'];assert risk['grant_id']==grants[1]['grant_id'] and buy['grant_id']==grants[0]['grant_id']
        assert risk['model_status']=='NOT_APPLICABLE' and buy['model_status']=='METHOD_ENGINEERING'
        assert risk['required_cash_yuan']=='0.00' and buy['required_cash_yuan']=='10005.00'
        assert all(d['execution_eligibility']=='METHOD_ONLY' and d['capability_status']['state']=='METHOD_GRANTED' for d in v['decisions'])
        assert v['joint_budget']['existing_exposure_yuan']=='30000.00' and v['joint_budget']['reserved_yuan']=='10005.00'
        assert next(d for d in v['refusals'] if d['instrument']=='SSE:600002')['reasons']==['ONE_NEW_ENTRY_LIMIT']
        assert not v['system_usable'] and c.get('/api/account').json()==account
        assert c.get('/api/actions/current').json()['decisions']==v['decisions']
        assert c.post('/api/actions/evaluations/'+v['evaluation_id']+'/replay').json()['matches_original']
        assert grants[0]['proof_id']!=grants[1]['proof_id']
        record(tmp_path,'ordered-public',{'evaluation':v,'grants':grants,'unchanged_account':account})

@pytest.mark.parametrize('fault',['unsupported','ungranted_invalid_probability'])
def test_profit_failure_preserves_qualified_risk(tmp_path,monkeypatch,fault):
    method_clock(monkeypatch);p=paired_package()
    if fault=='unsupported':p['action_packet']['policy']={'version':'UNSUPPORTED'}
    else:
        for row in p['action_packet']['opportunities']:row['probability']='INVALID_UNAUTHORIZED_NUMERIC_INPUT'
    file=save_package(tmp_path/'qualification.json',p)
    with TestClient(create_app(tmp_path/'data',capability_method_file=file,runtime_role='API'),raise_server_exceptions=False) as c:
        grants=qualify(c,p,profit=fault=='unsupported')
        r=c.post('/api/actions/evaluate',json={});assert r.status_code==201,r.text;v=r.json()
        assert [(d['action'],d['quantity'],d['target_quantity']) for d in v['decisions']]==[('REDUCE','100','200')]
        risk=v['decisions'][0];assert risk['grant_id']==grants[-1]['grant_id'] and risk['model_status']=='NOT_APPLICABLE' and risk['execution_eligibility']=='METHOD_ONLY'
        if fault=='unsupported':assert 'FROZEN_POLICY_NOT_SUPPORTED' in v['limitations']
        else:
            assert len(v['refusals'])==3
            for row in v['refusals']:
                assert row['capability_status']['state']=='UNGRANTED' and row['execution_eligibility']=='BLOCKED' and row['model_status']=='UNQUALIFIED'
                assert row['probability_visibility']=='UNQUALIFIED_INPUT_NOT_SCORED' and 'probability' not in row
        assert v['joint_budget']['reserved_yuan']=='0.00'
        assert c.post('/api/actions/evaluations/'+v['evaluation_id']+'/replay').json()['matches_original']
        record(tmp_path,'risk-retained',v)

def test_invalidation_first_fact_immutable_new_account_cause_restart(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test');p=action_package();file=save_package(tmp_path/'qualification.json',p);data=tmp_path/'data'
    with TestClient(create_app(data,capability_method_file=file,runtime_role='API')) as c:
        prepare(c,p);old=c.post('/api/actions/evaluate',json={}).json();assert len(old['decisions'])==1
        assert c.post('/api/funding/confirm',json=funding(2,total_exposure='10000.00',single_exposure='10000.00',cash_reserve='90000.00')).status_code==200
        first=c.get('/api/actions/current').json();assert first['invalidated'][0]['reasons']==['FUNDING_VERSION_CHANGE','GRANT_RESTRICTED']
        events=[e for e in c.get('/api/actions/events').json() if e['event_type']=='ACTION_INVALIDATED'];assert len(events)==1
        for _ in range(2):
            current=c.get('/api/actions/current').json();assert current['decisions']==[]
            assert 'PREVIOUSLY_INVALIDATED_REQUIRES_NEW_ACTION' in current['invalidated'][0]['reasons']
            assert [e for e in c.get('/api/actions/events').json() if e['event_type']=='ACTION_INVALIDATED']==events
        r=submit(c,{'kind':'ACCOUNT_DECLARATION','expected_account_version':2,'payload':{'effective_at':p['required_as_of'],'source':'Independent METHOD confirmed facts','record_id':'later-account','scope':['TRADES','ORDERS','CASH','EQUITY'],'changes':'NONE','basis':'Independent same no-change declaration'}},'later-account')
        assert r.status_code==200,r.text
        latest=c.get('/api/actions/current').json();assert latest['decisions']==[]
        assert 'ACCOUNT_VERSION_CHANGE' in latest['invalidated'][0]['reasons']
        assert c.get('/api/account').json()['version']==3 and c.get('/api/account/versions/3').status_code==200
        assert [e for e in c.get('/api/actions/events').json() if e['event_type']=='ACTION_INVALIDATED']==events
        assert c.get('/api/actions/evaluations/'+old['evaluation_id']).json()==old
        assert c.post('/api/actions/evaluations/'+old['evaluation_id']+'/replay').json()['matches_original']
        record(tmp_path,'invalidation-public',{'first_events':events,'first_current':first,'latest_current':latest,'old_evaluation':old,'new_account_receipt':r.json()})
    with TestClient(create_app(data,capability_method_file=file,runtime_role='API')) as c:
        assert c.get('/api/actions/current').json()['decisions']==[]
        assert [e for e in c.get('/api/actions/events').json() if e['event_type']=='ACTION_INVALIDATED']==events
        assert c.get('/api/actions/audit').json()['invalidated_actions']=={'status':'CHECKED','value':1}

def test_whole_envelope_child_shared_gate_and_production_refusal(tmp_path,monkeypatch):
    method_clock(monkeypatch);p=paired_package();file=save_package(tmp_path/'qualification.json',p)
    monkeypatch.delenv('ROLL_ENV')
    with pytest.raises(ValueError,match='CAPABILITY_METHOD_HOST_TEST_ONLY'):create_app(tmp_path/'prod',capability_method_file=file,runtime_role='API')
    monkeypatch.setenv('ROLL_ENV','test');v=json.loads(file.read_bytes());v['package']['risk_qualification']['deployment_fingerprints']['policy']='f'*64
    file.write_text(json.dumps(v),encoding='utf-8')
    with pytest.raises(ValueError,match='CAPABILITY_METHOD_PACKAGE_INVALID'):create_app(tmp_path/'tamper',capability_method_file=file,runtime_role='API')
    p=paired_package();p['risk_qualification']['current_data']={'status':'CONFLICT'};file=save_package(tmp_path/'shared.json',p)
    with pytest.raises(ValueError,match='CAPABILITY_METHOD_RISK_BINDING_INVALID'):create_app(tmp_path/'shared',capability_method_file=file,runtime_role='API')
    p=paired_package();p['risk_qualification']['gates']['STRESS_EXECUTION']='FAIL';file=save_package(tmp_path/'gate.json',p)
    with TestClient(create_app(tmp_path/'gate',capability_method_file=file,runtime_role='API')) as c:
        setup(c,p);assert c.post('/api/capabilities/grants',json=grant_command(p,'profit')).status_code==201
        r=c.post('/api/capabilities/grants',json=grant_command(p['risk_qualification'],'risk'));assert r.status_code==409,r.text
        assert 'REQUIRED_GATES_NOT_PASS' in r.json()['detail']['reasons']
        v=c.post('/api/actions/evaluate',json={}).json();assert [d['action'] for d in v['decisions']]==['BUY']
        assert v['holding_risks'][0]['capability_status']['state']=='UNGRANTED' and v['holding_risks'][0]['execution_eligibility']=='BLOCKED'
        record(tmp_path,'child-gate-refusal',{'refusal':r.json(),'evaluation':v})
