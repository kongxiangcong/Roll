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
