import sys,json,time,hashlib
from pathlib import Path
from datetime import datetime,timezone
import httpx
p=Path(__file__).parent
records=json.loads((p/'requests.json').read_text(encoding='utf-8')) if (p/'requests.json').exists() else []
assert len(records)<16
spent=sum(x['elapsed_seconds'] for x in records); size=sum(x.get('bytes',0) for x in records)
assert spent<150 and size<20*1024*1024
url=sys.argv[1]; ordinal=len(records)+1
r={'ordinal':ordinal,'url':url,'started_at':datetime.now(timezone.utc).isoformat(),'method':'GET','retries':0,'follow_redirects':False}
t=time.monotonic(); body=bytearray()
try:
 with httpx.Client(follow_redirects=False,timeout=min(20,150-spent)) as c:
  with c.stream('GET',url,headers={'Referer':'https://www.sse.com.cn/','User-Agent':'Mozilla/5.0'}) as resp:
   r.update(status=resp.status_code,headers=dict(resp.headers))
   for block in resp.iter_bytes():
    if len(body)+len(block)>20*1024*1024-size: raise ValueError('BYTE_BUDGET_EXCEEDED')
    body.extend(block)
   r['complete']=True
except Exception as e:r.update(error=type(e).__name__+': '+str(e),complete=False)
r.update(ended_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-t,bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),path=f'{ordinal:02}.raw')
(p/r['path']).write_bytes(body);records.append(r);(p/'requests.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(r,ensure_ascii=False)); print(bytes(body[:300]).decode('utf-8',errors='replace'))

