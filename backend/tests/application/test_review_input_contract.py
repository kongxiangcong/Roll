import json
import sqlite3

import httpx
import pytest
from fastapi.testclient import TestClient

from roll.app import create_app
from test_independent_verification import acquire,command,original_quote
from test_source_resolution import setup_request
from test_reviews import wait_result


def frozen_observation(client):
    setup_request(client);ref=acquire(client)
    task=wait_result(client,client.post('/api/reviews/tasks',json={'mode':'ON_DEMAND'}).json()['task_id'])
    return task,command([ref])


@pytest.mark.parametrize('name,size',[('reason',2001),('fact_id',101),('field',81)])
def test_review_creation_rejects_consumer_length_limits_before_persisting(tmp_path,name,size):
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,content=original_quote('A:first'))))) as client:
        task,payload=frozen_observation(client)
        if name=='reason':payload[name]='x'*size
        else:payload['facts'][0][name]='x'*size
        response=client.post('/api/reviews/tasks/'+task['task_id']+'/verification-request',json=payload)
        assert response.status_code==422,response.text
        assert any(error['type']=='string_too_long' and error['loc'][-1]==name for error in response.json()['detail'])
        assert client.get('/api/reviews/audits/'+task['audit_id']).json()['critical_review']['status']=='NOT_REQUIRED'


def test_old_incompatible_saved_request_is_actionably_refused_without_rewriting_history(tmp_path):
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,content=original_quote('A:first')))),raise_server_exceptions=False) as client:
        task,payload=frozen_observation(client)
        saved=client.post('/api/reviews/tasks/'+task['task_id']+'/verification-request',json=payload).json()
        # External persisted state from the old producer version; not a new API bypass.
        old={**saved,'request':{**saved['request'],'reason':'x'*2001}}
        with sqlite3.connect(tmp_path/'roll.sqlite3') as db:
            db.execute('UPDATE review_verification_requests SET value=? WHERE id=?',(json.dumps(old),saved['request_id']))
        response=client.post('/api/reviews/verification-requests/'+saved['request_id']+'/verify')
        assert response.status_code==409,response.text
        assert response.json()['detail']['code']=='SAVED_VERIFICATION_INPUT_INCOMPATIBLE'
        assert '重新提交' in response.json()['detail']['reason']
        assert len(response.content)<1000
        assert client.get('/api/reviews/verification-requests/'+saved['request_id']).json()==old
        assert client.get('/api/reviews/tasks/'+task['task_id']).json()['result']==task['result']
        assert client.get('/api/data/verifications').json()==[]
