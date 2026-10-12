from fastapi.testclient import TestClient
from roll.app import create_app
from test_transparent_models import known_method
import math
from decimal import Decimal
from test_account import submit, baseline
from test_fills import fill, fee_adjustment
from test_reconcile import correction
from datetime import date, timedelta


def setup(client, directory):
    dataset, protocol, dates = known_method(client, directory)
    model = client.post('/api/research/protocols/'+protocol['protocol_id']+'/models', json={
        'purpose': 'METHOD_VALIDATION', 'basis': 'Frozen deterministic shadow engineering'}).json()
    return dataset, protocol, model, dates


def freeze(client, protocol, model, **changes):
    command = {'model_run_id': model['model_run_id'],
        'attempt_ids': client.get('/api/research/protocols/'+protocol['protocol_id']+'/attempt-manifest').json()['attempt_ids'],
        'artifact_fingerprints': model['artifact_fingerprints'], 'baseline': {'cash_yuan': '100000.00', 'positions': []},
        'basis': 'METHOD frozen policy and isolated baseline, never qualification', **changes}
    return client.post('/api/research/protocols/'+protocol['protocol_id']+'/complete-freezes', json=command)


def test_complete_freeze_binds_all_methods_and_is_immutable_without_qualification(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        dataset, protocol, model, dates = setup(client, tmp_path)
        response = freeze(client, protocol, model)
        assert response.status_code == 201, response.text
        frozen = response.json()
        assert frozen['complete_experiment_frozen'] is True
        assert frozen['evidence_kind'] == 'METHOD_CASE'
        assert frozen['capability'] == 'NOT_GRANTED' and frozen['system_usable'] is False
        assert frozen['calibrator_fit_status'] == 'FITTED_UNVALIDATED'
        assert frozen['design']['g5'] == protocol['design']['g5']
        assert frozen['design']['formal_monitoring'] == protocol['design']['formal_monitoring']
        assert set(frozen['fingerprints']) >= {'model', 'calibrator', 'features_and_inputs', 'data', 'model_code',
            'policy', 'rules', 'fees', 'execution_missing', 'g5', 'formal_monitoring', 'shadow_code', 'design'}
        assert freeze(client, protocol, model).status_code == 409
        assert client.get('/api/research/complete-freezes/'+frozen['freeze_id']).json() == frozen
        assert client.get('/api/research/protocols/'+protocol['protocol_id']).json()['forward_started_at'] is None


def high_forecasts(client, model):
    candidate = next(p for p in model['calibration_predictions']
        if 1/(1+math.exp(-p['logit']-model['calibrator']['intercept_shift'])) >= .60)
    return [client.post('/api/research/models/'+model['model_run_id']+'/forecasts', json={
        'observation_date': candidate['observation_date'], 'basis': 'Historical METHOD archived opportunity'}).json() for _ in range(2)]


def test_continuous_joint_budget_replay_and_actual_backfill_do_not_reset_shadow(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        dataset, protocol, model, dates = setup(client, tmp_path)
        frozen = freeze(client, protocol, model).json()
        forecasts = high_forecasts(client, model)
        day = forecasts[0]['observation_cutoff'][:10]
        path = '/api/research/shadow/'+frozen['freeze_id']
        response = client.post(path+'/advance', json={'through_date': day, 'forecast_ids': [f['forecast_id'] for f in reversed(forecasts)], 'expected_revision': 0})
        assert response.status_code == 201, response.text
        state = response.json()
        assert [o['forecast_id'] for o in state['opportunities']] == sorted(f['forecast_id'] for f in forecasts)
        assert [o['action'] for o in state['opportunities']] == ['BUY', 'REFUSE']
        assert state['opportunities'][1]['reasons'] == ['OVERLAPPING_POSITION_OR_ORDER']
        assert state['cash_yuan'] == '100000.00'
        assert Decimal(state['reserved_cash_yuan']) > 0
        final_day = dates[dates.index(day)+20]
        final = client.post(path+'/advance', json={'through_date': final_day, 'forecast_ids': [], 'expected_revision': 1})
        assert final.status_code == 201, final.text
        state = final.json()
        assert [e['kind'] for e in state['events']] == ['BUY_FILL', 'SELL_FILL']
        assert state['positions'] == [] and state['reserved_cash_yuan'] == '0.00'
        assert state['opportunities'][1]['counterfactual']['diagnostic_only'] is True
        assert state['opportunities'][1]['model_loss_from_refusal'] is False
        assert set(state['comparators']) == {'CASH', 'START_HOLD', 'MA5_MA20'}
        assert state['comparators']['CASH']['cash_yuan'] == '100000.00'
        assert client.post(path+'/replay').json()['matches_original'] is True
        actual_baseline=baseline();actual_baseline['payload']['positions'][0]['instrument']='SSE:600519'
        submit(client, actual_baseline, 'actual-baseline')
        inverse=fill(1,'inverse','SELL','PROVISIONAL')
        inverse['payload'].update(instrument='SSE:600519',quantity='100')
        sale=submit(client,inverse,'actual-inverse-backfill')
        assert sale.status_code==200,sale.text
        assert submit(client,fee_adjustment(2,target='inverse'),'actual-fee-known').status_code==200
        replacement={'kind':'FILL','payload':{**inverse['payload'],'price':'11.00'}}
        assert submit(client,correction(3,'correct-inverse',sale.json()['event_ids'][0],replacement),'actual-correction').status_code==200
        assert client.get(path).json() == state
        separated = client.get('/api/research/results', params={'freeze_id': frozen['freeze_id']}).json()
        assert set(separated) == {'ACTUAL', 'HISTORICAL', 'SHADOW', 'ACCOUNT_CONDITIONAL'}
        assert separated['ACTUAL']['version'] == 4
        diagnostic = client.post(path+'/account-conditional', json={'forecast_ids': [f['forecast_id'] for f in forecasts]}).json()
        assert diagnostic['namespace'] == 'ACCOUNT_CONDITIONAL' and diagnostic['continuous_performance'] is False
        assert diagnostic['price_as_of_date']==day
        assert diagnostic['valuation_inputs'][0]['trade_date']==day
        assert diagnostic['valuation_basis']=='HISTORICAL_RAW_AT_FORECAST_CUTOFF_NOT_CURRENT_PRICE'
        assert client.get(path).json() == state
        assert client.post(path+'/advance', json={'through_date': final_day, 'forecast_ids': [], 'expected_revision': 1}).status_code == 409
    with TestClient(create_app(tmp_path)) as client:
        assert client.get(path).json() == state
        assert client.post(path+'/replay').json()['matches_original'] is True


def test_freeze_rejects_incomplete_binding_and_successor_starts_separate_budgeted_history(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        dataset, protocol, model, dates = setup(client, tmp_path)
        bad = freeze(client, protocol, model, artifact_fingerprints={})
        assert bad.status_code == 409 and 'ARTIFACT_FINGERPRINT_MISMATCH' in bad.json()['detail']['gaps']
        assert freeze(client, protocol, model, attempt_ids=[]).status_code == 409
        assert freeze(client, protocol, model, baseline={'cash_yuan': 'NaN', 'positions': []}).status_code == 422
        assert freeze(client, protocol, model, baseline={'cash_yuan': '0.00', 'positions': []}).status_code == 409
        frozen = freeze(client, protocol, model).json()
        assert client.post('/api/research/protocols/'+protocol['protocol_id']+'/attempts', json={
            'category': 'THRESHOLD', 'partition': 'DEVELOPMENT', 'configuration': {'threshold': '.55'}, 'basis': 'Changed policy requires successor'}).status_code == 409
        successor = client.post('/api/research/protocols', json={'dataset_id': dataset['dataset_id'],
            'predecessor_id': protocol['protocol_id'], 'basis': 'New isolated cash baseline, no inherited performance'}).json()
        second = freeze(client, successor, model, baseline={'cash_yuan': '5000.00', 'positions': []})
        assert second.status_code == 201, second.text
        forecasts = high_forecasts(client, model)
        new_path = '/api/research/shadow/'+second.json()['freeze_id']
        state = client.post(new_path+'/advance', json={'through_date': forecasts[0]['observation_cutoff'][:10],
            'forecast_ids': [f['forecast_id'] for f in forecasts], 'expected_revision': 0}).json()
        assert all(o['action'] == 'REFUSE' and 'INSUFFICIENT_JOINT_CASH' in o['reasons'] for o in state['opportunities'])
        assert state['cash_yuan'] == '5000.00' and state['events'] == []
        assert client.get('/api/research/shadow/'+frozen['freeze_id']).json()['revision'] == 0
        assert client.post(new_path+'/advance', json={'through_date': dates[170], 'forecast_ids': [], 'expected_revision': 1}).status_code == 422
        assert client.get('/api/research/protocols/'+successor['protocol_id']+'/attempt-manifest').json()['attempt_ids'] == client.get('/api/research/protocols/'+protocol['protocol_id']+'/attempt-manifest').json()['attempt_ids']


def test_cash_tax_and_unpaid_receivable_conserve_nav_before_and_after_payment():
    # Narrow arithmetic seam allowed by Testing Decisions §2: independently worked literal cash example.
    from roll.research.shadow import simulate
    days=[(date(2026,1,1)+timedelta(days=i)).isoformat() for i in range(23)]
    rule={'state':'CONFIRMED_NORMAL','company_actions':'CONFIRMED_NONE','price_tick_yuan':'0.01','normal_price_limit_percent':'10'}
    rows=[{'trade_date':d,'instrument':'SSE:600362','open':'100' if i<3 else '99','close':'100' if i<3 else '99',
        'high':'101','low':'98','volume_shares':'10000','completion_state':'COMPLETE_REPORTED_HISTORICAL',
        'errors':[],'execution_evidence':rule} for i,d in enumerate(days)]
    frozen={'baseline':{'cash_yuan':'100000.00','positions':[]},'scope':{'instruments':['SSE:600362']},'rules':{'SSE:600362':rule},
        'fingerprints':{'model':'fixture'},'policy':{'quantity':'200','probability_threshold':'.60','maximum_gross_exposure':'.50'},
        'design':{'event':'METHOD_CASH','costs':{'minimum_commission_yuan':'0','commission_scenario_rate':'0',
            'transfer_each_side_rate':'0','stamp_sell_rate':'0','extra_regulatory_charge':'0','slippage_each_side_rate':'0'}}}
    inputs={'facts':rows,'sessions':days,'statutory':{},'cash_events':[{'instrument':'SSE:600362','record_date':days[2],
        'ex_date':days[3],'cash_payment_date':days[22],'gross_cash_yuan_per_eligible_share':'1'}]}
    forecast={'instrument':'SSE:600362','forecast_id':'one','observation_cutoff':days[0],'probability':.8}
    sold=simulate(frozen,inputs,[forecast],days[20])
    assert sold['cash_yuan']=='99760.00' and sold['curve'][-1]['receivable_yuan']=='200.00'
    assert sold['nav_yuan']=='99960.00' and sold['realized_gain_yuan']=='-40.00'
    paid=simulate(frozen,inputs,[forecast],days[22])
    assert paid['cash_yuan']=='99960.00' and paid['nav_yuan']=='99960.00'
    assert paid['curve'][-1]['receivable_yuan']=='0.00'
    assert len([e for e in paid['events'] if e['kind']=='CASH_DISTRIBUTION'])==1


def test_corrupt_complete_protocol_archive_refuses_public_advance_before_mutation(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        _, protocol, model, dates=setup(client,tmp_path)
        frozen=freeze(client,protocol,model).json()
        (tmp_path/frozen['archive']['path']).write_bytes(b'corrupted frozen protocol')
        response=client.post('/api/research/shadow/'+frozen['freeze_id']+'/advance',json={
            'through_date':dates[100],'forecast_ids':[],'expected_revision':0})
        assert response.status_code==409,response.text
        assert response.json()['detail']=={'code':'ARCHIVE_MISSING_OR_CORRUPT'}


def test_nonempty_frozen_holdings_preserve_quantity_and_replay_without_cash(tmp_path):
    with TestClient(create_app(tmp_path),raise_server_exceptions=False) as client:
        _,protocol,model,dates=setup(client,tmp_path)
        position={'instrument':protocol['scope']['instruments'][0],'quantity':'200',
                  'acquisition_cost_yuan':'20000.00','acquired_on':dates[99]}
        for invalid in ['200.5','0','NaN','Infinity','-1']:
            response=freeze(client,protocol,model,baseline={'cash_yuan':'0.00','positions':[{**position,'quantity':invalid}]})
            assert response.status_code==422,response.text
        response=freeze(client,protocol,model,baseline={'cash_yuan':'0.00','positions':[position]})
        assert response.status_code==201,response.text
        frozen=response.json();path='/api/research/shadow/'+frozen['freeze_id']
        state=client.post(path+'/advance',json={'through_date':dates[101],'forecast_ids':[],'expected_revision':0})
        assert state.status_code==201,state.text
        state=state.json()
        assert state['cash_yuan']=='0.00' and state['positions'][0]['quantity']=='200'
        assert state['positions'][0]['cost_yuan']=='20000.00' and state['events']==[]
        assert Decimal(state['nav_yuan'])>0
        assert client.post(path+'/replay').json()['matches_original'] is True
        assert client.get('/api/account').json()['version']==0
