"""Explicit real-provider acceptance; credential file is read only by the host factory."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import httpx

root = Path(__file__).resolve().parents[4]
data = root / 'backend/.roll-data/12-live'
output = Path(__file__).parent / 'live'
output.mkdir(exist_ok=True)
mode = sys.argv[1] if len(sys.argv) > 1 else 'multiround'
port = 8122
env = dict(os.environ, ROLL_DATA_DIR=str(data), ROLL_ENV_FILE='D:/dsh-proj/Roll/.env')
env.pop('ROLL_ENV', None)
if mode == 'auth-error':
    env['DEEPSEEK_API_KEY'] = 'ROLL_REAL_PROVIDER_INVALID_AUTH_ACCEPTANCE'
log = (output / (mode + '-process.txt')).open('w', encoding='utf-8')
process = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', '-m', 'uvicorn', 'roll.app:create_app', '--factory', '--host', '127.0.0.1', '--port', str(port)], cwd=root / 'backend', env=env, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
client = httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=30, trust_env=False)
try:
    end = time.monotonic() + 40
    while time.monotonic() < end:
        try:
            if client.get('/api/health').status_code == 200:
                break
        except httpx.HTTPError:
            pass
        if process.poll() is not None:
            raise RuntimeError('host failed')
        time.sleep(.2)
    before = client.get('/api/account').json()
    if before['version'] == 0:
        draft = client.post('/api/account/drafts', json={'kind':'BASELINE','expected_account_version':0,'payload':{'effective_at':'2026-10-08T00:00:00+08:00','source':'12 isolated REAL_PROVIDER acceptance / synthetic account','cash_balance':'10000.00','broker_available':None,'broker_frozen':None,'withdrawable':None,'permission_profile':[],'positions':[{'instrument':'SSE:600519','quantity':'100','sellable_quantity':None,'reference_cost':None}]}}).json()
        client.post('/api/account/confirm', json={'draft_id':draft['draft_id'],'idempotency_key':'12-live-baseline'}).raise_for_status()
    before = client.get('/api/account').json()
    if mode == 'retry':
        prior = json.loads((output / 'multiround-run.json').read_text(encoding='utf-8'))
        request_id = prior['request_id']
    else:
        request = client.post('/api/data/requests', json={'instruments':['SSE:600519'],'groups':['QUOTE'],'purpose':'OBSERVATION','start_date':'2026-10-01','end_date':'2026-10-08','quote_source':'SINA','required_fields':['QUOTE.volume_shares']})
        request.raise_for_status()
        request_id = request.json()['request_id']
    command = {'question':'先用 roll_read_evidence 获取贵州茅台实际报价，再用 roll_read_source 补取 MOUTAI_OFFICIAL 公开网页。两轮先后调用。最后JSON只输出1条官网字面引用候选，每个字段不超过80字，以及至多3条简短缺口。仅报价解析字段而无原文字面证据不输出报价候选。来源事件时点未知则明确缺口，不作交易建议。'}
    if mode == 'retry':
        command['retry_of'] = prior['run_id']
    launched = client.post(f'/api/data/requests/{request_id}/deepseek', json=command)
    launched.raise_for_status()
    run_id = launched.json()['run_id']
    end = time.monotonic() + 135
    cancelled = False
    crashed = False
    while time.monotonic() < end:
        run = client.get('/api/data/runs/' + run_id).json()
        if run['status'] != 'RUNNING':
            break
        if mode == 'cancel' and len(run.get('model_requests', [])) >= 2 and not cancelled:
            client.post('/api/data/runs/' + run_id + '/cancel').raise_for_status()
            cancelled = True
        if mode == 'crash' and len(run.get('model_requests', [])) >= 2 and not crashed:
            process.kill()
            process.wait(timeout=20)
            crashed = True
            process = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', '-m', 'uvicorn', 'roll.app:create_app', '--factory', '--host', '127.0.0.1', '--port', str(port)], cwd=root / 'backend', env=env, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
            ready = time.monotonic() + 30
            while time.monotonic() < ready:
                try:
                    if client.get('/api/health').status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(.2)
        time.sleep(.2)
    (output / (mode + '-run.json')).write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding='utf-8')
    if run.get('snapshot_id'):
        (output / (mode + '-snapshot.json')).write_text(json.dumps(client.get('/api/data/snapshots/' + run['snapshot_id']).json(), ensure_ascii=False, indent=2), encoding='utf-8')
    report = {'mode':mode, 'run_id':run_id,'status':run['status'],'error':run.get('error'),'model_calls':len(run.get('model_requests',[])),'tools':len(run['tools']),'candidates':len(run['candidates']),'account_unchanged':client.get('/api/account').json()==before,'cancel_requested':cancelled,'host_crash_requested':crashed,'data_directory':str(data)}
    (output / (mode + '-result.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
finally:
    client.close()
    process.terminate()
    process.wait(timeout=20)
    log.close()
