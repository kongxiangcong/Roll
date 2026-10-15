import json
from fastapi.testclient import TestClient
from roll.app import create_app
from test_financial_statements import statements
from test_financial_income import CAPTURE


async def income(instrument,output):
    manifest=json.loads((CAPTURE/'capture.json').read_text())
    for c in manifest['captures']:(output/c['raw_file']).write_bytes((CAPTURE/c['raw_file']).read_bytes())
    return manifest


def prepare(client):
    client.post('/api/market/watch',json={'operation':'ADD','instrument':'SSE:600362','expected_list_version':client.get('/api/market/list').json()['version']})
    policy=next(p for p in client.get('/api/research/collection-sources').json() if p['id']=='akshare-financial-em')
    client.post('/api/research/collection-sources/akshare-financial-em/policy',json={'enabled':True,'expected_revision':policy['revision'],'basis':'METHOD metrics from archived source, no HTTP'})
    client.app.state.financial.worker=income;client.app.state.financial_statements.worker=statements
    base='/api/market/financial/SSE:600362'
    for name in ('income','statements'):assert client.post(base+'/'+name+'/collect',json={'idempotency_key':name,'basis':'METHOD metric inputs'}).json()['status']=='COMPLETE'
    return base


def test_metrics_quarters_ttm_ratios_and_asof_replay(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        base=prepare(client);response=client.get(base+'/metrics');assert response.status_code==200,response.text
        result=response.json();h1=next(r for r in result['periods'] if r['report_period']=='2026-06-30');m=h1['metrics']
        assert m['quarter_revenue']['value']=='168030866946'
        assert m['ttm_revenue']['value']=='594819535918'
        assert m['revenue_yoy']['value']=='19.534663' and m['revenue_yoy']['absolute_change']=='50196051858'
        assert m['net_margin']['value']=='3.093153'
        assert m['gross_margin']['value']=='5.823553'
        assert m['debt_ratio']['value']=='65.475577'
        assert m['cash_profit_ratio']['status']=='KNOWN' and m['cash_profit_ratio']['formula']=='operating_cash_flow / consolidated_net_profit'
        assert len(m['ttm_revenue']['source_fact_ids'])==5
        missing=next(r for r in result['periods'] if r['report_period']=='2025-06-30')['metrics']
        assert missing['quarter_revenue']['status']=='UNKNOWN' and missing['quarter_revenue']['reason']=='PRIOR_YTD_MISSING_OR_INCOMPARABLE'
        assert missing['debt_ratio']['status']=='UNKNOWN'
        cutoff=result['known_by'];assert client.get(base+'/metrics',params={'known_by':'2025-12-31T00:00:00+00:00'}).json()['periods']==[]
        old=client.get(base+'/metrics',params={'known_by':cutoff}).json();assert old['periods']==result['periods']
        assert client.get('/api/account').json()['version']==0
    with TestClient(create_app(tmp_path)) as client:assert client.get(base+'/metrics',params={'known_by':cutoff}).json()['periods']==old['periods']


def test_metrics_nonpositive_base_industry_and_revision_do_not_rewrite_cutoff(tmp_path):
    import hashlib
    with TestClient(create_app(tmp_path)) as client:
        base=prepare(client);before=client.get(base+'/metrics').json();cutoff=before['known_by']
        async def revise(instrument,output):
            manifest=await income(instrument,output);raw=json.loads((output/'03.raw').read_bytes())
            for row in raw['data']:
                if row['REPORT_DATE'].startswith('2025-06-30'):row.update(PARENT_NETPROFIT=-1)
                if row['REPORT_DATE'].startswith('2026-06-30'):row.update(NETPROFIT=0,ORG_TYPE='银行')
            body=json.dumps(raw).encode();(output/'03.raw').write_bytes(body);manifest['captures'][2]['sha256']=hashlib.sha256(body).hexdigest();return manifest
        client.app.state.financial.worker=revise
        assert client.post(base+'/income/collect',json={'idempotency_key':'revision','basis':'METHOD nonpositive and financial industry source variants'}).json()['status']=='COMPLETE'
        current=client.get(base+'/metrics').json();m=next(p for p in current['periods'] if p['report_period']=='2026-06-30')['metrics']
        assert m['parent_net_profit_yoy']['value'] is None and m['parent_net_profit_yoy']['absolute_change']=='8631822609'
        assert m['parent_net_profit_yoy']['reason']=='NON_POSITIVE_BASE'
        assert m['cash_profit_ratio']['reason']=='NON_POSITIVE_DENOMINATOR'
        assert m['gross_margin']['reason']=='FINANCIAL_OR_UNKNOWN_INDUSTRY_NOT_APPLICABLE'
        assert client.get(base+'/metrics',params={'known_by':cutoff}).json()['periods']==before['periods']
        assert current['periods']!=before['periods']
        async def zero_base(instrument,output):
            manifest=await revise(instrument,output);raw=json.loads((output/'03.raw').read_bytes())
            for row in raw['data']:
                if row['REPORT_DATE'].startswith('2025-06-30'):row['PARENT_NETPROFIT']=0
            body=json.dumps(raw).encode();(output/'03.raw').write_bytes(body);manifest['captures'][2]['sha256']=hashlib.sha256(body).hexdigest();return manifest
        client.app.state.financial.worker=zero_base
        assert client.post(base+'/income/collect',json={'idempotency_key':'zero-base','basis':'METHOD zero prior-year denominator'}).json()['status']=='COMPLETE'
        zero=next(p for p in client.get(base+'/metrics').json()['periods'] if p['report_period']=='2026-06-30')['metrics']['parent_net_profit_yoy']
        assert zero['value'] is None and zero['reason']=='NON_POSITIVE_BASE' and zero['absolute_change']=='8631822608'
        assert client.get(base+'/metrics',params={'known_by':cutoff}).json()['periods']==before['periods']


def test_operating_revenue_absence_or_conflict_cannot_use_total_revenue_for_margin(tmp_path):
    import hashlib
    with TestClient(create_app(tmp_path)) as client:
        base=prepare(client)
        for value in (None,100):
            async def conflict(instrument,output):
                manifest=await income(instrument,output);raw=json.loads((output/'03.raw').read_bytes());raw['data'][0]['OPERATE_INCOME']=value
                body=json.dumps(raw).encode();(output/'03.raw').write_bytes(body);manifest['captures'][2]['sha256']=hashlib.sha256(body).hexdigest();return manifest
            client.app.state.financial.worker=conflict
            assert client.post(base+'/income/collect',json={'idempotency_key':str(value),'basis':'METHOD operating revenue field missing or contradicts verified income header'}).json()['status']=='COMPLETE'
            m=next(p for p in client.get(base+'/metrics').json()['periods'] if p['report_period']=='2026-06-30')['metrics']
            assert m['gross_margin']['status']=='UNKNOWN'
            assert m['net_margin']['status']=='UNKNOWN'
            assert m['revenue']['value']=='307154938743'


def test_parent_like_amounts_and_ten_thousand_units_stay_unverified(tmp_path):
    import hashlib
    with TestClient(create_app(tmp_path)) as client:
        base=prepare(client)
        for name,revenue in [('parent','63060454123'),('ten-thousand','30715493.8743')]:
            async def source_variant(instrument,output):
                manifest=await income(instrument,output);raw=json.loads((output/'03.raw').read_bytes());raw['data'][0].update(TOTAL_OPERATE_INCOME=revenue,OPERATE_INCOME=revenue)
                body=json.dumps(raw).encode();(output/'03.raw').write_bytes(body);manifest['captures'][2]['sha256']=hashlib.sha256(body).hexdigest();return manifest
            client.app.state.financial.worker=source_variant
            assert client.post(base+'/income/collect',json={'idempotency_key':name,'basis':'METHOD parent company or ten-thousand yuan values lacking semantic proof'}).json()['status']=='COMPLETE'
            m=next(p for p in client.get(base+'/metrics').json()['periods'] if p['report_period']=='2026-06-30')['metrics']
            for key in ('gross_margin','cash_profit_ratio','quarter_revenue','ttm_revenue'):assert m[key]['status']=='UNKNOWN'
