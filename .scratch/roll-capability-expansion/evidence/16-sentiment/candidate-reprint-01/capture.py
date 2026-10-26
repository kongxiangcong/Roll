import json,hashlib,time
from pathlib import Path
from datetime import datetime,timezone
import requests
p=Path(__file__).resolve().parent;plan=json.loads((p/'plan.json').read_bytes());started=time.monotonic()
r={'status':'FAILED_CLOSED','requests':[],'bytes':0,'retries':0,'redirects':0,'started_at':datetime.now(timezone.utc).isoformat()}
s=requests.Session()
try:
 for i,url in enumerate(plan['urls'],1):
  assert i<=2;remaining=20-(time.monotonic()-started);assert remaining>0
  item={'url':url};r['requests'].append(item)
  with s.get(url,headers={'User-Agent':'Mozilla/5.0'},stream=True,allow_redirects=False,timeout=(min(5,remaining),min(5,remaining))) as response:
   item['http_status']=response.status_code;body=bytearray()
   for chunk in response.iter_content(65536):
    body.extend(chunk);r['bytes']+=len(chunk)
    if r['bytes']>2097152 or time.monotonic()-started>20:raise RuntimeError('BYTE_OR_TIME_LIMIT')
   f=p/f'{i:02}.html';f.write_bytes(body);item.update(file=f.name,bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
   if response.status_code!=200:raise RuntimeError('HTTP_'+str(response.status_code))
 r['status']='CAPTURED_CLOSED'
except Exception as error:r['error_type']=type(error).__name__;r['error_code']=str(error)[:100] if isinstance(error,RuntimeError) else 'TRANSPORT_FAILURE'
finally:
 s.close();r['elapsed_seconds']=time.monotonic()-started;(p/'receipt.json').write_bytes(json.dumps(r,ensure_ascii=False,indent=2).encode());print(json.dumps(r,ensure_ascii=False,indent=2))
