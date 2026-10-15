"""Zero-network replay of saved SDK entities for the browser METHOD path."""
import json
import os
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app


def app():
    application=create_app(Path(os.environ['ROLL_DATA_DIR']),runtime_role='API')
    source=Path(__file__).resolve().parents[3]/'.scratch/roll-capability-expansion/evidence/09-financial/actual-source'
    async def supplier(instrument,output):
        manifest=json.loads((source/'capture.json').read_text())
        for item in manifest['captures']:(output/item['raw_file']).write_bytes((source/item['raw_file']).read_bytes())
        return manifest
    application.state.financial.worker=supplier
    with TestClient(application) as client:
        version=client.get('/api/market/list').json()['version']
        assert client.post('/api/market/watch',json={'operation':'ADD','instrument':'SSE:600362','expected_list_version':version}).status_code==200
        policy=next(p for p in client.get('/api/research/collection-sources').json() if p['id']=='akshare-financial-em')
        assert client.post('/api/research/collection-sources/akshare-financial-em/policy',json={'enabled':True,'expected_revision':policy['revision'],'basis':'Isolated browser METHOD fixture only'}).status_code==200
    return application
