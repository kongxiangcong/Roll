"""Parent-authorized exact repair within two named SHM copies; retain changed bytes."""
import hashlib
import json
from pathlib import Path
import shutil

SCOPE=Path(__file__).resolve().parent
ROOT=SCOPE.parents[4]
DIAG=ROOT/'.roll-data/implementation-evidence/ticket30-producer-independent/diagnostic/shm-before'
DIFF=json.loads((SCOPE/'preservation-differences.json').read_text(encoding='utf-8'))
OWNER=json.loads((SCOPE/'reader-process-closeout.json').read_text(encoding='utf-8'))
assert OWNER['matching_live_reader_or_METHOD_source_processes']==0
assert DIFF['files']==13989 and len(DIFF['differences']) in {1,2}
def info(p):
    raw=p.read_bytes();return {'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
allowed={str(ROOT/'.roll-data/implementation-evidence/continuation-ticket30-producer/worktree/t30p-final-4'/name/'data/roll.sqlite3-shm')
    for name in ['test_source_crash_retains_orig0','test_source_crash_retains_orig1']}
assert {i['destination'] for i in DIFF['differences']}<=allowed
assert not DIAG.exists(),'Never overwrite old diagnostics'
DIAG.mkdir(parents=True)
repairs=[]
for index,item in enumerate(DIFF['differences']):
    source,target=Path(item['source']),Path(item['destination'])
    assert source.is_relative_to(ROOT/'.scratch/worktrees/ticket30-producer')
    assert not source.is_symlink() and not target.is_symlink()
    assert info(source)==item['expected']==item['actual']['source']
    before=info(target);assert before==item['actual']['destination']
    backup=DIAG/(str(index)+'.sqlite3-shm')
    shutil.copyfile(target,backup);assert info(backup)==before
    shutil.copyfile(source,target)
    after=info(target);assert after==item['expected']
    repairs.append({'source':str(source),'destination':str(target),'manifest':item['expected'],
        'source_verified_before':item['actual']['source'],'destination_before':before,
        'preserved_changed_bytes':str(backup),'preserved_changed_bytes_info':info(backup),'destination_after':after})
result={'status':'PASS','authorization':'Parent exact two stopped METHOD SHM restoration only',
    'root_profile_changes':'Only mismatching SHM within two named profiles restored to original manifest bytes; no DB/WAL/raw/profile semantic edits',
    'repairs':repairs,'historical_manifests_receipts_modified':False,'full_reverification_required':True}
(SCOPE/'shm-repair-results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print(str(len(repairs))+' exact SHM copies restored; changed bytes retained; full verification remains required')
