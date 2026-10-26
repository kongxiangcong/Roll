from fastapi.testclient import TestClient
from roll.app import create_app
from test_policy_successors import predecessor,register
from test_successor_shadow import freeze_successor,frame


def test_review_binds_saved_components_and_rejects_mixed_prefixes(tmp_path,monkeypatch):
    from report_method_app import ROOT
    monkeypatch.setenv('ROLL_SKLEARN_PYTHON',str(ROOT/'.scratch/rce-runtime/probability/Scripts/python.exe'))
    monkeypatch.setenv('ROLL_ARCH_PYTHON',str(ROOT/'.scratch/rce-runtime/arch/Scripts/python.exe'))
    with TestClient(create_app(tmp_path)) as client:
        previous=predecessor(client,tmp_path);proposal=register(client,previous).json();frozen=freeze_successor(client,proposal).json()
        parent=client.get('/api/research/protocols/'+previous['protocol_id']).json()
        child=client.post('/api/research/protocols',json={'dataset_id':parent['dataset_id'],'predecessor_id':parent['protocol_id'],'basis':'Saved component review'}).json()
        base='/api/research/policy-successor-freezes/'+frozen['successor_freeze_id']
        protocol=client.post(base+'/complete-protocol',json={'protocol_id':child['protocol_id'],'expected_protocol_fingerprint':child['protocol_fingerprint'],'expected_successor_fingerprint':frozen['successor_fingerprint'],'idempotency_key':'parameters','basis':'Before METHOD components'}).json()
        for day in range(1,4):assert client.post(base+'/shadow/advance',json=frame(day)).status_code==201
        stress=client.post(base+'/cost-stress',json={'expected_complete_protocol_fingerprint':protocol['complete_protocol_fingerprint'],'expected_revision':3,'idempotency_key':'source','basis':'Saved source'}).json()
        component_base='/api/research/successor-cost-stresses/'+stress['stress_id']
        ids={};records={}
        for name,path,key in [('segments','time-segments','segmentation_id'),('cash','cash-control','control_id'),('controls','registered-controls','comparison_id'),('entry','entry-stress','diagnostic_id')]:
            response=client.post(component_base+'/'+path,json={'idempotency_key':name,'basis':'Same source immutable METHOD component'})
            assert response.status_code==201,response.text
            records[name]=response.json();ids[name+'_id']=response.json()[key]
        route=component_base+'/evidence-review';command={**ids,'idempotency_key':'review','basis':'Keep source identity, failures and missing conditions'}
        response=client.post(route,json=command);assert response.status_code==201,response.text
        saved=response.json();identifier=saved['review_id']
        assert saved['bound_components']==['costs','segments','cash','controls','entry']
        assert saved['components']['probability']['bound'] is False
        assert saved['gates']['G3']['status']=='INCONCLUSIVE'
        assert 'PROBABILITY_BINDING_NOT_SELECTED' in saved['gates']['G3']['reasons']
        assert saved['validation_verdict']=='INCONCLUSIVE' and all(g['status']!='PASS' for g in saved['gates'].values())
        assert saved['complete_experiment_frozen'] is False and saved['confirmation_pass_look'] is False
        assert 'REAL_G6_G7' not in saved['complete_freeze_gaps'] and 'REAL_G6_G7' in saved['qualification_gaps']
        # Build the calendar through the existing original METHOD API. These
        # are the fixed test model's saved CAL vectors, not another model's.
        advanced=client.post('/api/research/shadow/'+previous['freeze_id']+'/advance',json={'through_date':parent['design']['windows']['CALIBRATION']['last_date'],'forecast_ids':[],'expected_revision':0})
        assert advanced.status_code==201,advanced.text
        probability=client.post('/api/research/complete-freezes/'+previous['freeze_id']+'/probability-reference',json={'expected_complete_protocol_fingerprint':previous['complete_protocol_fingerprint'],'idempotency_key':'prob','basis':'Current fixed METHOD model saved CAL only'})
        assert probability.status_code==201,probability.text
        blocks=client.post('/api/research/probability-references/'+probability.json()['reference_id']+'/block-reference',json={'idempotency_key':'blocks','basis':'Same saved current METHOD CAL calendar'})
        assert blocks.status_code==201,blocks.text
        binding=client.post(base+'/probability-evidence',json={'expected_complete_protocol_fingerprint':protocol['complete_protocol_fingerprint'],'probability_reference_id':probability.json()['reference_id'],'block_reference_id':blocks.json()['reference_id'],'idempotency_key':'bind','basis':'Same frozen model CAL is not independent support'})
        assert binding.status_code==201,binding.text
        with_cal=client.post(route,json={**command,'probability_id':binding.json()['binding_id'],'idempotency_key':'with-cal'})
        assert with_cal.status_code==201,with_cal.text
        cal=with_cal.json()['components']['probability']
        assert cal['bound'] is True and cal['calendar_join_with_execution'] is False
        assert cal['phases']==binding.json()['phases'] and cal['independent_calibration_validation'] is False
        assert 'CALIBRATION_FIT_WINDOW_REUSED' in with_cal.json()['gates']['G3']['reasons']
        cal_review=with_cal.json()
        assert client.post(route,json=command).json()==saved and client.get(route).json()==[saved,cal_review]
        assert client.get('/api/account').json()['version']==0
        # Later source cannot claim older entry/segment records as its own.
        assert client.post(base+'/shadow/advance',json=frame(4)).status_code==201
        next_source=client.post(base+'/cost-stress',json={'expected_complete_protocol_fingerprint':protocol['complete_protocol_fingerprint'],'expected_revision':4,'idempotency_key':'later','basis':'Later source'}).json()
        wrong=client.post('/api/research/successor-cost-stresses/'+next_source['stress_id']+'/evidence-review',json=command)
        assert wrong.status_code==409 and 'COMPONENT_PREFIX_MISMATCH' in wrong.text
        # Missing siblings remain explicit; later observed hard risk survives.
        adverse=frame(5);adverse['bars'][0].update(open_yuan='200.00',high_yuan='200.00',low_yuan='200.00',close_yuan='200.00',reference_close_yuan='200.00')
        assert client.post(base+'/shadow/advance',json=adverse).status_code==201
        risk_source=client.post(base+'/cost-stress',json={'expected_complete_protocol_fingerprint':protocol['complete_protocol_fingerprint'],'expected_revision':5,'idempotency_key':'risk','basis':'Observed exposure risk'}).json()
        risk_base='/api/research/successor-cost-stresses/'+risk_source['stress_id']
        risk_cash=client.post(risk_base+'/cash-control',json={'idempotency_key':'risk-cash','basis':'Observed absolute exposure'}).json()
        failed=client.post(risk_base+'/evidence-review',json={'cash_id':risk_cash['control_id'],'idempotency_key':'failed','basis':'Keep known hard FAIL'})
        assert failed.status_code==201,failed.text
        assert failed.json()['gates']['G4']['status']=='FAIL' and failed.json()['validation_verdict']=='FAIL'
        assert client.post('/api/research/successor-evidence-reviews/'+identifier+'/replay').json()['matches_original'] is True
        assert client.post('/api/research/successor-evidence-reviews/'+cal_review['review_id']+'/replay').json()['matches_original'] is True
        # Integrity is nested: losing a selected child original blocks the review.
        archive=records['entry']['input_archive'];raw=next(tmp_path.rglob(archive['sha256']+'.raw'))
        original=raw.read_bytes()
        try:
            raw.write_bytes(b'{}')
            assert client.get('/api/research/successor-evidence-reviews/'+identifier).status_code==409
        finally:raw.write_bytes(original)
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/research/successor-evidence-reviews/'+identifier).json()==saved
        assert client.post('/api/research/successor-evidence-reviews/'+identifier+'/replay').json()['matches_original'] is True
