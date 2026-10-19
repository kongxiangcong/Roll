"""Bounded issuer disclosure index acquisition; raw-first, no model calls."""
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
import requests
from object_contract import clean

out = Path(__file__).resolve().parent
plan = json.loads((out/'acquisition05-plan.json').read_bytes())
raw_dir = out/'source-05'
raw_dir.mkdir(exist_ok=False)
started = time.monotonic()
receipt = {'attempt_id':plan['attempt_id'],'status':'FAILED_CLOSED','started_at':datetime.now(timezone.utc).isoformat(),'requests':[],'bytes':0,'retries':0,'redirects':0}
session = requests.Session()
rows = []
try:
    for number,query in enumerate(plan['queries'],1):
        remaining = plan['limits']['maximum_seconds']-(time.monotonic()-started)
        if remaining<=0:
            raise RuntimeError('TIME_LIMIT')
        form = {**plan['identity'],'seDate':plan['interval'],'searchkey':query['keyword'],'sortName':'time','sortType':'asc','pageNum':str(query['page']),'pageSize':str(plan['page_size'])}
        item = {'number':number,'request_form':form,'received_at':datetime.now(timezone.utc).isoformat()}
        receipt['requests'].append(item)
        with session.post(plan['url'],data=form,headers={'Referer':'https://www.cninfo.com.cn/','User-Agent':'Mozilla/5.0'},stream=True,allow_redirects=False,timeout=(min(5,remaining),min(5,remaining))) as response:
            item['status_code'] = response.status_code
            body = bytearray()
            for chunk in response.iter_content(65536):
                receipt['bytes'] += len(chunk)
                if receipt['bytes']>plan['limits']['maximum_bytes'] or time.monotonic()-started>plan['limits']['maximum_seconds']:
                    raise RuntimeError('BYTE_OR_TIME_LIMIT')
                body.extend(chunk)
            path = raw_dir/f'{number:02}.raw'
            path.write_bytes(body)
            item.update(file=path.name,sha256=hashlib.sha256(body).hexdigest(),bytes=len(body))
            if response.status_code!=200:
                raise RuntimeError('HTTP_'+str(response.status_code))
            data = json.loads(body)
            announcements = data.get('announcements') or []
            item.update(returned=len(announcements),declared_total=data.get('totalAnnouncement'),has_more=data.get('hasMore'))
            for ordinal,row in enumerate(announcements):
                if (row.get('secCode'),row.get('orgId'),row.get('secName'))!=('600362','gssh0600362','江西铜业'):
                    raise RuntimeError('ISSUER_IDENTITY_MISMATCH')
                source_path = row.get('adjunctUrl') or ''
                match = re.fullmatch(r'finalpage/(\d{4}-\d{2}-\d{2})/(\d+)\.PDF',source_path,re.I)
                if not match or match[2]!=row['announcementId']:
                    raise RuntimeError('PDF_LOCATOR_IDENTITY_MISMATCH')
                original = clean(row['announcementTitle'])
                title = original if '江西铜业' in original else '江西铜业：'+original
                rows.append({'id':'05-'+row['announcementId'],'request':number,'row':ordinal,'raw_sha256':item['sha256'],
                             'title':title,'original_title':original,'summary':'','date':match[1],
                             'date_basis':'DISCLOSURE_PDF_PATH_DATE_NOT_HISTORICAL_PIT','url':'https://static.cninfo.com.cn/'+source_path,
                             'media':'CNINFO issuer disclosure index','announcement_id':row['announcementId'],'reported_associate':row.get('associateAnnouncement')})
    receipt['status'] = 'CAPTURED_CLOSED'
except Exception as error:
    receipt['error_type'] = type(error).__name__
    if isinstance(error,RuntimeError):
        receipt['error_code'] = str(error)
finally:
    session.close()
    unique = list({row['id']:row for row in reversed(rows)}.values())
    receipt.update(elapsed_seconds=round(time.monotonic()-started,3),returned=len(rows),unique=len(unique))
    (out/'corpus05.json').write_text(json.dumps({'instrument':'SSE:600362','items':unique},ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'acquisition05-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))
