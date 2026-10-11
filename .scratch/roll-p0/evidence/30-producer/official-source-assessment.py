"""One anonymous fixed SSE format assessment; no application/profile/forward writes."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import httpx

output=Path(__file__).parent/'runtime/source-assessment'
output.mkdir(parents=True,exist_ok=True)
url='http://yunhq.sse.com.cn:32041/v1/sh1/list/exchange/equity'
parameters={'select':'code,name,open,high,low,last,volume,amount,prev_close','begin':'0','end':'6000'}
receipt={'namespace':'SOURCE_ASSESSMENT','forward_started_at':None,'credentials_used':False,
    'attempts':1,'actual_started_at':datetime.now(timezone.utc).isoformat(),'url':url,'parameters':parameters,
    'unit_scope':'UNVERIFIED','current_status_actions_complete':False}
try:
    with httpx.Client(timeout=15,follow_redirects=False) as client:
        with client.stream('GET',url,params=parameters,headers={'Referer':'https://www.sse.com.cn/'}) as response:
            body=bytearray()
            for part in response.iter_bytes():
                body.extend(part)
                if len(body)>8*1024*1024:raise ValueError('DECODED_BYTE_LIMIT')
            sha=hashlib.sha256(body).hexdigest()
            (output/(sha+'.raw')).write_bytes(body)
            receipt.update(http_status=response.status_code,bytes=len(body),sha256=sha,
                content_type=response.headers.get('content-type'))
            try:
                payload=json.loads(body)
                matches=[r for r in payload.get('list',[]) if isinstance(r,list) and r and r[0]=='600362']
                receipt.update(source_date=payload.get('date'),source_time=payload.get('time'),
                    matched_rows=len(matches),field_count=len(matches[0]) if matches else None,
                    response_kind='JSON_BODY_NOT_COMPLETENESS_PROOF')
            except (ValueError,AttributeError):receipt['response_kind']='NON_JSON_OR_UNKNOWN_SCHEMA'
except (httpx.HTTPError,ValueError) as error:
    receipt.update(error_type=type(error).__name__,response_kind='ACQUISITION_FAILED')
receipt['actual_finished_at']=datetime.now(timezone.utc).isoformat()
(output/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(receipt,ensure_ascii=False))
