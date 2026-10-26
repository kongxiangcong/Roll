import json,os
from pathlib import Path
os.environ['ROLL_DOCLING_PYTHON']=r"D:\dsh-proj\Roll\.scratch\rce-runtime\docling\Scripts\python.exe"
from fastapi.testclient import TestClient
from roll.app import create_app
sha="b373067f9e97b9cdf6d712b76f65f6f2898486a19b32f371faa456849629ce71"
with TestClient(create_app(Path(r"D:\dsh-proj\Roll\.scratch\r13real"))) as client:
    response=client.post(f'/api/market/financial/documents/{sha}/parses',json={'first_page':10,'last_page':10,'idempotency_key':'observation-docling-link2','basis':'Actual Docling parse linked to financial observation'})
    assert response.status_code==201,response.text
    value=response.json();assert value['status'] in ('COMPLETE','PARTIAL'),value
    observation=client.get('/api/market/financial/SSE:600362/observations').json()['current']
    doc=next(item for item in observation['documents'] if item['sha256']==sha)
    assert doc['parses'],doc
    summary={'parse_id':value['parse_id'],'parse_status':value['status'],'artifact_sha256':value['artifact']['sha256'],
        'observation_id':observation['observation_id'],'observation_version':observation['observation_version'],
        'gap_reasons':[gap['reason'] for gap in observation['gaps']],'documents':[{'sha256':d['sha256'],'parses':[p['status'] for p in d['parses']]} for d in observation['documents']],
        'account_version':client.get('/api/account').json()['version'],'network_calls':observation['network_calls']}
    (Path(r"D:\dsh-proj\Roll\.scratch\roll-capability-expansion\evidence\13-observation")/'real-observation.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
