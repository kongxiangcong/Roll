import json
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from roll.app import create_app
from roll.accounts.ledger import encode
from roll.runtime import observation_updates
from test_news_events import register
from test_observation_updates import configure, BASE, submit, start, wait


def finish(service,job,clock,status='PARTIAL',ready=False,error=None):
    value={**job,'status':status,'source_ready':ready,'finished_at':clock.isoformat(),'error':error}
    with service.ledger.connection() as db:
        db.execute('UPDATE observation_update_jobs SET value=? WHERE id=?',(encode(value),job['job_id']))
    return value


def test_bounded_retry_clock_cancel_pause_restart(tmp_path):
    clock=datetime.fromisoformat('2026-10-20T15:06:00+08:00')
    with TestClient(create_app(tmp_path,runtime_role='API')) as c:
        configure(c,market_postclose=True)
        service=c.app.state.observation_updates
        service.schedule(clock);service.schedule(clock)
        jobs=c.get(BASE).json()['jobs'];assert len(jobs)==1
        first=finish(service,jobs[0],clock)
        service.schedule(clock+timedelta(minutes=14));assert len(c.get(BASE).json()['jobs'])==1
        service.schedule(clock+timedelta(minutes=15));jobs=c.get(BASE).json()['jobs'];assert len(jobs)==2
        assert jobs[0]['retry_of']==first['job_id'] and jobs[0]['scheduled_attempt']==2
        finish(service,jobs[0],clock+timedelta(minutes=15))
    with TestClient(create_app(tmp_path,runtime_role='API')) as c:
        service=c.app.state.observation_updates
        service.schedule(clock+timedelta(minutes=30));service.schedule(clock+timedelta(minutes=30))
        jobs=c.get(BASE).json()['jobs'];assert len(jobs)==3
        finish(service,jobs[0],clock+timedelta(minutes=30),'FAILED')
        service.schedule(clock+timedelta(hours=1));assert len(c.get(BASE).json()['jobs'])==3
        assert all(j['scheduled_checkpoint'].startswith('2026-10-20') for j in jobs)
        service.schedule(datetime.fromisoformat('2026-10-21T21:01:00+08:00'));assert len(c.get(BASE).json()['jobs'])==3
        service.schedule(datetime.fromisoformat('2026-10-21T15:06:00+08:00'))
        job=c.get(BASE).json()['jobs'][0];finish(service,job,clock,'CANCELLED',error='USER_CANCELLED')
        service.schedule(datetime.fromisoformat('2026-10-21T16:06:00+08:00'));assert len(c.get(BASE).json()['jobs'])==4


def test_ready_stops_retry_source_pause_honored(tmp_path):
    clock=datetime.fromisoformat('2026-10-20T15:06:00+08:00')
    with TestClient(create_app(tmp_path,runtime_role='API')) as c:
        configure(c,market_postclose=True,news_refresh=True)
        service=c.app.state.observation_updates;service.schedule(clock)
        job=c.get(BASE).json()['jobs'][0]
        finish(service,job,clock,'COMPLETE',True)
        service.schedule(clock+timedelta(hours=1));assert len(c.get(BASE).json()['jobs'])==1
        finish(service,job,clock,'PARTIAL',False)
        policy=next(p for p in c.get('/api/research/collection-sources').json() if p['id']=='sohu-daily')
        c.post('/api/research/collection-sources/sohu-daily/policy',json={'enabled':False,'expected_revision':policy['revision'],'basis':'METHOD pause'})
        service.schedule(clock+timedelta(hours=1));assert len(c.get(BASE).json()['jobs'])==1


def test_worker_publishes_report_without_browser_and_preserves_initial(tmp_path):
    with TestClient(create_app(tmp_path,runtime_role='API')) as c:
        configure(c)
        first=c.post('/api/daily-reports',json={}).json()
        job,_=submit(c,'publish','MARKET',False);start(c);wait(c,job)
        import time
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            history=c.get('/api/daily-reports').json()
            if len(history)>1:break
            time.sleep(.05)
        assert len(history)>1 and history[0]['edition']=='UPDATE'
        assert c.get('/api/daily-reports/'+first['report_id']).json()==first
        assert c.post('/api/daily-reports',json={}).json()==history[0]
