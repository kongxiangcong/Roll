from fastapi.testclient import TestClient
from roll.app import create_app
from report_method_app import copy_donor,FREEZE,ROOT


def test_saved_block_reference_preserves_calendar_and_replays(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test')
    monkeypatch.setenv('ROLL_SKLEARN_PYTHON',str(ROOT/'.scratch/rce-runtime/probability/Scripts/python.exe'))
    monkeypatch.setenv('ROLL_ARCH_PYTHON',str(ROOT/'.scratch/rce-runtime/arch/Scripts/python.exe'))
    with TestClient(create_app(copy_donor(tmp_path/'data'),runtime_role='API')) as client:
        frozen=client.get('/api/research/complete-freezes/'+FREEZE).json()
        probability=client.post('/api/research/complete-freezes/'+FREEZE+'/probability-reference',json={
            'expected_complete_protocol_fingerprint':frozen['complete_protocol_fingerprint'],'idempotency_key':'block-source','basis':'METHOD source reuse'}).json()
        base='/api/research/probability-references/'+probability['reference_id']+'/block-reference'
        command={'idempotency_key':'block-once','basis':'METHOD verify paired date groups; source gaps remain unknown'}
        response=client.post(base,json=command)
        assert response.status_code==201,response.text
        result=response.json();identifier=result['reference_id']
        assert result['library']['version']=='8.0.0'
        assert result['new_fit_calls']==result['sealed_reads']==result['network_calls']==0
        assert result['assumptions_verified'] is False and result['capability']=='NOT_GRANTED'
        source=[c for name,c in result['cases'].items() if name.startswith('SOURCE:')]
        assert len(source)==8
        assert all(c['calendar_sessions']==40 and c['status']=='INCOMPLETE_ALIGNED_CALENDAR_SCORES' for c in source)
        method=[c for name,c in result['cases'].items() if name.startswith('METHOD:')]
        assert len(method)==6 and all(c['status']=='NUMERICALLY_CONSISTENT' for c in method),method
        assert all(c['same_indices_max_statistic_error']<=1e-12 for c in method)
        assert client.post(base,json=command).json()==result
        assert client.get(base).json()==[result]
        assert client.get('/api/research/probability-references/'+probability['reference_id']).json()==probability
    monkeypatch.delenv('ROLL_ARCH_PYTHON');monkeypatch.delenv('ROLL_SKLEARN_PYTHON')
    with TestClient(create_app(tmp_path/'data',runtime_role='API')) as client:
        assert client.get('/api/research/block-references/'+identifier).json()==result
        assert client.post('/api/research/block-references/'+identifier+'/replay').json()=={'matches_original':True,'recomputed':False,'new_fit_calls':0,'sealed_reads':0}
