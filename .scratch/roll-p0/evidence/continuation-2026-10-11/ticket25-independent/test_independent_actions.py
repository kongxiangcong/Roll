from concurrent.futures import ThreadPoolExecutor
import time
import pytest
from fastapi.testclient import TestClient
from roll.app import create_app
from capability_method_app import save_package
from test_actions import action_package, prepare
from test_funding import funding

@pytest.mark.parametrize('prior_receipt',[False,True])
@pytest.mark.parametrize('mutation,reason',[
    ('funding','CURRENT_VERSION_CHANGED_BEFORE_PUBLICATION'),
    ('membership','CURRENT_DATA_OR_LIST_CHANGED_BEFORE_PUBLICATION'),
    ('expiry','ACTION_EXPIRED_BEFORE_PUBLICATION'),
    ('valuation','CURRENT_DATA_OR_LIST_CHANGED_BEFORE_PUBLICATION'),
])
def test_latest_writer_boundary_on_initial_and_existing_receipt(tmp_path,monkeypatch,prior_receipt,mutation,reason):
    monkeypatch.setenv('ROLL_ENV','test')
    p=action_package()
    p['action_packet']['method_publish_delay_ms']=2000
    method=save_package(tmp_path/'qualification.json',p)
    data=tmp_path/'data'
    with TestClient(create_app(data,capability_method_file=method)) as client:
        prepare(client,p)
        before=client.get('/api/account').json()
        original=client.post('/api/actions/evaluate',json={}).json() if prior_receipt else None
        if original:assert len(original['decisions'])==1
        with ThreadPoolExecutor(max_workers=2) as pool:
            computing=pool.submit(client.post,'/api/actions/evaluate',json={})
            time.sleep(.5)
            if mutation=='funding':
                response=client.post('/api/funding/confirm',json=funding(2,total_exposure='10000.00',single_exposure='10000.00',cash_reserve='90000.00'))
                assert response.status_code==200,response.text
            elif mutation=='membership':
                listing=client.get('/api/market/list').json()
                response=client.post('/api/market/watch',json={'instrument':'SSE:600000','operation':'REMOVE','expected_list_version':listing['version']})
                assert response.status_code==200,response.text
            elif mutation=='expiry':
                monkeypatch.setattr('roll.decisions.actions.now',lambda:p['expires_at'])
            else:
                response=client.post('/api/account/valuations',json={'as_of':p['required_as_of'],'origin_at':'2026-10-07T10:00:00+08:00','scope_kind':'ACCOUNT','scope_id':'account-1','baseline_account_version':2})
                assert response.status_code==201,response.text
            published=computing.result()
        assert published.status_code==201,published.text
        result=published.json()
        assert result['decisions']==[]
        assert result['limitations']==[reason]
        assert result['publication_check']['refusal']==[reason]
        if original:
            assert result['evaluation_id']!=original['evaluation_id']
            assert client.get('/api/actions/evaluations/'+original['evaluation_id']).json()==original
        assert client.get('/api/account').json()==before
        assert client.get('/api/actions/current').json()['decisions']==[]
        assert client.post('/api/actions/evaluations/'+result['evaluation_id']+'/replay').json()['matches_original']
    with TestClient(create_app(data,capability_method_file=method)) as client:
        assert client.get('/api/actions/evaluations/'+result['evaluation_id']).json()==result
        replay=client.post('/api/actions/evaluations/'+result['evaluation_id']+'/replay').json()
        assert replay['matches_original'] and replay['network_calls']==0
        assert client.get('/api/actions/current').json()['decisions']==[]
