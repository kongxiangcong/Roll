import hashlib,json
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app
from roll.market.akshare_financial_process import SDK_VERSION,SDK_SOURCE_SHA
from test_financial_income import CAPTURE


async def statements(instrument,output):
    # Anonymous transport fixture; numbers independently transcribed from issuer PDF pages59-67.
    data={'BALANCE':{'TOTAL_ASSETS':293265142356,'TOTAL_LIABILITIES':192017045263,'TOTAL_EQUITY':101248097093},
          'CASH_FLOW':{'NETCASH_OPERATE':5814230993,'NETCASH_INVEST':-23434970323,'NETCASH_FINANCE':30308136531,'CCE_ADD':12478238776}}
    captures=[]
    for statement,role in [('BALANCE','zcfzbAjaxNew'),('CASH_FLOW','xjllbAjaxNew')]:
        row={'SECUCODE':'600362.SH','REPORT_DATE':'2026-06-30 00:00:00','CURRENCY':'CNY','UPDATE_DATE':'2026-08-26 00:00:00',**data[statement]}
        body=json.dumps({'data':[row]}).encode();name=f'{len(captures)+1:02}.raw';(output/name).write_bytes(body)
        captures.append({'role':role,'raw_file':name,'url':'https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/'+role,'received_at':'2026-10-15T08:00:00+00:00','original_complete':True,'status_code':200,'sha256':hashlib.sha256(body).hexdigest()})
    return {'sdk_version':SDK_VERSION,'sdk_source_sha256':SDK_SOURCE_SHA,'status':'CAPTURED','captures':captures,'date_selections':{'BALANCE':['2026-06-30'],'CASH_FLOW':['2026-06-30']}}


def test_saved_three_statements_join_full_identities_and_replay(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        base='/api/market/financial/SSE:600362'
        client.post('/api/market/watch',json={'operation':'ADD','instrument':'SSE:600362','expected_list_version':client.get('/api/market/list').json()['version']})
        policy=next(p for p in client.get('/api/research/collection-sources').json() if p['id']=='akshare-financial-em')
        client.post('/api/research/collection-sources/akshare-financial-em/policy',json={'enabled':True,'expected_revision':policy['revision'],'basis':'METHOD isolated three statements'})
        client.app.state.financial_statements.worker=statements
        command={'idempotency_key':'three-once','basis':'METHOD fixture from issuer statement; no network'}
        saved=client.post(base+'/statements/collect',json=command)
        assert saved.status_code==201,saved.text
        saved=saved.json();assert saved['status']=='COMPLETE',saved
        assert len(saved['facts'])==2 and saved['network_calls']==0
        value=client.get(base+'/statements').json()
        group=value['groups'][0]
        assert group['balance_check']=={'status':'WITHIN_ROUNDING','difference':'0','tolerance':'1.5'}
        assert group['status']=='MISSING_STATEMENTS' and group['missing']==['INCOME']
        assert group['facts']['BALANCE']['period_basis']=='POINT_IN_TIME'
        assert group['facts']['CASH_FLOW']['values']['investing_cash_flow']=='-23434970323'
        assert group['facts']['CASH_FLOW']['period_basis']=='YEAR_TO_DATE'
        async def income(instrument,output):
            m=json.loads((CAPTURE/'capture.json').read_text())
            for c in m['captures']:(output/c['raw_file']).write_bytes((CAPTURE/c['raw_file']).read_bytes())
            return m
        client.app.state.financial.worker=income
        assert client.post(base+'/income/collect',json={**command,'idempotency_key':'SUPPLEMENT:three-once'}).json()['status']=='COMPLETE'
        complete=next(g for g in client.get(base+'/statements').json()['groups'] if g['report_period']=='2026-06-30')
        assert complete['status']=='MATCHED' and complete['missing']==[]
        assert set(complete['versions'])=={'BALANCE','CASH_FLOW','INCOME'}
        assert client.get(base+'/statements',params={'known_by':'2025-12-31T00:00:00+00:00'}).json()['groups']==[]
        assert client.post(base+'/statements/collect',json=command).json()==saved
        assert client.get('/api/account').json()['version']==0
    with TestClient(create_app(tmp_path)) as client:
        assert next(g for g in client.get(base+'/statements').json()['groups'] if g['report_period']=='2026-06-30')['status']=='MATCHED'


def test_three_statement_anomalies_are_visible_without_overwriting_originals(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        base='/api/market/financial/SSE:600362'
        client.post('/api/market/watch',json={'operation':'ADD','instrument':'SSE:600362','expected_list_version':client.get('/api/market/list').json()['version']})
        policy=next(p for p in client.get('/api/research/collection-sources').json() if p['id']=='akshare-financial-em')
        client.post('/api/research/collection-sources/akshare-financial-em/policy',json={'enabled':True,'expected_revision':policy['revision'],'basis':'METHOD isolated anomalies'})
        for name,field,value in [('imbalance','TOTAL_LIABILITIES',-1),('missing','TOTAL_EQUITY',None),('currency','CURRENCY','USD'),('period','REPORT_DATE','2026-03-31 00:00:00')]:
            async def changed(instrument,output):
                m=await statements(instrument,output);body=json.loads((output/'01.raw').read_bytes());body['data'][0][field]=value
                raw=json.dumps(body).encode();(output/'01.raw').write_bytes(raw);m['captures'][0]['sha256']=hashlib.sha256(raw).hexdigest()
                if name=='period':m['date_selections']['BALANCE']=['2026-03-31']
                return m
            client.app.state.financial_statements.worker=changed
            run=client.post(base+'/statements/collect',json={'idempotency_key':name,'basis':'METHOD explicit malformed source variant'}).json()
            assert run['status']=='COMPLETE',run
            balance=next(f for f in run['facts'] if f['statement']=='BALANCE')
            assert balance['original_fields'][field]==value
            group=next(g for g in client.get(base+'/statements').json()['groups'] if g['versions'].get('BALANCE')==balance['fact_id'])
            if name=='imbalance':assert group['balance_check']=={'status':'REQUIRES_REVIEW','difference':'192017045264','tolerance':'1.5'}
            if name=='missing':assert group['balance_check']['status']=='UNKNOWN'
            if name in ('currency','period'):assert group['status']=='UNVERIFIED_SCOPE' and 'CASH_FLOW' not in group['facts']
        count=len(client.get(base+'/statements').json()['facts'])
        async def duplicated(instrument,output):
            m=await statements(instrument,output);raw=(output/'01.raw').read_bytes().replace(b'"TOTAL_ASSETS":',b'"TOTAL_ASSETS": 1, "TOTAL_ASSETS":');(output/'01.raw').write_bytes(raw);m['captures'][0]['sha256']=hashlib.sha256(raw).hexdigest();return m
        client.app.state.financial_statements.worker=duplicated
        result=client.post(base+'/statements/collect',json={'idempotency_key':'duplicate','basis':'METHOD duplicated JSON column'}).json()
        assert result['status']=='FAILED' and 'FINANCIAL_DUPLICATED_COLUMN' in result['errors'][0]
        assert len(client.get(base+'/statements').json()['facts'])==count
