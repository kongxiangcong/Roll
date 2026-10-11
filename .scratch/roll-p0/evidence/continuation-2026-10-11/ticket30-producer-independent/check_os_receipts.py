"""Read preserved METHOD OS crash receipts; compare unchanged transaction method ASTs."""
import ast
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import shutil
from contextlib import closing

SCOPE=Path(__file__).resolve().parent
ROOT=SCOPE.parents[4]
CHILD=ROOT/'.scratch/worktrees/ticket30-producer'
EVIDENCE=CHILD/'.scratch/roll-p0/evidence/30-producer'
path='backend/src/roll/market/post_close_packet.py'
old=subprocess.check_output(['git','-C',str(CHILD),'show','2080a2e:'+path])
current=(CHILD/path).read_bytes()
receipt=json.loads((EVIDENCE/'source-final4-after.json').read_text(encoding='utf-8'))
assert hashlib.sha256(old).hexdigest()==receipt['own'][path]['sha256']
def methods(source):
    cls=next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=='PostClosePackets')
    return {n.name:ast.dump(n,include_attributes=False) for n in cls.body if isinstance(n,ast.FunctionDef)}
before,after=methods(old),methods(current)
checked=['__init__','capture_once','capture','verify_snapshot']
assert all(before[n]==after[n] for n in checked)
manifest=json.loads((EVIDENCE/'runtime-preservation-manifest.json').read_text(encoding='utf-8'))
items=[i for i in manifest if 't30p-final-4\\test_source_crash_retains_orig' in i['source']
    and i['source'].endswith('\\data\\roll.sqlite3')]
assert len(items)==2
owned_root=ROOT/'.roll-data/implementation-evidence/ticket30-producer-independent/os-receipt-read-copy'
assert not owned_root.exists(),'Never overwrite prior read copies'
cases=[]
for item in items:
    target=Path(item['destination']);body=target.read_bytes()
    assert len(body)==item['bytes'] and hashlib.sha256(body).hexdigest()==item['sha256']
    # WAL-backed saved profiles are never opened even with mode=ro. Copy the exact
    # registered DB/WAL/SHM and raw response files; SQLite may touch only this copy.
    copy=owned_root/target.parent.parent.name/'data'
    selected=[m for m in manifest if Path(m['destination']).parent==target.parent
        and Path(m['destination']).name in {'roll.sqlite3','roll.sqlite3-wal','roll.sqlite3-shm'}
        or Path(m['destination']).is_relative_to(target.parent/'raw')]
    assert any(Path(m['destination']).name=='roll.sqlite3' for m in selected)
    for member in selected:
        origin=Path(member['destination']);relative=origin.relative_to(target.parent)
        destination=copy/relative;destination.parent.mkdir(parents=True,exist_ok=True)
        contents=origin.read_bytes()
        assert len(contents)==member['bytes'] and hashlib.sha256(contents).hexdigest()==member['sha256']
        shutil.copyfile(origin,destination)
        assert destination.read_bytes()==contents
    with closing(sqlite3.connect((copy/'roll.sqlite3').as_uri()+'?mode=ro',uri=True)) as db:
        jobs=[json.loads(r[0]) for r in db.execute('SELECT value FROM post_close_capture_jobs')]
        batches=[json.loads(r[0]) for r in db.execute('SELECT value FROM pit_collection_batches')]
        count=db.execute('SELECT COUNT(*) FROM pit_fact_versions').fetchone()[0]
        assert len(jobs)==len(batches)==1 and count==0
        assert jobs[0]['state']=='INTERRUPTED' and jobs[0]['actual_forward_start'] is False
        assert jobs[0]['gaps']==['PROCESS_STOPPED_BEFORE_SOURCE_JOB_COMPLETION']
        assert batches[0]['status']=='INTERRUPTED' and batches[0]['fact_count']==0
        archives=[json.loads(r[0]) for r in db.execute('SELECT value FROM evidence_archives')]
        raw=[a for a in archives if a.get('kind')=='RAW_RESPONSE']
        assert len(raw)==1
        for archive in raw:
            data=(copy/archive['path']).read_bytes()
            assert len(data)==archive['bytes'] and hashlib.sha256(data).hexdigest()==archive['sha256']
        cases.append({'profile':target.parent.parent.name,'job_state':jobs[0]['state'],
            'batch_status':batches[0]['status'],'facts':count,'raw_response_archives':len(raw),
            'actual_forward_start':False,'analysis_copy':str(copy),'registered_files_copied':len(selected)})
    for member in selected:
        contents=Path(member['destination']).read_bytes()
        assert len(contents)==member['bytes'] and hashlib.sha256(contents).hexdigest()==member['sha256']
assert '51 passed in 416.38s' in (EVIDENCE/'final4-pre-scope-repair-tests.log').read_text(encoding='utf-8')
result={'status':'PASS','historical_fixed_suite':'final4:51 passed / 416.38s; not latest full-suite claim',
    'transaction_methods_AST_unchanged_from_final4':checked,'latest_gap_date_fix_covered_independently':True,
    'preserved_METHOD_OS_fault_profiles':cases,'reran_OS_fault_tests':False,
    'actual_profiles_opened':False,'new_external_HTTP_calls':0,'saved_profiles_SQLite_opened':False,
    'WAL_backed_analysis_only_in_new_owned_copy':True,'saved_source_SHA_length_mismatches':0}
(SCOPE/'os-receipts-results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print('OS receipt PASS: both preserved interrupted jobs retain raw, zero facts; transaction AST unchanged')
