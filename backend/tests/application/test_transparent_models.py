from fastapi.testclient import TestClient
from roll.app import create_app
from test_execution_labels import method_archive,register
import math
import hashlib


def known_method(client,directory,predecessor=None):
    changes={}
    for i in range(181):
        price=100+12*math.sin(i/7)
        changes[i]={k:str(round(price,4)) for k in ['open','close']}
        changes[i].update(high=str(round(price+1,4)),low=str(round(price-1,4)),volume_shares=str(10000+i*37))
    dates=method_archive(directory,changes)
    if predecessor:
        dataset=client.post('/api/research/datasets',json={'archive_id':'method-execution','basis':'19明确合成已知OHLC/状态，不代真实研究'}).json()
        protocol=client.post('/api/research/protocols',json={'dataset_id':dataset['dataset_id'],'predecessor_id':predecessor,'basis':'19固定M0数学METHOD工程，前序真实不足结论保留'}).json()
    else:dataset,protocol=register(client)
    pid=protocol['protocol_id']
    for part,indices in [('DEVELOPMENT',range(20,60)),('CALIBRATION',range(100,120))]:
        for i in indices:
            response=client.post('/api/research/protocols/'+pid+'/executions',json={'partition':part,'observation_date':dates[i],
                'label_as_of':'2026-10-07T16:00:00+08:00','basis':'明确合成已知状态方法，不作为真实训练','quantity':'200'})
            assert response.status_code==201,response.text
    return dataset,protocol,dates


def test_method_artifacts_time_isolation_forecast_and_offline_replay(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        dataset,protocol,dates=known_method(client,tmp_path);pid=protocol['protocol_id']
        response=client.post('/api/research/protocols/'+pid+'/models',json={'purpose':'METHOD_VALIDATION','basis':'固定数学与工件工程验证'})
        assert response.status_code==201,response.text
        model=response.json();assert model['status']=='METHOD_ARTIFACT_ONLY'
        assert model['evidence_kind']=='METHOD_CASE' and model['complete_experiment_frozen'] is False
        assert model['statistical_support']['calibration_total']==20
        assert 'CALIBRATION_PER_CLASS_SUPPORT_BELOW_20' in model['reasons']
        assert model['artifact_fingerprints']['data']==dataset['data_fingerprint']
        artifact=client.get('/api/data/archives/'+model['model_artifact']['sha256'])
        assert hashlib.sha256(artifact.content).hexdigest()==model['model_artifact']['sha256']
        assert model['fit']['standardization_partition']=='DEVELOPMENT'
        assert model['fit']['fitted_observation_dates']==dates[20:60]
        assert all(p['prediction_phase']=='BEFORE_CALIBRATOR_FIT' for p in model['calibration_predictions'])
        forecast=client.post('/api/research/models/'+model['model_run_id']+'/forecasts',json={'observation_date':dates[110],'basis':'时间外原模型/方法校准工程预测'})
        assert forecast.status_code==201,forecast.text
        bundle=forecast.json();assert 0<bundle['probability']<1 and bundle['capability']=='NOT_GRANTED'
        assert bundle['horizon_sessions']==20 and bundle['uncertainty']['qualification']=='NONE'
        assert bundle['feature_snapshot']['latest_input_trade_date']==dates[110]
        assert bundle['scope']['namespace']=='HISTORICAL' and bundle['execution']['scale']=='DAILY_ONLY_NO_INTRADAY_TOUCH_ORDER_INFERENCE'
        assert set(bundle['baselines'])=={'CASH','START_HOLD','MA5_MA20'}
        assert client.post('/api/research/models/'+model['model_run_id']+'/forecasts',json={'observation_date':dates[170],'basis':'封存禁止'}).status_code==403
        replay=client.post('/api/research/forecasts/'+bundle['forecast_id']+'/replay').json()
        assert replay['matches_original'] is True and replay['network_calls']==0
        assert client.get('/api/account').json()['version']==0
        assert client.get('/api/research/protocols/'+pid).json()['forward_started_at'] is None
        assert client.get('/api/research/protocols/'+pid+'/attempt-manifest').json()['attempts'][-1]['category']=='CALIBRATION'
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/research/forecasts/'+bundle['forecast_id']).json()==bundle


def test_unsupported_fit_is_a_persisted_failed_attempt_without_probability(tmp_path):
    method_archive(tmp_path,unknown=True)
    with TestClient(create_app(tmp_path)) as client:
        _,protocol=register(client);pid=protocol['protocol_id']
        client.post('/api/research/protocols/'+pid+'/executions',json={'partition':'DEVELOPMENT','observation_date':'2026-01-05','label_as_of':'2026-10-07T16:00:00+08:00','basis':'未知标签不得拟合'})
        response=client.post('/api/research/protocols/'+pid+'/models',json={'purpose':'METHOD_VALIDATION','basis':'公开拒拟合边界'})
        assert response.status_code==201,response.text
        run=response.json();assert run['status']=='FAILED' and run['model_artifact'] is None
        assert 'INSUFFICIENT_SCORABLE_SUPPORT' in run['reasons']
        assert run['support']['DEVELOPMENT']['eligible_for_training_count']==0
        attempt=client.get('/api/research/protocols/'+pid+'/attempt-manifest').json()['attempts'][-1]
        assert attempt['category']=='PRIMARY_FIT' and attempt['status']=='FAILED'
        assert client.post('/api/research/models/'+run['model_run_id']+'/forecasts',json={'observation_date':'2026-01-05','basis':'不能用失败模型'}).status_code==409
        assert client.post('/api/research/protocols/'+pid+'/freeze',json={'attempt_ids':[attempt['attempt_id']]}).status_code==409
        assert client.get('/api/account').json()['version']==0
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/research/models/'+run['model_run_id']).json()==run


def test_failed_attempts_consume_fixed_fit_budget_and_never_accept_llm_probability(tmp_path):
    method_archive(tmp_path,unknown=True)
    with TestClient(create_app(tmp_path)) as client:
        _,protocol=register(client);pid=protocol['protocol_id']
        for i in range(5):
            response=client.post('/api/research/protocols/'+pid+'/models',json={'basis':'失败也计预算 '+str(i)})
            assert response.status_code==201 and response.json()['status']=='FAILED'
        assert client.post('/api/research/protocols/'+pid+'/models',json={'basis':'超限不能丢弃失败'}).status_code==409
        assert client.post('/api/research/protocols/'+pid+'/models',json={'basis':'LLM概率不可输入','probability':.99}).status_code==422
        attempts=client.get('/api/research/protocols/'+pid+'/attempt-manifest').json()['attempts']
        assert len(attempts)==5 and all(a['status']=='FAILED' for a in attempts)
        assert any(e['action']=='ATTEMPT_BUDGET_REFUSED' for e in client.get('/api/research/protocols/'+pid+'/audit').json())


def test_missing_feature_day_and_unavailable_input_do_not_generate_forecast(tmp_path):
    # Only a difficult numeric/time boundary is tested directly; fit/forecast persistence uses the public seam above.
    from roll.research.models import features
    import json,pytest
    dates=method_archive(tmp_path)
    rows=json.loads((tmp_path/'research-inputs/method-execution/browser-live.json').read_text())['snapshot']['facts']
    with pytest.raises(ValueError,match='FEATURE_NOT_AVAILABLE_TO_CONSUMER'):
        features(rows,dates[20],True,'2026-02-01T00:00:00+08:00')
    with pytest.raises(ValueError,match='OBSERVATION_DAY_MISSING'):
        features(rows,dates[20]+'x',True,'2026-10-08T00:00:00+08:00')
    with pytest.raises(ValueError,match='HISTORICAL_POINT_IN_TIME_NOT_PROVEN'):
        features(rows,dates[20],False,'2026-10-08T00:00:00+08:00')
