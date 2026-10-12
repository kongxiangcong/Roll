"""Copy only the newly owned actual profile; offline public consumer proof in fresh copy."""
import hashlib
import json
import shutil
from datetime import datetime,timezone
from pathlib import Path
import httpx
from fastapi.testclient import TestClient
from roll.app import create_app
from roll.market.sse_company_actions import fingerprint as collector_fingerprint
from roll.market.sse_action_assessments import fingerprint

folder=Path(__file__).resolve().parent;repo=folder.parents[3]
summary=json.loads((folder/'actual-assessment-summary.json').read_bytes())
closure_body=(folder/'actual-budget-closure.json').read_bytes();closure=json.loads(closure_body)
assert closure['state']=='CLOSED_NO_MORE_ATTEMPTS' and closure['actual_attempts']==2
assert collector_fingerprint()=='63505424914969f9e1bd65237df93c886e163d01d0facb8cd2ca6754ce2eeb20'
origin=repo/'.scratch/t30a-actual';destination=repo/'.scratch/t30a-actual-consumer'
assert origin.is_dir() and not destination.exists()
def inventory(directory):
    result={}
    for file in directory.rglob('*'):
        assert not file.is_symlink() and not file.is_junction()
        if file.is_file():
            body=file.read_bytes();result[file.relative_to(directory).as_posix()]={'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body)}
    return result
before=inventory(origin)
shutil.copytree(origin,destination)
assert inventory(destination)==before
calls=[]
def forbidden(request):
    calls.append(str(request.url));raise AssertionError('Offline proof must not send external HTTP')
with TestClient(create_app(destination,market_transport=httpx.MockTransport(forbidden),runtime_role='API')) as client:
    base='/api/research/collections/'+summary['collection_plan_id']
    raw=client.get(base+'/sse-company-action-receipts').json()[0]
    assert raw['receipt_id']==summary['receipt_id'] and raw['evidence_kind']=='REAL_SOURCE_ASSESSMENT'
    response=client.post(base+'/sse-action-assessments',json={'source_receipt_id':raw['receipt_id'],
        'basis':'Explicit offline assessment of saved real first-page originals, no live HTTP'})
    assert response.status_code==201,response.text
    assessment=response.json()
    original=client.post(base+'/post-close-packets',json={'basis':'Original packet before explicit saved-raw action consumer'}).json()
    response=client.post(base+'/sse-action-packets',json={'source_receipt_id':raw['receipt_id'],
        'assessment_ids':[assessment['assessment_id']],'predecessor_packet_id':original['packet_id'],
        'basis':'Fixed real raw ID and offline assessment ID, partial action consumer only'})
    assert response.status_code==201,response.text
    packet=response.json()
    assert len(packet['action_candidates'])==5 and packet['assessment_ids']==[assessment['assessment_id']]
    assert not packet['complete_action_coverage'] and not packet['pending_older_obligations_complete']
    assert not packet['forward_admissible'] and not packet['system_usable']
    replay=client.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay').json()
    assert replay['matches_original'] and replay['network_calls']==0
    assert client.get(base+'/sse-company-action-receipts').json()==[raw]
    assert client.get(base+'/source-gaps').json()['action_assessments']==[assessment]
    assert client.get('/api/actions/current?instrument=SSE:600362').json()['decisions']==[]
    assert not calls
assert inventory(origin)==before and (folder/'actual-budget-closure.json').read_bytes()==closure_body
proof={'finished_host_at':datetime.now(timezone.utc).isoformat(),'source_profile':str(origin),
    'fresh_copy':str(destination),'actual_attempts_before_and_after':2,'consumer_external_http_attempts':0,
    'collector_fingerprint':collector_fingerprint(),'assessment_fingerprint':fingerprint(),
    'original_actual_profile_bytewise_unchanged':True,'source_profile_inventory':before,
    'copied_files_before_open':len(before),'budget_closure_unchanged':True,
    'source_receipt_id':raw['receipt_id'],'assessment':assessment,'original_packet_id':original['packet_id'],
    'successor_packet':packet,'replay':replay,'new_source_slice_attempts':0,
    'original_or_prior_preserved_sqlite_opened':False,'system_usable':False,'capability':'NOT_GRANTED'}
(folder/'offline-real-raw-consumer-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({key:proof[key] for key in ['copied_files_before_open','consumer_external_http_attempts',
    'original_actual_profile_bytewise_unchanged','assessment_fingerprint','actual_attempts_before_and_after']}))
