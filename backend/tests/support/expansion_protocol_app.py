"""Public-API METHOD seed for the successor protocol browser path."""
import os
import sys
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app


def app():
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'application'))
    from test_policy_successors import predecessor,register
    from test_successor_shadow import freeze_successor
    directory=Path(os.environ['ROLL_DATA_DIR'])
    application=create_app(directory,runtime_role='API')
    with TestClient(application) as client:
        previous=predecessor(client,directory)
        proposal=register(client,previous).json()
        assert freeze_successor(client,proposal).status_code==201
        parent=client.get('/api/research/protocols/'+previous['protocol_id']).json()
        assert client.post('/api/research/protocols',json={'dataset_id':parent['dataset_id'],'predecessor_id':parent['protocol_id'],
            'basis':'Browser METHOD linked successor before frames'}).status_code==201
    return application
