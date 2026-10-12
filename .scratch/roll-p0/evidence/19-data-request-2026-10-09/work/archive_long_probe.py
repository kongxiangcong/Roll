"""Long bounded probe of web.archive.org reachability across hosts/paths."""
import time, json
from curl_fetch import fetch
TARGETS = [
 'https://web.archive.org/cdx/search/cdx?url=hq.sinajs.cn%2Flist%3Dsh600362&matchType=exact&from=2016&to=2024&output=json&filter=statuscode%3A200&limit=10&fl=timestamp%2Coriginal%2Clength',
 'https://web.archive.org/web/20230317094630id_/http://hq.sinajs.cn/list=sh600362',
 'https://web.archive.org/web/2023id_/http://hq.sinajs.cn/list=sh600362',
]
res=[]
for rnd in range(4):
    for t in TARGETS:
        r=fetch(t, timeout=25)
        res.append({'round':rnd,'url':t[:80],'status':r['http_status'],'bytes':r['bytes'],'err':r['curl_stderr'][:80]})
        print(rnd, r['http_status'], r['bytes'], t[:60])
    time.sleep(20)
json.dump(res, open('archive-long-probe.json','w'), indent=2)
