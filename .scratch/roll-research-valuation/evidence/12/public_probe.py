"""One actual manual bounded JCC public check; never a natural postclose cycle."""
import json
import sys
from datetime import datetime,timezone
from pathlib import Path
import httpx
out=Path(__file__).parent
with httpx.Client(base_url='http://127.0.0.1:8033',trust_env=False,timeout=90) as c:
    if sys.argv[1]=='submit':
        r=c.post('/api/observation-updates/SSE:600362/requests',json=dict(kind='RESEARCH',
            idempotency_key='actual12-public-source-probe-01',basis='Actual12 one manual public JCC-only connectivity check before natural checkpoint; not a postclose cycle; no model auth',
            refresh_sources=True,retry_rejected=False))
        r.raise_for_status();job=r.json()
        assert job['scheduled_checkpoint'] is None
        (out/'public-probe-submission.json').write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(dict(job_id=job['job_id'],status=job['status'],scheduled_checkpoint=None,natural_cycle_count=0)))
    else:
        r=c.get('/api/observation-updates/SSE:600362');r.raise_for_status();listing=r.json()
        identifier=json.loads((out/'public-probe-submission.json').read_text(encoding='utf-8'))['job_id']
        job=next(j for j in listing['jobs'] if j['job_id']==identifier)
        receipt=dict(observed_at=datetime.now(timezone.utc).isoformat(),job=job,
            observations=listing['observations'],health=listing['health'],sources=listing['sources'],worker=listing['worker'],
            natural_cycles=sum(bool(j['scheduled_checkpoint']) for j in listing['jobs']))
        (out/'public-probe-result.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(dict(status=job['status'],job_id=identifier,errors=job.get('errors'),error=job.get('error'),
            natural_cycles=receipt['natural_cycles'],finished_at=job.get('finished_at')),ensure_ascii=False))
