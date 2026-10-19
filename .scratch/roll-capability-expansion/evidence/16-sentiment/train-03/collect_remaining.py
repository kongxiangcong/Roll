"""Final13 requests in original32 cap; exact historical queries frozen first."""
import hashlib,json,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
import requests
from object_contract import clean
from cninfo_materials import parse_rows

out=Path(__file__).resolve().parent
plan=json.loads((out/'remaining-plan.json').read_bytes())
priors=[json.loads((out/n).read_bytes()) for n in plan['prior_receipts']]
used_calls=sum(len(x['requests']) for x in priors);used_bytes=sum(x['bytes'] for x in priors);used_time=sum(x['transfer_seconds'] for x in priors)
assert used_calls==19
raw=out/'source-remaining';raw.mkdir(exist_ok=False)
receipt={'attempt_id':plan['attempt_id'],'status':'FAILED_CLOSED','started_at':datetime.now(timezone.utc).isoformat(),
         'requests':[],'bytes':0,'transfer_seconds':0.,'retries':0,'redirects':0}
session=requests.Session();rows=[]
def capture(command):
    assert used_calls+len(receipt['requests'])<32
    remaining=120-used_time-receipt['transfer_seconds']
    if remaining<=0:raise RuntimeError('SHARED_TIME_LIMIT')
    item={'number':used_calls+len(receipt['requests'])+1,'command':command,'at':datetime.now(timezone.utc).isoformat()}
    receipt['requests'].append(item);tick=time.monotonic()
    try:
        form=command.get('form')
        with session.request('POST' if form else 'GET',command['url'],params=command.get('params'),data=form,
                             headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/' if form else 'https://search.sina.com.cn/'},
                             stream=True,allow_redirects=False,timeout=(min(5,remaining),min(8,remaining))) as response:
            item['status_code']=response.status_code;body=bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk);receipt['bytes']+=len(chunk)
                if used_bytes+receipt['bytes']>16777216 or time.monotonic()-tick>remaining:raise RuntimeError('SHARED_BYTE_OR_TIME_LIMIT')
            path=raw/f"{item['number']:02}.raw";path.write_bytes(body);item.update(file=path.name,sha256=hashlib.sha256(body).hexdigest(),bytes=len(body))
            if response.status_code!=200:raise RuntimeError('HTTP_'+str(response.status_code))
            data=json.loads(body)
            if form:
                values=parse_rows(data.get('announcements') or [],str(item['number']),item['sha256'])
                # A different page at known valid30 must not be represented as a new page if identical.
                prior_digest=command['invalid50_page1_sha256']
                item['same_as_invalid50_page1']=item['sha256']==prior_digest
                if item['same_as_invalid50_page1']:raise RuntimeError('PAGINATION_STILL_NOT_DISTINCT')
                rows.extend(values);item['returned']=len(values)
            else:
                if data.get('code')!=0:raise RuntimeError('PUBLIC_SEARCH_CODE_ERROR_STOP_NO_LOGIN_OR_VERIFICATION')
                values=data['data']['list'];item.update(returned=len(values),declared_total=data['data'].get('total'),reported_size=data['data'].get('size'))
                for ordinal,row in enumerate(values):
                    date=row.get('dataTime') or row.get('time')
                    if not date or not command['minimum_date']<=date[:10]<=command['maximum_date']:raise RuntimeError('HISTORICAL_DATE_FILTER_MISMATCH')
                    rows.append({'id':f"S{item['number']}-{ordinal:02}",'request':item['number'],'row':ordinal,'raw_sha256':item['sha256'],
                                 'title':clean(row.get('title')),'summary':clean(row.get('intro') or row.get('searchSummary')),
                                 'date':date,'url':row['url'],'media':row.get('media_show'),'reported_source':row.get('source'),
                                 'date_basis':'SINA_SEARCH_REPORTED_PUBLICATION_NOT_HISTORICAL_PIT','planned_period':command['period']})
    finally:
        elapsed=time.monotonic()-tick;receipt['transfer_seconds']+=elapsed;item['transfer_seconds']=elapsed
try:
    for command in plan['commands']:capture(command)
    receipt['status']='CAPTURED_CLOSED'
except Exception as error:
    receipt.update(error_type=type(error).__name__,error_code=str(error)[:200] if isinstance(error,(RuntimeError,ValueError)) else 'TRANSPORT_OR_PARSE_FAILURE')
finally:
    session.close();receipt['cumulative']={'requests':used_calls+len(receipt['requests']),'bytes':used_bytes+receipt['bytes'],'transfer_seconds':used_time+receipt['transfer_seconds']}
    receipt['returned']=len(rows)
    (out/'remaining-corpus.json').write_bytes(json.dumps({'items':rows},ensure_ascii=False,indent=2).encode())
    (out/'remaining-receipt.json').write_bytes(json.dumps(receipt,ensure_ascii=False,indent=2).encode())
    print(json.dumps(receipt,ensure_ascii=False,indent=2))
    if receipt['status']!='CAPTURED_CLOSED':raise SystemExit(1)
