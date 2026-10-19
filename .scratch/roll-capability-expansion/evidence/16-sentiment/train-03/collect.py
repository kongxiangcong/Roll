"""One shared acquisition budget, source-only adaptation; never loads a model."""
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import requests
from object_contract import clean
from cninfo_materials import parse_rows

out=Path(__file__).resolve().parent
plan=json.loads((out/'acquisition-plan.json').read_bytes())
raw=out/'source';raw.mkdir(exist_ok=False)
receipt={'attempt_id':plan['attempt_id'],'started_at':datetime.now(timezone.utc).isoformat(),
         'status':'FAILED_CLOSED','requests':[],'bytes':0,'transfer_seconds':0.,'retries':0,'redirects':0}
session=requests.Session();news=[];disclosures=[]
def capture(url,kind,command,form=None,param=None):
    assert len(receipt['requests'])<32
    remaining=120-receipt['transfer_seconds']
    if remaining<=0: raise RuntimeError('TRANSFER_TIME_LIMIT')
    tick=time.monotonic()
    item={'number':len(receipt['requests'])+1,'kind':kind,'command':command,'at':datetime.now(timezone.utc).isoformat()}
    receipt['requests'].append(item)
    try:
        with session.request('POST' if form else 'GET',url,data=form,params=param,
                             headers={'Referer':'https://www.cninfo.com.cn/' if form else 'https://so.eastmoney.com/',
                                      'User-Agent':'Mozilla/5.0'},stream=True,allow_redirects=False,
                             timeout=(min(5,remaining),min(8,remaining))) as response:
            item['status_code']=response.status_code;body=bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk);receipt['bytes']+=len(chunk)
                if receipt['bytes']>16777216 or time.monotonic()-tick>remaining: raise RuntimeError('BYTE_OR_TIME_LIMIT')
            path=raw/f"{item['number']:02}.raw";path.write_bytes(body)
            item.update(file=path.name,bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
            if response.status_code!=200: raise RuntimeError('HTTP_'+str(response.status_code))
            text=body.decode('utf-8-sig').strip()
            return json.loads(text if text.startswith('{') else text[text.find('(')+1:text.rfind(')')]),item
    finally:
        elapsed=time.monotonic()-tick;receipt['transfer_seconds']+=elapsed;item['transfer_seconds']=elapsed

def get_news(keyword,page):
    param={'uid':'','keyword':keyword,'type':['cmsArticleWebOld'],'client':'web','clientType':'web','clientVersion':'curr',
           'param':{'cmsArticleWebOld':{'searchScope':'title','sort':'default','pageIndex':page,'pageSize':100,'preTag':'<em>','postTag':'</em>'}}}
    data,item=capture(plan['news_url'],'NEWS_TITLE',{'keyword':keyword,'page':page,'scope':'title'},
                      param={'cb':'rollTrain03','param':json.dumps(param,ensure_ascii=False,separators=(',',':'))})
    values=data['result']['cmsArticleWebOld'];item['returned']=len(values)
    item['title_hit_ratio']=sum(keyword in clean(r.get('title')) for r in values)/len(values) if values else None
    for ordinal,row in enumerate(values):
        news.append({'id':f"N{item['number']:02}-{ordinal:03}",'request':item['number'],'row':ordinal,
                     'raw_sha256':item['sha256'],'title':clean(row.get('title')),'summary':clean(row.get('content')),
                     'date':row.get('date'),'url':row.get('url'),'media':row.get('mediaName')})
    return item

started=time.monotonic()
try:
    eligible={}
    for keyword in plan['news_keywords']:
        first=get_news(keyword,1);eligible[keyword]=bool(first['returned'] and first['title_hit_ratio']>=.8)
    receipt['title_scope_eligible']=eligible
    for keyword,allowed in eligible.items():
        if allowed:
            for page in range(2,11):
                item=get_news(keyword,page)
                if not item['returned']: break
                if item['title_hit_ratio']<.8: raise RuntimeError('TITLE_SCOPE_CHANGED')
    for interval in plan['cninfo_intervals']:
        for page in (1,2):
            form={'stock':'600362,gssh0600362','column':'sse','tabName':'fulltext','seDate':interval,
                  'searchkey':'','sortName':'time','sortType':'asc','pageNum':str(page),'pageSize':'50'}
            data,item=capture(plan['cninfo_url'],'CNINFO_INDEX',form,form=form)
            rows=parse_rows(data.get('announcements') or [],str(item['number']),item['sha256'])
            item['returned']=len(rows);item['declared_total']=data.get('totalAnnouncement');disclosures.extend(rows)
    receipt['status']='CAPTURED_CLOSED'
except Exception as error:
    receipt.update(error_type=type(error).__name__,error_code=str(error)[:200] if isinstance(error,(ValueError,RuntimeError)) else 'TRANSPORT_OR_PARSE_FAILURE')
finally:
    session.close()
    seen=set();unique=[];duplicates=[]
    for row in news+disclosures:
        parsed=urlsplit(row['url']);key=(parsed.hostname,parsed.path.rstrip('/'))
        if key in seen: duplicates.append(row)
        else: unique.append(row);seen.add(key)
    receipt.update(elapsed_seconds=time.monotonic()-started,returned=len(news)+len(disclosures),unique=len(unique),duplicates=len(duplicates),
                   remaining_requests=32-len(receipt['requests']),remaining_bytes=16777216-receipt['bytes'],remaining_transfer_seconds=120-receipt['transfer_seconds'])
    (out/'corpus.json').write_bytes(json.dumps({'items':unique,'duplicates':duplicates},ensure_ascii=False,indent=2).encode())
    (out/'acquisition-receipt.json').write_bytes(json.dumps(receipt,ensure_ascii=False,indent=2).encode())
    print(json.dumps(receipt,ensure_ascii=False,indent=2))
    if receipt['status']!='CAPTURED_CLOSED': raise SystemExit(1)
