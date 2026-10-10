from fastapi.testclient import TestClient
from roll.app import create_app
from test_shadow import setup, freeze, high_forecasts


def prepared(client, directory):
    dataset, protocol, model, dates = setup(client, directory)
    frozen = freeze(client, protocol, model).json()
    forecasts = high_forecasts(client, model)
    day = forecasts[0]['observation_cutoff'][:10]
    path = '/api/research/shadow/' + frozen['freeze_id']
    response = client.post(path + '/advance', json={'through_date': dates[dates.index(day)+20],
        'forecast_ids': [f['forecast_id'] for f in forecasts], 'expected_revision': 0})
    assert response.status_code == 201, response.text
    return frozen, protocol, model


def test_current_validation_manifest_is_persistent_replayable_and_never_a_grant(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        frozen, protocol, model = prepared(client, tmp_path)
        response = client.post('/api/research/complete-freezes/'+frozen['freeze_id']+'/validations', json={
            'purpose': 'DIAGNOSTIC', 'expected_complete_protocol_fingerprint': frozen['complete_protocol_fingerprint'],
            'basis': 'Current METHOD evidence gap review, no actual qualification'})
        assert response.status_code == 201, response.text
        manifest = response.json()
        assert set(manifest['gates']) == {'G1','G2','G3','G4','G5','G6','G7'}
        assert manifest['validation_verdict'] in ('FAIL','INCONCLUSIVE')
        assert manifest['capability_status'] == 'NOT_GRANTED'
        assert manifest['review_status'] == 'PENDING_TECHNICAL_REVIEW'
        assert manifest['gates']['G7']['status'] == 'INCONCLUSIVE'
        assert manifest['gates']['G4']['details']['basis'] == 'CONSTRAINED_CONTINUOUS_NAV'
        assert manifest['gates']['G4']['details']['unique_opportunities']==1
        assert manifest['gates']['G4']['details']['selected']==1
        assert manifest['gates']['G4']['details']['decision_coverage']==1
        assert 'MINIMUM_DECISION_COVERAGE_NOT_MET' not in manifest['gates']['G4']['details']['hard_failures']
        assert sum(c['details']['closed_positions'] for c in manifest['gates']['G5']['details']['time_segments'])==1
        assert manifest['gates']['G3']['details']['duplicate_event_count'] == 1
        assert all(c['status'] != 'INCOMPLETE' for c in manifest['gates']['G5']['details']['delays'])
        partial=next(c for c in manifest['gates']['G5']['details']['delays'] if c['component']=='NEXT_OPEN_FILL=0.50')
        assert next(e for e in partial['execution_events'] if e['kind']=='BUY_FILL')['quantity']=='100'
        assert manifest['confirmation_pass_look'] is False
        method = manifest['monitoring_method_validation']
        assert method['checks_passed'] is True
        assert method['execution_cases'][1]['actual']['restrict'] is True
        assert method['maturity_cases'][0]['actual']['review_status'] == 'NOT_AT_REGISTERED_CHECKPOINT'
        assert method['maturity_cases'][1]['actual']['excluded_unmatured'] == 1
        assert manifest['gate_combination_method']['cases'][0]['actual'] == 'FAIL'
        assert manifest['gate_combination_method']['cases'][1]['actual'] == 'INCONCLUSIVE'
        assert client.post('/api/research/validations/'+manifest['validation_id']+'/replay').json()['matches_original'] is True
        assert client.get('/api/account').json()['version'] == 0
        assert client.get('/api/research/protocols/'+protocol['protocol_id']).json()['forward_started_at'] is None
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/research/validations/'+manifest['validation_id']).json() == manifest


def test_confirmation_and_tampered_inputs_are_refused_before_test_access_or_new_result(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        frozen, protocol, model = prepared(client,tmp_path)
        path='/api/research/complete-freezes/'+frozen['freeze_id']+'/validations'
        command={'purpose':'CONFIRMATORY','expected_complete_protocol_fingerprint':frozen['complete_protocol_fingerprint'], 'basis':'Pre-admission refuses actual independent deficits'}
        response=client.post(path,json=command)
        assert response.status_code==409,response.text
        admission=response.json()['detail']
        assert admission['sealed_read'] is False and admission['input_content_consumed'] is False
        assert 'METHOD_OR_PUBLIC_SOURCE_NOT_REAL_CONFIRMATION' in admission['gaps']
        assert client.get(path).json()==[]
        assert not any(e['action']=='SEALED_INPUT_ACCESSED' for e in client.get('/api/research/protocols/'+protocol['protocol_id']+'/audit').json())
        assert client.post(path,json={**command,'purpose':'DIAGNOSTIC','expected_complete_protocol_fingerprint':'wrong'}).status_code==409
        (tmp_path/model['calibrator_artifact']['path']).write_bytes(b'corrupted calibrator')
        assert client.post(path,json={**command,'purpose':'DIAGNOSTIC'}).status_code==409
        assert client.get(path).json()==[]


def test_empty_unobserved_strategy_is_insufficient_but_budget_refusals_cannot_average_away(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        dataset, protocol, model, dates=setup(client,tmp_path)
        frozen=freeze(client,protocol,model).json()
        forecasts=high_forecasts(client,model)
        day=forecasts[0]['observation_cutoff'][:10]
        path='/api/research/shadow/'+frozen['freeze_id']
        assert client.post(path+'/advance',json={'through_date':day,'forecast_ids':[],'expected_revision':0}).status_code==201
        def check(f):
            r=client.post('/api/research/complete-freezes/'+f['freeze_id']+'/validations',json={'purpose':'DIAGNOSTIC',
                'expected_complete_protocol_fingerprint':f['complete_protocol_fingerprint'],'basis':'Unknown observations versus witnessed hard constraint'})
            assert r.status_code==201,r.text
            return r.json()
        empty=check(frozen)
        assert empty['validation_verdict']=='INCONCLUSIVE'
        assert empty['gates']['G4']['details']['unique_opportunities']==0
        assert empty['gates']['G4']['details']['candidate']['net_return']==0
        assert empty['gates']['G3']['details']['dependent_brier_improvement_intervals'][0]['status']=='INCOMPLETE_ALIGNED_CALENDAR_SCORES'
        successor=client.post('/api/research/protocols',json={'dataset_id':dataset['dataset_id'],'predecessor_id':protocol['protocol_id'],'basis':'Separate insufficient joint budget, preserve parent'}).json()
        low=freeze(client,successor,model,baseline={'cash_yuan':'5000.00','positions':[]}).json()
        assert client.post('/api/research/shadow/'+low['freeze_id']+'/advance',json={'through_date':day,
            'forecast_ids':[f['forecast_id'] for f in forecasts],'expected_revision':0}).status_code==201
        failed=check(low)
        assert failed['gates']['G4']['status']=='FAIL' and 'MINIMUM_DECISION_COVERAGE_NOT_MET' in failed['gates']['G4']['reasons']
        assert failed['gates']['G7']['status']=='INCONCLUSIVE' and failed['validation_verdict']=='FAIL'
        assert client.get('/api/research/validations/'+empty['validation_id']).json()==empty
