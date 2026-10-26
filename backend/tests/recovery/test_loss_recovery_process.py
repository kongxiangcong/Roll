import json,os,subprocess,sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from roll.app import create_app
from capability_method_app import save_package
from test_capability_monitoring import monitored_package
from test_loss_recovery import prepared_loss

CHILD="""
import json,sys
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app
with TestClient(create_app(Path(sys.argv[1]),capability_method_file=Path(sys.argv[2]))) as client:
    result=client.post(sys.argv[3],json=json.loads(sys.argv[4]))
    print(result.status_code,result.text)
"""

@pytest.mark.parametrize('point,committed',[('loss_recovery_before_commit',False),('loss_recovery_after_commit',True)])
def test_loss_recovery_actual_process_exit_preserves_atomic_ack_and_permission_history(tmp_path,monkeypatch,point,committed):
    monkeypatch.setenv('ROLL_ENV','test')
    p=monitored_package();p['action_packet']['loss_facts']={**p['loss_facts'],'facts_version':'method-loss6000','net_assets':'94000.10','realized_pnl':'-6000.00'}
    file=save_package(tmp_path/'qualification.json',p);directory=tmp_path/'data'
    with TestClient(create_app(directory,capability_method_file=file)) as client:
        original,decline,pause,successor,command=prepared_loss(client,p)
        checked=client.post('/api/funding/loss-recovery/checks',json=command).json();assert checked['status']=='READY',checked
    backend=Path(__file__).resolve().parents[2]
    env={**os.environ,'ROLL_ENV':'test','ROLL_TEST_CRASH_POINT':point,'PYTHONPATH':os.pathsep.join(str(backend/p) for p in ('src','tests/support','tests/application'))}
    route='/api/funding/loss-recovery/checks/'+checked['check_id']+'/activate'
    activate={'idempotency_key':'crash-activation','acknowledge_preserved_peak':True,'basis':'Explicit isolated process-exit recovery test'}
    process=subprocess.run([sys.executable,'-X','utf8','-B','-c',CHILD,str(directory),str(file),route,json.dumps(activate)],env=env,capture_output=True,text=True,timeout=40)
    assert process.returncode==86,process.stdout+process.stderr
    with TestClient(create_app(directory,capability_method_file=file)) as client:
        receipts=client.get('/api/funding/loss-recovery/receipts').json()
        assert len(receipts)==int(committed)
        assert ('loss_recovery' in client.get('/api/funding').json())==committed
        assert client.get('/api/capabilities/grants/'+original['grant_id']+'/status').json()['state']=='REVOKED'
        if committed:
            retry=client.post(route,json=activate)
            assert retry.status_code==201 and retry.json()==receipts[0]
            assert client.get('/api/capabilities/lifecycle').json()['new_risk_allowed'] is True
        else:
            assert client.get('/api/capabilities/lifecycle').json()['new_risk_allowed'] is False
            assert client.get('/api/capabilities/recovery').json()['state']=='RECOVERY_LOCK'
