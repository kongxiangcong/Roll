import asyncio,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
import httpx
root=Path(__file__).parent
plan=json.loads((root/'document-plan.json').read_text())
receipt=root/'document-receipt.json'
if receipt.exists():raise SystemExit('Fixed documentation attempt is already consumed')
state={'plan':plan,'documents':[],'state':'CLAIMED_NO_RETRY'};used=0
def save():receipt.write_text(json.dumps(state,indent=2),encoding='utf-8')
save()
async def fetch():
    global used
    async with httpx.AsyncClient(timeout=18,follow_redirects=False,trust_env=False) as client:
        for spec in plan['documents']:
            item={**spec,'complete':False,'status_code':None};state['documents'].append(item);save();body=bytearray()
            try:
                async with client.stream('GET',spec['url']) as response:
                    item['status_code']=response.status_code
                    async for part in response.aiter_bytes():
                        available=plan['max_total_bytes']-used;body.extend(part[:available]);used+=min(len(part),available)
                        if len(part)>available:raise ValueError('DOCUMENT_TOTAL_BYTE_BUDGET_PREFIX')
                    item['complete']=True
            finally:
                filename=spec['id']+'.pdf';(root/filename).write_bytes(body)
                item.update(filename=filename,sha256=hashlib.sha256(body).hexdigest(),bytes=len(body),received_at=datetime.now(timezone.utc).isoformat())
                save()
try:asyncio.run(asyncio.wait_for(fetch(),timeout=plan['total_timeout_seconds']))
except Exception as error:state['error']=type(error).__name__
state['state']='CLOSED_NO_RETRY';save()
print(json.dumps({'documents':[{k:v for k,v in d.items() if k!='url'} for d in state['documents']],'error':state.get('error')}))
