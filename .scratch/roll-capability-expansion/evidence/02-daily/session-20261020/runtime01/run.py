import json,socket
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app
out=Path(__file__).resolve().parent;data=Path('.scratch/r02-session-compare01').resolve()
def save(n,v):(out/n).write_bytes(json.dumps(v,ensure_ascii=False,indent=2).encode())
original=socket.socket.connect
def offline(sock,address,*args,**kwargs):
 if address[0] not in {'127.0.0.1','::1'}:raise RuntimeError('EXTERNAL_NETWORK_FORBIDDEN')
 return original(sock,address,*args,**kwargs)
socket.socket.connect=offline
try:
 with TestClient(create_app(data,runtime_role='API')) as c:
  account=c.get('/api/account').json();options=c.get('/api/market/source-authority/daily-options').json();assert len(options)==1
  before=c.get('/api/data/snapshots/'+options[0]['snapshot_id']).json()
  command={'kind':'DAILY_SESSION','snapshot_id':options[0]['snapshot_id'],'idempotency_key':'actual-session-components01'}
  r=c.post('/api/market/source-authority',json=command);save('assessment.json',r.json());assert r.status_code==201,r.text
  value=r.json();assert value['evidence_kind']=='REAL_SAVED_SOURCE_OBSERVATION';assert value['details']['qualified_total_bar'] is None
  rows={r['trade_date']:r for r in value['details']['session_rows']};assert rows['2026-10-19']['two_decimal_presentation_compatible'] and rows['2026-10-20']['two_decimal_presentation_compatible']
  assert rows['2026-10-20']['block_reported_total'] is None and rows['2026-10-20']['block_query_state']=='SOURCE_FAILED_NOT_ZERO'
  assert c.post('/api/market/source-authority',json=command).json()==value
  assert c.get('/api/data/snapshots/'+options[0]['snapshot_id']).json()==before
  assert c.get('/api/market/source-authority',params={'instrument':'SSE:600362','known_by':'2026-10-19T23:59:59+08:00'}).json()==[]
  assert c.get('/api/account').json()==account
 with TestClient(create_app(data,runtime_role='API')) as c:assert c.get('/api/market/source-authority/'+value['assessment_id']).json()==value
 save('summary.json',{'status':'REAL_COMPONENT_DIAGNOSTIC_REPLAYED_NOT_QUALIFIED_DAILY','public_creation':201,'rows':len(rows),'same_day_component_cases':2,'new_source_HTTP':0,'model_calls':0,'fit_calls':0,'account_unchanged':True,'old_daily_snapshot_exact':True,'idempotency_and_restart_exact':True,'past_cutoff_excludes_new_record':True,'all_session_daily_input_allowed':False,'capability':'NOT_GRANTED','data_directory':str(data)})
 print('Actual session API201; bothdatedcases compatible, failureunknown, immutable and restart exact',flush=True)
finally:socket.socket.connect=original
