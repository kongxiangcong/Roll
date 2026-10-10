"""One anonymous read-only status request, not a WorkBuddy task or Wind query."""
from pathlib import Path
from datetime import datetime, timezone
from hashlib import sha256
import json
import httpx

out = Path(__file__).resolve().parent
url = 'https://www.workbuddy.cn/openapi/v2/localassistant'
report = {'test':'ANONYMOUS_OFFICIAL_OPENAPI_STATUS_PROBE', 'checked_at':datetime.now(timezone.utc).isoformat(),
          'method':'GET', 'url':url, 'authorization_sent':False, 'message_posted':False,
          'wind_query_executed':False, 'fits':0, 'sealed_read':False}
try:
    with httpx.Client(timeout=15, follow_redirects=False) as client:
        response=client.get(url,headers={'Accept':'application/json'})
    raw=response.content
    path=out/'workbuddy-openapi-anonymous-response.raw'
    path.write_bytes(raw)
    report.update({'http_status':response.status_code,'body_sha256':sha256(raw).hexdigest(),
                   'body_bytes':len(raw),'response_file':path.name})
except httpx.HTTPError as error:
    report.update({'http_status':None,'error_type':type(error).__name__})
(out/'workbuddy-openapi-probe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
