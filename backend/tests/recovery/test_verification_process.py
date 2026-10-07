import httpx
import json
import pytest
from fastapi.testclient import TestClient

from roll.app import create_app
from test_account_process import Server


def original_quote(origin):
    return json.dumps({'instrument':'SSE:600519','method_case_status':'NORMAL','last':'100.000',
        'upstream_at':'2026-09-30T15:00:00+08:00','basis':'METHOD_CASE crash fixture',
        '_roll14_original_provenance':{'original_record':origin,'producer':origin.split(':')[0],
            'generation_basis':'METHOD_CASE independent generation','origin_kind':'DIRECT_ORIGINAL'}}).encode()


def acquire(client):
    request=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['QUOTE'],
        'purpose':'OBSERVATION','start_date':'2026-09-30','end_date':'2026-09-30'}).json()
    run=client.post('/api/data/requests/'+request['request_id']+'/retrieve').json()
    return {'snapshot_id':run['snapshot_id'],'fact_index':0}


def command(refs):
    return {'trigger':'USER_SELECTED','reason':'METHOD_CASE crash durability check',
        'facts':[{'fact_id':'price','field':'last','references':refs}]}


@pytest.mark.parametrize('fault,count',[('verification_before_commit',0),('verification_after_commit',1),('after_receipt',1)])
def test_verification_record_and_original_values_survive_native_crash_and_restart(tmp_path,fault,count):
    directory=tmp_path/'data';raw=[original_quote('A:first')]
    with TestClient(create_app(directory,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,content=raw[0])))) as client:
        listing=client.get('/api/market/list').json()
        assert client.post('/api/market/watch',json={'operation':'ADD','instrument':'SSE:600519',
            'expected_list_version':listing['version']}).status_code==200
        a=acquire(client)
        raw[0]=original_quote('B:second');b=acquire(client)
    server=Server(directory,None if fault=='after_receipt' else fault)
    original=None
    try:
        if fault=='after_receipt':
            response=server.client.post('/api/data/verifications',json=command([a,b]))
            assert response.status_code==201,response.text
            original=response.json()
        else:
            with pytest.raises(httpx.TransportError):server.client.post('/api/data/verifications',json=command([a,b]))
            assert server.process.wait(timeout=10)==86
    finally:server.stop()
    restarted=Server(directory)
    try:
        history=restarted.client.get('/api/data/verifications').json()
        assert len(history)==count
        if not history:history=[restarted.client.post('/api/data/verifications',json=command([a,b])).json()]
        record=history[0]
        assert record['evidence_kind']=='METHOD_CASE'
        assert record['result']=='VERIFIED' and record['formal_judgment']=='DISABLED'
        assert [e['value'] for e in record['facts'][0]['evidence']]==['100.000','100.000']
        if original:assert record==original
        replay=restarted.client.post('/api/data/verifications/'+record['verification_id']+'/replay').json()
        assert replay['facts']==record['facts'] and replay['network_calls']==0
    finally:restarted.stop()


@pytest.mark.parametrize('fault,consumed',[('verification_before_commit',False),('verification_after_commit',True)])
def test_review_verification_and_audit_link_commit_together_across_native_crash(tmp_path,fault,consumed):
    import time
    directory=tmp_path/'data';raw=[original_quote('A:first')]
    with TestClient(create_app(directory,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,content=raw[0])))) as client:
        listing=client.get('/api/market/list').json()
        client.post('/api/market/watch',json={'operation':'ADD','instrument':'SSE:600519','expected_list_version':listing['version']})
        a=acquire(client);raw[0]=original_quote('B:second');b=acquire(client)
        task=client.post('/api/reviews/tasks',json={'mode':'ON_DEMAND'}).json()
        for _ in range(100):
            task=client.get('/api/reviews/tasks/'+task['task_id']).json()
            if task.get('result'):break
            time.sleep(.02)
        assert task['result']
        request=client.post('/api/reviews/tasks/'+task['task_id']+'/verification-request',json=command([a,b])).json()
    path='/api/reviews/verification-requests/'+request['request_id']
    server=Server(directory,fault)
    try:
        with pytest.raises(httpx.TransportError):server.client.post(path+'/verify')
        assert server.process.wait(timeout=10)==86
    finally:server.stop()
    restarted=Server(directory)
    try:
        saved=restarted.client.get(path).json()
        audit=restarted.client.get('/api/reviews/audits/'+task['audit_id']).json()
        assert (saved['status']=='CONSUMED') is consumed
        assert bool(saved['verification_id']) is consumed
        assert bool(audit['critical_review']['verification_id']) is consumed
        assert len(restarted.client.get('/api/data/verifications').json())==int(consumed)
        value=restarted.client.post(path+'/verify').json()
        assert value['result']=='VERIFIED'
        assert restarted.client.post(path+'/verify').json()['verification_id']==value['verification_id']
        assert len(restarted.client.get('/api/data/verifications').json())==1
        assert restarted.client.get('/api/reviews/tasks/'+task['task_id']).json()['result']==task['result']
    finally:restarted.stop()
