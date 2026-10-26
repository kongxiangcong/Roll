from fastapi.testclient import TestClient
from roll.app import create_app
from test_policy_successors import predecessor,register
from test_successor_shadow import freeze_successor,frame


def test_successor_protocol_binds_family_before_frames_and_replays_validation_prefix(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        previous=predecessor(client,tmp_path)
        proposal=register(client,previous).json()
        frozen=freeze_successor(client,proposal).json()
        parent=client.get('/api/research/protocols/'+previous['protocol_id']).json()
        child=client.post('/api/research/protocols',json={'dataset_id':parent['dataset_id'],'predecessor_id':parent['protocol_id'],'basis':'Preregister same-family successor policy before METHOD frames'}).json()
        command={'protocol_id':child['protocol_id'],'expected_protocol_fingerprint':child['protocol_fingerprint'],
            'expected_successor_fingerprint':frozen['successor_fingerprint'],'idempotency_key':'complete-v2','basis':'Inherit fixed objectives, no new fitting or protected evidence'}
        base='/api/research/policy-successor-freezes/'+frozen['successor_freeze_id']
        response=client.post(base+'/complete-protocol',json=command)
        assert response.status_code==201,response.text
        complete=response.json()
        assert complete['complete_experiment_frozen'] is False and complete['protocol_parameters_frozen'] is True
        assert complete['design']['primary_objective']==previous['design']['primary_objective']
        assert complete['design']['statistics']==previous['design']['statistics']
        assert complete['capability']=='NOT_GRANTED' and complete['evidence_kind']=='METHOD_CASE'
        assert client.post(base+'/complete-protocol',json=command).json()==complete
        for session in range(1,4):
            assert client.post(base+'/shadow/advance',json=frame(session)).status_code==201
        checked=client.post(base+'/validations',json={'expected_complete_protocol_fingerprint':complete['complete_protocol_fingerprint'],'expected_revision':3,'idempotency_key':'validate-3','basis':'METHOD prefix diagnostic only'})
        assert checked.status_code==201,checked.text
        result=checked.json()
        assert result['validation_verdict']=='INCONCLUSIVE'
        assert result['method_checks']['replay_matches'] is True
        assert result['method_checks']['statistical_arithmetic_passed'] is True
        assert result['shadow_revision']==3 and result['system_usable'] is False
        declined=frame(4)
        declined['bars'][0].update(open_yuan='1.00',high_yuan='1.10',low_yuan='0.90',close_yuan='1.00',reference_close_yuan='1.00')
        assert client.post(base+'/shadow/advance',json=declined).status_code==201
        failed=client.post(base+'/validations',json={'expected_complete_protocol_fingerprint':complete['complete_protocol_fingerprint'],'expected_revision':4,'idempotency_key':'validate-4','basis':'Retain METHOD hard drawdown failure'}).json()
        assert failed['validation_verdict']=='FAIL' and failed['gates']['G4']['status']=='FAIL'
        assert failed['economics']['maximum_drawdown']>0.10
        replay=client.post('/api/research/successor-validations/'+result['validation_id']+'/replay')
        assert replay.status_code==200,replay.text
        assert replay.json()['matches_original'] is True and replay.json()['shadow_revision']==3
        assert client.get('/api/research/complete-freezes/'+previous['freeze_id']).json()==previous
        assert client.get('/api/account').json()['version']==0
        alternate=register(client,previous,version='20-policy-v2-alternate',idempotency_key='register-alternate').json()
        alternative=freeze_successor(client,alternate).json()
        reused=client.post('/api/research/policy-successor-freezes/'+alternative['successor_freeze_id']+'/complete-protocol',json={
            **command,'expected_successor_fingerprint':alternative['successor_fingerprint'],'idempotency_key':'complete-alternate'})
        assert reused.status_code==409,reused.text
        zero=register(client,previous,version='20-policy-v2-zero',idempotency_key='register-zero').json()
        empty=freeze_successor(client,zero,cash_yuan='0.00').json()
        denied=client.post('/api/research/policy-successor-freezes/'+empty['successor_freeze_id']+'/complete-protocol',json={
            **command,'expected_successor_fingerprint':empty['successor_fingerprint'],'idempotency_key':'complete-zero'})
        assert denied.status_code==409 and 'EMPTY_ZERO_VALUE_BASELINE' in denied.json()['detail']['gaps']
        with client.app.state.ledger.connection() as db:
            db.execute("UPDATE research_successor_frames SET value='{}' WHERE freeze_id=? AND revision=4",(frozen['successor_freeze_id'],))
            db.commit()
        independent=client.post('/api/research/successor-validations/'+result['validation_id']+'/replay')
        assert independent.status_code==200,independent.text
        assert independent.json()['matches_original'] is True
    with TestClient(create_app(tmp_path)) as client:
        assert client.get(base+'/complete-protocol').json()==complete
