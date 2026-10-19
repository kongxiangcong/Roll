"""One bounded real acquisition; archives bytes before parsing, never calls a model."""
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlencode
import requests
from object_contract import clean

out = Path(__file__).resolve().parent
repo = Path(__file__).resolve().parents[5]
plan = json.loads((out/'acquisition04-plan.json').read_bytes())
raw_dir = out/'source-04'
raw_dir.mkdir(exist_ok=False)
started = time.monotonic()
receipt = {'attempt_id':plan['attempt_id'],'started_at':datetime.now(timezone.utc).isoformat(),'status':'FAILED_CLOSED','requests':[],'bytes':0,'retries':0,'redirects':0}
session = requests.Session()


def canonical(url):
    parsed = urlsplit(url or '')
    return parsed.hostname,parsed.path.rstrip('/')


def text_hash(title,summary):
    return hashlib.sha256((clean(title)+'\n'+clean(summary)).encode()).hexdigest()


old_urls, old_texts = set(), set()
old_sources = []
for relative in ('corpus-attempt/corpus.json','corpus-name-attempt/corpus.json','fresh-02/corpus.json'):
    path = out.parent/relative
    body = path.read_bytes()
    old_sources.append({'path':relative,'sha256':hashlib.sha256(body).hexdigest()})
    for row in json.loads(body)['items']:
        old_urls.add(canonical(row.get('url')))
        old_texts.add(text_hash(row.get('title'),row.get('summary')))
rows = []
try:
    for number, command in enumerate(plan['requests'],1):
        remaining = plan['limits']['maximum_seconds']-(time.monotonic()-started)
        if remaining <= 0:
            raise RuntimeError('ACQUISITION_TIME_LIMIT')
        param = {'uid':'','keyword':command['keyword'],'type':['cmsArticleWebOld'],'client':'web','clientType':'web','clientVersion':'curr',
                 'param':{'cmsArticleWebOld':{'searchScope':'default','sort':'default','pageIndex':command['page'],'pageSize':plan['page_size'],'preTag':'<em>','postTag':'</em>'}}}
        query = {'cb':'rollSentimentCorpus03','param':json.dumps(param,ensure_ascii=False,separators=(',',':')),'_':str(int(time.time()*1000))}
        item = {'number':number,'command':command,'received_at':datetime.now(timezone.utc).isoformat()}
        receipt['requests'].append(item)
        with session.get(plan['upstream'],params=query,headers={'Referer':'https://so.eastmoney.com/','User-Agent':'Mozilla/5.0'},
                         stream=True,allow_redirects=False,timeout=(min(5,remaining),min(5,remaining))) as response:
            item['status_code'] = response.status_code
            body = bytearray()
            for chunk in response.iter_content(65536):
                receipt['bytes'] += len(chunk)
                if receipt['bytes']>plan['limits']['maximum_bytes'] or time.monotonic()-started>plan['limits']['maximum_seconds']:
                    raise RuntimeError('ACQUISITION_BYTE_OR_TIME_LIMIT')
                body.extend(chunk)
            path = raw_dir/f'{number:02}.raw'
            path.write_bytes(body)
            item.update(file=path.name,bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
            if response.status_code!=200:
                raise RuntimeError('UPSTREAM_HTTP_'+str(response.status_code))
            text = body.decode('utf-8-sig').strip()
            data = json.loads(text if text.startswith('{') else text[text.find('(')+1:text.rfind(')')])
            page = data['result']['cmsArticleWebOld']
            item['returned'] = len(page)
            for index,row in enumerate(page):
                rows.append({'request':number,'row':index,'raw_sha256':item['sha256'],'title':clean(row.get('title')),'summary':clean(row.get('content')),
                             'url':row.get('url'),'media':row.get('mediaName'),'date':row.get('date'),'code':row.get('code')})
            if len(rows)>plan['limits']['maximum_rows']:
                raise RuntimeError('ACQUISITION_ROW_LIMIT')
    receipt['status'] = 'CAPTURED_CLOSED'
except Exception as error:
    receipt['error_type'] = type(error).__name__
    if isinstance(error,RuntimeError):
        receipt['error_code'] = str(error)
finally:
    session.close()
    unique, excluded = [], []
    seen_urls, seen_texts = set(), set()
    for row in rows:
        url, digest = canonical(row['url']),text_hash(row['title'],row['summary'])
        reason = 'PREVIOUSLY_CAPTURED' if url in old_urls or digest in old_texts else 'DUPLICATE_IN_NEW_CAPTURE' if url in seen_urls or digest in seen_texts else None
        if reason:
            excluded.append({**row,'exclusion':reason})
        else:
            unique.append({**row,'index':len(unique),'text_sha256':digest})
            seen_urls.add(url);seen_texts.add(digest)
    receipt.update(elapsed_seconds=round(time.monotonic()-started,3),returned=len(rows),new_unique=len(unique),excluded=len(excluded),old_corpus_sources=old_sources)
    (out/'corpus04.json').write_text(json.dumps({'instrument':'SSE:600362','upstream':plan['upstream'],'items':unique,'excluded':excluded},ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'acquisition04-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))
