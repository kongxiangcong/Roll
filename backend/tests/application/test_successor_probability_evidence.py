from fastapi.testclient import TestClient
from roll.app import create_app
from report_method_app import copy_donor,ROOT,FREEZE


def test_successor_binds_same_frozen_probability_and_block_archives(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test')
    monkeypatch.setenv('ROLL_SKLEARN_PYTHON',str(ROOT/'.scratch/rce-runtime/probability/Scripts/python.exe'))
    monkeypatch.setenv('ROLL_ARCH_PYTHON',str(ROOT/'.scratch/rce-runtime/arch/Scripts/python.exe'))
    with TestClient(create_app(copy_donor(tmp_path/'data'),runtime_role='API')) as client:
        account=client.get('/api/account').json()
        previous=client.get('/api/research/complete-freezes/'+FREEZE).json()
        probability=client.post('/api/research/complete-freezes/'+FREEZE+'/probability-reference',json={'expected_complete_protocol_fingerprint':previous['complete_protocol_fingerprint'],'idempotency_key':'prob-source','basis':'Reuse saved METHOD CAL, no new fitting'}).json()
        blocks=client.post('/api/research/probability-references/'+probability['reference_id']+'/block-reference',json={'idempotency_key':'block-source','basis':'Same archived calendar reference'}).json()
        proposal=client.post('/api/research/policy-successors',json={'predecessor_freeze_id':FREEZE,'predecessor_policy_fingerprint':previous['fingerprints']['policy'],'version':'METHOD-successor-probability-v2','idempotency_key':'successor','basis':'Same frozen model and existing policy'}).json()
        successor=client.post('/api/research/policy-successors/'+proposal['proposal_id']+'/freezes',json={'policy_fingerprint':proposal['policy_fingerprint'],'idempotency_key':'successor-freeze','starting_session':0,'cash_yuan':'10000.00','positions':[],'basis':'METHOD baseline'}).json()
        parent=client.get('/api/research/protocols/'+previous['protocol_id']).json()
        child=client.post('/api/research/protocols',json={'dataset_id':parent['dataset_id'],'predecessor_id':parent['protocol_id'],'basis':'Source binding only, no fit'}).json()
        base='/api/research/policy-successor-freezes/'+successor['successor_freeze_id']
        complete=client.post(base+'/complete-protocol',json={'protocol_id':child['protocol_id'],'expected_protocol_fingerprint':child['protocol_fingerprint'],'expected_successor_fingerprint':successor['successor_fingerprint'],'idempotency_key':'parameters','basis':'Original economic/statistical design'}).json()
        attempts=client.get('/api/research/protocols/'+child['protocol_id']+'/attempts').json()
        command={'expected_complete_protocol_fingerprint':complete['complete_protocol_fingerprint'],'probability_reference_id':probability['reference_id'],'block_reference_id':blocks['reference_id'],'idempotency_key':'bind','basis':'Reuse same source archives; never grant independent calibration'}
        response=client.post(base+'/probability-evidence',json=command)
        assert response.status_code==201,response.text
        saved=response.json();identifier=saved['binding_id']
        assert saved['G3_status']=='INCONCLUSIVE' and saved['independent_calibration_validation'] is False
        assert saved['system_usable'] is False and saved['capability']=='NOT_GRANTED'
        assert len(saved['phases'])==2 and all(p['mature_unique']==20 for p in saved['phases'].values())
        for name,phase in saved['phases'].items():
            expected=[r for r in probability['phases'][name]['accepted_rows'] if r['probability']>=.6]
            assert phase['selected_mature']==len(expected)
        assert all('CALIBRATION_FIT_WINDOW_REUSED' in p['gaps'] and p['missing_calendar_sessions']==20 for p in saved['phases'].values())
        assert saved['probability_manifest']==probability['archive'] and saved['block_manifest']==blocks['archive']
        assert client.post(base+'/probability-evidence',json=command).json()==saved
        assert client.get(base+'/probability-evidence').json()==[saved]
        # This historical donor retains its old inherited engine fingerprint.
        # Do not relabel it to run a different current execution engine.
        from test_successor_shadow import frame
        symbol=next(iter(successor['rules']))
        for day in range(1,4):
            observation=frame(day);observation['bars'][0]['instrument']=symbol;observation['signals'][0]['instrument']=symbol
            assert client.post(base+'/shadow/advance',json=observation).status_code==201
        stress_response=client.post(base+'/cost-stress',json={'expected_complete_protocol_fingerprint':complete['complete_protocol_fingerprint'],'expected_revision':3,'idempotency_key':'review-cost','basis':'METHOD execution kept distinct from saved CAL'})
        assert stress_response.status_code==409 and 'WORKER_FAILED' in stress_response.text
        # Corrupt only newly generated archives in this disposable copy.
        for archive in (probability['source'],blocks['source']):
            path=client.app.state.evidence.raw(archive['sha256']);original=path.read_bytes();path.write_bytes(b'corrupt nested reference')
            try:
                assert client.get('/api/research/successor-probability-evidence/'+identifier).status_code==409
                assert client.post('/api/research/successor-probability-evidence/'+identifier+'/replay').status_code==409
            finally:path.write_bytes(original)
        wrong=client.post(base+'/probability-evidence',json={**command,'idempotency_key':'wrong-binding','probability_reference_id':blocks['reference_id']})
        assert wrong.status_code==404
        second=client.post('/api/research/complete-freezes/'+FREEZE+'/probability-reference',json={'expected_complete_protocol_fingerprint':previous['complete_protocol_fingerprint'],'idempotency_key':'another-probability-source','basis':'Second saved numerical report, no fitting'}).json()
        mismatched=client.post(base+'/probability-evidence',json={**command,'idempotency_key':'mixed-source','probability_reference_id':second['reference_id']})
        assert mismatched.status_code==409 and 'BLOCK_SOURCE_MISMATCH' in str(mismatched.json())
        assert client.post(base+'/probability-evidence',json={**command,'basis':'changed'}).status_code==409
        assert client.get('/api/research/protocols/'+child['protocol_id']+'/attempts').json()==attempts
        assert client.get('/api/research/complete-freezes/'+FREEZE).json()==previous
        assert client.get(base+'/complete-protocol').json()==complete
        assert client.get('/api/account').json()==account
    monkeypatch.delenv('ROLL_SKLEARN_PYTHON');monkeypatch.delenv('ROLL_ARCH_PYTHON')
    with TestClient(create_app(tmp_path/'data',runtime_role='API')) as client:
        assert client.get('/api/research/successor-probability-evidence/'+identifier).json()==saved
        assert client.post('/api/research/successor-probability-evidence/'+identifier+'/replay').json()['matches_original'] is True
