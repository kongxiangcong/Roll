import sys,json
from pathlib import Path
from uuid import uuid4
sys.path[:0]=[r'D:\dsh-proj\Roll\backend\src',r'D:\dsh-proj\Roll\backend\tests\application']
from fastapi.testclient import TestClient
from roll.app import create_app
from test_research_protocol import engineering_archive
root=Path(r'D:\dsh-proj\Roll\backend\.roll-data')/('review-family-'+uuid4().hex[:8])
engineering_archive(root)
with TestClient(create_app(root)) as client:
    ds=client.post('/api/research/datasets',json={'archive_id':'method-181','basis':'Explicit METHOD fixed archive for directed review'}).json()
    base=client.post('/api/research/protocols',json={'dataset_id':ds['dataset_id'],'basis':'Base overlapping family'}).json()
    sibling1=client.post('/api/research/protocols',json={'dataset_id':ds['dataset_id'],'predecessor_id':base['protocol_id'],'basis':'First successor'}).json()
    command={'category':'PRIMARY_FIT','partition':'DEVELOPMENT','configuration':{'candidate':'PRICE_VOLUME_LOGIT_V1'},'basis':'Finite failed method attempt'}
    for i in range(5):
        a=client.post('/api/research/protocols/'+sibling1['protocol_id']+'/attempts',json=command)
        a.raise_for_status()
        client.post('/api/research/attempts/'+a.json()['attempt_id']+'/finish',json={'status':'FAILED','reason':'Explicit failed method case, no model fitted'}).raise_for_status()
    sixth=client.post('/api/research/protocols/'+sibling1['protocol_id']+'/attempts',json=command)
    sibling2_response=client.post('/api/research/protocols',json={'dataset_id':ds['dataset_id'],'predecessor_id':base['protocol_id'],'basis':'Branch from older common parent after exhausted first successor'})
    sibling2_response.raise_for_status();sibling2=sibling2_response.json()
    bypass=client.post('/api/research/protocols/'+sibling2['protocol_id']+'/attempts',json=command)
    manifest=client.get('/api/research/protocols/'+sibling2['protocol_id']+'/attempt-manifest').json()
    result={'root':str(root),'first_successor_sixth_status':sixth.status_code,'second_successor_registered':sibling2_response.status_code,'second_successor_extra_fit_status':bypass.status_code,'manifest_count':len(manifest['attempts']),'manifest_lineage':manifest['lineage'],'omitted_first_successor_id':sibling1['protocol_id']}
    if bypass.status_code==201:client.post('/api/research/attempts/'+bypass.json()['attempt_id']+'/finish',json={'status':'ABORTED','reason':'Directed review completed, no computation performed'}).raise_for_status()
Path(r'C:\Users\72449\.codex\visualizations\2026\10\07\01a116b0-7a64-7d10-8659-68853d73dbfe\roll-spec-review-family.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
