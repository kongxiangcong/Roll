"""Explicit one-resource subplan, sharing the original acquisition ledger caps."""
import hashlib,json,time,sys
from datetime import datetime,timezone
from pathlib import Path
import requests

out=Path(__file__).resolve().parent
plan_path=out/sys.argv[1];plan=json.loads(plan_path.read_bytes())
assert not (out/plan['receipt']).exists()
prior=[json.loads((out/name).read_bytes()) for name in plan['prior_receipts']]
used_calls=sum(len(r['requests']) for r in prior)
used_bytes=sum(r['bytes'] for r in prior)
used_time=sum(r['transfer_seconds'] for r in prior)
assert used_calls<1 and used_bytes<1048576 and used_time<10
receipt={'attempt_id':plan['attempt_id'],'status':'FAILED_CLOSED','started_at':datetime.now(timezone.utc).isoformat(),
         'requests':[],'bytes':0,'transfer_seconds':0.,'prior_calls':used_calls,'prior_bytes':used_bytes,'prior_transfer_seconds':used_time,'retries':0,'redirects':0}
session=requests.Session();tick=time.monotonic()
try:
    item={'url':plan['url']};receipt['requests'].append(item)
    remaining=10-used_time
    with session.get(plan['url'],stream=True,allow_redirects=False,timeout=(min(5,remaining),min(8,remaining)),headers={'User-Agent':'Mozilla/5.0'}) as response:
        item['status_code']=response.status_code;body=bytearray()
        for chunk in response.iter_content(65536):
            body.extend(chunk);receipt['bytes']+=len(chunk)
            if used_bytes+receipt['bytes']>1048576 or len(body)>plan.get('maximum_file_bytes',6291456) or time.monotonic()-tick>remaining:
                raise RuntimeError('SHARED_BYTE_OR_TIME_LIMIT')
        path=out/plan['output'];assert not path.exists();path.write_bytes(body)
        item.update(file=plan['output'],bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
        if response.status_code!=200: raise RuntimeError('HTTP_'+str(response.status_code))
        receipt['status']='CAPTURED_CLOSED'
except Exception as error:
    receipt['error_type']=type(error).__name__;receipt['error_code']=str(error)[:160] if isinstance(error,RuntimeError) else 'TRANSPORT_FAILURE'
finally:
    session.close();receipt['transfer_seconds']=time.monotonic()-tick
    receipt['cumulative']={'requests':used_calls+len(receipt['requests']),'bytes':used_bytes+receipt['bytes'],'transfer_seconds':used_time+receipt['transfer_seconds']}
    (out/plan['receipt']).write_bytes(json.dumps(receipt,ensure_ascii=False,indent=2).encode())
    print(json.dumps(receipt,ensure_ascii=False,indent=2))
    if receipt['status']!='CAPTURED_CLOSED':raise SystemExit(1)
