"""Evaluate new admission with current host GET metadata; never POST to legacy host."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import sys
import httpx
from fastapi import HTTPException

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'backend/src'))
from roll.research.training_preflight import admit_model_training

OUT=Path(__file__).resolve().parent
PID='a9792e33-98e1-464e-85ba-046623fb4bd1'

class MetadataAdapter:
    def __init__(self,client):
        self.client=client
        self.requests=[]

    def fetch(self,path):
        response=self.client.get('http://127.0.0.1:8010'+path)
        response.raise_for_status()
        self.requests.append({'method':'GET','path':path,'status':response.status_code,
                              'sha256':hashlib.sha256(response.content).hexdigest(),'bytes':len(response.content)})
        return response.json()

    def get(self,pid):
        return self.fetch('/api/research/protocols/'+pid)

    def dataset(self,did):
        return self.fetch('/api/research/datasets/'+did)

    def attempt_manifest(self,pid):
        return self.fetch('/api/research/protocols/'+pid+'/attempt-manifest')

with httpx.Client(timeout=10) as client:
    adapter=MetadataAdapter(client)
    before=adapter.attempt_manifest(PID)
    reports=[]
    for _ in range(2):
        try:
            admit_model_training(adapter,PID,'RESEARCH')
            raise AssertionError('Actual unqualified source must be rejected')
        except HTTPException as error:
            assert error.status_code==409
            reports.append(error.detail)
    after=adapter.attempt_manifest(PID)
assert before==after and reports[0]==reports[1]
assert reports[0]['budget']['primary_and_neighbors']['remaining']==3
assert reports[0]['budget']['calibration']['remaining']==1
initial=json.loads((OUT/'initial-state.json').read_bytes())
assert initial['attempt_manifest']==after
module=ROOT/'backend/src/roll/research/training_preflight.py'
report={'checked_at':datetime.now(timezone.utc).isoformat(),'protocol_id':PID,
        'transport':'LOCAL_ADMISSION_FUNCTION_WITH_LIVE_HOST_METADATA_GET_ADAPTER',
        'production_route_deployed_or_posted':False,'requests':adapter.requests,
        'admission':reports[0],'repeated_equal':True,'attempt_manifest_unchanged':True,
        'unchanged_since_initial_snapshot':True,'actual_source_integrity_checked':False,
        'sealed_read':False,'labels_read_or_computed':False,'fits':0,
        'function_sha256':hashlib.sha256(module.read_bytes()).hexdigest()}
(OUT/'live-admission-metadata.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:report[k] for k in ['repeated_equal','attempt_manifest_unchanged','unchanged_since_initial_snapshot','sealed_read','fits']}))
