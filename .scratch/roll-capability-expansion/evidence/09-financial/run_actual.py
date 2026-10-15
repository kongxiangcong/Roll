"""One predeclared source assessment; captures failure, never retries/falls back."""
import json,subprocess,time
from pathlib import Path
root=Path(__file__).resolve().parents[4]
target=Path(__file__).with_name('actual-source')
target.mkdir(exist_ok=True)
guard=target/'attempt.json'
if guard.exists():raise SystemExit('The one actual source attempt has already been consumed')
plan=json.loads(Path(__file__).with_name('actual-plan.json').read_text())
guard.write_text(json.dumps({'status':'CLAIMED_NO_IMPLICIT_RETRY','plan':plan,'started_at':time.time()},indent=2),encoding='utf-8')
command={'instrument':'SSE:600362','output_directory':str(target),'deadline_at':time.time()+18}
with (target/'stdout.log').open('w',encoding='utf-8') as out,(target/'stderr.log').open('w',encoding='utf-8') as err:
    try:
        result=subprocess.run([str(root/'.scratch/rce-runtime/akshare/Scripts/python.exe'),'-B',str(root/'backend/src/roll/market/akshare_financial_process.py')],
            input=json.dumps(command),text=True,stdout=out,stderr=err,timeout=18,cwd=root)
        completion={'exit_code':result.returncode,'status':'FINISHED_NO_RETRY'}
    except subprocess.TimeoutExpired:completion={'status':'TIMEOUT_NO_RETRY'}
guard.write_text(json.dumps({'plan':plan,**completion},indent=2),encoding='utf-8')
capture=target/'capture.json'
if capture.exists():
    state=json.loads(capture.read_text(encoding='utf-8'))
    print(json.dumps({'status':state['status'],'captures':len(state['captures']),'errors':state['errors'],
        'sdk_result':state['sdk_result'],'date_selection':state['date_selection']},ensure_ascii=False))
else:print(json.dumps(completion))
