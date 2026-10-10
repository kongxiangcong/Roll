"""One real bounded technical review per configured provider, over identical frozen materials."""
import json
import hashlib
import os
from pathlib import Path
import time
from fastapi.testclient import TestClient
from roll.app import create_app

ROOT=Path(__file__).resolve().parents[4]
PROFILE=ROOT/'.roll-data/implementation-evidence/23/actual-current-copy'
OUT=ROOT/'.roll-data/implementation-evidence/23/actual-provider-results'
APPROVAL=ROOT/'.roll-data/implementation-evidence/23/provider-approval'
OUT.mkdir(parents=True,exist_ok=True)
VALIDATION='baf981b6-b2bf-4f6f-b46f-1726f261de8e'
os.environ['ROLL_ENV_FILE']=str(ROOT/'.env')
manifest=json.loads((APPROVAL/'provider-material-manifest.json').read_text(encoding='utf-8'))
assert manifest['material_fingerprint']=='35e42b0da239e415e2b7e3f3f0c9243d4e32a3e3bc02ceac92a92b17559ac9da'
for row in manifest['files']:
    raw=(APPROVAL/'provider-materials'/Path(row['path']).name).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==row.get('tool_response_sha256',row.get('sha256'))
    assert len(raw)==row.get('tool_response_bytes',row.get('bytes'))
records=[]
with TestClient(create_app(PROFILE)) as client:
    original=client.get('/api/research/validations/'+VALIDATION);original.raise_for_status();original=original.json()
    before={'account':client.get('/api/account').json(),'attempts':client.get('/api/research/protocols/'+original['protocol_id']+'/attempt-manifest').json(),
        'audit':client.get('/api/research/protocols/'+original['protocol_id']+'/audit').json(),'protocol':client.get('/api/research/protocols/'+original['protocol_id']).json()}
    response=client.get('/api/research/review-materials/'+manifest['material_id']);response.raise_for_status();material=response.json()
    assert material['material_fingerprint']==manifest['material_fingerprint']
    existing=client.get('/api/research/review-materials/'+material['material_id']+'/reviews');existing.raise_for_status()
    assert not existing.json(),'Already attempted: do not automatically repeat actual provider calls'
    for backend in ['CODEX','DEEPSEEK']:
        settings=client.get('/api/agents/settings').json()
        if settings['backend']!=backend:
            client.post('/api/agents/settings',json={'expected_version':settings['version'],'backend':backend}).raise_for_status()
        started=client.post('/api/research/review-materials/'+material['material_id']+'/reviews',json={'expected_material_fingerprint':material['material_fingerprint']})
        started.raise_for_status();identifier=started.json()['run_id']
        deadline=time.monotonic()+140
        while time.monotonic()<deadline:
            run=client.get('/api/research/technical-reviews/'+identifier);run.raise_for_status();run=run.json()
            if run['status']!='RUNNING':break
            time.sleep(.2)
        else:raise RuntimeError('Review exceeded bounded host termination margin')
        records.append(run)
        (OUT/('actual-'+backend.lower()+'.json')).write_text(json.dumps(run,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'backend':backend,'run_id':identifier,'status':run['status'],'resolved_model':run['resolved_model'],'error':run.get('error'),'material_fingerprint':run['material_fingerprint']},ensure_ascii=False),flush=True)
    delivery=client.get('/api/research/review-materials/'+material['material_id']+'/delivery').json()
    exported=client.post('/api/research/review-materials/'+material['material_id']+'/export',json={});exported.raise_for_status()
    after={'account':client.get('/api/account').json(),'attempts':client.get('/api/research/protocols/'+original['protocol_id']+'/attempt-manifest').json(),
        'audit':client.get('/api/research/protocols/'+original['protocol_id']+'/audit').json(),'protocol':client.get('/api/research/protocols/'+original['protocol_id']).json()}
    assert before==after,'Review changed account, fit manifest, SEALED access or forward protocol'
    assert original==client.get('/api/research/validations/'+VALIDATION).json(),'Review rewrote historical validation'
    assert len({r['material_fingerprint'] for r in records})==1
    assert delivery['preliminary'] and delivery['capability_status']=='NOT_GRANTED'
    report={'validation_id':VALIDATION,'material_id':material['material_id'],'material_fingerprint':material['material_fingerprint'],
        'inventory_bytes':sum(i['bytes'] for i in material['inventory']),'delivery':delivery,'export':exported.json(),
        'same_material_both_providers':True,'account_attempts_sealed_forward_unchanged':True,'historical_validation_unchanged':True,
        'original_runtime_started':False,'fits_or_sealed_consumed':False}
    (OUT/'actual-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
