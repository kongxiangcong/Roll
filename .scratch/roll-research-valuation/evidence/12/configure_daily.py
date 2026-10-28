"""Configure only the existing postclose research chain in isolated daily copy."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import httpx

out=Path(__file__).parent
root=Path('D:/dsh-proj/Roll/.scratch/rv12-daily01')
# Operational queue preflight only; no business data mutation or model input read.
with sqlite3.connect('file:'+str(root/'roll.sqlite3')+'?mode=ro',uri=True) as db:
    tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    queue_counts={}
    for table in ['company_research_jobs','assistance_runs','observation_update_jobs','review_jobs']:
        if table in tables:
            queue_counts[table]=db.execute(f"SELECT count(*) FROM {table} WHERE json_extract(value,'$.status') IN ('QUEUED','RUNNING')").fetchone()[0]
    assert all(v==0 for v in queue_counts.values()),queue_counts
with httpx.Client(base_url='http://127.0.0.1:8033',trust_env=False,timeout=90) as c:
    before={instrument:c.get('/api/observation-updates/'+instrument).json() for instrument in ['SSE:600362','SZSE:000848']}
    settings={}
    for instrument,listing in before.items():
        old=listing['settings']
        response=c.post('/api/observation-updates/'+instrument+'/settings',json=dict(expected_revision=old['revision'],
            enabled=True,research_postclose=True,news_postclose=False,financial_postclose=False,market_postclose=False,
            news_refresh=True,classify=False,profile='legacy',
            basis='Actual12 isolated natural postclose acceptance; existing bounded public sources where supported; no model auth; no offline/backfill or other postclose kinds'))
        response.raise_for_status();settings[instrument]=response.json()
    source_listing=c.get('/api/data/sources');source_listing.raise_for_status()
    receipt=dict(at=datetime.now(timezone.utc).isoformat(),store=str(root),queue_counts=queue_counts,
        settings=settings,actual_cycles_before={i:sum(bool(j['scheduled_checkpoint']) for j in v['jobs']) for i,v in before.items()},
        source_listing=source_listing.json(),worker_started=False,model_auth_configured=False,
        earliest_two_checkpoints=['2026-10-28T15:05:00+08:00','2026-10-29T15:05:00+08:00'],
        limitations=['JCC public refresh still subject to existing source switches, adapters and limits',
                    'Other company public scope unsupported is a gap; archive-only results do not prove public coverage',
                    'No clock override or new platform automation; actual completed outcomes still required'])
(out/'daily-configuration.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(queue_counts=queue_counts,settings={i:dict(revision=s['revision'],research_postclose=s['research_postclose'],news_refresh=s['news_refresh']) for i,s in settings.items()},actual_cycles_before=receipt['actual_cycles_before'])))
