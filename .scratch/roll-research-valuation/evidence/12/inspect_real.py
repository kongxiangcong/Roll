"""Bounded loopback reads; no source refresh or model call."""
import json
from pathlib import Path
import httpx

out = Path(__file__).parent
with httpx.Client(base_url='http://127.0.0.1:8032', trust_env=False, timeout=90) as client:
    values = {}
    for name, path in [('companies', '/api/company-research/companies'), ('market', '/api/market/list'),
                       ('health', '/api/health')]:
        response = client.get(path)
        response.raise_for_status()
        values[name] = response.json()
    for company in values['companies']['companies']:
        cid = company['company_id']
        for suffix in ['snapshots', 'materials', 'checks', 'reports', 'daily']:
            response = client.get('/api/company-research/companies/' + cid + '/' + suffix)
            values[cid + '/' + suffix] = dict(status_code=response.status_code, value=response.json())
    (out/'initial-live.json').write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(companies=[dict(id=c['company_id'], name=c['legal_name'],
        listings=[v['listing_id'] for v in c['listings']]) for c in values['companies']['companies']],
        keys=list(values), market_members=values['market']['members']), ensure_ascii=False))
