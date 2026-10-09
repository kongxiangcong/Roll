from fastapi.testclient import TestClient
from roll.app import create_app
from test_market_directory import establish
import httpx


def acquire(client):
    establish(client,['SSE:600362'])
    client.post('/api/market/identities',json={'instrument':'SSE:600362','exchange':'SSE','board':'MAIN',
        'instrument_type':'STOCK','name':'江西铜业','basis':'明确合成主板身份','effective_at':'2026-10-07T00:00:00+08:00'})
    request=client.post('/api/data/requests',json={'instruments':['SSE:600362'],'groups':['DAILY'],
        'purpose':'RESEARCH','start_date':'2026-09-28','end_date':'2026-09-30'}).json()
    run=client.post('/api/data/requests/'+request['request_id']+'/retrieve').json()
    assert run['status']=='COMPLETE',run
    return run


def provider(request):
    return httpx.Response(200,json={'rc':0,'data':{'code':'600362','market':1,'klines':[
        '2026-09-28,40,40,41,39,100,400000','2026-09-29,41,41,42,40,100,410000',
        '2026-09-30,42,42,43,41,100,420000']}})


def test_host_acquisition_import_is_source_backed_and_never_invents_historical_windows_or_account_authority(tmp_path):
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        run=acquire(client)
        before=client.get('/api/account').json()
        response=client.post('/api/research/datasets',json={'source_run_id':run['run_id'],'basis':'仅从宿主实际归档登记覆盖，不认定历史PIT'})
        assert response.status_code==201,response.text
        dataset=response.json()
        assert dataset['source_origin']=='HOST_DATA_REQUEST'
        assert dataset['source_run_id']==run['run_id'] and dataset['source_snapshot_id']==run['snapshot_id']
        assert dataset['scope']['instruments']==['SSE:600362']
        assert dataset['scope']['source_account_authority']=='NONE; MARKET_DATA_ONLY'
        assert dataset['coverage']['session_count']==3
        assert dataset['coverage']['missing_amount_rows']==0
        assert dataset['coverage']['first_date']=='2026-09-28'
        assert dataset['coverage']['daily_sources']==['eastmoney-daily']
        assert not dataset['scope']['historical_point_in_time_proven']
        assert dataset['training_readiness']['state']=='BLOCKED'
        assert 'HISTORICAL_POINT_IN_TIME_NOT_PROVEN' in dataset['training_readiness']['blockers']
        assert 'RESEARCH_WINDOWS_NOT_PREREGISTERED' in dataset['training_readiness']['blockers']
        assert all(p['state']=='NOT_PREREGISTERED' for p in dataset['partitions'].values())
        assert client.get('/api/research/datasets/'+dataset['dataset_id']+'/partitions/DEVELOPMENT').status_code==409
        assert client.get('/api/research/datasets/'+dataset['dataset_id']+'/partitions/SEALED').status_code==403
        assert client.get('/api/account').json()==before
        protocol=client.post('/api/research/protocols',json={'dataset_id':dataset['dataset_id'],'basis':'覆盖登记不等于可拟合协议'}).json()
        assert protocol['status']=='DATA_COVERAGE_REGISTERED'
        assert 'RESEARCH_WINDOWS_NOT_PREREGISTERED' in protocol['freeze_gaps']
        response=client.post('/api/research/protocols/'+protocol['protocol_id']+'/models',json={'basis':'公开入口拒绝不可时点训练'})
        assert response.status_code==409,response.text
        detail=response.json()['detail']
        assert detail['code']=='TRAINING_ADMISSION_BLOCKED' and detail['attempt_started'] is False
        assert 'RESEARCH_WINDOWS_NOT_PREREGISTERED' in detail['blockers']
        assert 'HISTORICAL_POINT_IN_TIME_NOT_PROVEN' in detail['blockers']
        assert client.get('/api/research/protocols/'+protocol['protocol_id']+'/attempts').json()==[]
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/research/datasets').json()[0]==dataset
        assert client.get('/api/research/protocols/'+protocol['protocol_id']+'/models').json()==[]


def test_import_refuses_corrupt_original_before_registering_dataset(tmp_path):
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        run=acquire(client)
        snapshot=client.get('/api/data/snapshots/'+run['snapshot_id']).json()
        source=snapshot['archives'][0]
        (tmp_path/source['path']).write_bytes(b'changed provider bytes')
        response=client.post('/api/research/datasets',json={'source_run_id':run['run_id'],'basis':'损坏的源不能成为研究输入'})
        assert response.status_code==409 and response.json()['detail']['code']=='ARCHIVE_MISSING_OR_CORRUPT'
        assert client.get('/api/research/datasets').json()==[]


def test_client_cannot_grant_as_of_eligibility_or_select_ambiguous_sources(tmp_path):
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        run=acquire(client)
        for extra in [{'historical_point_in_time_proven':True},{'eligible_for_training':True},{'archive_id':'method-181'}]:
            response=client.post('/api/research/datasets',json={'source_run_id':run['run_id'],'basis':'客户端声明不能替代源证据',**extra})
            assert response.status_code==422,response.text
        assert client.post('/api/research/datasets',json={'basis':'没有源标识'}).status_code==422
        assert client.get('/api/research/datasets').json()==[]
