import json,os
from pathlib import Path
os.environ['ROLL_SENTIMENT_PYTHON']=r"D:\dsh-proj\Roll\.scratch\rce-runtime\docling\Scripts\python.exe"
from fastapi.testclient import TestClient
from roll.app import create_app
with TestClient(create_app(Path(r"D:\dsh-proj\Roll\.scratch\r16-takeover-20261018"))) as client:
    historical=client.get('/api/market/sentiment/runs/d77051ee-4cac-42cb-ad34-ce06575aa9ad').json()
    before=client.get('/api/account').json()['version']
    response=client.post('/api/market/sentiment/SSE:600362/classify',json={'idempotency_key':'takeover-20261018-corrected-metrics','basis':'Actual limited sentiment on archived 10 news facts'})
    assert response.status_code==201,response.text
    value=response.json()
    assert client.get('/api/market/sentiment/runs/d77051ee-4cac-42cb-ad34-ce06575aa9ad').json()==historical
    assert value['reference']['evaluation']['combined']['negative_recall']==0.2
    assert value['reference']['evaluation']['combined']['per_class']['NEGATIVE']['support']==30
    summary={'run_id':value['run_id'],'status':value['status'],'evidence_kind':value['evidence_kind'],'counts':value['counts'],
        'reject_counts':value.get('reject_counts'),'coverage':value['coverage'],'model':value['reference']['model'],
        'weights_sha256':value['reference']['weights_sha256'],'network_calls':value['network_calls'],'historical_run_unchanged':True,'evaluation':value['reference']['evaluation'],
        'account_before':before,'account_after':client.get('/api/account').json()['version'],
        'facts':[{'title':row['title'],'label':row['label'],'reject':row['reject_reason'],'confidence':row['confidence'],'association':row['association']} for row in value['facts']]}
    (Path(r"D:\dsh-proj\Roll\.scratch\roll-capability-expansion\evidence\16-sentiment")/'takeover-20261018'/'real-sentiment-corrected.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
