import json,sys
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app

data=Path(r"D:\dsh-proj\Roll\.scratch\r15real")
out=Path(r"D:\dsh-proj\Roll\.scratch\roll-capability-expansion\evidence\15-events")
with TestClient(create_app(data)) as client:
    before=client.get('/api/account').json()['version']
    listing=client.get('/api/market/list').json()
    if 'SSE:600362' not in {m['instrument'] for m in listing['members']}:
        response=client.post('/api/market/watch',json={'operation':'ADD','instrument':'SSE:600362','expected_list_version':listing['version']})
        assert response.status_code==200,response.text
    member=next(m for m in client.get('/api/market/list').json()['members'] if m['instrument']=='SSE:600362')
    if not (member.get('identity') or {}).get('name'):
        response=client.post('/api/market/identities',json={'instrument':'SSE:600362','exchange':'SSE','board':'主板','instrument_type':'STOCK',
            'name':'江西铜业股份有限公司','basis':'09财务原件 SECURITY_NAME_ABBR=江西铜业；600362.SH','effective_at':'2026-01-01T00:00:00+08:00'})
        assert response.status_code==200,response.text
    news=client.get('/api/market/news/SSE:600362').json()
    after=client.get('/api/account').json()['version']
    summary={'instrument':'SSE:600362','facts':len(news['facts']),'unique_event_count':news['unique_event_count'],
        'reprint_count':news['reprint_count'],'revision_count':news['revision_count'],'association_counts':news['association_counts'],
        'account_version_before':before,'account_version_after':after,
        'derivation':news['derivation'],'events':news['events'],
        'rows':[{'title':f['title'],'url':f['url'],'media':f['media'],'body_status':f['body_status'],
            'classification':f['association']['classification'],'basis':f['association']['basis'],
            'objects':f['association']['objects'],'event_id':f['event']['event_id'],'relation':f['event']['relation']} for f in news['facts']]}
(out/'real-association.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k not in ('events','rows')},ensure_ascii=False,indent=2))
for row in summary['rows']:
    print(row['classification'],'|',row['title'][:40],'|',row['relation'])
