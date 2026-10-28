"""Two bounded GETs of issuer disclosures; no model, credentials or advice."""
import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import httpx

out=Path(__file__).parent
store=Path('D:/dsh-proj/Roll/.scratch/rv12-real01')
rawdir=store/'acceptance-source'
rawdir.mkdir(exist_ok=True)
cid='54abcc3d-67c2-453e-83b4-8fdc92b7a292'
sources=[dict(name='annual2025',url='https://static.cninfo.com.cn/finalpage/2026-04-28/1225208968.PDF',period_start='2025-01-01',period_end='2025-12-31',disclosed_at='2026-04-28T00:00:00+08:00'),
 dict(name='halfyear2026',url='https://disc.static.szse.cn/disc/disk03/finalpage/2026-08-15/32efb525-6244-462e-9b50-90739f771ddc.PDF',period_start='2026-01-01',period_end='2026-06-30',disclosed_at='2026-08-15T00:00:00+08:00')]
receipts=[]
with httpx.Client(timeout=35,follow_redirects=True,trust_env=False) as external, httpx.Client(base_url='http://127.0.0.1:8032',timeout=90,trust_env=False) as local:
    existing=local.get(f'/api/company-research/companies/{cid}/materials').json()['materials']
    for source in sources:
        receipt=dict(source,started_at=datetime.now(timezone.utc).isoformat())
        try:
            response=external.get(source['url'])
            receipt.update(http_status=response.status_code,final_url=str(response.url))
            response.raise_for_status()
            content=response.content
            if len(content)>12*1024*1024 or not content.startswith(b'%PDF-'):
                raise ValueError('Not bounded PDF bytes')
            digest=hashlib.sha256(content).hexdigest()
            (rawdir/(source['name']+'.pdf')).write_bytes(content)
            matches=[m['material_id'] for m in existing if m['archive']['sha256']==digest]
            receipt.update(status='SUCCESS',bytes=len(content),sha256=digest,previous_matching_material_ids=matches,
                           import_status='NOT_IMPORTED_PENDING_DOCUMENT_IDENTITY_REVIEW',source_kind='ISSUER_DISCLOSURE_HOSTED_BY_EXCHANGE_OR_CNINFO')
        except Exception as error:
            receipt.update(status='FAILED',error_type=type(error).__name__,error=str(error)[:300])
        receipt['finished_at']=datetime.now(timezone.utc).isoformat()
        receipts.append(receipt)
(out/'primary-acquisition.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(receipts,ensure_ascii=False))
