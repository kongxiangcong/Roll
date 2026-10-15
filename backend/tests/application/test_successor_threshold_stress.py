import json
from uuid import uuid4
from fastapi.testclient import TestClient
from roll.app import create_app
from test_policy_successors import predecessor,register
from test_successor_shadow import freeze_successor,frame


def test_threshold_grid_reuses_probabilities_preserves_support_and_attempt_lineage(tmp_path,monkeypatch):
    with TestClient(create_app(tmp_path)) as client:
        previous=predecessor(client,tmp_path);proposal=register(client,previous).json();frozen=freeze_successor(client,proposal).json()
        parent=client.get('/api/research/protocols/'+previous['protocol_id']).json();child=client.post('/api/research/protocols',json={'dataset_id':parent['dataset_id'],'predecessor_id':parent['protocol_id'],'basis':'Entry threshold neighborhood before METHOD frames'}).json()
        base='/api/research/policy-successor-freezes/'+frozen['successor_freeze_id']
        protocol=client.post(base+'/complete-protocol',json={'protocol_id':child['protocol_id'],'expected_protocol_fingerprint':child['protocol_fingerprint'],'expected_successor_fingerprint':frozen['successor_fingerprint'],'idempotency_key':'parameters','basis':'Fixed entry grid only'}).json()
        original_attempts=client.get('/api/research/protocols/'+child['protocol_id']+'/attempts').json()
        for day in range(1,9):assert client.post(base+'/shadow/advance',json=frame(day,'0.58' if day<=4 else '0.62')).status_code==201
        state=client.get(base+'/shadow').json();source=client.post(base+'/cost-stress',json={'expected_complete_protocol_fingerprint':protocol['complete_protocol_fingerprint'],'expected_revision':8,'idempotency_key':'source','basis':'Reuse only these saved probabilities'}).json()
        route='/api/research/successor-cost-stresses/'+source['stress_id']+'/threshold-stress';command={'idempotency_key':'thresholds','basis':'Entry-only, support fixed; no winner or fitting'}
        response=client.post(route,json=command);assert response.status_code==201,response.text
        saved=response.json();identifier=saved['diagnostic_id'];scenarios={s['entry_threshold']:s for s in saved['scenarios']}
        assert set(scenarios)=={'0.55','0.60','0.65'} and scenarios['0.60']['result']==state
        assert all(s['support_threshold']=='0.60' for s in scenarios.values())
        low=scenarios['0.55']['result'];high=scenarios['0.65']['result']
        assert any(e['kind']=='BUY_FILL' and e['session']==2 for e in low['events'])
        assert any(e['kind']=='SELL_FILL' and e['session']==5 for e in low['events'])  # support remains0.60, not lowered0.55.
        assert not any(e['kind']=='BUY_FILL' for e in high['events'])
        manifest=saved['method_attempt_manifest'];assert len(manifest['attempts'])==3
        assert all(a['status']=='SUCCEEDED' and a['partition'] is None and a['data_scope']=='METHOD_DECLARED_SLOTS' for a in manifest['attempts'])
        assert all(a['category']=='THRESHOLD' for a in manifest['attempts'])
        assert client.post(route,json=command).json()==saved and client.get(route).json()==[saved]
        live=client.get('/api/research/protocols/'+parent['protocol_id']+'/successor-method-attempts').json()
        assert live['attempt_ids']==manifest['attempt_ids']
        assert client.get('/api/research/protocols/'+child['protocol_id']+'/attempts').json()==original_attempts
        assert client.get(base+'/shadow').json()==state and client.get('/api/account').json()['version']==0
        assert client.post('/api/research/successor-threshold-stresses/'+identifier+'/replay').json()['matches_original'] is True
        unknown=frame(10,expected_revision=8);unknown['bars'][0].update(close_yuan=None,completion='UNKNOWN',market_state='UNKNOWN',company_actions='UNKNOWN')
        assert client.post(base+'/shadow/advance',json=unknown).status_code==201
        adverse=frame(11,expected_revision=9);adverse['bars'][0].update(open_yuan='200.00',high_yuan='200.00',low_yuan='200.00',close_yuan='200.00',reference_close_yuan='200.00')
        assert client.post(base+'/shadow/advance',json=adverse).status_code==201
        later=client.post(base+'/cost-stress',json={'expected_complete_protocol_fingerprint':protocol['complete_protocol_fingerprint'],'expected_revision':10,'idempotency_key':'risk','basis':'Keep missing9 and unknown10 with later observed risk'}).json()
        risky=client.post('/api/research/successor-cost-stresses/'+later['stress_id']+'/threshold-stress',json=command)
        assert risky.status_code==201,risky.text
        assert risky.json()['status']=='SUCCEEDED' and risky.json()['G5_status']=='FAIL'
        assert any('MAXIMUM_EXPOSURE_EXCEEDED' in s['hard_failures'] for s in risky.json()['scenarios'])
        assert all(s['economics']['net_return'] is None for s in risky.json()['scenarios'])
        raw=client.app.state.evidence.raw(saved['input_archive']['sha256']);body=raw.read_bytes()
        try:
            raw.write_bytes(b'corrupt saved threshold input')
            assert client.get('/api/research/successor-threshold-stresses/'+identifier).status_code==409
        finally:raw.write_bytes(body)
        # A real file blocks preparation of a new output directory after START.
        # Only this disposable profile's own diagnostic output is moved.
        output=client.app.state.evidence.directory/'successor-threshold-stress';assert output.is_relative_to(tmp_path)
        backup=output.with_name('successor-threshold-before-failure');output.rename(backup);output.write_text('METHOD output-path conflict',encoding='utf-8')
        try:
            failed_command={**command,'idempotency_key':'filesystem-failure'}
            failed=client.post(route,json=failed_command);assert failed.status_code==409,failed.text
            failed_id=failed.json()['detail']['diagnostic_id']
            failed_run=client.get('/api/research/successor-threshold-stresses/'+failed_id).json()
            assert failed_run['status']=='FAILED' and all(a['status']=='FAILED' for a in failed_run['method_attempts'])
            assert 'scenarios' not in failed_run
            duplicate=client.post(route,json=failed_command)
            assert duplicate.status_code==409 and duplicate.json()['detail']['diagnostic_id']==failed_id
        finally:
            output.unlink();backup.rename(output)
        # Persisted START/dead-host fixture exercises recovery of an abandoned
        # METHOD run; it does not claim an actual process-kill experiment.
        recovery=json.loads(json.dumps(saved));recovery['diagnostic_id']=str(uuid4());recovery['status']='RUNNING';recovery['host_owner']={'pid':0,'creation_ticks':None};recovery.pop('archive')
        recovery['method_attempts']=[{**a,'method_attempt_id':str(uuid4()),'status':'RUNNING'} for a in saved['method_attempts']]
        with client.app.state.ledger.connection() as db:
            db.execute('INSERT INTO research_successor_threshold_runs VALUES(?,?,?,?,?)',(recovery['diagnostic_id'],source['stress_id'],'dead-host','fixture',json.dumps(recovery)))
            for a in recovery['method_attempts']:
                event={**a,'action':'SUCCESSOR_METHOD_THRESHOLD_STARTED','event_id':str(uuid4()),'protocol_id':child['protocol_id']}
                db.execute('INSERT INTO research_events(protocol_id,value) VALUES(?,?)',(child['protocol_id'],json.dumps(event)))
            db.commit()
        # Two initializers read the same stale START before either can close it.
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from roll.research.policy_successors import PolicySuccessors
        from roll.research.successor_shadow import SuccessorShadow
        from roll.research.successor_protocol import SuccessorProtocols
        from roll.research.successor_stress import SuccessorStresses
        from roll.research import successor_threshold
        stresses=SuccessorStresses(SuccessorProtocols(SuccessorShadow(PolicySuccessors(client.app.state.shadow)),client.app.state.validation))
        barrier=Barrier(2);original_alive=successor_threshold.owner_alive
        def synchronized_owner(run):
            if run['diagnostic_id']==recovery['diagnostic_id']:barrier.wait(timeout=10)
            return original_alive(run)
        monkeypatch.setattr(successor_threshold,'owner_alive',synchronized_owner)
        with ThreadPoolExecutor(2) as pool:
            constructors=[pool.submit(successor_threshold.SuccessorThresholdStresses,stresses) for _ in range(2)]
            assert all(job.result(timeout=20) is not None for job in constructors)
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/research/successor-threshold-stresses/'+identifier).json()==saved
        assert client.post('/api/research/successor-threshold-stresses/'+identifier+'/replay').json()['matches_original'] is True
        interrupted=client.get('/api/research/successor-threshold-stresses/'+recovery['diagnostic_id']).json()
        assert interrupted['status']=='ABORTED' and all(a['status']=='INTERRUPTED' for a in interrupted['method_attempts'])
        live=client.get('/api/research/protocols/'+parent['protocol_id']+'/successor-method-attempts').json()
        assert len(live['attempts'])==12 and sum(a['status']=='INTERRUPTED' for a in live['attempts'])==3
        assert sum(a['status']=='FAILED' for a in live['attempts'])==3
        assert client.get('/api/research/protocols/not-a-protocol/successor-method-attempts').status_code==404
        assert client.get('/api/research/protocols/'+child['protocol_id']+'/attempts').json()==original_attempts
