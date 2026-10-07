"""One finite Agents SDK worker in a Windows Job, with acquisition retained by the host."""
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from uuid import uuid4

from roll.accounts.ledger import encode, now
from roll.agents.codex_process import Job,clean_environment,command,tool,publish


def execute(host,run,request,cancel,key):
    started=time.monotonic();deadline=started+run['limits']['timeout_seconds']
    state={'facts':[],'snapshots':[],'http_calls':0,'bytes':0,'returned_bytes':0,'source_texts':{}}
    root=Path(tempfile.mkdtemp(prefix='roll-deepseek-task-'+run['run_id']+'-')).resolve()
    nonce=str(uuid4())
    (root/'.roll-owner.json').write_text(encode({'run_id':run['run_id'],'nonce':nonce}),encoding='utf-8')
    (root/'home').mkdir();(root/'user').mkdir()
    run['process']={'task_root':str(root),'owner_nonce':nonce,'credential_persisted':False}
    worker=Path(__file__).with_name('deepseek_worker.py')
    process=subprocess.Popen([sys.executable,'-I','-B',str(worker)],cwd=root,
        env=clean_environment(root),stdin=subprocess.PIPE,stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
    job=None;messages=queue.Queue()
    def drain():
        while True:
            line=process.stdout.readline(262145)
            if not line:messages.put({'kind':'eof'});return
            if len(line)>262144:messages.put({'kind':'failure','code':'WORKER_RESPONSE_TOO_LARGE'});return
            try:messages.put(json.loads(line))
            except ValueError:messages.put({'kind':'failure','code':'WORKER_PROTOCOL_ERROR'});return
    def send(value):
        process.stdin.write(encode(value)+'\n');process.stdin.flush()
    try:
        job=Job(process.pid)
        run['process'].update(worker_pid=process.pid,containment='WINDOWS_JOB_KILL_ON_CLOSE',
            isolated_cwd=True,isolated_home=True,environment_keys=sorted(clean_environment(root)))
        threading.Thread(target=drain,daemon=True).start()
        frozen=command(run,request)
        run['tool_schema_fingerprint']=hashlib.sha256(encode(frozen['tools']).encode()).hexdigest()
        # Key crosses this private pipe once, and is never a prompt/tool/audit field or file.
        send({**frozen,'key':key,'endpoint':host.endpoint,'limits':run['limits']});host.save(run)
        key=None
        while True:
            if cancel.is_set() or time.monotonic()>=deadline:
                run.update(status='CANCELLED' if cancel.is_set() else 'TIMED_OUT',interrupt_requested_at=now())
                send({'kind':'cancel'});time.sleep(.1);break
            try:event=messages.get(timeout=.05)
            except queue.Empty:
                if process.poll() is not None:
                    run.update(status='FAILED',error={'code':'DEEPSEEK_WORKER_EXIT'});break
                continue
            kind=event.pop('kind')
            if kind=='bootstrap':
                run.setdefault('bootstrap_audit',[]).append(event)
            elif kind=='runtime':
                run['runtime_audit'].update(event)
            elif kind=='model_request':
                run.setdefault('model_requests',[]).append(event)
            elif kind=='model_response':
                output=event.pop('body')
                archive=host.evidence.archive(output.encode(),'DEEPSEEK_PROVIDER_RESPONSE',run_id=run['run_id'],
                    received_at=now(),redacted=True,http_status=event['http_status'])
                run.setdefault('model_responses',[]).append({**event,'sha256':archive['sha256'],'bytes':archive['bytes']})
                if event.get('resolved_model'):run['resolved_model']=event['resolved_model']
            elif kind=='tool':
                result=tool(host,run,request,state,event,deadline,cancel)
                send({'kind':'tool_result','id':event['id'],'result':result})
            elif kind=='denied':
                run.setdefault('denied_requests',[]).append(event)
            elif kind=='completed':
                run['token_usage']=event['usage']
                publish(host,run,request,state,event['output']);break
            elif kind in {'failure','eof'}:
                code=event.get('code','DEEPSEEK_WORKER_EXIT')
                status='UNAVAILABLE' if code in {'DEEPSEEK_AUTH_REJECTED','DEEPSEEK_MODEL_UNAVAILABLE','DEEPSEEK_QUOTA_OR_RATE_LIMIT'} else 'INVALID_OUTPUT' if code=='DEEPSEEK_OUTPUT_SCHEMA_INVALID' else 'TOOL_LIMIT' if code=='DEEPSEEK_MODEL_CALL_LIMIT' else 'FAILED'
                run.update(status=status,error={'code':code,'type':event.get('error_type'),'http_status':event.get('http_status')})
                break
            else:
                run.update(status='FAILED',error={'code':'DEEPSEEK_WORKER_PROTOCOL_ERROR'});break
            if len(run['tools'])>run['limits']['tool_calls']:
                run.update(status='TOOL_LIMIT',error={'code':'TOOL_BUDGET_EXHAUSTED'});break
            run['process']['observed_pids']=job.pids();host.save(run)
    finally:
        if job:
            run['process']['pids_before_cleanup']=job.pids();job.terminate()
            process.wait(timeout=5);run['process']['remaining_pids']=job.pids();job.close()
        else:
            process.kill();process.wait(timeout=5)
        process.stdout.close();process.stdin.close()
        run['elapsed_seconds']=round(time.monotonic()-started,3)
        run['acquisition_usage']={'http_calls':state['http_calls'],'received_bytes':state['bytes'],
            'archived_bytes':sum(a['bytes'] for a in run['archives']),'model_tool_result_bytes':state['returned_bytes']}
        # Only the exact directory created above, no credentials were written into it.
        for attempt in range(10):
            try:
                shutil.rmtree(root);run['process']['temporary_directory_removed']=True;break
            except PermissionError:time.sleep(.1)
        else:run['process']['temporary_directory_removed']=False
