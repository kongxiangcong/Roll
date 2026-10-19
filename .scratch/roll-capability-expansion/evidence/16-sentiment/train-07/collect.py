"""Autonomous bounded16 distinct training-only page2 queries, one-shot source acquisition only."""
import hashlib,json,time
from datetime import datetime,timezone,timedelta
from pathlib import Path
import requests
from object_contract import clean

out=Path(__file__).resolve().parent
plan=json.loads((out/'acquisition-plan.json').read_bytes())
freeze=json.loads((out/'acquisition-freeze.json').read_bytes())
for name,digest in freeze['files'].items():assert hashlib.sha256((out/name).read_bytes()).hexdigest()==digest
raw=out/'source';raw.mkdir(exist_ok=False)
receipt={'status':'FAILED_CLOSED','started_at':datetime.now(timezone.utc).isoformat(),'attempt_id':'SENTIMENT-TRAIN-SUPPLEMENT-07',
         'requests':[],'bytes':0,'transfer_seconds':0.,'retries':0,'automatic_redirects':0,'model_calls':0,'training_runs':0}
session=requests.Session();rows=[];zone=timezone(timedelta(hours=8))
started=time.monotonic()
def persist():
    (out/'corpus.json').write_bytes(json.dumps({'items':rows},ensure_ascii=False,indent=2).encode())
    (out/'acquisition-receipt.json').write_bytes(json.dumps(receipt,ensure_ascii=False,indent=2).encode())
try:
    assert len(plan['commands'])==16
    for number,command in enumerate(plan['commands'],1):
        assert number<=16
        remaining=80-receipt['transfer_seconds']
        if remaining<=0:raise RuntimeError('TRANSFER_TIME_LIMIT')
        params={'q':command['keyword'],'tp':'news','sort':command['sort'],'page':command['page'],'size':command['page_size'],'from':'advanced_search',
                'stime':int(datetime.fromisoformat(command['minimum_date']).replace(tzinfo=zone).timestamp()),
                'etime':int(datetime.fromisoformat(command['maximum_date']+'T23:59:59').replace(tzinfo=zone).timestamp())}
        item={'number':number,'command':command,'params':params,'at':datetime.now(timezone.utc).isoformat()};receipt['requests'].append(item)
        tick=time.monotonic()
        try:
            with session.get(plan['endpoint'],params=params,headers={'Referer':'https://search.sina.com.cn/','User-Agent':'Mozilla/5.0'},
                             stream=True,allow_redirects=False,timeout=(min(5,remaining),min(8,remaining))) as response:
                item['http_status']=response.status_code;body=bytearray()
                for chunk in response.iter_content(65536):
                    body.extend(chunk);receipt['bytes']+=len(chunk)
                    if receipt['bytes']>4194304 or time.monotonic()-tick>remaining:raise RuntimeError('BYTE_OR_TRANSFER_TIME_LIMIT')
                path=raw/f'{number:02}.raw';path.write_bytes(body);item.update(file=path.name,sha256=hashlib.sha256(body).hexdigest(),bytes=len(body))
                if response.status_code!=200:raise RuntimeError('HTTP_'+str(response.status_code))
                data=json.loads(body);item['code']=data.get('code')
                if data.get('code')!=0:raise RuntimeError('PUBLIC_CODE_ERROR_STOP_NO_LOGIN_OR_VERIFICATION')
                values=data['data']['list'] or [];item.update(returned=len(values),reported_size=data['data'].get('size'),declared_total=data['data'].get('total'))
                assert len(values)<=20
                for ordinal,row in enumerate(values):
                    date=row.get('dataTime') or row.get('time')
                    if not date or not command['minimum_date']<=date[:10]<=command['maximum_date']:raise RuntimeError('DATE_FILTER_MISMATCH')
                    rows.append({'id':f'Q{number:02}-{ordinal:02}','request':number,'row':ordinal,'raw_sha256':item['sha256'],'title':clean(row.get('title')),
                                 'summary':clean(row.get('intro') or row.get('searchSummary')),'date':date,'url':row['url'],
                                 'media':row.get('media_show'),'reported_source':row.get('source'),'planned_period':command['period'],
                                 'date_basis':'SINA_SEARCH_REPORTED_PUBLICATION_NOT_HISTORICAL_PIT'})
        finally:
            elapsed=time.monotonic()-tick;receipt['transfer_seconds']+=elapsed;item['transfer_seconds']=elapsed
        if number%8==0:
            persist();print(json.dumps({'completed_requests':number,'rows':len(rows),'bytes':receipt['bytes'],'transfer_seconds':receipt['transfer_seconds']}),flush=True)
    receipt['status']='CAPTURED_CLOSED'
except Exception as error:
    receipt.update(error_type=type(error).__name__,error_code=str(error)[:180] if isinstance(error,(ValueError,RuntimeError)) else 'TRANSPORT_OR_PARSE_FAILURE')
finally:
    session.close();receipt.update(elapsed_seconds=time.monotonic()-started,returned=len(rows),remaining_requests=16-len(receipt['requests']))
    persist();print(json.dumps({key:value for key,value in receipt.items() if key!='requests'},ensure_ascii=False,indent=2),flush=True)
    if receipt['status']!='CAPTURED_CLOSED':raise SystemExit(1)
