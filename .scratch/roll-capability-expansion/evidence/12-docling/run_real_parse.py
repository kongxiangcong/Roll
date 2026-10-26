import json,os,sys
from pathlib import Path
os.environ['ROLL_DOCLING_PYTHON']=r"D:\dsh-proj\Roll\.scratch\rce-runtime\docling\Scripts\python.exe"
from fastapi.testclient import TestClient
from roll.app import create_app

data=Path(r"D:\dsh-proj\Roll\.scratch\r12real")
out=Path(r"D:\dsh-proj\Roll\.scratch\roll-capability-expansion\evidence\12-docling")
sha="b373067f9e97b9cdf6d712b76f65f6f2898486a19b32f371faa456849629ce71"
with TestClient(create_app(data)) as client:
    before=client.get('/api/account').json()['version']
    listing=client.get(f'/api/market/financial/documents/{sha}/parses').json()
    assert listing['source_sha256']==sha
    response=client.post(f'/api/market/financial/documents/{sha}/parses',json={'first_page':10,'last_page':10,'idempotency_key':'real-docling-q3-p10d','basis':'Actual Docling 2.139.0 runtime on archived 2025 Q3 PDF page 10'})
    assert response.status_code==201,response.text
    value=response.json()
    assert value['status'] in ('COMPLETE','PARTIAL'),value
    artifact=client.get('/api/data/archives/'+value['artifact']['sha256'])
    assert artifact.status_code==200 and len(artifact.content)>1000
    document=json.loads(artifact.content)['document']
    pages=sorted({p['page_no'] for item in document.get('texts',[])+document.get('tables',[]) for p in item['prov']})
    assert pages==[10],pages
    original=client.get('/api/data/archives/'+sha)
    assert original.status_code==200 and original.content.startswith(b'%PDF')
    after=client.get('/api/account').json()['version']
    summary={'prior_parse_statuses':[p['status'] for p in listing['parses']],'parse_id':value['parse_id'],'status':value['status'],'conversion_status':value.get('conversion_status'),
        'parser_version':value['parser_version'],'artifact_sha256':value['artifact']['sha256'],'artifact_bytes':value['artifact']['bytes'],
        'pages':pages,'texts':len(document.get('texts',[])),'tables':len(document.get('tables',[])),
        'table_shapes':[(t['data']['num_rows'],t['data']['num_cols']) for t in document.get('tables',[])],
        'warnings':value['warnings'],'account_version_before':before,'account_version_after':after,
        'network_calls':value['network_calls'],'system_usable':value['system_usable']}
    (out/'real-api-parse.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
