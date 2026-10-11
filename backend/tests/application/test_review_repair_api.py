"""New frozen repair contracts persist via real FastAPI/SQLite/archive boundaries."""
from fastapi.testclient import TestClient
from roll.app import create_app
from test_validation import prepared


def test_repaired_comparator_and_subset_contracts_are_frozen_and_replayable(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        frozen, protocol, _ = prepared(client,tmp_path)
        contract=frozen['method_validation']['comparator_contract']
        assert contract['MA5_MA20']['exit']=='HORIZON_SESSION20_CLOSE'
        assert contract['MA5_MA20']['quantity']=='200'
        assert 'previous MA5-MA20<=0 and current MA5-MA20>0' in contract['MA5_MA20']['entry']
        assert contract['START_HOLD']['sizing']=='FIXED_LOT_WITHIN_CAP_NOT_TARGET_EXPOSURE'
        assert frozen['statistical_methods']['version']=='20-statistical-method-v2'
        assert frozen['statistical_methods']['real_sampling_assumptions_verified'] is False
        assert all(r['lower_95']==r['upper_95']==.21 for r in frozen['statistical_methods']['worked_examples']['conditional_observed_nonmembers'])
        shadow='/api/research/shadow/'+frozen['freeze_id']
        assert client.post(shadow+'/replay').json()['matches_original'] is True
        command={'purpose':'DIAGNOSTIC','expected_complete_protocol_fingerprint':frozen['complete_protocol_fingerprint'],
                 'basis':'METHOD comparator exposure and conditional subset repair; no new qualification'}
        response=client.post('/api/research/complete-freezes/'+frozen['freeze_id']+'/validations',json=command)
        assert response.status_code==201,response.text
        manifest=response.json()
        for reference in manifest['gates']['G4']['details']['comparisons'].values():
            assert reference['baseline_exposure']['observed_sessions']>0
            assert reference['baseline_exposure']['unknown_sessions']==0
            assert set(reference['position_difference'])=={'average_gross_exposure','maximum_gross_exposure','occupied_session_fraction'}
            assert reference['risk_matching']=='COMMON_CONSTRAINTS_DO_NOT_ESTABLISH_REALIZED_RISK_MATCHING'
        assert manifest['capability_status']=='NOT_GRANTED' and manifest['system_usable'] is False
        assert manifest['confirmation_pass_look'] is manifest['sealed_read'] is False
        assert manifest['validation_verdict'] in {'FAIL','INCONCLUSIVE'}
        assert client.post('/api/research/validations/'+manifest['validation_id']+'/replay').json()['matches_original'] is True
        assert client.get('/api/account').json()['version']==0
        assert client.get('/api/research/protocols/'+protocol['protocol_id']).json()['forward_started_at'] is None
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/research/complete-freezes/'+frozen['freeze_id']).json()==frozen
        assert client.get('/api/research/validations/'+manifest['validation_id']).json()==manifest
        assert client.post(shadow+'/replay').json()['matches_original'] is True
        assert client.post('/api/research/validations/'+manifest['validation_id']+'/replay').json()['matches_original'] is True
