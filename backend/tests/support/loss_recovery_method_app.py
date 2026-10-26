"""Isolated browser seed: an explicit METHOD LOSS pause and qualified successor."""
import os,sys
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app


def app():
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'application'))
    from capability_method_app import save_package
    from test_capability_monitoring import monitored_package
    from test_loss_recovery import prepared_loss
    directory=Path(os.environ['ROLL_DATA_DIR']);p=monitored_package()
    p['action_packet']['loss_facts']={**p['loss_facts'],'facts_version':'method-loss6000','net_assets':'94000.10','realized_pnl':'-6000.00'}
    file=save_package(directory/'qualification.json',p);application=create_app(directory,capability_method_file=file,runtime_role='API')
    with TestClient(application) as client:prepared_loss(client,p)
    return application
