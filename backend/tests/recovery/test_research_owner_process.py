"""Real HTTP/SQLite and owned OS processes; no model or provider requests."""
from test_account_process import Server
from roll.agents.codex_process import Job,owner_alive
import time


ATTEMPT={'category':'PRIMARY_FIT','partition':'DEVELOPMENT','configuration':{'candidate_id':'PRICE_VOLUME_LOGIT_V1'},'basis':'owned OS lifecycle evidence'}


def test_live_peer_and_dead_owner_have_distinct_recovery_outcomes(tmp_path):
    directory=tmp_path/'data'
    first=Server(directory)
    peer=None
    job=None
    try:
        protocol=first.client.post('/api/research/protocols',json={'basis':'actual OS peer lifecycle'}).json()
        path='/api/research/protocols/'+protocol['protocol_id']
        attempt=first.client.post(path+'/attempts',json=ATTEMPT).json()
        # Windows' venv redirector may have a distinct PID from the actual host.
        assert owner_alive(attempt)
        assert attempt['host_owner']['creation_ticks']
        job=Job(attempt['host_owner']['pid'])
        peer=Server(directory)
        assert peer.client.get(path+'/attempts').json()[0]['status']=='RUNNING'
        assert first.client.post('/api/research/attempts/'+attempt['attempt_id']+'/finish',json={'status':'FAILED','reason':'original active process finishes'}).status_code==200
        unfinished=first.client.post(path+'/attempts',json=ATTEMPT).json()
        job.terminate()
        first.stop()
        deadline=time.monotonic()+5
        while owner_alive(unfinished) and time.monotonic()<deadline:time.sleep(.01)
        assert not owner_alive(unfinished)
        assert job.pids()==[]
        replacement=Server(directory)
        try:
            observed=replacement.client.get(path+'/attempts').json()
            assert [value['status'] for value in observed]==['FAILED','INTERRUPTED']
            events=replacement.client.get(path+'/audit').json()
            interruptions=[e for e in events if e['action']=='ATTEMPT_INTERRUPTED']
            assert len(interruptions)==1
            assert interruptions[0]['attempt_id']==unfinished['attempt_id']
            assert peer.client.get(path+'/attempts').json()==observed
        finally:replacement.stop()
    finally:
        first.stop()
        if job:job.close()
        if peer:peer.stop()
