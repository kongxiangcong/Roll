from fastapi.testclient import TestClient
from roll.app import create_app
from test_policy_successors import predecessor,register
from test_successor_shadow import freeze_successor,frame


def test_joint_review_extends_without_rewriting_old_review_or_replay(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        previous=predecessor(client,tmp_path);proposal=register(client,previous).json();frozen=freeze_successor(client,proposal).json()
        parent=client.get('/api/research/protocols/'+previous['protocol_id']).json()
        child=client.post('/api/research/protocols',json={'dataset_id':parent['dataset_id'],'predecessor_id':parent['protocol_id'],'basis':'Versioned evidence extension'}).json()
        base='/api/research/policy-successor-freezes/'+frozen['successor_freeze_id']
        protocol=client.post(base+'/complete-protocol',json={'protocol_id':child['protocol_id'],'expected_protocol_fingerprint':child['protocol_fingerprint'],'expected_successor_fingerprint':frozen['successor_fingerprint'],'idempotency_key':'parameters','basis':'Original design'}).json()
        for day in range(1,4):assert client.post(base+'/shadow/advance',json=frame(day)).status_code==201
        def source(revision,key):
            result=client.post(base+'/cost-stress',json={'expected_complete_protocol_fingerprint':protocol['complete_protocol_fingerprint'],'expected_revision':revision,'idempotency_key':key,'basis':'Exact frozen METHOD prefix'}).json()
            route='/api/research/successor-cost-stresses/'+result['stress_id'];command={'idempotency_key':key,'basis':'Saved component'}
            control=client.post(route+'/registered-controls',json=command).json();entry=client.post(route+'/entry-stress',json=command).json()
            joint=client.post(route+'/joint-stress',json={**command,'controls_id':control['comparison_id'],'entry_id':entry['diagnostic_id']}).json()
            review=client.post(route+'/evidence-review',json={**command,'controls_id':control['comparison_id'],'entry_id':entry['diagnostic_id']}).json()
            return review,joint
        original,joint=source(3,'source');old_path='/api/research/successor-evidence-reviews/'+original['review_id'];route=old_path+'/joint-review'
        before_replay=client.post(old_path+'/replay').json();command={'joint_id':joint['joint_id'],'idempotency_key':'extension','basis':'Bind joint scenarios without editing old report'}
        response=client.post(route,json=command);assert response.status_code==201,response.text
        saved=response.json();identifier=saved['joint_review_id'];new_path='/api/research/successor-joint-reviews/'+identifier
        assert saved['components']['joint']['bound'] is True and saved['components']['joint']['scenario_count']==12
        assert 'JOINT_COMPARATOR_STRESS_NOT_BOUND' not in saved['gates']['G5']['reasons']
        assert saved['validation_verdict']=='INCONCLUSIVE' and all(g['status']!='PASS' for g in saved['gates'].values())
        assert 'REAL_G6_G7' not in saved['complete_freeze_gaps'] and 'REAL_G6_G7' in saved['qualification_gaps']
        assert client.get(old_path).json()==original and client.post(old_path+'/replay').json()==before_replay
        assert client.post(route,json=command).json()==saved and client.get(route).json()==[saved]
        assert client.get('/api/account').json()['version']==0
        adverse=frame(4);adverse['bars'][0].update(open_yuan='200.00',high_yuan='200.00',low_yuan='200.00',close_yuan='200.00',reference_close_yuan='200.00')
        assert client.post(base+'/shadow/advance',json=adverse).status_code==201
        failed_source,failed_joint=source(4,'risk')
        assert client.post(route,json={**command,'joint_id':failed_joint['joint_id'],'idempotency_key':'mixed'}).status_code==409
        failed=client.post('/api/research/successor-evidence-reviews/'+failed_source['review_id']+'/joint-review',json={**command,'joint_id':failed_joint['joint_id']})
        assert failed.status_code==201,failed.text
        assert failed.json()['validation_verdict']=='FAIL' and failed.json()['gates']['G5']['status']=='FAIL'
        assert failed.json()['gates']['G4']['status']=='FAIL'
        raw=client.app.state.evidence.raw(joint['input_archive']['sha256']);body=raw.read_bytes()
        try:
            raw.write_bytes(b'corrupt selected joint input')
            assert client.get(new_path).status_code==409 and client.post(new_path+'/replay').status_code==409
        finally:raw.write_bytes(body)
        assert client.post(new_path+'/replay').json()['matches_original'] is True
    with TestClient(create_app(tmp_path)) as client:
        assert client.get(new_path).json()==saved and client.post(new_path+'/replay').json()['matches_original'] is True
        assert client.get(old_path).json()==original and client.post(old_path+'/replay').json()==before_replay
