"""Bounded, public-only source feasibility probes; not model inputs or acceptance."""
import concurrent.futures
import datetime as dt
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

OUT = Path(__file__).with_name('free-source-probe-2026-10-08')
OUT.mkdir(exist_ok=True)
MAX_BYTES = 2_000_000

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

ENDPOINTS = {
    'tencent_quote': 'https://qt.gtimg.cn/q=sh600362',
    'tencent_daily': 'https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get?' + urllib.parse.urlencode({'param': 'sh600362,day,2026-09-01,2026-09-30,100,'}),
    'yahoo_chart': 'https://query1.finance.yahoo.com/v8/finance/chart/600362.SS?' + urllib.parse.urlencode({'range': '1mo', 'interval': '1d', 'events': 'div,splits'}),
    'sina_actions': 'https://vip.stock.finance.sina.com.cn/corp/go.php/vISSUE_ShareBonus/stockid/600362.phtml',
}

def probe(item):
    name, url = item
    record = {'source': name, 'url': url, 'started_at': dt.datetime.now(dt.timezone.utc).isoformat(),
              'classification': 'PUBLIC_FEASIBILITY_PROBE_ONLY_NOT_PIT_OR_TRAINING_INPUT',
              'retries': 0, 'timeout_seconds': 20}
    opener = urllib.request.build_opener(NoRedirect())
    req = urllib.request.Request(url, headers={'User-Agent': 'RollSourceResearch/1.0', 'Accept': '*/*'})
    try:
        try:
            response = opener.open(req, timeout=20)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            body = response.read(MAX_BYTES + 1)
            record.update(http_status=response.code, content_type=response.headers.get('Content-Type'),
                          server_date=response.headers.get('Date'))
        if len(body) > MAX_BYTES:
            record['error'] = 'RESPONSE_BYTE_BUDGET_EXCEEDED'
        else:
            path = OUT / (name + '.raw')
            path.write_bytes(body)
            record.update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest(), raw_file=path.name)
            if name == 'tencent_daily':
                data = json.loads(body)
                series = data.get('data', {}).get('sh600362', {})
                rows = series.get('day', [])
                record.update(business_code=data.get('code'), series_keys=list(series), daily_rows=len(rows),
                              first_row=rows[0] if rows else None, last_row=rows[-1] if rows else None)
            elif name == 'yahoo_chart':
                data = json.loads(body)
                chart = data.get('chart', {})
                results = chart.get('result') or []
                record.update(chart_error=chart.get('error'), result_count=len(results))
                if results:
                    result = results[0]
                    record.update(symbol=result.get('meta', {}).get('symbol'),
                                  timestamps=len(result.get('timestamp', [])),
                                  quote_fields=list(result.get('indicators', {}).get('quote', [{}])[0]),
                                  event_types=list(result.get('events', {})))
            elif name == 'tencent_quote':
                fields = body.decode('gb18030', errors='replace').split('~')
                record.update(field_count=len(fields), instrument_text=fields[1:3],
                              timestamp_field_30=fields[30] if len(fields)>30 else None,
                              note='Positional fields are feasibility only; semantics need source contract verification.')
            elif name == 'sina_actions':
                content = body.decode('gb18030', errors='replace')
                record['field_labels_present'] = {label: label in content for label in ['公告日期', '除权除息日', '股权登记日', '红股上市日', '配股价格', '缴款起始日']}
    except Exception as exc:
        record['error'] = type(exc).__name__
    record['finished_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
    return record

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    records = list(pool.map(probe, ENDPOINTS.items()))
(OUT / 'manifest.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(records, ensure_ascii=False, indent=2))
