from fastapi.testclient import TestClient
from roll.app import create_app
from capability_method_app import save_package
from test_capability_monitoring import monitored_package
from test_actions import prepare


def test_correction_records_source_improvement_modules_and_plan_without_rewriting_pass(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    package = monitored_package(20, outside=4)
    file = save_package(tmp_path / 'qualification.json', package)
    directory = tmp_path / 'data'
    with TestClient(create_app(directory, capability_method_file=file)) as client:
        grant = prepare(client, package)
        check = client.post('/api/capabilities/monitoring/check', json={'grant_id': grant['grant_id'], 'basis': 'frozen data drift'}).json()
        command = {'monitoring_check_id': check['check_id'], 'category': 'DATA_REPAIR',
            'error_source': '核对四个归档输入是否存在来源映射错误',
            'expected_improvement': '恢复原冻结输入口径，不重新拟合DEV界限',
            'affected_modules': ['market/evidence', 'research/forward_features'],
            'validation_plan': '原始归档重放、映射回归及同一冻结参考的后续监测',
            'changes_frozen': False, 'idempotency_key': 'data-correction'}
        response = client.post('/api/capabilities/corrections', json=command)
        assert response.status_code == 201, response.text
        correction = response.json()
        assert correction['review_state'] == 'OPEN' and correction['category'] == 'DATA_REPAIR'
        assert correction['error_source'] == command['error_source']
        assert correction['expected_improvement'] == command['expected_improvement']
        assert correction['affected_modules'] == command['affected_modules']
        assert correction['validation_plan'] == command['validation_plan']
        assert correction['source_check_archive_sha256'] == check['archive']['sha256']
        assert correction['source_protocol_fingerprint'] == grant['complete_protocol_fingerprint']
        assert correction['qualification_verdict_changed'] is False
        assert client.post('/api/capabilities/corrections', json=command).json() == correction
        assert client.get('/api/capabilities/corrections').json() == [correction]
        delayed = client.post('/api/capabilities/corrections', json={**command, 'category':'USER_DELAY', 'idempotency_key':'unproven-delay'})
        assert delayed.status_code == 409
        assert delayed.json()['detail'] == 'USER_DELAY_NOT_ESTABLISHED_BY_SOURCE'
        assert client.get('/api/capabilities/monitoring/' + check['check_id']).json() == check
        assert client.get('/api/capabilities/grants').json() == [grant]
        refused = client.post('/api/capabilities/corrections', json={**command, 'category': 'MODEL_RESEARCH',
            'changes_frozen': True, 'idempotency_key': 'unregistered-change'})
        assert refused.status_code == 422
        assert client.get('/api/capabilities/corrections').json() == [correction]
        successor = client.post('/api/capabilities/corrections', json={**command, 'category':'MODEL_RESEARCH',
            'changes_frozen':True,'successor_protocol_id':'planned-method-successor','successor_version_fingerprint':'f'*64,
            'idempotency_key':'new-protocol-plan'})
        assert successor.status_code == 201, successor.text
        planned = successor.json()
        assert planned['successor_validation_state'] == 'PENDING_REGISTRATION_AND_VALIDATION'
        assert planned['qualification_verdict_changed'] is False and planned['automatic_retraining'] is False
        assert client.get('/api/capabilities/grants').json() == [grant]
    with TestClient(create_app(directory, capability_method_file=file)) as client:
        assert client.get('/api/capabilities/corrections').json() == [correction, planned]


def test_literal_delay_correction_is_execution_hypothesis_and_does_not_blame_model(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test')
    package=monitored_package(20)
    g5=package['monitoring_basis']['frozen']['design']['g5']
    package['monitoring_basis']['method_execution_facts']=[{'delay':'METHOD_OUTSIDE_REGISTERED_DELAY',
        'fill_fraction':'.5','commission_scenario_rate':g5['commission_rates'][0],
        'slippage_each_side_rate':g5['slippage_each_side_rates'][0], 'price_in_frozen_window':True}]
    file=save_package(tmp_path/'qualification.json',package)
    with TestClient(create_app(tmp_path/'data',capability_method_file=file)) as client:
        grant=prepare(client,package)
        check=client.post('/api/capabilities/monitoring/check',json={'grant_id':grant['grant_id'],'basis':'固定METHOD延迟假设，不是实际送达证据'}).json()
        assert check['correction_class']=='EXECUTION_ASSUMPTION'
        assert 'DELAY_OUTSIDE_FROZEN_SCENARIOS' in check['reasons']
        response=client.post('/api/capabilities/corrections',json={'monitoring_check_id':check['check_id'],
            'category':'USER_DELAY','error_source':'声明的METHOD延迟超出冻结场景，不是模型错误',
            'expected_improvement':'单独记录执行条件偏差','affected_modules':['decisions/intents'],
            'validation_plan':'与实际送达、已读和操作时点分别核对；未知不补齐',
            'changes_frozen':False,'idempotency_key':'delay-plan'})
        assert response.status_code==201,response.text
        assert response.json()['qualification_verdict_changed'] is False
        assert response.json()['category']=='USER_DELAY'
        assert client.get('/api/capabilities/monitoring/'+check['check_id']).json()==check
