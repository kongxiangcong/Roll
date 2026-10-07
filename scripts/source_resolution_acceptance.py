"""08 isolated real HTTP/process acceptance; separate real providers and method wait."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import httpx

from account_confirmation_performance import measure_confirmations


def checked(response):
    response.raise_for_status()
    return response.json()


def establish(client):
    draft=checked(client.post('/api/account/drafts',json={'kind':'BASELINE','expected_account_version':0,
        'payload':{'effective_at':'2026-10-07T00:00:00+08:00','source':'08隔离合成确认性能基线',
            'cash_balance':'1000000','broker_available':None,'broker_frozen':None,'withdrawable':None,
            'permission_profile':[],'positions':[{'instrument':'SSE:600519','quantity':'100','sellable_quantity':None,'reference_cost':None}]}}))
    checked(client.post('/api/account/confirm',json={'draft_id':draft['draft_id'],'idempotency_key':'08-perf-baseline'}))
    checked(client.post('/api/market/identities',json={'instrument':'SSE:600519','exchange':'SSE','board':'MAIN',
        'instrument_type':'STOCK','name':'贵州茅台','basis':'08合成账户身份；真实取数对象公开证券',
        'effective_at':'2026-10-07T00:00:00+08:00'}))


def serve(backend,directory,port,method):
    env={**os.environ,'ROLL_DATA_DIR':str(directory),'ROLL_ENV':'test'}
    target='roll.app:create_app'
    if method:
        directory.mkdir(parents=True,exist_ok=True)
        (directory/'acceptance_app.py').write_text('''import time
import httpx
from roll.app import create_app
def wait(request):
    time.sleep(6)
    raise httpx.ReadTimeout("08 fixed method read timeout after controlled six-second callback wait",request=request)
def factory():
    return create_app(market_transport=httpx.MockTransport(wait))
''',encoding='utf-8')
        env['PYTHONPATH']=str(directory)+os.pathsep+env.get('PYTHONPATH','')
        target='acceptance_app:factory'
    directory.mkdir(parents=True,exist_ok=True)
    log=(directory/'server.log').open('ab')
    process=subprocess.Popen([sys.executable,'-X','utf8','-m','uvicorn',target,'--factory','--host','127.0.0.1','--port',str(port)],
        cwd=backend,env=env,stdout=log,stderr=subprocess.STDOUT)
    deadline=time.monotonic()+25
    while time.monotonic()<deadline:
        if process.poll() is not None:raise RuntimeError('isolated server exited; inspect '+str(directory/'server.log'))
        try:
            if httpx.get(f'http://127.0.0.1:{port}/api/health').status_code==200:return process,log
        except httpx.HTTPError:pass
        time.sleep(.1)
    process.terminate();process.wait(timeout=10);log.close()
    raise RuntimeError('isolated server did not become ready')


def stop(process,log):
    process.terminate()
    process.wait(timeout=15)
    log.close()


def measure(backend,directory,port,method):
    process,log=serve(backend,directory,port,method)
    base=f'http://127.0.0.1:{port}'
    try:
        with httpx.Client(base_url=base,timeout=30) as client:
            establish(client)
            command={'instruments':['SSE:600519'],'groups':['QUOTE'] if method else ['DAILY'],
                'purpose':'OBSERVATION','start_date':'2026-09-29','end_date':'2026-09-30',
                'required_fields':['QUOTE.last'] if method else ['DAILY.close'],'max_calls':1 if method else 4,
                'timeout_seconds':10 if method else 30}
            request=checked(client.post('/api/data/requests',json=command))
            started=time.perf_counter()
            accepted=checked(client.post('/api/data/requests/'+request['request_id']+'/resolve',json={'usage':'HISTORICAL_RESEARCH'}))
            accepted_ms=(time.perf_counter()-started)*1000
            windows=[];errors=[];finished=threading.Event();confirmation_times=[]
            def poll():
                try:
                    with httpx.Client(base_url=base,timeout=15) as reader:
                        while not finished.is_set():
                            value=checked(reader.get('/api/data/resolutions/'+accepted['resolution_id']))
                            windows.append({'at':time.perf_counter(),'status':value['status']})
                            if value['status']!='RUNNING':return
                            time.sleep(.025)
                except Exception as error:errors.append(type(error).__name__+': '+str(error))
            thread=threading.Thread(target=poll);thread.start()
            def response_hook(response):
                if response.request.url.path=='/api/account/confirm':confirmation_times.append(time.perf_counter())
            client.event_hooks['response']=[response_hook]
            performance=measure_confirmations(client,100,10)
            thread.join(timeout=40);finished.set()
            if thread.is_alive() or errors:raise AssertionError('resolution polling did not complete: '+str(errors))
            resolution=checked(client.get('/api/data/resolutions/'+accepted['resolution_id']))
            assert resolution['status']=='COMPLETED',resolution
            ended=next((w['at'] for w in windows if w['status']!='RUNNING'),time.perf_counter())
            overlap=[ms for at,ms in zip(confirmation_times[-100:],performance['samples_ms']) if at<=ended]
            performance.update(external_task_integration='SAME_PROCESS_HTTP_WITH_'+('CONTROLLED_METHOD_WAIT' if method else 'REAL_PROVIDER_ACQUISITION'),
                accepted_http_ms=accepted_ms,overlap_samples=len(overlap),
                overlap_p95_ms=sorted(overlap)[math.ceil(.95*len(overlap))-1] if overlap else None,
                overlap_observation='Response completion during polling-observed RUNNING interval; polling can overestimate overlap by one poll interval',
                resolution_poll_timeline=windows)
            assert performance['p95_ms']<=2000
            assert len(overlap)>0,'actual acquisition finished before measured confirmations; no concurrency claim'
            runs=[checked(client.get('/api/data/runs/'+a['run_id'])) for a in resolution['attempts']]
            report={'evidence_kind':'METHOD_WAIT_AND_FIXED_READ_TIMEOUT' if method else 'REAL_ACQUISITION',
                'method_boundary':'MockTransport six-second callback wait and raised ReadTimeout; not a real upstream timing measurement' if method else None,
                'runtime_data_directory':str(directory),'request':request,'resolution':resolution,'source_runs':runs,
                'confirmation_performance':performance,'replay':checked(client.post('/api/data/resolutions/'+resolution['resolution_id']+'/replay'))}
            if method:
                second=checked(client.post('/api/data/requests/'+request['request_id']+'/resolve',json={'usage':'HISTORICAL_RESEARCH','use_cache':False}))
                time.sleep(.25)
                assert checked(client.get('/api/data/resolutions/'+second['resolution_id']))['status']=='RUNNING'
                account_before=checked(client.get('/api/account'))
                stop(process,log);process,log=serve(backend,directory,port,method)
                recovered=checked(client.get('/api/data/resolutions/'+second['resolution_id']))
                assert recovered['status']=='INTERRUPTED'
                assert checked(client.get('/api/account'))==account_before
                assert checked(client.get('/api/data/replays/'+report['replay']['replay_id']))==report['replay']
                report['actual_process_restart']={'interrupted_resolution':recovered,'account_version_preserved':account_before['version'],
                    'prior_replay_preserved':report['replay']['replay_id'],'process_termination':'Owned subprocess terminate during six-second controlled method wait'}
            (directory/'acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            originals=[]
            for path in directory.rglob('*'):
                if path.is_file() and path.suffix in {'.raw','.parquet'}:
                    originals.append({'path':str(path),'size':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
            (directory/'originals.json').write_text(json.dumps(originals,indent=2),encoding='utf-8')
            return {'kind':report['evidence_kind'],'p95_ms':performance['p95_ms'],'overlap_samples':len(overlap),
                'overlap_p95_ms':performance['overlap_p95_ms'],'external_elapsed_seconds':resolution['elapsed_seconds'],
                'state':resolution['state'],'source_ids':[t['source_id'] for r in runs for t in r['tools']],'directory':str(directory)}
    finally:
        if process.poll() is None:stop(process,log)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root',required=True)
    parser.add_argument('--port',type=int,default=8028)
    parser.add_argument('--kind',choices=['both','real','method-wait'],default='both')
    args=parser.parse_args()
    root=Path(args.data_root).resolve()
    backend=Path(__file__).resolve().parents[1]/'backend'
    selected=[(kind,method) for kind,method in [('real',False),('method-wait',True)] if args.kind in {'both',kind}]
    if any((root/kind).exists() for kind,_ in selected):raise ValueError('Use a new isolated acceptance directory; never overwrite an earlier run')
    results=[measure(backend,root/kind,args.port,method) for kind,method in selected]
    print(json.dumps(results,ensure_ascii=False,indent=2))
