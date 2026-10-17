import json,os
from pathlib import Path
os.environ['ROLL_DOCLING_PYTHON']=r"D:\dsh-proj\Roll\.scratch\rce-runtime\docling\Scripts\python.exe"
from fastapi.testclient import TestClient
from roll.app import create_app

data=Path(r"D:\dsh-proj\Roll\.scratch\r12real")
out=Path(r"D:\dsh-proj\Roll\.scratch\roll-capability-expansion\evidence\12-docling")
sha="034233ef8b8b392497ed6ad592ca04219eb71c4d4c93aa13a9ed3272e14b2caa"
with TestClient(create_app(data)) as client:
    before=client.get('/api/account').json()['version']
    response=client.post(f'/api/market/financial/documents/{sha}/parses',json={'first_page':102,'last_page':103,'idempotency_key':'real-docling-annual-scan-102-103','basis':'Actual Docling OCR on image-only annual report statement pages 102-103'})
    assert response.status_code==201,response.text
    value=response.json()
    assert value['status']=='COMPLETE',value
    artifact=client.get('/api/data/archives/'+value['artifact']['sha256'])
    assert artifact.status_code==200
    document=json.loads(artifact.content)['document']
    pages=sorted({p['page_no'] for item in document.get('texts',[])+document.get('tables',[]) for p in item['prov']})
    assert pages==[102,103],pages
    after=client.get('/api/account').json()['version']
    summary={'parse_id':value['parse_id'],'status':value['status'],'conversion_status':value.get('conversion_status'),
        'artifact_sha256':value['artifact']['sha256'],'artifact_bytes':value['artifact']['bytes'],'pages':pages,
        'texts':len(document.get('texts',[])),'tables':len(document.get('tables',[])),
        'table_shapes':[(t['data']['num_rows'],t['data']['num_cols'],sorted({p['page_no'] for p in t['prov']})) for t in document.get('tables',[])],
        'warnings':value['warnings'],'account_version_before':before,'account_version_after':after,'network_calls':value['network_calls']}
    (out/'real-api-scanned.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
