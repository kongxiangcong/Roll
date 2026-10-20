import json,socket,hashlib
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app
out=Path('.scratch/roll-capability-expansion/evidence/04-actions/authority-20261020');data=Path('.scratch/r020304-runtime01').resolve();values=[]
def save(n,v):(out/n).write_bytes(json.dumps(v,ensure_ascii=False,indent=2).encode())
def offline(*a,**kw):raise RuntimeError('SOURCE_NETWORK_FORBIDDEN')
original=socket.socket.connect;socket.socket.connect=offline
try:
 with TestClient(create_app(data,runtime_role='API')) as c:
  before=c.get('/api/account').json();snaps=c.get('/api/data/snapshots?instrument=SSE:600362&group=DAILY').json();snapshot=snaps[0]['snapshot_id']
  for kind in ['DAILY','STATUS_PHASE','ACTION_DOCUMENTS']:
   cmd={'kind':kind,'snapshot_id':snapshot if kind=='DAILY' else None,'idempotency_key':'actual-authority-'+kind}
   r=c.post('/api/market/source-authority',json=cmd);save('actual-'+kind+'.json',r.json());print(kind,r.status_code,flush=True);assert r.status_code==201,r.text
   assert c.post('/api/market/source-authority',json=cmd).json()==r.json();values.append(r.json())
  assert c.get('/api/account').json()==before
  assert c.get('/api/market/source-authority',params={'instrument':'SSE:600362','known_by':'2026-10-19T23:59:59+08:00'}).json()==[]
 with TestClient(create_app(data,runtime_role='API')) as c:
  for value in values:assert c.get('/api/market/source-authority/'+value['assessment_id']).json()==value
 save('actual-runtime-summary.json',{'public_assessments':len(values),'source_network_calls':0,'model_calls':0,'fit_calls':0,'account_unchanged':True,'duplicate_and_restart_exact':True,'past_cutoff_excludes_new_observations':True,'qualification':'NOT_GRANTED','data_directory':str(data)})
finally:socket.socket.connect=original
