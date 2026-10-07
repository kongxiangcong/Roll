from fastapi.testclient import TestClient
from roll.app import create_app
from test_execution_labels import method_archive,register
from test_account import baseline,submit
from test_funding import funding
from test_reconcile import declaration
import httpx
import pytest
from test_fills import fill


ASOF='2026-09-30T15:05:00+08:00'


def policy_case(client,directory,sellable='1050',quantity='1050',single='20000.00'):
    method_archive(directory)
    base=baseline();base['payload'].update(effective_at='2026-09-30T09:00:00+08:00',source='METHOD合成券商快照，非真实资金授权')
    base['payload']['positions']=[{'instrument':'SSE:600519','quantity':quantity,'sellable_quantity':sellable,'reference_cost':None}]
    submit(client,base,'method-account').raise_for_status()
    command=funding(single_exposure=single);command['authorization'].update(effective_at='2026-09-30T10:00:00+08:00',basis='METHOD已确认原参数；非人类真实资金',purpose='隔离METHOD账户')
    client.post('/api/funding/confirm',json=command).raise_for_status()
    client.post('/api/market/identities',json={'instrument':'SSE:600519','exchange':'SSE','board':'MAIN','instrument_type':'STOCK','name':'METHOD证券',
        'basis':'明确METHOD身份，不按代码猜板块','effective_at':'2026-09-30T09:00:00+08:00'}).raise_for_status()
    submit(client,declaration(1,['TRADES','ORDERS','EQUITY'],at=ASOF,record='method-fresh'),'method-fresh').raise_for_status()
    request=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['QUOTE'],'purpose':'OBSERVATION','start_date':'2026-09-30','end_date':'2026-09-30'}).json()
    client.post('/api/data/requests/'+request['request_id']+'/retrieve').raise_for_status()
    _,protocol=register(client)
    response=client.post('/api/research/protocols/'+protocol['protocol_id']+'/risk-policies',json={'basis':'固定独立暴露上限规则，不借收益G3/G4/G7豁免'})
    assert response.status_code==201,response.text
    return protocol,response.json()


def transport(price='30',status='NORMAL'):
    return httpx.MockTransport(lambda request:httpx.Response(200,json={'instrument':'SSE:600519','last':price,'upstream_at':'2026-09-30T15:00:00+08:00',
        'method_case_status':status,'basis':'明确METHOD9/30交易日行情；现在取得，不伪造历史可用','reported_limit_up':'33','reported_limit_down':'27'}))


def test_known_reduction_survives_cash_only_pending_and_rounds_minimum_quantity_without_default_sell_all(tmp_path):
    with TestClient(create_app(tmp_path,market_transport=transport())) as client:
        protocol,policy=policy_case(client,tmp_path)
        cash_draft=client.post('/api/account/drafts',json={'kind':'FEE','expected_account_version':2,'payload':{
            'effective_at':'2026-09-30T15:00:00+08:00','source':'METHOD纯费用待核','record_id':'fee-pending','amount':'5','basis':'金额待确认','instrument':None,'broker_available_after':None}})
        assert cash_draft.status_code==201,cash_draft.text
        before=client.get('/api/account').json()
        response=client.post('/api/research/risk-policies/'+policy['policy_id']+'/evaluations',json={'required_as_of':ASOF,'basis':'cash-only不 blanket block独立qty'})
        assert response.status_code==201,response.text
        result=response.json();assert result['account_use_check']['state']=='UPDATE_PENDING' and result['account_use_check']['allowed'] is True
        row=result['positions'][0];assert row['triggered'] is True and row['executable_quantity']=='400' and row['target_quantity']=='650'
        assert row['exposure_yuan']=='31500.00' and row['authorized_single_exposure_yuan']=='20000.00'
        assert result['engineering_verdict']=='PASS' and result['formal_action'] is None and result['capability']=='NOT_GRANTED'
        assert result['evidence_kind']=='METHOD_CASE' and result['validation_verdict']=='INCONCLUSIVE'
        assert row['stress']['gap_up']['remaining_exposure_yuan']=='21450.00' and row['stress']['limit_down_no_fill']['remaining_exposure_yuan']=='28350.00'
        assert client.post('/api/research/risk-evaluations/'+result['evaluation_id']+'/replay').json()['matches_original'] is True
        validation=client.get('/api/research/risk-policies/'+policy['policy_id']+'/validation').json()
        assert validation['gate_results']['ONLINE_CONSISTENCY']=='PASS' and validation['validation_verdict']=='INCONCLUSIVE'
        assert client.get('/api/account').json()==before
        assert client.get('/api/capabilities').json()['state']=='UNGRANTED'


def test_current_authorization_shrink_uses_existing_single_exposure_field_and_revoke_is_hard_failure(tmp_path):
    with TestClient(create_app(tmp_path,market_transport=transport())) as client:
        _,policy=policy_case(client,tmp_path)
        command=funding(1,single_exposure='10000.00',effective_at='2026-09-30T10:00:00+08:00')
        client.post('/api/funding/confirm',json=command).raise_for_status()
        result=client.post('/api/research/risk-policies/'+policy['policy_id']+'/evaluations',json={'required_as_of':ASOF,'basis':'授权缩小立即收窄，旧政策历史不变'}).json()
        assert result['positions'][0]['executable_quantity']=='800' and result['positions'][0]['target_quantity']=='250'
        assert result['authorization']['single_exposure']=='10000.00'
        assert client.get('/api/research/risk-policies/'+policy['policy_id']).json()==policy
        command=funding(2,enabled=False,single_exposure='10000.00',effective_at='2026-09-30T10:00:00+08:00')
        client.post('/api/funding/confirm',json=command).raise_for_status()
        blocked=client.post('/api/research/risk-policies/'+policy['policy_id']+'/evaluations',json={'required_as_of':ASOF,'basis':'撤回不是自动清仓'}).json()
        assert blocked['engineering_verdict']=='FAIL' and blocked['executable_quantities'] is None and blocked['formal_action'] is None
        assert 'AUTHORIZATION_REVOKED' in blocked['reasons']


@pytest.mark.parametrize('case',['sellable_unknown','quantity_draft','rule_unknown','suspended','no_excess_loss_unknown'])
def test_unknown_or_unresolved_required_facts_do_not_become_zero_quantity_or_default_judgment(case,tmp_path):
    with TestClient(create_app(tmp_path,market_transport=transport(price='10' if case=='no_excess_loss_unknown' else '30',status='SUSPENDED' if case=='suspended' else 'NORMAL'))) as client:
        _,policy=policy_case(client,tmp_path,sellable=None if case=='sellable_unknown' else '1050')
        if case=='quantity_draft':
            command=fill(2,'pending-qty');command['payload'].update(instrument='SSE:600519',effective_at='2026-09-30T13:00:00+08:00')
            assert client.post('/api/account/drafts',json=command).status_code==201
        if case=='rule_unknown':
            client.post('/api/market/identities',json={'instrument':'SSE:600519','exchange':'SSE','board':'UNKNOWN','instrument_type':'STOCK','name':'METHOD已知身份不足',
                'basis':'未知规则不得从代码猜','effective_at':'2026-09-30T09:00:00+08:00'}).raise_for_status()
        result=client.post('/api/research/risk-policies/'+policy['policy_id']+'/evaluations',json={'required_as_of':ASOF,'basis':case}).json()
        assert result['executable_quantities'] is None and result['formal_action'] is None and result['positions'][0]['executable_quantity'] is None
        assert result['display_state']=='FACTS_AND_PENDING_ONLY' and result['engineering_verdict']=='INCONCLUSIVE'
        assert client.post('/api/research/risk-evaluations/'+result['evaluation_id']+'/replay').json()['matches_original'] is True
        if case=='no_excess_loss_unknown':assert result['positions'][0]['triggered'] is None and 'LOSS_FACTS_UNKNOWN_NO_DEFAULT_JUDGMENT' in result['reasons']


@pytest.mark.parametrize('quantity,sellable,single,expected,target',[('1050','150','20000.00','100','950'),('50','50','1000.00','50','0')])
def test_sellable_intersection_and_entire_odd_remainder_are_calculated_without_inventing_t_plus_one(quantity,sellable,single,expected,target,tmp_path):
    with TestClient(create_app(tmp_path,market_transport=transport())) as client:
        _,policy=policy_case(client,tmp_path,sellable,quantity,single)
        result=client.post('/api/research/risk-policies/'+policy['policy_id']+'/evaluations',json={'required_as_of':ASOF,'basis':'sellable及整股/零股规则'}).json()
        row=result['positions'][0];assert row['executable_quantity']==expected and row['target_quantity']==target
        assert row['sellable_quantity']==sellable and result['formal_action'] is None
        assert client.post('/api/research/risk-evaluations/'+result['evaluation_id']+'/replay').json()['network_calls']==0


def test_unknown_real_loss_contract_cannot_trigger_or_reset_exposure_policy(tmp_path):
    with TestClient(create_app(tmp_path,market_transport=transport(price='10'))) as client:
        _,policy=policy_case(client,tmp_path)
        valuation=client.post('/api/account/valuations',json={'baseline_account_version':1,'origin_at':'2026-09-30T10:00:00+08:00','as_of':ASOF,'scope_kind':'ACCOUNT','scope_id':'account-1'})
        assert valuation.status_code==201,valuation.text
        assert valuation.json()['facts']['valuation_status']!='COMPLETE'
        response=client.post('/api/research/risk-policies/'+policy['policy_id']+'/evaluations',json={'required_as_of':ASOF,'valuation_id':valuation.json()['valuation_id'],'basis':'09同范围真实接口的期初未知，不能补0'})
        assert response.status_code==201,response.text
        result=response.json();assert result['loss_result']['status']=='RESTRICTED' and result['loss_result']['loss'] is None
        assert result['positions'][0]['triggered'] is None and result['executable_quantities'] is None
        assert client.post('/api/research/risk-evaluations/'+result['evaluation_id']+'/replay').json()['matches_original'] is True


def test_independent_policy_registration_without_authorization_keeps_facts_and_no_default_action(tmp_path):
    method_archive(tmp_path)
    with TestClient(create_app(tmp_path)) as client:
        _,protocol=register(client);pid=protocol['protocol_id']
        response=client.post('/api/research/protocols/'+pid+'/risk-policies',json={'basis':'独立确定性暴露边界政策，不继承收益模型结论'})
        assert response.status_code==201,response.text
        policy=response.json();assert policy['policy_type']=='AUTHORIZED_EXPOSURE_CAP_V1'
        assert policy['profit_model_dependency'] is False and policy['capability']=='NOT_GRANTED'
        assert policy['authorization']['version']==0 and 'FUNDING_AUTHORIZATION_MISSING' in policy['gaps']
        result=client.post('/api/research/risk-policies/'+policy['policy_id']+'/evaluations',json={'required_as_of':'2026-09-30T15:05:00+08:00','basis':'无授权事实路径'}).json()
        assert result['validation_verdict']=='INCONCLUSIVE' and result['formal_action'] is None
        assert result['display_state']=='FACTS_AND_PENDING_ONLY' and result['executable_quantities'] is None
        assert client.get('/api/account').json()['version']==0
        assert client.post('/api/formal/evaluate',json={'basis_type':'RISK_POLICY','policy_id':policy['policy_id'],'action':'EXIT'}).status_code==403
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/research/risk-policies/'+policy['policy_id']).json()==policy
        assert client.get('/api/research/risk-evaluations/'+result['evaluation_id']).json()==result
