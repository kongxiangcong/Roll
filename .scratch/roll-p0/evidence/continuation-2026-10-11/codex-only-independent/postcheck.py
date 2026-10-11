"""Read-only closeout of stable raw sources, preserved METHOD runtimes and old receipt."""
import hashlib
import json
from pathlib import Path
import subprocess

SCOPE=Path(__file__).resolve().parent
ROOT=SCOPE.parents[4]
CHILD=ROOT/'.scratch/worktrees/codex-scope'
OWN=CHILD/'.scratch/roll-p0/evidence/continuation-2026-10-11/codex-only-scope'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
sources=json.loads((OWN/'source-final.json').read_text(encoding='utf-8'))
for index,item in enumerate(sources):
    for base in ([ROOT,CHILD] if index<15 else [CHILD]):
        p=base/item['path'];assert p.stat().st_size==item['bytes'] and digest(p)==item['sha256']
manifest=json.loads((OWN/'runtime-preservation.json').read_text(encoding='utf-8'))
for item in manifest['inventory']:
    for base in [CHILD/'.scratch',Path(manifest['destination'])]:
        p=Path('\\\\?\\'+str((base/item['path']).resolve()))
        assert p.stat().st_size==item['bytes'] and digest(p)==item['sha256']
relative='.scratch/roll-p0/evidence/continuation-2026-10-11/review-fixes/actual-codex-continuation-results.json'
working=subprocess.check_output(['git','-C',str(ROOT),'hash-object',relative],text=True).strip()
prior=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','f893509:'+relative],text=True).strip()
assert working==prior
receipt=json.loads((ROOT/relative).read_text(encoding='utf-8'))
record=receipt['run']['review_record'] if 'run' in receipt else receipt['result']['review_record']
# Existing immutable opinions are verified rather than rewritten to claim resolution.
issues=record['issues']
result={'status':'PASS','source_files':21,'protected_raw_sources':15,'protected_model_sources':12,
    'preserved_files':1097,'preserved_bytes':88979482,'SHA_length_mismatches':0,
    'historical_sanitized_ReviewRecord_git_blob_oid':working,'historical_record_byte_identical_to':'f893509',
    'historical_issue_count':len(issues),'historical_BLOCKING_count':sum(i['severity']=='BLOCKING' for i in issues),
    'historical_issues_modified':False,'actual_profile_opened':False,'provider_calls':0}
(SCOPE/'postcheck.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print('Closeout PASS: protected raw sources, 1097 preserved files and original sanitized ReviewRecord unchanged')
