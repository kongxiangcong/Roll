import json,httpx
from fastapi.testclient import TestClient
from roll.app import create_app
def forbidden(r):raise AssertionError('diagnosis must not acquire source')
with TestClient(create_app('D:/dsh-proj/Roll/.roll-data/t30si-worker-corrected/test_shared_worker_and_restart0',market_transport=httpx.MockTransport(forbidden),runtime_role='API')) as c:
    pid=c.get('/api/research/collections').json()[0]['plan_id']
    r=c.post('/api/research/collections/'+pid+'/post-close/check',json={'basis':'Read same persisted refused worker for diagnosis'})
    print(json.dumps(r.json(),ensure_ascii=False))
