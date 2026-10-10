"""Fixed public repository and independent archive metadata; never fetch market rows."""
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import httpx

OUT = Path(__file__).resolve().parent
RAW = OUT/'.roll-data'/'alternative-metadata'
RAW.mkdir(parents=True, exist_ok=False)

def request(url, params=None):
    row = {'url': str(httpx.Request('GET', url, params=params).url),
           'requested_at': datetime.now(timezone.utc).isoformat()}
    try:
        with httpx.Client(timeout=25, follow_redirects=False) as client:
            with client.stream('GET', url, params=params) as response:
                row.update(http_status=response.status_code, headers=dict(response.headers))
                content = bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content)>2*1024*1024:
                        raise ValueError('SIZE_LIMIT')
        body = bytes(content)
        sha = hashlib.sha256(body).hexdigest()
        path = RAW/(sha+'.raw')
        path.write_bytes(body)
        row.update(path=str(path), sha256=sha, bytes=len(body),
                   received_at=datetime.now(timezone.utc).isoformat(), body_kind='HTTPX_DECODED_RESPONSE_BODY')
    except Exception as error:
        row['error'] = type(error).__name__+': '+str(error)
    return row

rows = []
rows.append(request('https://api.github.com/repos/huzpsb/ihq_bin/commits',
                    {'path':'ihq.bin', 'until':'2025-12-31T23:59:59Z', 'per_page':'100'}))
rows.append(request('https://raw.githubusercontent.com/huzpsb/ihQuant/main/readme.md'))
collection = request('https://index.commoncrawl.org/collinfo.json')
rows.append(collection)
tasks = []
if collection.get('http_status') == 200:
    catalog = json.loads(Path(collection['path']).read_bytes())
    selected = []
    for year in ['2023', '2025']:
        candidates = [r for r in catalog if r['id'].startswith('CC-MAIN-'+year+'-')]
        if candidates:
            selected.append(min(candidates, key=lambda r:r['id']))
    for item in selected:
        for url in ['hq.sinajs.cn/list=sh600362', 'q.stock.sohu.com/cn/600362/lshq.shtml',
                    'finance.sina.com.cn/realstock/company/sh600362/nc.shtml']:
            tasks.append((item['cdx-api'], {'url':url,'matchType':'exact','output':'json','filter':'status:200'}))
with ThreadPoolExecutor(max_workers=3) as pool:
    rows.extend(pool.map(lambda task:request(*task), tasks))
for row in rows:
    if row.get('http_status') == 200 and 'output=json' in row['url']:
        try:
            text = Path(row['path']).read_text(encoding='utf-8')
            row['indexed_records'] = [json.loads(line) for line in text.splitlines() if line.strip()]
        except ValueError as error:
            row['parse_error'] = str(error)
    if 'api.github.com' in row['url'] and row.get('http_status') == 200:
        data = json.loads(Path(row['path']).read_bytes())
        row['commits_returned'] = len(data) if isinstance(data,list) else None
        row['commit_metadata_not_publication_proof'] = True
report = {'requests':rows, 'maximum_requests':9,'actual_requests':len(rows),
          'selection':'First catalogued collection in2023 and2025, chosen before examining indexed contents',
          'market_payloads_fetched':0,'labels_computed':False,'fits':0,'sealed_read':False}
(OUT/'alternative-metadata-receipts.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps([{k:r.get(k) for k in ['url','http_status','commits_returned','error']} |
                  {'index_records':len(r.get('indexed_records',[]))} for r in rows],ensure_ascii=False))
