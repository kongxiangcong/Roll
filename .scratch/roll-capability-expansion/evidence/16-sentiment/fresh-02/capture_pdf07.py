import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import requests
from pypdf import PdfReader

out = Path(__file__).resolve().parent
plan = json.loads((out/'pdf07-plan.json').read_bytes())
folder = out/'source-pdf07'
folder.mkdir(exist_ok=False)
receipt = {'attempt_id':plan['attempt_id'],'started_at':datetime.now(timezone.utc).isoformat(),'status':'FAILED_CLOSED','requests':[],'bytes':0,'retries':0}
started = time.monotonic()
session = requests.Session()
documents = []
try:
    for item in plan['requests']:
        remaining = plan['limits']['maximum_seconds']-(time.monotonic()-started)
        if remaining<=0:
            raise RuntimeError('TIME_LIMIT')
        entry = {**item,'received_at':datetime.now(timezone.utc).isoformat()}
        receipt['requests'].append(entry)
        with session.get(item['url'],headers={'User-Agent':'Mozilla/5.0'},stream=True,allow_redirects=False,timeout=(min(5,remaining),min(5,remaining))) as response:
            entry['status_code'] = response.status_code
            body = bytearray()
            for chunk in response.iter_content(65536):
                receipt['bytes'] += len(chunk)
                if receipt['bytes']>plan['limits']['maximum_bytes'] or time.monotonic()-started>plan['limits']['maximum_seconds']:
                    raise RuntimeError('BYTE_OR_TIME_LIMIT')
                body.extend(chunk)
            path = folder/(item['announcement_id']+'.pdf')
            path.write_bytes(body)
            entry.update(file=path.name,bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
            if response.status_code!=200 or not body.startswith(b'%PDF'):
                raise RuntimeError('PDF_RESPONSE_INVALID')
            pages = [{'page':number+1,'text':page.extract_text() or ''} for number,page in enumerate(PdfReader(path).pages)]
            documents.append({**item,'sha256':entry['sha256'],'pages':pages})
    receipt['status'] = 'CAPTURED_CLOSED'
except Exception as error:
    receipt['error_type'] = type(error).__name__
    if isinstance(error,RuntimeError):
        receipt['error_code'] = str(error)
finally:
    session.close()
    receipt['elapsed_seconds'] = round(time.monotonic()-started,3)
    (out/'pdf07-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'pdf07-text.json').write_text(json.dumps(documents,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))
