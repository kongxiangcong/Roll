"""One bounded retry for known capture failures, plus two newly indexed exact captures."""
import concurrent.futures,hashlib,json
from pathlib import Path
HERE=Path(__file__).parent
namespace={"__file__":str(HERE/'collect-sina-archive-payloads.py')}
source=(HERE/'collect-sina-archive-payloads.py').read_text(encoding='utf8')
exec(source.split('with concurrent.futures.ThreadPoolExecutor')[0].replace('timeout=30','timeout=20').replace(r'(?::80)?/list=sh600362',r'(?::80)?/(?:\?)?list=sh600362'),namespace)
original=json.loads((HERE/'sina-archive-payload-receipts.json').read_text(encoding='utf8'))
jobs=[(row['cdx'],row['url']) for row in original['captures'] if row['status']=='FAILED']
extra=json.loads((HERE/'sina-kline-index-receipts.json').read_text(encoding='utf8'))['sources'][1]['indexed_captures']
jobs += [(row,None) for row in extra]
assert len(jobs)<=26
def get(job):
 row=namespace['collect'](job[0]);row['retry_parent']=job[1];row['attempt']=2 if job[1] else 1
 return row
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(get,jobs))
mismatches=[]
for r in rows:
 if 'path' in r:
  b=Path(r['path']).read_bytes()
  if len(b)!=r['bytes'] or hashlib.sha256(b).hexdigest()!=r['sha256']:mismatches.append(r['url'])
receipt={'captures':rows,'limits':{'known_failures_once':24,'new_exact_captures':2,'parallel':4,'timeout_seconds':20,'single_bytes':2097152},'verification':{'checked':sum('path' in r for r in rows),'mismatches':mismatches},'live_fallback':False,'original_failure_receipt':'sina-archive-payload-receipts.json','qualification':'NONE'}
(HERE/'sina-archive-payload-retry-receipts.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'requests':len(rows),'responses':sum('path' in r for r in rows),'quotes':sum('quote' in r for r in rows),'failures':sum(r['status']=='FAILED' for r in rows),'hash_length_mismatches':len(mismatches)}))
