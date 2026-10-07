import os,sys,json
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,r'D:\dsh-proj\Roll\backend\src')
from fastapi.testclient import TestClient
from roll.app import create_app
root=Path(r'D:\dsh-proj\Roll\backend\.roll-data')/('review-spec-'+uuid4().hex[:8])
with TestClient(create_app(root)) as first:
    p=first.post('/api/research/protocols',json={'basis':'Read-only review directed public case'}).json()
    pid=p['protocol_id']
    a=first.post('/api/research/protocols/'+pid+'/attempts',json={'category':'ENGINEERING_REPLAY','partition':'DEVELOPMENT','configuration':{},'basis':'Live host original attempt'}).json()
    before=first.get('/api/research/protocols/'+pid+'/attempts').json()
    with TestClient(create_app(root)) as second:
        after=first.get('/api/research/protocols/'+pid+'/attempts').json()
        finished=first.post('/api/research/attempts/'+a['attempt_id']+'/finish',json={'status':'SUCCEEDED','reason':'Original live host now finishes'})
        result={'case':'Peer application startup while original host remains alive','root':str(root),'before_status':before[0]['status'],'after_status':after[0]['status'],'finish_status':finished.status_code,'finish_body':finished.json()}
Path(r'C:\Users\72449\.codex\visualizations\2026\10\07\01a116b0-7a64-7d10-8659-68853d73dbfe\roll-spec-review-peer.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
