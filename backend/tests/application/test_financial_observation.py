import hashlib,json
from fastapi.testclient import TestClient
from roll.app import create_app
from test_financial_metrics import prepare,income


def test_observation_fresh_trend_documents_and_missing(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        prepare(client);base='/api/market/financial/SSE:600362'
        response=client.get(base+'/observations');assert response.status_code==200,response.text
        value=response.json();current=value['current']
        assert current['status']=='FRESH' and current['latest_period']=='2026-06-30'
        assert current['industry']=={'organization_type':'通用','support':'GENERAL_SUPPORTED'}
        texts=' '.join(item['text'] for item in current['analysis'])
        assert '3,071.55 亿元' in texts and '+19.53%' in texts and '86.32 亿元' in texts and '+106.77%' in texts
        assert len(current['trend'])>=4 and current['documents']
        assert all(document['sha256'] for document in current['documents'])
        assert isinstance(current['revision']['revised'],bool) and current['revision']['fact_ids'] and current['network_calls']==0 and current['capability']=='NOT_GRANTED'
        assert current['system_usable'] is False
        again=client.get(base+'/observations').json()
        assert again['current']['observation_id']==current['observation_id'] and len(again['versions'])==1
        missing=client.get(base+'/observations',params={'known_by':'2025-01-01T00:00:00+00:00'}).json()['current']
        assert missing['status']=='MISSING' and missing['analysis']==[] and missing['latest_period'] is None
        assert client.get('/api/market/financial/observations/'+current['observation_id']).json()==current


def test_observation_revision_industry_and_disabled_source_keep_history(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        prepare(client);base='/api/market/financial/SSE:600362'
        before=client.get(base+'/observations').json()['current']
        async def revise(instrument,output):
            manifest=await income(instrument,output);raw=json.loads((output/'03.raw').read_bytes())
            for row in raw['data']:
                if row['REPORT_DATE'].startswith('2025-06-30'):row.update(PARENT_NETPROFIT=-1)
                if row['REPORT_DATE'].startswith('2026-06-30'):row.update(NETPROFIT=0,ORG_TYPE='银行')
            body=json.dumps(raw).encode();(output/'03.raw').write_bytes(body);manifest['captures'][2]['sha256']=hashlib.sha256(body).hexdigest();return manifest
        client.app.state.financial.worker=revise
        assert client.post(base+'/income/collect',json={'idempotency_key':'observation-revision','basis':'METHOD revision for observation'}).json()['status']=='COMPLETE'
        current=client.get(base+'/observations').json()['current']
        assert current['observation_version']==2 and current['revision']['revised'] is True
        assert current['industry']['support']=='FINANCIAL_OR_SPECIAL_NOT_SUPPORTED'
        reasons={gap['reason'] for gap in current['gaps']}
        assert 'FINANCIAL_OR_UNKNOWN_INDUSTRY_NOT_APPLICABLE' in reasons or 'NON_POSITIVE_BASE' in reasons
        assert any('行业专用口径不适用' in item['description'] for item in current['gaps'])
        old=client.get('/api/market/financial/observations/'+before['observation_id']).json()
        assert old==before
        policy=next(p for p in client.get('/api/research/collection-sources').json() if p['id']=='akshare-financial-em')
        assert client.post('/api/research/collection-sources/akshare-financial-em/policy',json={'enabled':False,'expected_revision':policy['revision'],'basis':'METHOD observation must read saved facts only'}).status_code==200
        after_disable=client.get(base+'/observations').json()['current']
        assert after_disable['observation_id']==current['observation_id']
        assert client.get('/api/account').json()['version']==0
