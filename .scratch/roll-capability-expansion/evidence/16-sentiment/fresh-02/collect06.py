"""Remaining new CNINFO requests after05 parser stop; never refetches its page1."""
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import requests
from cninfo_materials import parse_rows

out = Path(__file__).resolve().parent
plan = json.loads((out/'acquisition06-plan.json').read_bytes())
raw_dir = out/'source-06'
raw_dir.mkdir(exist_ok=False)
prior = out/'source-05/01.raw'
prior_body = prior.read_bytes()
rows = parse_rows(json.loads(prior_body)['announcements'],'05-1',hashlib.sha256(prior_body).hexdigest())
started = time.monotonic()
receipt = {'attempt_id':plan['attempt_id'],'status':'FAILED_CLOSED','started_at':datetime.now(timezone.utc).isoformat(),'requests':[],'bytes':0,'retries':0,'redirects':0,
           'prior_raw_reused_readonly':{'path':'source-05/01.raw','sha256':hashlib.sha256(prior_body).hexdigest(),'rows':len(rows)}}
session = requests.Session()
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
            rows.extend(parse_rows(announcements,'06-'+str(number),item['sha256']))
    receipt['status'] = 'CAPTURED_CLOSED'
except Exception as error:
    receipt['error_type'] = type(error).__name__
    if isinstance(error,(RuntimeError,ValueError)):
        receipt['error_code'] = str(error)
finally:
    session.close()
    unique = list({row['id']:row for row in reversed(rows)}.values())
    receipt.update(elapsed_seconds=round(time.monotonic()-started,3),returned_including_prior=len(rows),unique=len(unique))
    (out/'corpus06.json').write_text(json.dumps({'instrument':'SSE:600362','items':unique},ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'acquisition06-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))
