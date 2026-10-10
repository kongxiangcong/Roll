import threading
import sqlite3

import httpx
from fastapi.testclient import TestClient

from roll.app import create_app
from test_source_resolution import setup_request,quote_bytes,completed
from test_research_protocol import engineering_archive
from test_execution_labels import method_archive,register


ATTEMPT={'category':'PRIMARY_FIT','partition':'DEVELOPMENT','configuration':{'candidate_id':'PRICE_VOLUME_LOGIT_V1'},'basis':'METHOD lifecycle evidence'}


def test_peer_host_keeps_live_attempt_and_original_host_can_finish(tmp_path):
    with TestClient(create_app(tmp_path)) as first:
        protocol=first.post('/api/research/protocols',json={'basis':'live peer host test'}).json()
        pid=protocol['protocol_id'];attempt=first.post('/api/research/protocols/'+pid+'/attempts',json=ATTEMPT).json()
        with TestClient(create_app(tmp_path)) as peer:
            assert peer.get('/api/research/protocols/'+pid+'/attempts').json()[0]['status']=='RUNNING'
            response=first.post('/api/research/attempts/'+attempt['attempt_id']+'/finish',json={'status':'FAILED','reason':'original owner completed actual failure'})
            assert response.status_code==200,response.text
            assert peer.get('/api/research/protocols/'+pid+'/attempts').json()[0]['status']=='FAILED'
            assert not any(e['action']=='ATTEMPT_INTERRUPTED' for e in peer.get('/api/research/protocols/'+pid+'/audit').json())


def test_peer_host_keeps_active_source_resolution_while_original_provider_waits(tmp_path):
    entered=threading.Event();release=threading.Event()
    def provider(request):
        entered.set();assert release.wait(10)
        return httpx.Response(200,content=quote_bytes())
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as first:
        request=setup_request(first,quote_source='SINA')
        resolution=first.post('/api/data/requests/'+request['request_id']+'/resolve',json={'usage':'HISTORICAL_RESEARCH','allow_fallback':False}).json()
        try:
            assert entered.wait(5)
            with TestClient(create_app(tmp_path)) as peer:
                assert peer.get('/api/data/resolutions/'+resolution['resolution_id']).json()['status']=='RUNNING'
        finally:release.set()
        assert completed(first,resolution['resolution_id'])['status']=='COMPLETED'


def test_overlapping_sibling_manifest_and_budget_include_failed_family_attempts(tmp_path):
    engineering_archive(tmp_path)
    with TestClient(create_app(tmp_path)) as client:
        dataset=client.post('/api/research/datasets',json={'archive_id':'method-181','basis':'same original interval'}).json()
        a=client.post('/api/research/protocols',json={'dataset_id':dataset['dataset_id'],'basis':'A registered'}).json()
        b=client.post('/api/research/protocols',json={'dataset_id':dataset['dataset_id'],'predecessor_id':a['protocol_id'],'basis':'B successor'}).json()
        attempts=[]
        for _ in range(5):
            attempt=client.post('/api/research/protocols/'+b['protocol_id']+'/attempts',json=ATTEMPT).json();attempts.append(attempt['attempt_id'])
            assert client.post('/api/research/attempts/'+attempt['attempt_id']+'/finish',json={'status':'FAILED','reason':'actual failure retained'}).status_code==200
        assert client.post('/api/research/protocols/'+b['protocol_id']+'/attempts',json=ATTEMPT).status_code==409
        c=client.post('/api/research/protocols',json={'dataset_id':dataset['dataset_id'],'predecessor_id':a['protocol_id'],'basis':'C from same old parent'}).json()
        assert client.post('/api/research/protocols/'+c['protocol_id']+'/attempts',json=ATTEMPT).status_code==409
        manifest=client.get('/api/research/protocols/'+c['protocol_id']+'/attempt-manifest').json()
        assert set(manifest['attempt_ids'])==set(attempts)
        assert all(a['status']=='FAILED' for a in manifest['attempts'])
        response=client.post('/api/research/protocols/'+c['protocol_id']+'/freeze',json={'attempt_ids':[]})
        assert 'ATTEMPT_MANIFEST_INCOMPLETE' in response.json()['detail']['gaps']
        calibration={**ATTEMPT,'category':'CALIBRATION','partition':'CALIBRATION'}
        calibrated=client.post('/api/research/protocols/'+b['protocol_id']+'/attempts',json=calibration).json()
        assert client.post('/api/research/attempts/'+calibrated['attempt_id']+'/finish',json={'status':'ABORTED','reason':'failed calibration retained across sibling branches'}).status_code==200
        assert client.post('/api/research/protocols/'+c['protocol_id']+'/attempts',json=calibration).status_code==409
        assert len(client.get('/api/research/protocols/'+c['protocol_id']+'/attempt-manifest').json()['attempts'])==6


def test_peer_leaves_method_pending_execution_owned_by_live_host_unchanged(tmp_path):
    """External persisted-state fixture represents the committed pre-result boundary."""
    method_archive(tmp_path)
    with TestClient(create_app(tmp_path)) as first:
        _,protocol=register(first)
        response=first.post('/api/research/protocols/'+protocol['protocol_id']+'/executions',json={
            'partition':'DEVELOPMENT','observation_date':'2026-01-05','label_as_of':'2026-01-06T16:00:00+08:00','basis':'explicit METHOD pending-state fixture'})
        assert response.status_code==201,response.text
        run=response.json();identifier=run['execution_id']
        with sqlite3.connect(tmp_path/'roll.sqlite3') as db:
            completion=db.execute('SELECT value FROM research_execution_results WHERE id=?',(identifier,)).fetchone()[0]
            finished=db.execute("SELECT ordinal,protocol_id,value FROM research_events WHERE json_extract(value,'$.action')='EXECUTION_FINISHED' AND json_extract(value,'$.execution_id')=?",(identifier,)).fetchall()
            db.execute('DELETE FROM research_execution_results WHERE id=?',(identifier,))
            db.executemany('DELETE FROM research_events WHERE ordinal=?',[(row[0],) for row in finished])
        try:
            with TestClient(create_app(tmp_path)) as peer:
                observed=peer.get('/api/research/executions/'+identifier).json()
                assert observed['status']=='RUNNING'
                assert observed['host_owner']==run['host_owner']
                assert observed['definition']==run['definition']
                assert observed['input_archive']==run['input_archive']
                assert observed['data_fingerprint']==run['data_fingerprint']
            assert first.get('/api/research/executions/'+identifier).json()['status']=='RUNNING'
        finally:
            with sqlite3.connect(tmp_path/'roll.sqlite3') as db:
                db.execute('INSERT OR REPLACE INTO research_execution_results VALUES(?,?)',(identifier,completion))
                db.executemany('INSERT INTO research_events(ordinal,protocol_id,value) VALUES(?,?,?)',finished)
        assert first.get('/api/research/executions/'+identifier).json()==run
