from uuid import uuid4
from fastapi.testclient import TestClient
from roll.app import create_app
from test_policy_successors import predecessor,register
from test_successor_shadow import freeze_successor,frame
from report_method_app import ROOT


def test_complete_method_binding_inventory_keeps_real_freeze_and_later_gates_separate(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_SKLEARN_PYTHON',str(ROOT/'.scratch/rce-runtime/probability/Scripts/python.exe'))
    monkeypatch.setenv('ROLL_ARCH_PYTHON',str(ROOT/'.scratch/rce-runtime/arch/Scripts/python.exe'))
    with TestClient(create_app(tmp_path)) as client:
        previous=predecessor(client,tmp_path);proposal=register(client,previous).json();frozen=freeze_successor(client,proposal).json()
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
        assert saved['diagnostic_package_complete'] is True and saved['bound_diagnostic_count']==9
        assert saved['engineering_complete'] is False and saved['complete_experiment_frozen'] is False
        assert saved['complete_freeze_admission']['status']=='NOT_ADMITTED'
        assert 'REAL_G6_G7' not in saved['complete_freeze_admission']['reasons'] and 'REAL_G6_G7' in saved['qualification_gaps']
        assert saved['validation_verdict']=='INCONCLUSIVE' and saved['capability']=='NOT_GRANTED'
        assert client.post(check_route,json=check_command).json()==saved and client.get(check_route).json()==[saved]
        assert client.get('/api/account').json()['version']==0 and client.get(base+'/complete-protocol').json()==protocol
        # Only immutable terminal threshold records may become parents.
        import copy,json
        pending=copy.deepcopy(records['threshold']);pending['diagnostic_id']=str(uuid4());pending['status']='RUNNING';pending.pop('archive')
        with client.app.state.ledger.connection() as db:db.execute('INSERT INTO research_successor_threshold_runs VALUES(?,?,?,?,?)',(pending['diagnostic_id'],source['stress_id'],'pending-fixture','fixture',json.dumps(pending)))
        try:
            refused=client.post(check_route,json={**check_command,'idempotency_key':'pending-parent','threshold_id':pending['diagnostic_id']})
            assert refused.status_code==409 and 'TERMINAL_THRESHOLD_RECORD' in refused.text
        finally:
            with client.app.state.ledger.connection() as db:db.execute('DELETE FROM research_successor_threshold_runs WHERE id=?',(pending['diagnostic_id'],))
        # Direct METHOD aggregation fixture checks that completed engineering
        # bindings cannot erase a known negative candidate outcome.
        from roll.research.successor_completion import derive
        inputs=json.loads(client.app.state.evidence.raw(saved['input_archive']['sha256']).read_text(encoding='utf-8'));negative=copy.deepcopy(inputs);negative['threshold']['G5_status']='FAIL'
        assert derive(negative)['validation_verdict']=='FAIL' and derive(negative)['gates']['G5']['status']=='FAIL'
        # An unclosed family METHOD START blocks readiness, even with all nine
        # selected component outputs. This is a lifecycle fixture, not a fit.
        from roll.research.successor_threshold import START,INTERRUPT
        method_id=str(uuid4());client.app.state.research.event(child['protocol_id'],START,method_attempt_id=method_id,category='THRESHOLD',partition=None,data_scope='METHOD_DECLARED_SLOTS',status='RUNNING')
        running=client.post(check_route,json={**check_command,'idempotency_key':'running'}).json()
        assert running['diagnostic_package_complete'] is False and 'FAMILY_METHOD_ATTEMPT_RUNNING' in running['diagnostic_binding_gaps']
        client.app.state.research.event(child['protocol_id'],INTERRUPT,method_attempt_id=method_id,status='INTERRUPTED',reason='Explicit METHOD lifecycle fixture closed')
        assert client.get('/api/research/successor-completion-checks/'+running['check_id']).json()==running
        assert client.get('/api/research/protocols/'+child['protocol_id']+'/attempts').json()==attempts
        assert client.post(path+'/replay').json()['matches_original'] is True
        assert client.post(base+'/shadow/advance',json=frame(4)).status_code==201
        later_source=client.post(base+'/cost-stress',json={**command,'idempotency_key':'later','expected_complete_protocol_fingerprint':protocol['complete_protocol_fingerprint'],'expected_revision':4}).json()
        later_audit=client.post('/api/research/successor-cost-stresses/'+later_source['stress_id']+'/migration-audit',json=command).json()
        assert client.post(check_route,json={**check_command,'idempotency_key':'mixed','migration_id':later_audit['audit_id']}).status_code==409
        raw=client.app.state.evidence.raw(records['threshold']['input_archive']['sha256']);body=raw.read_bytes()
        try:
            raw.write_bytes(b'corrupt selected threshold input')
            assert client.get(path).status_code==409 and client.post(path+'/replay').status_code==409
        finally:raw.write_bytes(body)
    monkeypatch.delenv('ROLL_SKLEARN_PYTHON');monkeypatch.delenv('ROLL_ARCH_PYTHON')
    with TestClient(create_app(tmp_path)) as client:
        assert client.get(path).json()==saved and client.post(path+'/replay').json()['matches_original'] is True
