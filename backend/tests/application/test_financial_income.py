import json
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app

CAPTURE=Path(__file__).resolve().parents[3]/'.scratch/roll-capability-expansion/evidence/09-financial/actual-source'


def test_income_raw_versions_failures_and_restart(tmp_path):
    calls=[]
    async def supplier(instrument,output):
        calls.append(instrument)
        manifest=json.loads((CAPTURE/'capture.json').read_text())
        for item in manifest['captures']:
            (output/item['raw_file']).write_bytes((CAPTURE/item['raw_file']).read_bytes())
        return manifest
    with TestClient(create_app(tmp_path)) as client:
        # A finite watch member, not a fabricated actual holding.
        version=client.get('/api/market/list').json()['version']
        assert client.post('/api/market/watch',json={'operation':'ADD','instrument':'SSE:600362','expected_list_version':version}).status_code==200
        base='/api/market/financial/SSE:600362/income'
        response=client.get(base)
        assert response.status_code==200,response.text
        assert response.json()['facts']==[]
        client.app.state.financial.worker=supplier
        policy=next(p for p in client.get('/api/research/collection-sources').json() if p['id']=='akshare-financial-em')
        assert not policy['enabled']
        command={'idempotency_key':'income-once','basis':'METHOD replay actual captured SDK entities, zero network'}
        assert client.post(base+'/collect',json=command).status_code==409
        assert not calls
        assert client.post('/api/research/collection-sources/akshare-financial-em/policy',json={'enabled':True,'expected_revision':policy['revision'],'basis':'Explicit isolated METHOD source scope'}).status_code==200
        response=client.post(base+'/collect',json=command)
        assert response.status_code==201,response.text
        saved=response.json()
        assert saved['status']=='COMPLETE' and saved['evidence_kind']=='METHOD_CASE'
        assert saved['network_calls']==0 and saved['upstream_entity_count']==3
        assert len(saved['facts'])==5
        fact=saved['facts'][0]
        assert fact['report_period']=='2026-06-30' and fact['values']['revenue']=='307154938743'
        assert fact['currency']=='CNY' and fact['unit']=='YUAN' and fact['statement_scope']=='CONSOLIDATED'
        assert fact['publication_precision']=='DATE' and not fact['historical_pit_eligible']
        assert client.get('/api/data/archives/'+fact['raw_sha256']).content==(CAPTURE/'03.raw').read_bytes()
        assert client.post(base+'/collect',json=command).json()==saved
        assert len(calls)==1
        second=client.post(base+'/collect',json={**command,'idempotency_key':'income-second'}).json()
        assert [f['fact_id'] for f in second['facts']]==[f['fact_id'] for f in saved['facts']]
        assert len(client.get(base).json()['facts'])==5
        old=next(f for f in saved['facts'] if f['report_period']=='2025-06-30')
        assert old['reported_update_date'].startswith('2026-08-26')
        assert client.get(base,params={'known_by':'2025-12-31T23:00:00+08:00'}).json()['facts']==[]
        async def broken(instrument,output):
            manifest=await supplier(instrument,output)
            (output/'03.raw').write_bytes(b'broken')
            return manifest
        client.app.state.financial.worker=broken
        failed=client.post(base+'/collect',json={**command,'idempotency_key':'corrupt'}).json()
        assert failed['status']=='FAILED' and len(client.get(base).json()['facts'])==5
        async def revised(instrument,output):
            import hashlib
            manifest=await supplier(instrument,output)
            content=json.loads((output/'03.raw').read_bytes())
            content['data'][0]['NOTICE_DATE']='2026-08-27 00:00:00'
            (output/'03.raw').write_text(json.dumps(content),encoding='utf-8')
            manifest['captures'][2]['sha256']=hashlib.sha256((output/'03.raw').read_bytes()).hexdigest()
            return manifest
        client.app.state.financial.worker=revised
        revision=client.post(base+'/collect',json={**command,'idempotency_key':'revision'}).json()
        assert revision['facts'][0]['version']==2 and revision['facts'][0]['supersedes_id']==fact['fact_id']
        assert len(client.get(base).json()['facts'])==6
        async def revised_amount(instrument,output):
            import hashlib
            manifest=await supplier(instrument,output)
            content=json.loads((output/'03.raw').read_bytes())
            content['data'][0]['TOTAL_OPERATE_INCOME']=307154938744
            content['data'][0]['UPDATE_DATE']='2026-10-15 00:00:00'
            (output/'03.raw').write_text(json.dumps(content),encoding='utf-8')
            manifest['captures'][2]['sha256']=hashlib.sha256((output/'03.raw').read_bytes()).hexdigest()
            return manifest
        client.app.state.financial.worker=revised_amount
        changed=client.post(base+'/collect',json={**command,'idempotency_key':'changed-amount'}).json()['facts'][0]
        assert changed['version']==3 and changed['supersedes_id']==revision['facts'][0]['fact_id']
        assert changed['unit']=='UNKNOWN' and changed['statement_scope']=='UNKNOWN'
        assert changed['comparable_with_superseded'] is False
        assert client.get('/api/account').json()['version']==0
    with TestClient(create_app(tmp_path)) as client:
        assert len(client.get(base).json()['facts'])==7
        assert client.post(base+'/collect',json=command).json()==saved


def test_income_active_capture_can_be_cancelled_without_versions(tmp_path):
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    import threading
    entered=threading.Event()
    async def supplier(instrument,output):
        entered.set()
        await asyncio.sleep(60)
    with TestClient(create_app(tmp_path)) as client:
        version=client.get('/api/market/list').json()['version']
        client.post('/api/market/watch',json={'operation':'ADD','instrument':'SSE:600362','expected_list_version':version})
        client.app.state.financial.worker=supplier
        policy=next(p for p in client.get('/api/research/collection-sources').json() if p['id']=='akshare-financial-em')
        client.post('/api/research/collection-sources/akshare-financial-em/policy',json={'enabled':True,'expected_revision':policy['revision'],'basis':'METHOD cancellation'})
        base='/api/market/financial/SSE:600362/income'
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending=pool.submit(client.post,base+'/collect',json={'idempotency_key':'cancel','basis':'METHOD cancel no network'})
            assert entered.wait(5)
            with client.app.state.ledger.connection() as db:
                identifier=db.execute('SELECT id FROM financial_income_runs').fetchone()[0]
            cancelled=client.post('/api/market/financial/runs/'+identifier+'/cancel')
            assert cancelled.status_code==200,cancelled.text
            assert pending.result(timeout=5).json()['status']=='CANCELLED'
        assert client.get(base).json()['facts']==[]
        assert client.get('/api/account').json()['version']==0
