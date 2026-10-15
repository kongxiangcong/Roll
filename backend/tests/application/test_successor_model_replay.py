from uuid import uuid4
from fastapi.testclient import TestClient
from roll.app import create_app
from test_policy_successors import predecessor,register
from test_successor_shadow import freeze_successor,frame
from report_method_app import ROOT


def test_saved_cal_predictions_drive_separate_full_calendar_method_replay(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_SKLEARN_PYTHON',str(ROOT/'.scratch/rce-runtime/probability/Scripts/python.exe'))
    monkeypatch.setenv('ROLL_ARCH_PYTHON',str(ROOT/'.scratch/rce-runtime/arch/Scripts/python.exe'))
    with TestClient(create_app(tmp_path)) as client:
        previous=predecessor(client,tmp_path);proposal=register(client,previous).json();frozen=freeze_successor(client,proposal,cash_yuan="100000").json()
        parent=client.get('/api/research/protocols/'+previous['protocol_id']).json();child=client.post('/api/research/protocols',json={'dataset_id':parent['dataset_id'],'predecessor_id':parent['protocol_id'],'basis':'Versioned METHOD component completion inventory'}).json()
        base='/api/research/policy-successor-freezes/'+frozen['successor_freeze_id'];command={'idempotency_key':'saved','basis':'Same saved METHOD components'}
        protocol=client.post(base+'/complete-protocol',json={**command,'protocol_id':child['protocol_id'],'expected_protocol_fingerprint':child['protocol_fingerprint'],'expected_successor_fingerprint':frozen['successor_fingerprint']}).json()
        attempts=client.get('/api/research/protocols/'+child['protocol_id']+'/attempts').json()
        assert client.post('/api/research/shadow/'+previous['freeze_id']+'/advance',json={'through_date':parent['design']['windows']['CALIBRATION']['last_date'],'forecast_ids':[],'expected_revision':0}).status_code==201
        probability=client.post('/api/research/complete-freezes/'+previous['freeze_id']+'/probability-reference',json={**command,'expected_complete_protocol_fingerprint':previous['complete_protocol_fingerprint']}).json()
        blocks=client.post('/api/research/probability-references/'+probability['reference_id']+'/block-reference',json=command).json()
        binding=client.post(base+'/probability-evidence',json={**command,'expected_complete_protocol_fingerprint':protocol['complete_protocol_fingerprint'],'probability_reference_id':probability['reference_id'],'block_reference_id':blocks['reference_id']}).json()
        for day in range(1,4):assert client.post(base+'/shadow/advance',json=frame(day)).status_code==201
        source=client.post(base+'/cost-stress',json={**command,'expected_complete_protocol_fingerprint':protocol['complete_protocol_fingerprint'],'expected_revision':3}).json();route='/api/research/successor-cost-stresses/'+source['stress_id']
        records={}
        for name,path in [('segments','time-segments'),('cash','cash-control'),('controls','registered-controls'),('entry','entry-stress'),('threshold','threshold-stress'),('migration','migration-audit')]:
            response=client.post(route+'/'+path,json=command);assert response.status_code==201,response.text
            records[name]=response.json()
        original=client.post(route+'/evidence-review',json={**command,'segments_id':records['segments']['segmentation_id'],'cash_id':records['cash']['control_id'],'controls_id':records['controls']['comparison_id'],'entry_id':records['entry']['diagnostic_id'],'probability_id':binding['binding_id']}).json()
        joint=client.post(route+'/joint-stress',json={**command,'controls_id':records['controls']['comparison_id'],'entry_id':records['entry']['diagnostic_id']}).json()
        extension=client.post('/api/research/successor-evidence-reviews/'+original['review_id']+'/joint-review',json={**command,'joint_id':joint['joint_id']}).json()
        check_route='/api/research/successor-joint-reviews/'+extension['joint_review_id']+'/completion-check';check_command={**command,'threshold_id':records['threshold']['diagnostic_id'],'migration_id':records['migration']['audit_id']}
        response=client.post(check_route,json=check_command);assert response.status_code==201,response.text
        saved=response.json();identifier=saved['check_id'];path='/api/research/successor-completion-checks/'+identifier
        route=path+'/primary-center-binding'
        before=client.get('/api/research/protocols/'+child['protocol_id']+'/attempts').json()
        response=client.post(route,json=command);assert response.status_code==201,response.text
        center=response.json();center_path='/api/research/successor-primary-center-bindings/'+center['binding_id']
        original_shadow=client.get(base+'/shadow').json()
        replay_route=center_path+'/model-execution-replay'
        response=client.post(replay_route,json=command);assert response.status_code==201,response.text
        replay=response.json();replay_path='/api/research/successor-model-execution-replays/'+replay['replay_id']
        assert replay['calendar_session_count']==40 and replay['prediction_count']==20
        assert len(replay['curve'])==41 and len(replay['frames'])==40
        assert sum(len(f['signals']) for f in replay['frames'])==20
        assert all(not f['signals'] for f in replay['frames'][20:])
        assert [f['trade_date'] for f in replay['frames']]==replay['calendar_sessions']
        assert [(e['kind'],e['session']) for e in replay['result']['events']]==[('BUY_FILL',14),('SELL_FILL',34)]
        import json
        predictions=json.loads(client.get('/api/data/archives/'+center['artifacts']['calibrated_prediction_archive']['sha256']).content)
        assert [(f['trade_date'],f['signals'][0]['probability']) for f in replay['frames'] if f['signals']]==[(p['observation_date'],str(p['probability'])) for p in predictions]
        assert replay['frames'][0]['bars'][0]['close_yuan']=='111.8678'
        assert replay['new_prediction_calls']==replay['new_fit_calls']==0
        assert replay['source_scope']=='SAVED_CALIBRATION_FIT_IN_SAMPLE_NOT_INDEPENDENT'
        assert replay['real_input_admitted'] is False and replay['capability']=='NOT_GRANTED'
        assert replay['complete_experiment_frozen'] is False
        assert client.get(base+'/shadow').json()==original_shadow
        assert client.get(center_path).json()==center
        assert client.get('/api/research/protocols/'+child['protocol_id']+'/attempts').json()==before
        assert client.get('/api/account').json()['version']==0
        assert client.post(replay_route,json=command).json()==replay and client.get(replay_route).json()==[replay]
        assert client.post(replay_route,json={**command,'basis':'conflict'}).status_code==409
        assert client.post(replay_path+'/replay').json()['matches_original']
        raw=client.app.state.evidence.raw(replay['calendar_archive']['sha256']);body=raw.read_bytes()
        try:
            raw.write_bytes(b'corrupt saved calendar')
            assert client.get(replay_path).status_code==409 and client.post(replay_path+'/replay').status_code==409
        finally:raw.write_bytes(body)
    monkeypatch.delenv('ROLL_SKLEARN_PYTHON');monkeypatch.delenv('ROLL_ARCH_PYTHON')
    with TestClient(create_app(tmp_path)) as client:
        assert client.get(replay_path).json()==replay and client.post(replay_path+'/replay').json()['matches_original']
