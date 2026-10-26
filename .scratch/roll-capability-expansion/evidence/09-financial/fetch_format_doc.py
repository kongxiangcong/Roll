import hashlib,json,time
from pathlib import Path
from datetime import datetime,timezone
import httpx
root=Path(__file__).parent
plan=json.loads((root/'format-doc-plan.json').read_text())
receipt=root/'format-doc-receipt.json'
if receipt.exists():raise SystemExit('Documentation budget already consumed')
receipt.write_text(json.dumps({'state':'CLAIMED','plan':plan}),encoding='utf-8')
body=bytearray();status=None;complete=False;error=None
try:
    with httpx.Client(timeout=18,follow_redirects=False,trust_env=False) as client:
        with client.stream('GET',plan['source_url']) as response:
            status=response.status_code
            for part in response.iter_bytes():
                available=plan['max_bytes']-len(body);body.extend(part[:available])
                if len(part)>available:raise ValueError('DOCUMENT_BYTE_LIMIT_PREFIX')
            complete=True
except Exception as e:error=type(e).__name__
(root/'formatData.raw').write_bytes(body)
value={'status_code':status,'complete':complete,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),
    'received_at':datetime.now(timezone.utc).isoformat(),'error':error,'calls':1,'plan':plan,'state':'CLOSED_NO_RETRY'}
receipt.write_text(json.dumps(value,indent=2),encoding='utf-8');print(json.dumps(value))
