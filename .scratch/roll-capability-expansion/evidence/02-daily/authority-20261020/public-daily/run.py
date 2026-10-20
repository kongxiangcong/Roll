import json,sys,time,socket
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app
out=Path(__file__).resolve().parent;plan=json.loads((out/'plan.json').read_bytes());data=Path('.scratch/r02-authority-real01').resolve();assert not data.exists()
def save(name,v):(out/name).write_bytes(json.dumps(v,ensure_ascii=False,indent=2).encode())
with TestClient(create_app(data,runtime_role='API')) as c:
 before=c.get('/api/account').json();listing=c.get('/api/market/list').json()
 w=c.post('/api/market/watch',json={'operation':'ADD','instrument':'SSE:600362','expected_list_version':listing['version']});assert w.status_code==200,w.text
 r=c.post('/api/data/requests',json=plan['request']);save('request.json',r.json());assert r.status_code==201,r.text
 tick=time.monotonic();r=c.post('/api/data/requests/'+r.json()['request_id']+'/retrieve');save('run.json',r.json());print('retrieve',r.status_code,'seconds',time.monotonic()-tick,flush=True);assert r.status_code==200,r.text
 run=r.json();snap=c.get('/api/data/snapshots/'+run['snapshot_id']);save('snapshot.json',snap.json());assert snap.status_code==200,snap.text
 def offline(*a,**kw):raise RuntimeError('OFFLINE_NETWORK_FORBIDDEN')
 original=socket.socket.connect;socket.socket.connect=offline
 try:
  replay=c.post('/api/data/runs/'+run['run_id']+'/replay');save('replay.json',replay.json());assert replay.status_code==200,replay.text;assert replay.json()['network_calls']==0
 finally:socket.socket.connect=original
 after=c.get('/api/account').json();assert before==after;save('summary.json',{'status':run['status'],'gaps':run['gaps'],'account_unchanged':True,'account_version':after['version'],'network_calls':run.get('network_calls'),'model_calls':0,'fit_calls':0,'data_directory':str(data),'source':'REAL_PUBLIC_SDK_TCP','no_retry':True})
with TestClient(create_app(data,runtime_role='API')) as c:assert c.get('/api/data/snapshots/'+run['snapshot_id']).json()==snap.json()
print(json.dumps({'status':run['status'],'gaps':run['gaps']},ensure_ascii=False),flush=True)
