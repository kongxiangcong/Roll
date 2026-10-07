"""Public SQLite/Parquet method cases; financial inputs are explicit synthetic evidence."""
import hashlib
import json
import pytest
from datetime import date,timedelta
from io import BytesIO

import pyarrow as pa
import pyarrow.parquet as pq
from fastapi.testclient import TestClient
from roll.app import create_app


def method_archive(directory,changes=None,unknown=False):
    source=directory/'research-inputs'/'method-execution';source.mkdir(parents=True)
    holidays=[('2026-01-01','2026-01-04'),('2026-02-15','2026-02-23'),('2026-04-04','2026-04-06'),
        ('2026-05-01','2026-05-05'),('2026-06-19','2026-06-21'),('2026-09-25','2026-09-27'),('2026-10-01','2026-10-07')]
    dates=[];day=date(2026,1,5)
    while len(dates)<181:
        if day.weekday()<5 and not any(a<=day.isoformat()<=b for a,b in holidays):dates.append(day.isoformat())
        day+=timedelta(days=1)
    rows=[]
    for index,d in enumerate(dates):
        values={'open':'100','close':'105' if index==1 else '100','high':'106','low':'99','volume_shares':'10000','volume_unit':'SHARE'}
        rows.append({'instrument':'SSE:600519','group':'DAILY','adjustment':'RAW','trade_date':d,**values,
            'amount_yuan':None,'available_at':'2026-10-07T00:00:00+08:00','completion_state':'COMPLETE_REPORTED_HISTORICAL',
            'method_completion_available_at':d+'T15:01:00+08:00',
            'evidence_kind':'METHOD_CASE','namespace':'HISTORICAL','errors':[],
            'execution_evidence':{'state':'UNKNOWN' if unknown else 'CONFIRMED_NORMAL','company_actions':'UNKNOWN' if unknown else 'CONFIRMED_NONE',
                'rule_scope':'METHOD_CASE_ONLY','buy_minimum':'100','buy_increment':'100','price_tick_yuan':'0.01','resale':'NEXT_TRADING_DAY','close_time':'15:00:00','normal_price_limit_percent':'10'}})
        changed=(changes or {}).get(index,{})
        rows[-1]['execution_evidence'].update(changed.get('execution_evidence',{}))
        rows[-1].update({k:v for k,v in changed.items() if k!='execution_evidence'})
    raw=json.dumps({'kind':'METHOD_CASE','description':'explicit synthetic OHLC and known/unknown execution-state method scenario','rows':rows},ensure_ascii=False).encode()
    digest=hashlib.sha256(raw).hexdigest();(source/(digest+'.raw')).write_bytes(raw)
    for row in rows:row['raw_hash']=digest
    buffer=BytesIO();pq.write_table(pa.Table.from_pylist([{'payload':json.dumps(row)} for row in rows]),buffer)
    parquet=buffer.getvalue();pqhash=hashlib.sha256(parquet).hexdigest();(source/(pqhash+'.parquet')).write_bytes(parquet)
    (source/'browser-live.json').write_text(json.dumps({'request':{'identity_context':{'SSE:600519':{'exchange':'SSE','board':'MAIN','instrument_type':'STOCK'}}},
        'run':{'run_id':'method18-source-run','evidence_kind':'METHOD_CASE'},'snapshot':{'snapshot_id':'method18-source-snapshot','adapter_version':'METHOD18',
        'evidence_kind':'METHOD_CASE','facts':rows,'archives':[{'sha256':digest,'path':'raw/'+digest+'.raw','kind':'RAW_RESPONSE','bytes':len(raw)}],
        'parquet':{'sha256':pqhash,'path':'parquet/'+pqhash+'.parquet','kind':'NORMALIZED_PARQUET','bytes':len(parquet)}}}),encoding='utf-8')
    return dates


def register(client):
    dataset=client.post('/api/research/datasets',json={'archive_id':'method-execution','basis':'明确METHOD_CASE，不作为真实模型训练或G7'}).json()
    protocol=client.post('/api/research/protocols',json={'dataset_id':dataset['dataset_id'],'basis':'固定20日事件、原价、费用与成熟机制验收'}).json()
    return dataset,protocol


def test_twenty_session_event_is_not_mature_after_next_day_rise_and_replays_original_inputs(tmp_path):
    method_archive(tmp_path)
    with TestClient(create_app(tmp_path)) as client:
        dataset,protocol=register(client)
        response=client.post('/api/research/protocols/'+protocol['protocol_id']+'/executions',json={
            'partition':'DEVELOPMENT','observation_date':'2026-01-05','label_as_of':'2026-01-06T16:00:00+08:00','basis':'次日上涨仍不成熟'})
        assert response.status_code==201,response.text
        run=response.json();result=run['result']
        assert result['label_matures_at']=='2026-02-02T15:00:00+08:00'
        assert result['label_status']=='IMMATURE' and result['label'] is None
        assert result['scoreable'] is False and result['eligible_for_training'] is False and result['net_pnl_yuan'] is None
        assert run['namespace']=='HISTORICAL' and run['capability']=='NOT_GRANTED' and run['data_fingerprint']==dataset['data_fingerprint']
        assert run['definition']['horizon_sessions']==20 and run['definition']['event']==protocol['design']['event']
        replay=client.post('/api/research/executions/'+run['execution_id']+'/replay').json()
        assert replay['network_calls']==0 and replay['result']==result and replay['input_sha256']==run['input_archive']['sha256']
        original=client.get('/api/data/archives/'+run['input_archive']['sha256'])
        assert original.status_code==200 and hashlib.sha256(original.content).hexdigest()==run['input_archive']['sha256']
        assert client.get('/api/account').json()['version']==0
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/research/executions/'+run['execution_id']).json()==run


def test_mature_fee_after_execution_delays_partial_missed_and_unknown_remain_distinct(tmp_path):
    method_archive(tmp_path,{2:{'open':'101'},20:{'close':'110','high':'111'}})
    with TestClient(create_app(tmp_path)) as client:
        _,protocol=register(client);pid=protocol['protocol_id'];runs=[]
        for delay,expected_date,expected_price in [('NEXT_OPEN','2026-01-06','100.05'),('NEXT_CLOSE','2026-01-06','105.05'),('ONE_MORE_SESSION_OPEN','2026-01-07','101.05')]:
            response=client.post('/api/research/protocols/'+pid+'/executions',json={'partition':'DEVELOPMENT','observation_date':'2026-01-05',
                'label_as_of':'2026-02-02T16:00:00+08:00','delay':delay,'quantity':'200','fill_fraction':'0.50','basis':'预登记延迟/50%成交费用场景'})
            assert response.status_code==201,response.text
            run=response.json();result=run['result'];runs.append(run)
            assert result['label_status']=='MATURE' and result['label']==1 and result['scoreable'] is True
            assert result['eligible_for_training'] is False and result['training_restrictions']==['METHOD_CASE_NOT_REAL_TRAINING_INPUT']
            assert result['execution_status']=='PARTIAL' and result['filled_quantity']=='100' and result['unfilled_quantity']=='100'
            assert result['entry']['trade_date']==expected_date and result['entry']['price_yuan']==expected_price
            assert result['earliest_resale_date']==('2026-01-07' if delay!='ONE_MORE_SESSION_OPEN' else '2026-01-08')
            assert result['exit']['trade_date']=='2026-02-02' and result['exit']['price_yuan']=='109.95'
            assert result['exit']['fees']=={'commission_yuan':'5.00','transfer_yuan':'0.11','stamp_yuan':'5.50','extra_regulatory_yuan':'0.00','total_yuan':'10.61'}
            assert result['label_available_at']>=run['registered_at'] and result['label_available_at']!=result['label_matures_at']
        assert runs[0]['result']['net_pnl_yuan']=='974.29'
        for command,reason in [({'delay':'OUTSIDE_ALLOWED_PRICE_NO_FILL'},'OUTSIDE_FROZEN_PRICE_WINDOW'),({'fill_fraction':'0'},'DECLARED_MISSED_FILL')]:
            run=client.post('/api/research/protocols/'+pid+'/executions',json={'partition':'DEVELOPMENT','observation_date':'2026-01-05','label_as_of':'2026-02-02T16:00:00+08:00','quantity':'200','basis':'未成交不能成为预测亏损',**command}).json()
            result=run['result'];assert result['execution_status']=='NO_EXECUTION' and result['label'] is None and not result['scoreable']
            assert result['net_pnl_yuan']=='0.00' and result['reasons']==[reason] and result['entry'] is None
        assert client.get('/api/account').json()['version']==0


def test_unknown_or_incomplete_evidence_is_not_a_negative_label_and_sealed_is_audited(tmp_path):
    method_archive(tmp_path,unknown=True)
    with TestClient(create_app(tmp_path)) as client:
        _,protocol=register(client);pid=protocol['protocol_id']
        run=client.post('/api/research/protocols/'+pid+'/executions',json={'partition':'DEVELOPMENT','observation_date':'2026-01-05','label_as_of':'2026-02-02T16:00:00+08:00','basis':'未知公司行为/停牌不能填正常'}).json()
        assert run['result']['label_status']=='UNSCORABLE' and run['result']['label'] is None and run['result']['net_pnl_yuan'] is None
        assert 'HISTORICAL_STATUS_UNKNOWN' in run['result']['reasons'] and 'COMPANY_ACTIONS_UNKNOWN' in run['result']['reasons']
        refused=client.post('/api/research/protocols/'+pid+'/executions',json={'partition':'SEALED','observation_date':'2026-09-01','basis':'不允许绕封存'})
        assert refused.status_code==403
        assert client.get('/api/research/protocols/'+pid+'/audit').json()[-1]['action']=='EXECUTION_REFUSED'


def test_same_day_path_ambiguity_keeps_interval_and_t_plus_one_not_favorable_touch(tmp_path):
    dates=method_archive(tmp_path,{1:{'low':'97','high':'106'},2:{'low':'97','high':'106'}})
    with TestClient(create_app(tmp_path)) as client:
        _,protocol=register(client);pid=protocol['protocol_id'];results={}
        for policy in ['CONSERVATIVE','INTERVAL','UNDETERMINABLE']:
            run=client.post('/api/research/protocols/'+pid+'/executions',json={'partition':'DEVELOPMENT','observation_date':dates[0],
                'label_as_of':'2026-02-02T16:00:00+08:00','quantity':'100','path_policy':policy,
                'method_barriers':{'stop_price_yuan':'98','profit_price_yuan':'104'},'basis':'明确方法压力，非真实触价成交'}).json()
            result=run['result'];results[policy]=result
            assert result['same_day_path']['ambiguous_trade_date']==dates[2] and result['same_day_path']['entry_day_touch_ignored_for_resale']==[dates[1]]
            assert result['same_day_path']['observed_fill_proven'] is False
        assert results['CONSERVATIVE']['label_status']=='MATURE' and results['CONSERVATIVE']['label']==0
        assert results['CONSERVATIVE']['same_day_path']['selected_bound']=='LOWER'
        assert results['INTERVAL']['label_status']=='INTERVAL' and results['INTERVAL']['label'] is None and not results['INTERVAL']['scoreable']
        assert results['INTERVAL']['net_pnl_yuan'] is None and float(results['INTERVAL']['net_pnl_interval_yuan']['lower'])<0<float(results['INTERVAL']['net_pnl_interval_yuan']['upper'])
        assert results['UNDETERMINABLE']['label_status']=='UNSCORABLE' and results['UNDETERMINABLE']['label'] is None


def test_confirmed_terminal_settlement_uses_archived_time_and_unconfirmed_stays_immature(tmp_path):
    method_archive(tmp_path,{3:{'open':None,'high':None,'low':None,'close':None,'execution_evidence':{'company_actions':'CONFIRMED_TERMINAL_CASH_TREATMENT'},'terminal_settlement':{'state':'CONFIRMED_ALL_SHARES_CASH_SETTLED','cash_per_share_yuan':'90',
        'effective_at':'2026-01-08T12:00:00+08:00','available_at':'2026-10-07T00:00:00+08:00','method_settlement_available_at':'2026-01-08T12:01:00+08:00','exit_fee_treatment':'FINAL_CASH_NO_ADDITIONAL_FEE'}}})
    with TestClient(create_app(tmp_path)) as client:
        _,protocol=register(client)
        run=client.post('/api/research/protocols/'+protocol['protocol_id']+'/executions',json={'partition':'DEVELOPMENT','observation_date':'2026-01-05',
            'label_as_of':'2026-01-08T13:00:00+08:00','quantity':'100','basis':'预登记确定性终止结算方法'}).json()
        result=run['result'];assert result['label_status']=='MATURE' and result['label']==0
        assert result['label_matures_at']=='2026-01-08T12:00:00+08:00' and result['exit']['basis']=='CONFIRMED_TERMINAL_CASH_SETTLEMENT'
        assert run['definition']['terminal_settlement']['state']=='CONFIRMED_ALL_SHARES_CASH_SETTLED'
        assert client.post('/api/research/executions/'+run['execution_id']+'/replay').json()['matches_original']


def test_new_assessment_is_immutable_child_and_support_does_not_train_methods_or_duplicate_opportunities(tmp_path):
    method_archive(tmp_path)
    with TestClient(create_app(tmp_path)) as client:
        _,protocol=register(client);pid=protocol['protocol_id']
        original=client.post('/api/research/protocols/'+pid+'/executions',json={'partition':'DEVELOPMENT','observation_date':'2026-01-05',
            'label_as_of':'2026-01-06T16:00:00+08:00','quantity':'100','basis':'原始未成熟'}).json()
        assessed=client.post('/api/research/executions/'+original['execution_id']+'/assessments',json={'label_as_of':'2026-02-02T16:00:00+08:00','basis':'成熟复评不重写次日结果'})
        assert assessed.status_code==201,assessed.text
        child=assessed.json();assert child['parent_execution_id']==original['execution_id'] and child['result']['label_status']=='MATURE'
        assert child['definition']['event']==original['definition']['event'] and child['data_fingerprint']==original['data_fingerprint']
        assert client.get('/api/research/executions/'+original['execution_id']).json()==original
        support=client.get('/api/research/protocols/'+pid+'/execution-support?partition=DEVELOPMENT').json()
        assert support['opportunity_count']==1 and support['record_count']==2 and support['eligible_for_training_count']==0
        assert support['latest_assessment_counts']['MATURE']==1 and support['method_case_count']==1
        assert support['records'][0]['execution_id']==child['execution_id'] and support['records'][0]['input_sha256']==child['input_archive']['sha256']


@pytest.mark.parametrize('change,reason,status',[
    ({'completion_state':'UNCONFIRMED_CURRENT_DAY'},'INCOMPLETE_DAILY:2026-01-06','UNSCORABLE'),
    ({'open':None},'INVALID_OHLC:2026-01-06','UNSCORABLE'),
    ({'volume_unit':'UNKNOWN','volume_shares':None},'EXECUTION_VOLUME_UNKNOWN','UNSCORABLE'),
    ({'volume_shares':'0'},'ZERO_REPORTED_VOLUME','NO_EXECUTION'),
    ({'open':'120','high':'121','close':'120'},'OUTSIDE_FROZEN_PRICE_WINDOW','NO_EXECUTION'),
    ({'available_at':'2099-01-01T00:00:00+08:00'},'NOT_AVAILABLE_TO_CONSUMER:2026-01-06','UNSCORABLE'),
])
def test_missing_incomplete_zero_volume_outside_window_and_future_available_do_not_become_losses(tmp_path,change,reason,status):
    method_archive(tmp_path,{1:change})
    with TestClient(create_app(tmp_path)) as client:
        _,protocol=register(client)
        run=client.post('/api/research/protocols/'+protocol['protocol_id']+'/executions',json={'partition':'DEVELOPMENT','observation_date':'2026-01-05',
            'label_as_of':'2026-02-02T16:00:00+08:00','quantity':'100','basis':'完整性/成交限制公开边界'}).json()
        assert run['result']['label_status']==status and reason in run['result']['reasons']
        assert run['result']['label'] is None and not run['result']['scoreable']
        assert client.post('/api/research/executions/'+run['execution_id']+'/replay').json()['matches_original']


def test_purged_boundary_context_quote_injection_and_unconfirmed_terminal_are_not_scored(tmp_path):
    method_archive(tmp_path,{3:{'terminal_settlement':{'state':'UNCONFIRMED','cash_per_share_yuan':'90','effective_at':'2026-01-08T12:00:00+08:00'}}})
    with TestClient(create_app(tmp_path)) as client:
        dataset,protocol=register(client);pid=protocol['protocol_id']
        early=client.post('/api/research/protocols/'+pid+'/executions',json={'partition':'DEVELOPMENT','observation_date':'2026-01-05','label_as_of':'2026-01-08T13:00:00+08:00','basis':'未确认结算不能提前成熟'}).json()
        assert early['result']['label_status']=='IMMATURE' and early['definition']['terminal_settlement'] is None
        edge=client.post('/api/research/protocols/'+pid+'/executions',json={'partition':'DEVELOPMENT','observation_date':dataset['partitions']['DEVELOPMENT']['last_date'],'basis':'跨分片边界不计入训练'}).json()
        assert edge['result']['label_status']=='UNSCORABLE' and 'LABEL_SPANS_PARTITION_BOUNDARY' in edge['result']['reasons']
        context=client.post('/api/research/protocols/'+pid+'/executions',json={'partition':'CALIBRATION','observation_date':dataset['partitions']['CALIBRATION']['context_first_date'],'basis':'上下文不是校准标签'})
        assert context.status_code==422
        quote=client.post('/api/research/protocols/'+pid+'/executions',json={'partition':'DEVELOPMENT','observation_date':'2026-01-05','execution_price':'1','basis':'不能注入报价当成交'})
        assert quote.status_code==422


def test_preregistered_fee_stress_does_not_invent_actual_broker_cost(tmp_path):
    method_archive(tmp_path,{20:{'close':'110','high':'110'}})
    with TestClient(create_app(tmp_path)) as client:
        _,protocol=register(client);pid=protocol['protocol_id']
        body={'partition':'DEVELOPMENT','observation_date':'2026-01-05','quantity':'100','commission_scenario_rate':'0.003','slippage_each_side_rate':'0.002','basis':'已登记G5费用压力'}
        response=client.post('/api/research/protocols/'+pid+'/executions',json=body)
        assert response.status_code==201,response.text
        run=response.json();assert run['result']['net_pnl_yuan']=='889.31'
        assert run['definition']['costs']['broker_actual_commission']=='UNKNOWN' and run['definition']['costs']['extra_regulatory_charge']=='0'
        assert client.post('/api/research/protocols/'+pid+'/executions',json={**body,'commission_scenario_rate':'0'}).status_code==422


@pytest.mark.parametrize('day,expected,reason',[(1,'NO_EXECUTION','CONFIRMED_SUSPENSION_ON_ENTRY'),(20,'BLOCKED_EXIT','CONFIRMED_SUSPENSION_ON_EXIT')])
def test_confirmed_suspension_retains_unexecuted_or_unexitable_case(tmp_path,day,expected,reason):
    method_archive(tmp_path,{day:{'execution_evidence':{'state':'CONFIRMED_SUSPENDED'}}})
    with TestClient(create_app(tmp_path)) as client:
        _,protocol=register(client)
        run=client.post('/api/research/protocols/'+protocol['protocol_id']+'/executions',json={'partition':'DEVELOPMENT','observation_date':'2026-01-05','quantity':'100','basis':'停牌/无法退出保留'}).json()
        assert run['result']['execution_status']==expected and run['result']['label'] is None
        assert reason in run['result']['reasons'] and not run['result']['scoreable']


@pytest.mark.parametrize('unexecutable',[{'execution_evidence':{'state':'CONFIRMED_SUSPENDED'}},{'volume_shares':'0'}])
def test_daily_touch_cannot_choose_exit_on_intermediate_suspended_or_zero_volume_bar(tmp_path,unexecutable):
    method_archive(tmp_path,{1:{'low':'97','high':'106'},2:{'low':'97','high':'106',**unexecutable},20:{'close':'110','high':'110'}})
    with TestClient(create_app(tmp_path)) as client:
        _,protocol=register(client)
        response=client.post('/api/research/protocols/'+protocol['protocol_id']+'/executions',json={'partition':'DEVELOPMENT','observation_date':'2026-01-05','quantity':'100',
            'method_barriers':{'stop_price_yuan':'98','profit_price_yuan':'104'},'path_policy':'CONSERVATIVE','basis':'中间停牌/零成交量触线不得选非法退出'})
        assert response.status_code==201,response.text
        result=response.json()['result'];assert result['exit']['trade_date']=='2026-01-08'
        assert result['same_day_path']['excluded_unexecutable_touch_dates']==['2026-01-07']
        assert result['same_day_path']['entry_day_touch_ignored_for_resale']==['2026-01-06'] and result['label']==1


def test_completion_availability_and_official_adapted_close_prevent_premature_labels(tmp_path):
    method_archive(tmp_path,{20:{'method_completion_available_at':'2026-02-03T15:01:00+08:00'}})
    with TestClient(create_app(tmp_path)) as client:
        _,protocol=register(client);pid=protocol['protocol_id']
        run=client.post('/api/research/protocols/'+pid+'/executions',json={'partition':'DEVELOPMENT','observation_date':'2026-01-05','label_as_of':'2026-02-02T16:00:00+08:00','quantity':'100','basis':'最终完成bar延迟可得仍未成熟'}).json()
        assert run['result']['label_status']=='IMMATURE' and run['result']['label'] is None
        assert 'COMPLETE_EXIT_BAR_NOT_YET_AVAILABLE_AT_ASSESSMENT' in run['result']['reasons']
        assert run['definition']['maturity_evidence_clock_kind']=='METHOD_SYNTHETIC_COMPLETION_CLOCK'
        # This date is in the real06 adapted rule window. Use the public rule API
        # to verify its provenance separately from the synthetic price source.
        rule=client.get('/api/market/rules',params={'exchange':'SSE','board':'MAIN','date':'2026-08-03'}).json()
        assert rule['implementation_status']=='ADAPTED'


def test_official_adapted_close_is_frozen_even_without_method_rule_clock(tmp_path):
    method_archive(tmp_path,{i:{'execution_evidence':{'rule_scope':'UNKNOWN','close_time':None}} for i in range(181)})
    with TestClient(create_app(tmp_path)) as client:
        _,protocol=register(client)
        run=client.post('/api/research/protocols/'+protocol['protocol_id']+'/executions',json={'partition':'CALIBRATION','observation_date':'2026-07-06',
            'label_as_of':'2026-08-03T08:00:00+08:00','quantity':'100','basis':'实际已适配官方时段，成熟日盘前不能成熟；价格仍METHOD'}).json()
        assert run['result']['label_status']=='IMMATURE' and run['result']['label'] is None
        assert run['definition']['label_matures_at']=='2026-08-03T15:00:00+08:00'
        assert run['definition']['maturity_clock_basis']=='ARCHIVED_RULE_CALENDAR_ADAPTED_DATE'
