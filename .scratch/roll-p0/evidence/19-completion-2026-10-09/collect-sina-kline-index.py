"""Bounded CDX requests for paths proven in first-party Sina SDK/page."""
import concurrent.futures, hashlib, json, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
HERE=Path(__file__).parent
OUT=HERE/'.roll-data'/'sina-kline-discovery-v3'
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None
targets=[
 ('finance.sina.com.cn/realstock/company/sh600362/hisdata/klc_kl.js','prefix','4',80),
 ('hq.sinajs.cn/?list=sh600362','exact','6',160),
]
def get(spec):
 target,match,collapse,limit=spec
 query={'url':target,'matchType':match,'output':'json','from':'2013','to':'2025','filter':'statuscode:200','collapse':'timestamp:'+collapse,'limit':str(limit),'fl':'timestamp,original,mimetype,statuscode,digest,length'}
 url='https://web.archive.org/cdx/search/cdx?'+urllib.parse.urlencode(query)
 row={'target':target,'url':url,'match_type':match,'limit':limit,'requested_at':datetime.now(timezone.utc).isoformat(),'live_fallback':False}
 try:
  try:r=urllib.request.build_opener(NoRedirect).open(url,timeout=30)
  except urllib.error.HTTPError as e:r=e
  b=r.read(2*1024*1024+1)
  if len(b)>2*1024*1024:raise ValueError('2MiB_CAP')
  sha=hashlib.sha256(b).hexdigest();path=OUT/(sha+'.raw');path.write_bytes(b)
  row.update(http_status=r.status,received_at=datetime.now(timezone.utc).isoformat(),headers=dict(r.headers),bytes=len(b),sha256=sha,path=str(path))
  if r.status==200:
   rows=json.loads(b);row['rows']=max(0,len(rows)-1);row['indexed_captures']=[dict(zip(rows[0],x)) for x in rows[1:]] if rows else []
 except Exception as e:row['error']=type(e).__name__+': '+str(e)
 return row
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(get,targets))
result={'first_party_path_evidence':'sina-kline-discovery-receipts.json','index_budget':8,'index_requests':len(rows),'sources':rows}
(HERE/'sina-kline-index-receipts.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(result,ensure_ascii=False))
