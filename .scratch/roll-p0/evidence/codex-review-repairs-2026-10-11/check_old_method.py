"""Version refusal at the public API; only this explicit isolated METHOD profile."""
import hashlib
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from roll.app import create_app

root=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(root/'backend/tests/application'))
from test_validation import prepared

mode=sys.argv[1]
directory=root/'.scratch/old-comparator-method'
evidence=Path(__file__).resolve().parent
with TestClient(create_app(directory)) as client:
    if mode=='prepare':
        frozen,protocol,_=prepared(client,directory)
        response=client.post('/api/research/complete-freezes/'+frozen['freeze_id']+'/validations',json={
            'purpose':'DIAGNOSTIC','expected_complete_protocol_fingerprint':frozen['complete_protocol_fingerprint'],
            'basis':'Original METHOD algorithm archive before the engineering repair'})
        assert response.status_code==201,response.text
        manifest=response.json()
    else:
        metadata=json.loads((evidence/'old-method-identities.json').read_text(encoding='utf-8'))
        frozen=client.get('/api/research/complete-freezes/'+metadata['freeze_id']).json()
        manifest=client.get('/api/research/validations/'+metadata['validation_id']).json()
        protocol=client.get('/api/research/protocols/'+frozen['protocol_id']).json()
        assert hashlib.sha256(json.dumps(frozen,sort_keys=True).encode()).hexdigest()==metadata['frozen_hash']
        assert hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()==metadata['manifest_hash']
    shadow='/api/research/shadow/'+frozen['freeze_id']
    replay=client.post(shadow+'/replay')
    validation_replay=client.post('/api/research/validations/'+manifest['validation_id']+'/replay')
    if mode=='prepare':
        assert replay.json()['matches_original'] is validation_replay.json()['matches_original'] is True
    else:
        assert replay.status_code==validation_replay.status_code==409
    receipt={'freeze_id':frozen['freeze_id'],'validation_id':manifest['validation_id'],
        'frozen_hash':hashlib.sha256(json.dumps(frozen,sort_keys=True).encode()).hexdigest(),
        'manifest_hash':hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest(),
        'shadow_replay_status':replay.status_code,'validation_replay_status':validation_replay.status_code,
        'responses':{'shadow':replay.json(),'validation':validation_replay.json()},
        'actual_account_version':client.get('/api/account').json()['version'],
        'actual_forward_started_at':protocol['forward_started_at'],'evidence_kind':'METHOD_CASE'}
    assert receipt['actual_account_version']==0 and receipt['actual_forward_started_at'] is None
    (evidence/('old-method-identities.json' if mode=='prepare' else 'old-method-refusal.json')).write_text(
        json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False))
