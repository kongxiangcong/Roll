import hashlib
import json
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import httpx

root = Path(__file__).resolve().parent
plan = json.loads((root/'plan.json').read_text(encoding='utf8'))
assert not (root/'capture-manifest.json').exists(), 'Closed budget cannot be retried'
start = time.monotonic()
records = []
total = 0
class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.items=[]; self.href=None; self.label=''
    def handle_starttag(self, tag, attrs):
        if tag=='a': self.href=dict(attrs).get('href'); self.label=''
    def handle_data(self, data):
        if self.href: self.label+=data
    def handle_endtag(self, tag):
        if tag=='a' and self.href:
            self.items.append({'href':self.href,'label':self.label.strip()}); self.href=None

with httpx.Client(timeout=12.0,follow_redirects=False,headers={'User-Agent':'Roll bounded official-sample contract research'}) as client:
    def fetch(url, label):
        global total
        record={'url':url,'label':label,'started_at':datetime.now(timezone.utc).isoformat()}
        body=[]
        try:
            with client.stream('GET',url) as resp:
                record.update(status=resp.status_code,headers=dict(resp.headers))
                for chunk in resp.iter_bytes():
                    if total+len(chunk)>plan['max_bytes'] or time.monotonic()-start>plan['max_seconds']: raise RuntimeError('Budget exceeded; incomplete body retained')
                    total+=len(chunk); body.append(chunk)
                record['complete']=True
        except Exception as exc: record.update(complete=False,error=type(exc).__name__+': '+str(exc))
        data=b''.join(body); name=f'{len(records)+1:02d}.raw'; (root/name).write_bytes(data)
        record.update(path=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),received_at=datetime.now(timezone.utc).isoformat()); records.append(record)
        (root/'progress.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf8')
        return record,data
    page, data=fetch(plan['page'],'official CIIS historical data introduction')
    if page.get('status')==200 and page['complete']:
        links=Links(); links.feed(data.decode('utf8',errors='replace'))
        candidates=[]
        for item in links.items:
            text=(item['label']+' '+item['href']).lower()
            if 'sample' in text and ('601398' in text or '127350' in text):
                url=urljoin(plan['page'],item['href'])
                if urlsplit(url).scheme in ('https','http') and urlsplit(url).hostname in ('www.ciis.com.hk','ciis.com.hk'):
                    candidates.append(dict(item,url=url))
        (root/'discovered-links.json').write_text(json.dumps(candidates,ensure_ascii=False,indent=2),encoding='utf8')
        # Prefer Level-1 601398, Level-2 601398, then one 127350; deduplicate exact URLs.
        candidates.sort(key=lambda x:('601398' not in (x['label']+' '+x['href']), 'level-1' not in x['label'].lower(), 'tick' in x['label'].lower()))
        used=set()
        for item in candidates:
            if len(records)>=4 or time.monotonic()-start>=plan['max_seconds'] or total>=plan['max_bytes']: break
            if item['url'] in used: continue
            used.add(item['url']); fetch(item['url'],item['label'])
result={'state':'CLOSED_NO_RETRY','requests':len(records),'bytes':total,'elapsed_seconds':time.monotonic()-start,'roll_observations_created':0,'records':records}
(root/'capture-manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:v for k,v in result.items() if k!='records'}))
