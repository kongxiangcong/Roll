"""Boundary/method tests only; real-source fitting evidence is separately archived."""
import copy,time
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from roll.research.models import features,fit_logit
from roll.research.reconstruction import ReconstructionCommand,reconstruct,verify_sources,cash_economics
from roll.research.execution import evaluate

def bars():
    rows=[]
    for i in range(1,32):
        day=f'2020-07-{i:02d}'
        rows.append({'instrument':'SSE:600362','trade_date':day,'adjustment':'RAW','volume_unit':'SHARE','close':str(100+i),'volume_shares':str(10000+i*100),
            'errors':[],'completion_state':'COMPLETE_REPORTED_HISTORICAL','available_at':'2026-10-10T01:00:00+08:00',
            'received_at':'2026-10-10T01:00:00+08:00','research_completion_available_at':day+'T15:05:00+08:00','data_use':'RECONSTRUCTED_RESEARCH','cash_events_effective':[],'raw_hash':'fixture-original'})
    return rows

def test_future_prices_and_labels_never_change_observation_features_or_dev_fit():
    rows=bars();original=features(rows,'2020-07-21',False,'2026-10-10T10:00:00+08:00');changed=copy.deepcopy(rows)
    for r in changed[21:]:r.update(close='999999',volume_shares='1',future_label=0)
    assert features(changed,'2020-07-21',False,'2026-10-10T10:00:00+08:00')==original
    examples=[{'observation_date':r['trade_date'],'label':i%2,'feature_snapshot':features(rows,r['trade_date'],False,'2026-10-10T10:00:00+08:00')} for i,r in enumerate(rows[20:25])]
    fitted=fit_logit(examples,time.monotonic()+60)
    after_dev=copy.deepcopy(rows)
    for row in after_dev[25:]:row.update(close='999999',volume_shares='1',future_label=0)
    changed_dev=[{**e,'feature_snapshot':features(after_dev,e['observation_date'],False,'2026-10-10T10:00:00+08:00')} for e in examples]
    assert changed_dev==examples
    assert fit_logit(changed_dev,time.monotonic()+60)==fitted
    assert fitted['standardization_partition']=='DEVELOPMENT'

def test_receipt_is_preserved_and_reconstruction_clock_does_not_grant_strict_pit():
    rows=bars();before=copy.deepcopy(rows)
    snapshot=features(rows,'2020-07-21',False,'2026-10-10T10:00:00+08:00')
    assert 'NOT_STRICT_PIT' in snapshot['availability_basis'] and rows==before
    with pytest.raises(ValueError,match='FEATURE_NOT_AVAILABLE_TO_CONSUMER'):
        features(rows,'2020-07-21',False,'2020-07-21T16:00:00+08:00')
    registry=SimpleNamespace(dataset=lambda _:pytest.fail('Strict use must reject before reading source'))
    with pytest.raises(HTTPException) as error:
        reconstruct(registry,'x',ReconstructionCommand(status_run_id='x',data_use='STRICT_HISTORICAL_AS_OF',basis='strict remains blocked'))
    assert error.value.status_code==409
    for row in rows:row.pop('data_use')
    with pytest.raises(ValueError,match='HISTORICAL_POINT_IN_TIME_NOT_PROVEN'):
        features(rows,'2020-07-21',False,'2026-10-10T10:00:00+08:00')

def test_cash_ex_day_is_economic_not_a_mechanical_loss_and_future_action_is_ignored():
    rows=bars()
    for r in rows:r['close']='100'
    event={'gross_cash_yuan_per_eligible_share':'1','source':{'sha256':'cash-original'}}
    for r in rows[20:]:r['close']='99'
    rows[20]['cash_events_effective']=[event];rows[25]['cash_events_effective']=[{**event,'gross_cash_yuan_per_eligible_share':'50'}]
    snapshot=features(rows,'2020-07-21',False,'2026-10-10T10:00:00+08:00')
    assert snapshot['features']['economic_return_20']==0 and snapshot['features']['economic_return_volatility_20']==0
    rows[25]['cash_events_effective']=[]
    assert features(rows,'2020-07-21',False,'2026-10-10T10:00:00+08:00')==snapshot

@pytest.mark.parametrize('evidence,instruments',[('METHOD_CASE',['SSE:600362']),('REAL_ACQUISITION',['SSE:600519'])])
def test_method_or_wrong_security_cannot_enter_real_reconstruction(evidence,instruments):
    source={'source_evidence_kind':evidence,'scope':{'instruments':instruments}}
    with pytest.raises(HTTPException,match='REAL_SINGLE_NAME_RECONSTRUCTION_SOURCE_REQUIRED'):
        verify_sources(None,source)

def test_unit_error_or_required_field_error_cannot_build_features():
    rows=bars();rows[5]['volume_unit']='HAND'
    with pytest.raises(ValueError,match='FEATURE_INPUT_NOT_COMPLETE_RAW_SHARE'):
        features(rows,'2020-07-21',False,'2026-10-10T10:00:00+08:00')
    rows[5]['volume_unit']='SHARE';rows[5]['errors']=['UNRESOLVED_VOLUME_CONFLICT']
    with pytest.raises(ValueError,match='FEATURE_INPUT_NOT_COMPLETE_RAW_SHARE'):
        features(rows,'2020-07-21',False,'2026-10-10T10:00:00+08:00')

def test_known_cash_entitlement_includes_record_close_and_tax_and_receivable():
    event={'record_date':'2020-07-21','ex_date':'2020-07-22','cash_payment_date':'2020-07-22','gross_cash_yuan_per_eligible_share':'1',
        'source':{'received_at':'2026-10-09T01:00:00+08:00','sha256':'cash-original'}}
    result=cash_economics([event],'2020-07-01','2020-07-21',Decimal(100),'2026-10-10T10:00:00+08:00')
    assert result['net_economic_entitlement_yuan']=='80.00' and result['events'][0]['payment_basis']=='RECEIVABLE_AT_EXIT'
    assert result['account_authority']=='NONE'
    with pytest.raises(ValueError,match='TAX_CALENDAR_ANNIVERSARY_UNDEFINED'):
        cash_economics([event],'2020-01-31','2020-07-21',Decimal(100),'2026-10-10T10:00:00+08:00')

def test_immature_label_cannot_be_a_negative_or_eligible_sample():
    inputs={'evidence_kind':'REAL_ACQUISITION','data_use':'RECONSTRUCTED_RESEARCH'}
    result=evaluate(inputs,{'label_matures_at':'2020-08-01T15:00:00+08:00','maturity_date':'2020-08-01'},datetime.fromisoformat('2020-07-21T16:00:00+08:00'))
    assert result['label_status']=='IMMATURE' and result['label'] is None and not result['eligible_for_training']

def test_protected_range_in_source_container_rejects_before_opening_payload():
    source={'coverage':{'first_date':'2016-01-01','last_date':'2023-12-31'},'partitions':{'SEALED':{'first_date':'2016-02-01','last_date':'2016-02-29'}},'scope':{'instruments':['SSE:600362']}}
    evidence=SimpleNamespace(get=lambda table,_: {'request_id':'request'} if table=='retrieval_runs' else {'instruments':['SSE:600362'],'start_date':'2016-12-01','end_date':'2023-12-31'},raw=lambda _:pytest.fail('Protected payload must never open'))
    registry=SimpleNamespace(evidence=evidence,dataset=lambda _:source,protocols=lambda:[{'dataset_id':'source'}])
    with pytest.raises(HTTPException,match='PROTECTED_SEALED_RANGE'):
        reconstruct(registry,'source',ReconstructionCommand(status_run_id='status',basis='protected whole container'))

def test_status_source_outside_allowed_range_rejects_before_payload():
    evidence=SimpleNamespace(get=lambda table,_:{'request_id':'request'} if table=='retrieval_runs' else {'instruments':['SSE:600362'],'start_date':'2024-01-01','end_date':'2026-10-10'},raw=lambda _:pytest.fail('Unexpected payload must never open'))
    registry=SimpleNamespace(evidence=evidence,dataset=lambda _:{},protocols=lambda:pytest.fail('Invalid request must reject early'))
    with pytest.raises(HTTPException,match='STATUS_CONTAINER_OUTSIDE'):
        reconstruct(registry,'source',ReconstructionCommand(status_run_id='status',basis='bounded scope'))

def test_cash_tax_uses_frozen_half_up_rounding():
    event={'record_date':'2020-07-21','ex_date':'2020-07-22','cash_payment_date':'2020-07-22','gross_cash_yuan_per_eligible_share':'.025',
        'source':{'received_at':'2026-10-09T01:00:00+08:00','sha256':'fixture'}}
    result=cash_economics([event],'2020-07-01','2020-07-21',Decimal(1),'2026-10-10T10:00:00+08:00')
    assert result['events'][0]['final_tax_yuan']=='0.01'

@pytest.mark.parametrize('suspended,expected',[('2020-07-02','NO_EXECUTION'),('2020-07-21','BLOCKED_EXIT')])
def test_reconstructed_null_price_suspension_retains_unresolved_opportunity(suspended,expected):
    rows=[]
    for day in ['2020-07-01','2020-07-02','2020-07-21']:
        halted=day==suspended
        rows.append({'trade_date':day,'errors':[],'completion_state':'SUSPENSION_PLACEHOLDER' if halted else 'COMPLETE_REPORTED_HISTORICAL',
            'available_at':'2026-10-10T01:00:00+08:00',**{k:None if halted else '100' for k in ['open','high','low','close']},'volume_unit':'SHARE','volume_shares':'0' if halted else '10000',
            'execution_evidence':{'state':'REPORTED_SUSPENDED_RECONSTRUCTED' if halted else 'REPORTED_NORMAL_RECONSTRUCTED','company_actions':'SOURCE_BOUND_CASH_AND_ANNUAL_SHARE_AUDIT'}})
    inputs={'evidence_kind':'REAL_ACQUISITION','data_use':'RECONSTRUCTED_RESEARCH','facts':rows,'partition_last_date':'2020-07-21'}
    definition={'observation_date':'2020-07-01','maturity_date':'2020-07-21','label_matures_at':'2020-07-21T15:00:00+08:00',
        'maturity_evidence_available_at':'2026-10-10T01:00:00+08:00','consumer_knowledge_cutoff':'2026-10-10T10:00:00+08:00','scheduled_sessions':['2020-07-02','2020-07-21'],
        'historical_costs':{'BUY':{'reasons':[]},'SELL':{'reasons':[]}},'rule':{'implementation_status':'ADAPTED','buy_increment':'100','buy_minimum':'100'},
        'costs':{'commission_includes_regulatory_fees':True,'extra_regulatory_charge':'0'},'order':{'quantity':'100','fill_fraction':'1','delay':'NEXT_OPEN','entry_date':'2020-07-02','earliest_resale_date':'2020-07-03','price_window':{'lower_yuan':'90','upper_yuan':'110'}}}
    result=evaluate(inputs,definition,datetime.fromisoformat('2026-10-10T10:00:00+08:00'))
    assert result['execution_status']==expected and result['label'] is None and not result['eligible_for_training']
