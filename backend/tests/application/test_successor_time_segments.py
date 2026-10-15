from fastapi.testclient import TestClient
from roll.app import create_app
from test_policy_successors import predecessor,register
from test_successor_shadow import freeze_successor,frame


def test_time_segments_preserve_carry_in_and_do_not_reset_trajectory(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        previous=predecessor(client,tmp_path);proposal=register(client,previous).json();frozen=freeze_successor(client,proposal).json()
        parent=client.get('/api/research/protocols/'+previous['protocol_id']).json()
        child=client.post('/api/research/protocols',json={'dataset_id':parent['dataset_id'],'predecessor_id':parent['protocol_id'],'basis':'Fixed chronological thirds'}).json()
        base='/api/research/policy-successor-freezes/'+frozen['successor_freeze_id']
        protocol=client.post(base+'/complete-protocol',json={'protocol_id':child['protocol_id'],'expected_protocol_fingerprint':child['protocol_fingerprint'],'expected_successor_fingerprint':frozen['successor_fingerprint'],'idempotency_key':'parameters','basis':'Before all source frames'}).json()
        states=[]
        for day in range(1,7):
            command=frame(day)
            if day==5:command['bars'][0].update(close_yuan=None,completion='UNKNOWN',market_state='UNKNOWN',company_actions='UNKNOWN')
            response=client.post(base+'/shadow/advance',json=command);assert response.status_code==201,response.text
            states.append(response.json())
        stress=client.post(base+'/cost-stress',json={'expected_complete_protocol_fingerprint':protocol['complete_protocol_fingerprint'],'expected_revision':6,'idempotency_key':'costs','basis':'METHOD saved prefix source'}).json()
        route='/api/research/successor-cost-stresses/'+stress['stress_id']+'/time-segments'
        command={'idempotency_key':'thirds','basis':'Keep original carry-in; no funding reset'}
        response=client.post(route,json=command)
        assert response.status_code==201,response.text
        saved=response.json();identifier=saved['segmentation_id']
        assert saved['G5_status']=='INCONCLUSIVE' and len(saved['segments'])==3
        assert [(s['first_session'],s['last_session']) for s in saved['segments']]==[(1,2),(3,4),(5,6)]
        second=saved['segments'][1]
        assert second['carry_in']['cash_yuan']==states[1]['cash_yuan']
        assert second['carry_in']['positions']==states[1]['positions']
        assert second['curve'][0]==stress['base']['curve'][2]
        assert saved['segments'][2]['economics']['net_return'] is None
        assert any(p['nav_yuan'] is None for p in saved['segments'][2]['curve'])
        assert saved['source_manifest']==stress['archive'] and saved['capability']=='NOT_GRANTED'
        assert client.post(route,json=command).json()==saved
        assert client.get(route).json()==[saved]
        assert client.get(base+'/shadow').json()==states[-1]
        assert client.get(base+'/complete-protocol').json()==protocol
        # Later sparse frames remain holes in the declared span, including
        # the exact boundary before the last third. Never carry state across it.
        for revision,session in ((6,10),(7,12)):
            assert client.post(base+'/shadow/advance',json=frame(session,expected_revision=revision,calendar_previous_session=session-1)).status_code==201
        sparse=client.post(base+'/cost-stress',json={'expected_complete_protocol_fingerprint':protocol['complete_protocol_fingerprint'],'expected_revision':8,'idempotency_key':'sparse-costs','basis':'METHOD missing slots preserved'}).json()
        sparse_response=client.post('/api/research/successor-cost-stresses/'+sparse['stress_id']+'/time-segments',json=command)
        assert sparse_response.status_code==201,sparse_response.text
        last=sparse_response.json()['segments'][2]
        assert last['declared_sessions']==[9,10,11,12] and last['missing_declared_sessions']==[9,11]
        assert last['carry_in']['session']==8 and last['carry_in']['boundary_state_known'] is False
        assert last['carry_in']['cash_yuan'] is None and last['carry_in']['positions'] is None
        assert last['economics']['net_return'] is None
        assert {g['session'] for g in last['input_gaps']}=={10,12}
        assert client.post('/api/research/successor-time-segments/'+identifier+'/replay').json()['matches_original'] is True
        path=client.app.state.evidence.raw(stress['source']['sha256']);original=path.read_bytes();path.write_bytes(b'corrupt only disposable copy')
        try:assert client.get('/api/research/successor-time-segments/'+identifier).status_code==409
        finally:path.write_bytes(original)
        assert client.post(base+'/shadow/advance',json=frame(1000,expected_revision=8,calendar_previous_session=999)).status_code==201
        wide=client.post(base+'/cost-stress',json={'expected_complete_protocol_fingerprint':protocol['complete_protocol_fingerprint'],'expected_revision':9,'idempotency_key':'wide-costs','basis':'METHOD span rejection'}).json()
        refused=client.post('/api/research/successor-cost-stresses/'+wide['stress_id']+'/time-segments',json=command)
        assert refused.status_code==422 and 'SPAN_LIMIT_NO_COMPRESSION' in str(refused.json())
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/research/successor-time-segments/'+identifier).json()==saved
        assert client.post('/api/research/successor-time-segments/'+identifier+'/replay').json()['matches_original'] is True
