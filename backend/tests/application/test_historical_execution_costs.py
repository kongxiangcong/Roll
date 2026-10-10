"""Synthetic archive/API cases only; they do not qualify actual research data."""
import hashlib
import json
from datetime import date, timedelta
from io import BytesIO

import pyarrow as pa
import pyarrow.parquet as pq
from fastapi.testclient import TestClient
from roll.app import create_app
from test_execution_labels import method_archive, register


def historical_archive(directory, start):
    method_archive(directory)
    source=directory/'research-inputs/method-execution'
    bundle=json.loads((source/'browser-live.json').read_text(encoding='utf-8'))
    dates=[];day=date.fromisoformat(start)
    # These are explicitly synthetic daily observations, not a historical calendar claim.
    while len(dates)<181:
        if day.weekday()<5:dates.append(day.isoformat())
        day+=timedelta(days=1)
    for row,day in zip(bundle['snapshot']['facts'],dates):
        row.update(trade_date=day,evidence_kind='PUBLIC_SYNTHETIC_TEST_ONLY')
        row.pop('method_completion_available_at')
    raw=json.dumps({'evidence_kind':'PUBLIC_SYNTHETIC_TEST_ONLY','rows':bundle['snapshot']['facts']}).encode()
    sha=hashlib.sha256(raw).hexdigest();(source/(sha+'.raw')).write_bytes(raw)
    for row in bundle['snapshot']['facts']:row['raw_hash']=sha
    buffer=BytesIO();pq.write_table(pa.Table.from_pylist([{'payload':json.dumps(row)} for row in bundle['snapshot']['facts']]),buffer)
    content=buffer.getvalue();pqsha=hashlib.sha256(content).hexdigest();(source/(pqsha+'.parquet')).write_bytes(content)
    bundle['snapshot']['archives']=[{'sha256':sha,'kind':'RAW_RESPONSE','bytes':len(raw)}]
    bundle['snapshot']['parquet']={'sha256':pqsha,'kind':'NORMALIZED_PARQUET','bytes':len(content)}
    bundle['snapshot']['evidence_kind']='PUBLIC_SYNTHETIC_TEST_ONLY'
    (source/'browser-live.json').write_text(json.dumps(bundle),encoding='utf-8')


def test_historical_execution_freezes_separate_entry_exit_tax_versions_and_keeps_data_gates(tmp_path):
    historical_archive(tmp_path,'2023-07-03')
    with TestClient(create_app(tmp_path)) as client:
        _,protocol=register(client)
        response=client.post('/api/research/protocols/'+protocol['protocol_id']+'/executions',json={
            'partition':'DEVELOPMENT','observation_date':'2023-08-01','quantity':'200',
            'basis':'合成价格仅验证历史税费解析，不是历史PIT/训练证据'})
        assert response.status_code==201,response.text
        run=response.json();costs=run['definition']['historical_costs']
        assert costs['BUY']['trade_date']=='2023-08-02'
        assert costs['BUY']['stamp_sell_rate']=='0.001'
        assert costs['SELL']['trade_date']=='2023-08-29'
        assert costs['SELL']['stamp_sell_rate']=='0.0005'
        assert costs['BUY']['stamp_applied_rate']=='0'
        assert costs['SELL']['stamp_applied_rate']=='0.0005'
        assert costs['commission_basis']=='PREREGISTERED_SCENARIO_INCLUDES_REGULATORY_FEES'
        assert run['result']['eligible_for_training'] is False
        assert client.get('/api/account').json()['version']==0
        assert client.post('/api/research/executions/'+run['execution_id']+'/replay').json()['matches_original']
        for item in costs['sources']:
            original=client.get('/api/data/archives/'+item['sha256'])
            assert original.status_code==200
            assert hashlib.sha256(original.content).hexdigest()==item['sha256']
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/research/executions/'+run['execution_id']).json()==run


def test_fee_calculation_uses_statutory_trade_date_rates_and_does_not_duplicate_commission():
    # A difficult Decimal fee boundary, permitted by the spec; actual data gates are unchanged.
    from decimal import Decimal
    from roll.research.execution import fees
    costs={'minimum_commission_yuan':'5','commission_scenario_rate':'0.0003',
        'transfer_each_side_rate':'0.00001','stamp_sell_rate':'0.0005','extra_regulatory_charge':'0'}
    verified={'status':'VERIFIED_STATUTORY_SCHEDULE','transfer_each_side_rate':'0.00002',
        'stamp_sell_rate':'0.001','stamp_applied_rate':'0.001','trade_date':'2018-08-01','side':'SELL'}
    actual=fees(Decimal('100000'),costs,'SELL',verified)
    assert actual=={'commission_yuan':'30.00','transfer_yuan':'2.00','stamp_yuan':'100.00',
        'extra_regulatory_yuan':'0.00','total_yuan':'132.00'}
    # METHOD remains a frozen assumed-cost calculation, not statutory proof.
    assert fees(Decimal('100000'),costs,'SELL')['total_yuan']=='81.00'


def test_old_face_value_fee_without_period_or_minimum_stays_unscorable(tmp_path):
    historical_archive(tmp_path,'2013-07-01')
    with TestClient(create_app(tmp_path)) as client:
        _,protocol=register(client)
        response=client.post('/api/research/protocols/'+protocol['protocol_id']+'/executions',json={
            'partition':'DEVELOPMENT','observation_date':'2013-07-02','quantity':'200','basis':'合成旧期费用未知不能猜最低一元'})
        assert response.status_code==201,response.text
        run=response.json();item=run['definition']['historical_costs']['BUY']
        assert item['transfer_each_side_rate'] is None and item['status']=='UNKNOWN'
        assert item['prior_reported_transfer']=={'basis':'SHARE_FACE_VALUE','rate':'0.0003',
            'minimum_yuan':None,'period_start':None,'source_id':'2015-fee-change'}
        assert run['result']['label_status']=='UNSCORABLE'
        assert 'HISTORICAL_TRANSFER_FACE_VALUE_START_AND_MINIMUM_UNPROVEN' in run['result']['reasons']
        assert run['result']['net_pnl_yuan'] is None and not run['result']['eligible_for_training']
        assert client.post('/api/research/executions/'+run['execution_id']+'/replay').json()['matches_original']


def test_current_display_is_a_tariff_scenario_with_explicit_historical_interval_limit(tmp_path):
    historical_archive(tmp_path,'2026-07-06')
    with TestClient(create_app(tmp_path)) as client:
        _,protocol=register(client)
        response=client.post('/api/research/protocols/'+protocol['protocol_id']+'/executions',json={
            'partition':'DEVELOPMENT','observation_date':'2026-07-06','quantity':'200','basis':'合成验证当前费率场景，不证明历史稳定或训练资格'})
        assert response.status_code==201,response.text
        run=response.json();costs=run['definition']['historical_costs']
        assert costs['status']=='CURRENT_DISPLAY_SCENARIO'
        assert costs['BUY']['transfer_each_side_rate']=='0.00001'
        assert run['result']['entry']['fees']['stamp_yuan']=='0.00'
        assert run['result']['exit']['fees']['stamp_yuan']=='10.00'
        assert run['result']['net_pnl_yuan']=='-42.40'
        assert run['result']['eligible_for_training'] is False
        assert run['definition']['costs']['broker_actual_commission']=='UNKNOWN'
        assert client.post('/api/research/executions/'+run['execution_id']+'/replay').json()['matches_original']


def test_official_transfer_notice_changes_each_side_only_from_april29(tmp_path):
    historical_archive(tmp_path,'2022-04-01')
    with TestClient(create_app(tmp_path)) as client:
        _,protocol=register(client)
        runs=[]
        for day in ['2022-04-27','2022-04-28']:
            response=client.post('/api/research/protocols/'+protocol['protocol_id']+'/executions',json={
                'partition':'DEVELOPMENT','observation_date':day,'quantity':'200','basis':'合成税费边界，不替历史规则准入'})
            assert response.status_code==201,response.text
            runs.append(response.json())
        before,after=[r['definition']['historical_costs'] for r in runs]
        assert before['BUY']['trade_date']=='2022-04-28' and before['BUY']['transfer_each_side_rate']=='0.00002'
        assert after['BUY']['trade_date']=='2022-04-29' and after['BUY']['transfer_each_side_rate']=='0.00001'
        assert before['SELL']['transfer_each_side_rate']==after['SELL']['transfer_each_side_rate']=='0.00001'
        assert runs[0]['definition']['cost_fingerprint']!=runs[1]['definition']['cost_fingerprint']
        for run in runs:
            assert run['result']['label_status']=='UNSCORABLE'
            assert 'HISTORICAL_RULE_SCOPE_UNKNOWN' in run['result']['reasons']
            assert client.post('/api/research/executions/'+run['execution_id']+'/replay').json()['matches_original']


def test_changed_cost_dependency_cannot_replay_old_execution_and_keeps_original(tmp_path,monkeypatch):
    from roll.research import historical_costs
    method_archive(tmp_path)
    with TestClient(create_app(tmp_path)) as client:
        _,protocol=register(client)
        original=client.post('/api/research/protocols/'+protocol['protocol_id']+'/executions',json={
            'partition':'DEVELOPMENT','observation_date':'2026-01-05','quantity':'200','basis':'合成不可变依赖版本门禁'}).json()
        assert client.post('/api/research/executions/'+original['execution_id']+'/replay').json()['matches_original']
        # File configuration seam only; no calculator/registry collaborator is mocked.
        items=json.loads(historical_costs.MANIFEST.read_text(encoding='utf-8'))
        items[0]['changed_basis']='A new dependency version cannot silently replace the old frozen schedule'
        changed=tmp_path/'changed-cost-source-manifest.json';changed.write_text(json.dumps(items),encoding='utf-8')
        monkeypatch.setattr(historical_costs,'MANIFEST',changed)
        assert client.post('/api/research/executions/'+original['execution_id']+'/replay').status_code==409
        assert client.post('/api/research/executions/'+original['execution_id']+'/assessments',json={
            'label_as_of':'2026-10-08T00:00:00+08:00','basis':'改变依赖不得默用新版本复评'}).status_code==409
        assert client.get('/api/research/executions/'+original['execution_id']).json()==original
