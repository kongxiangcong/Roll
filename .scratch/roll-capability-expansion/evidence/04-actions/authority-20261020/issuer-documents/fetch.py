import sys,json,time,hashlib,asyncio
from pathlib import Path
from datetime import datetime,timezone
import httpx
out=Path(__file__).resolve().parent
plan=json.loads((out/'acquisition-plan.json').read_bytes())
rpath=out/'acquisition-receipt.json'
receipt=json.loads(rpath.read_bytes()) if rpath.exists() else {'attempt_id':plan['attempt_id'],'requests':[],'bytes':0,'transfer_seconds':0,'evidence_kind':'REAL_PUBLIC_SOURCE_DOCUMENT','closed_historical_budgets_not_reopened':True}
async def main():
 for url in sys.argv[1:]:
  assert url.startswith(('https://www.sse.com.cn/','https://query.sse.com.cn/','https://static.sse.com.cn/','https://static.cninfo.com.cn/','https://www.hkexnews.hk/'))
  assert len(receipt['requests'])<plan['maximum_requests'] and receipt['transfer_seconds']<plan['maximum_transfer_seconds'] and receipt['bytes']<plan['maximum_bytes']
  rec={'number':len(receipt['requests'])+1,'url':url,'started_at':datetime.now(timezone.utc).isoformat(),'complete':False};receipt['requests'].append(rec);body=bytearray();tick=time.monotonic()
  (out/f"request-{rec['number']:02}.json").write_bytes(json.dumps({'url':url,'method':'GET','retries':0,'plan_sha256':hashlib.sha256((out/'acquisition-plan.json').read_bytes()).hexdigest()},indent=2).encode())
  async def get():
   async with httpx.AsyncClient(timeout=15,follow_redirects=False) as client:
    async with client.stream('GET',url,headers={'Referer':'https://www.sse.com.cn/','User-Agent':'Mozilla/5.0'}) as response:
     rec.update(status=response.status_code,headers=dict(response.headers))
     async for part in response.aiter_bytes():
      remaining=plan['maximum_bytes']-receipt['bytes'];body.extend(part[:remaining]);receipt['bytes']+=min(len(part),remaining)
      if len(part)>remaining:raise ValueError('BYTE_BUDGET')
     rec['complete']=True
  try:await asyncio.wait_for(get(),min(15,plan['maximum_transfer_seconds']-receipt['transfer_seconds']))
  except Exception as e:rec['error']=type(e).__name__
  finally:
   elapsed=time.monotonic()-tick;receipt['transfer_seconds']+=elapsed;rec.update(transfer_seconds=elapsed,received_at=datetime.now(timezone.utc).isoformat(),sha256=hashlib.sha256(body).hexdigest(),bytes=len(body),path=f"{rec['number']:02}.raw")
   (out/rec['path']).write_bytes(body);rpath.write_bytes(json.dumps(receipt,ensure_ascii=False,indent=2).encode());print(json.dumps({k:v for k,v in rec.items() if k!='headers'}),flush=True)
asyncio.run(main())
