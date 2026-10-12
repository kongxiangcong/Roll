"""Bounded probe: is web.archive.org reachable right now, and what differs on success."""
import time, json
from curl_fetch import fetch
URL='https://web.archive.org/cdx/search/cdx?url=hq.sinajs.cn%2Flist%3Dsh600362&matchType=exact&from=2016&to=2024&output=json&filter=statuscode%3A200&limit=10&fl=timestamp%2Coriginal%2Clength'
res=[]
for i in range(6):
    r=fetch(URL, timeout=20)
    res.append({'try':i,'status':r['http_status'],'bytes':r['bytes'],'err':r['curl_stderr'][:120]})
    print(i, r['http_status'], r['bytes'], r['curl_stderr'][:80])
    if r['http_status']==200 and r['bytes']>0:
        print(r['body'][:300].decode('latin-1')); break
    time.sleep(8)
json.dump(res, open('archive-probe.json','w'), indent=2)
