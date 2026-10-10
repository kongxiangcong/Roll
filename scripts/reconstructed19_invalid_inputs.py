"""Host rejection using a damaged private copy of this run's real public response."""
import hashlib,json,os
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'.scratch/roll-p0/evidence/19-reconstruction-2026-10-10';DATA=OUT/'negative-real-integrity'
def main():
    os.environ['ROLL_ENV']='test';original=OUT/'status-collection/daily.wire';before=hashlib.sha256(original.read_bytes()).hexdigest()
    app=create_app(DATA)
    with TestClient(app) as client:
        archive=app.state.evidence.archive(original.read_bytes(),'REAL_PUBLIC_RESPONSE_PRIVATE_NEGATIVE_COPY',evidence_kind='REAL_ACQUISITION')
        assert client.get('/api/data/archives/'+archive['sha256']).status_code==200
        path=app.state.evidence.raw(archive['sha256']);path.write_bytes(path.read_bytes()+b'\nintentional private negative-test damage')
        refused=client.get('/api/data/archives/'+archive['sha256']);assert refused.status_code==409
        trust=client.post('/api/research/datasets/invalid/reconstruct',json={'status_run_id':'invalid','basis':'client cannot grant trust','trusted':True});assert trust.status_code==422
        assert hashlib.sha256(original.read_bytes()).hexdigest()==before
        result={'real_original_sha256':before,'original_unchanged':True,'damaged_private_copy_rejected':refused.status_code,'client_trust_flag_rejected':trust.status_code,'real_model_or_account_modified':False}
        (OUT/'negative-real-integrity.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()
