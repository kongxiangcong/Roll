"""One retry per recorded failure, with prior receipts retained."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json

OUT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('public_capture', OUT/'collect-archive-payloads.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.RAW = OUT/'.roll-data'/'exact-payload-retry'
module.RAW.mkdir(parents=True, exist_ok=False)
before = json.loads((OUT/'exact-payload-receipts.json').read_bytes())
failed = [r for r in before['requests'] if r['status']=='FAILED']
with ThreadPoolExecutor(max_workers=4) as pool:
    rows = list(pool.map(module.collect, [r['capture'] for r in failed]))
for row, parent in zip(rows, failed):
    row['retry_parent'] = {'receipt': 'exact-payload-receipts.json', 'url': parent['url'], 'error': parent['error']}
report = {'requests': rows, 'request_count': len(rows), 'retry_limit_per_target': 1,
          'labels_computed': False, 'models_fitted': 0, 'sealed_read': False}
(OUT/'exact-payload-retry-receipts.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'requests': len(rows), 'quotes': sum('quote' in r for r in rows),
                  'pages': sum('page' in r for r in rows), 'failed': sum(r['status']=='FAILED' for r in rows)}))
