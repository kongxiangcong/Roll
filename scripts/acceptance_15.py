"""Read-only original archive copy, actual-host cached observation evidence."""
import hashlib
import json
import platform
import shutil
import time
from datetime import datetime,timezone
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app

root=Path(__file__).resolve().parents[1]
source=Path('D:/dsh-proj/Roll/backend/.roll-data/implementation-evidence/07/acceptance-07')
destination=root/('backend/.roll-data/acceptance-15-real-'+datetime.now(timezone.utc).strftime('%H%M%S'))
evidence=root/'.scratch/roll-p0/evidence/15'
evidence.mkdir(parents=True,exist_ok=True)
if destination.exists():raise RuntimeError('Choose a fresh acceptance destination; never overwrite previous runtime evidence')
originals=[{'path':p.relative_to(source).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(source.rglob('*')) if p.is_file()]
shutil.copytree(source,destination)
assert all(hashlib.sha256((destination/item['path']).read_bytes()).hexdigest()==item['sha256'] for item in originals)
started=datetime.now(timezone.utc).isoformat()
with TestClient(create_app(destination)) as client:
    account=client.get('/api/account').json()
    listing=client.get('/api/market/list').json()
    for instrument in ['SSE:600519']+[f'SSE:{600000+i}' for i in range(30)]:
        if len(listing['members'])==20:break
        if instrument in {m['instrument'] for m in listing['members']}:continue
        response=client.post('/api/market/watch',json={'operation':'ADD','instrument':instrument,'expected_list_version':listing['version']})
        assert response.status_code==200,response.text
        listing=response.json()
    task=client.post('/api/reviews/tasks',json={'mode':'ON_DEMAND'}).json()
    for _ in range(200):
        task=client.get('/api/reviews/tasks/'+task['task_id']).json()
        if task['result']:break
        time.sleep(.02)
    assert task['result'] and task['attempts']==1
    actual=[i for i in task['result']['instruments'] if i['instrument']=='SSE:600519'][0]
    assert actual['quote']['evidence_kind']=='REAL_ACQUISITION'
    assert actual['quote']['upstream_at'].startswith('2026-09-30')
    assert actual['quote']['available_at'].startswith('2026-10-07')
    assert task['result']['forecast'] is None and task['result']['forward_sample_created'] is False
    replay=client.post('/api/reviews/tasks/'+task['task_id']+'/replay')
    assert replay.status_code==200,replay.text
    assert replay.json()['result']==task['result'] and replay.json()['network_calls']==0
    samples=[]
    for _ in range(50):
        start=time.perf_counter()
        assert client.get('/api/today').status_code==200
        summary=client.get('/api/reviews/summary')
        assert summary.status_code==200
        samples.append((time.perf_counter()-start)*1000)
    p95=sorted(samples)[47]
    assert p95<=2000
    assert client.get('/api/account').json()==account
    result={'started_at':started,'finished_at':datetime.now(timezone.utc).isoformat(),'source':str(source),'runtime_directory':str(destination),
        'original_copy':originals,'source_after_copy_differences':sum(hashlib.sha256((source/item['path']).read_bytes()).hexdigest()!=item['sha256'] for item in originals),
        'scope':'synthetic inherited engineering account and 20-member watch list; original actual public provider bytes, no user wealth claim',
        'device':{'platform':platform.platform(),'processor':platform.processor(),'python':platform.python_version()},
        'members':len(listing['members']),'backgrounds':len([i for i in task['result']['instruments'] if i['role']=='BACKGROUND']),
        'positive_cached_quote_count':sum(i['quote'] is not None for i in task['result']['instruments']),
        'positive_cached_daily_count':sum(i['last_complete_daily'] is not None for i in task['result']['instruments']),
        'original_quote':actual['quote'],'task':task,'replay':replay.json(),
        'http_local_only_p95_ms':p95,'samples_ms':samples,'network_calls':0,'timing_scope':'today plus compact review summary, in-process real FastAPI/SQLite; actual Chrome page load measured separately'}
    (evidence/'real-archive-and-api-performance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({k:result[k] for k in ['runtime_directory','members','backgrounds','positive_cached_quote_count','positive_cached_daily_count','http_local_only_p95_ms','source_after_copy_differences']},ensure_ascii=False))
