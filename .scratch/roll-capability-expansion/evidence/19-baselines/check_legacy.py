import hashlib,json,os,shutil,sqlite3
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app
root=Path('D:/dsh-proj/Roll');source=root/'.scratch/r19bf3';target=root/'.scratch/r19old'
assert not target.exists()
before={p.relative_to(source).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
shutil.copytree(source,target)
with sqlite3.connect('file:'+str(target/'roll.sqlite3')+'?mode=ro',uri=True) as db:
    original=[json.loads(row[0]) for row in db.execute('SELECT value FROM research_performance_reports')]
assert original
os.environ['ROLL_ENV']='test';os.environ.pop('ROLL_QUANTSTATS_PYTHON',None)
with TestClient(create_app(target,runtime_role='API')) as client:
    for saved in original:
        assert 'benchmarks' not in saved['namespaces']['SHADOW']
        base='/api/research/performance-reports/'+saved['performance_report_id']
        assert client.get(base).json()==saved
        assert client.post(base+'/replay').json()['matches_original'] is True
        assert hashlib.sha256(client.get(base+'/export').content).hexdigest()==saved['export']['sha256'].lower()
after={p.relative_to(source).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
assert before==after
result={'legacy_reports':len(original),'original_profile_modified':False,'recomputed':False,'runtime_configured':False,
    'legacy_renderer_fingerprints':[r['renderer_fingerprint'] for r in original],'exact_read_and_export_match':True}
Path(__file__).with_name('legacy-replay.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
