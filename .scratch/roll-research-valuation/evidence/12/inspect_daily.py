"""Read actual scheduled records; never schedule, simulate or backfill a cycle."""
import json
import sys
from datetime import datetime,timezone
from pathlib import Path
import httpx
out=Path(__file__).parent
label=sys.argv[1] if len(sys.argv)>1 else '01'
path=out/('daily-status'+label+'.json')
if path.exists():raise RuntimeError('Preserve earlier actual observation; use a new suffix')
with httpx.Client(base_url='http://127.0.0.1:8033',trust_env=False,timeout=90) as c:
    records={}
    for instrument in ['SSE:600362','SZSE:000848']:
        r=c.get('/api/observation-updates/'+instrument);r.raise_for_status();records[instrument]=r.json()
receipt=dict(observed_at=datetime.now(timezone.utc).isoformat(),records=records,
    actual_scheduled_records={i:[j for j in v['jobs'] if j['scheduled_checkpoint']] for i,v in records.items()},
    manual_records_not_counted=True,worker_health_is_not_cycle_evidence=True)
path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(observed_at=receipt['observed_at'],actual_scheduled_counts={i:len(v) for i,v in receipt['actual_scheduled_records'].items()},
    worker={i:v['worker'] for i,v in records.items()},sources={i:v['sources'] for i,v in records.items()}),ensure_ascii=False))
