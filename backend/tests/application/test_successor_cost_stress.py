from fastapi.testclient import TestClient
from roll.app import create_app
from test_policy_successors import predecessor,register
from test_successor_shadow import freeze_successor,frame


def test_saved_successor_cost_scenarios_preserve_original_and_replay(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        previous=predecessor(client,tmp_path);proposal=register(client,previous).json();frozen=freeze_successor(client,proposal).json()
        parent=client.get('/api/research/protocols/'+previous['protocol_id']).json()
        child=client.post('/api/research/protocols',json={'dataset_id':parent['dataset_id'],'predecessor_id':parent['protocol_id'],'basis':'Same-family preregistered cost sensitivity'}).json()
        base='/api/research/policy-successor-freezes/'+frozen['successor_freeze_id']
        protocol=client.post(base+'/complete-protocol',json={'protocol_id':child['protocol_id'],'expected_protocol_fingerprint':child['protocol_fingerprint'],
            'expected_successor_fingerprint':frozen['successor_fingerprint'],'idempotency_key':'parameters','basis':'Before all METHOD frames'}).json()
        for day in range(1,4):assert client.post(base+'/shadow/advance',json=frame(day)).status_code==201
        state=client.get(base+'/shadow').json();attempts=client.get('/api/research/protocols/'+child['protocol_id']+'/attempts').json()
        command={'expected_complete_protocol_fingerprint':protocol['complete_protocol_fingerprint'],'expected_revision':3,'idempotency_key':'costs-3','basis':'METHOD cost stress only; same prefix, no new policy or fitting'}
        assert client.post(base+'/cost-stress',json={**command,'expected_revision':201,'idempotency_key':'too-long'}).status_code==422
        response=client.post(base+'/cost-stress',json=command)
        assert response.status_code==201,response.text
        saved=response.json();identifier=saved['stress_id']
        assert saved['base_matches_saved_prefix'] is True and saved['G5_status']=='INCONCLUSIVE'
        assert len(saved['scenarios'])==6 and saved['evidence_kind']=='METHOD_CASE'
        assert saved['system_usable'] is False and saved['capability']=='NOT_GRANTED'
        assert saved['assumptions_verified'] is False
        assert saved['base']['result']==state
        assert all(s['input_prefix_fingerprint']==saved['input_prefix_fingerprint'] for s in saved['scenarios'])
        assert all(len(s['curve'])==4 and s['fees_yuan'] for s in saved['scenarios'])
        assert any(s['fees_yuan']!=saved['base']['fees_yuan'] for s in saved['scenarios'])
        assert client.get(base+'/shadow').json()==state
        assert client.get(base+'/complete-protocol').json()==protocol
        assert client.post(base+'/cost-stress',json=command).json()==saved
        assert client.post(base+'/cost-stress',json={**command,'basis':'changed'}).status_code==409
        assert client.get(base+'/cost-stress').json()==[saved]
        assert client.get('/api/research/protocols/'+child['protocol_id']+'/attempts').json()==attempts
        assert client.get('/api/account').json()['version']==0
        # Later corrupt history must not affect this already saved prefix.
        adverse=frame(4);adverse['bars'][0].update(open_yuan='1.00',high_yuan='1.10',low_yuan='0.90',close_yuan='1.00',reference_close_yuan='1.00')
        assert client.post(base+'/shadow/advance',json=adverse).status_code==201
        failed=client.post(base+'/cost-stress',json={**command,'expected_revision':4,'idempotency_key':'adverse-4'})
        assert failed.status_code==201,failed.text
        assert failed.json()['G5_status']=='FAIL'
        assert any(s['hard_failures'] for s in failed.json()['scenarios'])
        unknown=frame(5);unknown['bars'][0].update(close_yuan=None,completion='UNKNOWN',market_state='UNKNOWN',company_actions='UNKNOWN')
        assert client.post(base+'/shadow/advance',json=unknown).status_code==201
        incomplete=client.post(base+'/cost-stress',json={**command,'expected_revision':5,'idempotency_key':'unknown-5'})
        assert incomplete.status_code==201,incomplete.text
        assert incomplete.json()['G5_status']=='FAIL'  # Earlier hard failure survives unknown later NAV.
        assert all(s['economics']['net_return'] is None and s['input_gaps'] for s in incomplete.json()['scenarios'])
        with client.app.state.ledger.connection() as db:
            db.execute("UPDATE research_successor_frames SET value='{}' WHERE freeze_id=? AND revision=4",(frozen['successor_freeze_id'],));db.commit()
        assert client.post('/api/research/successor-cost-stresses/'+identifier+'/replay').json()['matches_original'] is True
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/research/successor-cost-stresses/'+identifier).json()==saved
