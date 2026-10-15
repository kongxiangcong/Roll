"""Compare saved CAL vectors through the real pinned sklearn runtime."""
from fastapi.testclient import TestClient
from roll.app import create_app
from report_method_app import copy_donor,FREEZE,ROOT


def test_probability_reference_reads_saved_calibration_without_new_fit(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test')
    monkeypatch.setenv('ROLL_SKLEARN_PYTHON',str(ROOT/'.scratch/rce-runtime/probability/Scripts/python.exe'))
    with TestClient(create_app(copy_donor(tmp_path/'data'),runtime_role='API')) as client:
        frozen=client.get('/api/research/complete-freezes/'+FREEZE).json()
        model=client.get('/api/research/models/'+frozen['model_run_id']).json()
        attempts=client.get('/api/research/protocols/'+frozen['protocol_id']+'/attempts').json()
        base='/api/research/complete-freezes/'+FREEZE+'/probability-reference'
        command={'expected_complete_protocol_fingerprint':frozen['complete_protocol_fingerprint'],'idempotency_key':'probability-once','basis':'METHOD compare only archived CAL vectors; no fit or new validation'}
        response=client.post(base,json=command)
        assert response.status_code==201,response.text
        result=response.json()
        assert result['library']['version']=='1.9.1'
        assert result['capability']=='NOT_GRANTED' and result['statistical_assumptions_verified'] is False
        assert result['new_fit_calls']==0 and result['sealed_reads']==0 and result['network_calls']==0
        assert set(result['phases'])=={'BEFORE_CALIBRATION','AFTER_CALIBRATION'}
        for phase in result['phases'].values():
            assert phase['status']=='NUMERICALLY_CONSISTENT',phase
            assert phase['mature_unique']>0
            assert phase['absolute_tolerance']==1e-12
            assert phase['independent_calibration_validation'] is False
        assert client.post(base,json=command).json()==result
        assert client.get(base).json()==[result]
        assert client.get('/api/research/models/'+frozen['model_run_id']).json()==model
        assert client.get('/api/research/protocols/'+frozen['protocol_id']+'/attempts').json()==attempts
        identifier=result['reference_id']
        # A relabelled database pointer cannot substitute another vector for
        # the original model-freeze archive, even when the model ID is unchanged.
        import json
        swapped={**model,'calibrated_prediction_archive':model['calibration_prediction_archive']}
        with client.app.state.ledger.connection() as db:
            db.execute('UPDATE research_models SET value=? WHERE id=?',(json.dumps(swapped),model['model_run_id']));db.commit()
        denied=client.post(base,json={**command,'idempotency_key':'swapped-vector'})
        assert denied.status_code==409 and 'BINDING' in str(denied.json()),denied.text
        with client.app.state.ledger.connection() as db:
            db.execute('UPDATE research_models SET value=? WHERE id=?',(json.dumps(model),model['model_run_id']));db.commit()
    monkeypatch.delenv('ROLL_SKLEARN_PYTHON')
    with TestClient(create_app(tmp_path/'data',runtime_role='API')) as client:
        assert client.get('/api/research/probability-references/'+identifier).json()==result
        assert client.post('/api/research/probability-references/'+identifier+'/replay').json()['matches_original'] is True
