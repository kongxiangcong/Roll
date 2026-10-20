import hashlib, json, time
from datetime import datetime, timezone
from pathlib import Path
import httpx

root=Path(__file__).resolve().parent
plan=json.loads((root/'plan.json').read_text(encoding='utf-8'))
if (root/'capture-manifest.json').exists(): raise SystemExit('CLOSED: no implicit retry')
start=time.monotonic(); total=0; records=[]
with httpx.Client(timeout=15,follow_redirects=False,headers={'Referer':'https://www.sse.com.cn/','User-Agent':'Roll bounded public-source research'}) as client:
    for index,url in enumerate(plan['fixed_requests']):
        if index>=12 or time.monotonic()-start>=120 or total>=16777216: break
        entry={'url':url,'started_at':datetime.now(timezone.utc).isoformat(),'request_headers':dict(client.headers),'original_complete':False}
        body=bytearray()
        try:
            with client.stream('GET',url) as response:
                entry.update(status_code=response.status_code,headers=dict(response.headers))
                for part in response.iter_bytes():
                    remaining=16777216-total
                    body.extend(part[:remaining]);total+=min(len(part),remaining)
                    if len(part)>remaining: raise ValueError('TOTAL_BYTE_LIMIT')
                    if time.monotonic()-start>=120: raise ValueError('WALL_LIMIT')
                entry['original_complete']=True
        except Exception as exc: entry['error']=type(exc).__name__+': '+str(exc)
        digest=hashlib.sha256(body).hexdigest(); name=f'{index+1:02d}-{digest}.raw'
        (root/name).write_bytes(body)
        entry.update(received_at=datetime.now(timezone.utc).isoformat(),bytes=len(body),sha256=digest,path=name)
        records.append(entry)
        (root/'capture-progress.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
manifest={'state':'CLOSED_NO_RETRY','requests':len(records),'bytes':total,'elapsed_seconds':time.monotonic()-start,'records':records,'evidence_kind':'REAL_PUBLIC_SOURCE_RESEARCH_NOT_MODEL_ELIGIBLE'}
(root/'capture-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in manifest.items() if k!='records'},ensure_ascii=False))
