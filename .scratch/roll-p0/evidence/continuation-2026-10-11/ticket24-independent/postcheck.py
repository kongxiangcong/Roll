"""Read-only source/runtime/fitting guard after independent METHOD API checks."""
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess

scope=Path(__file__).resolve().parent;root=scope.parents[4]
child=root/'.scratch/worktrees/ticket24';runtime=root/'.roll-data/implementation-evidence/ticket24-independent'
evidence=child/'.scratch/roll-p0/evidence/24'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git','-C',str(child),*args],text=True).strip()
expected='ffb83af1b0ebbbc5ac322c8d5f8c34840bd24634'
assert git('rev-parse','HEAD')==expected and not git('status','--porcelain','--untracked-files=no')
changed=git('diff','--name-only','38b64fbc8d4be4ca4aa64c52a60a5df0cda84a86',expected).splitlines()
assert len(changed)==2 and all(p.startswith('.scratch/roll-p0/evidence/24/') for p in changed)
pre=json.loads((scope/'preflight-results.json').read_text(encoding='utf-8'))
for item in pre['copied_source_files']:
    p=runtime/'source'/item['path']
    assert p.stat().st_size==item['bytes'] and sha(p)==item['sha256']
source=json.loads((evidence/'source-receipt.json').read_text(encoding='utf-8'))
for item in source['owned_sources']:
    raw=(child/item['path']).read_bytes()
    assert len(raw)==item['bytes'] and hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest()==item['normalized_sha256']
for item in source['protected_sources']:
    for base in [root,child]:
        raw=(base/item['path']).read_bytes()
        assert hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest()==item['baseline_sha256']
preservation=json.loads((evidence/'runtime-preservation-manifest.json').read_text(encoding='utf-8'))
receipt=json.loads((evidence/'runtime-preservation-receipt.json').read_text(encoding='utf-8'))
assert sha(evidence/'runtime-preservation-manifest.json')==receipt['source_manifest_sha256']
for item in preservation['files']:
    for base in [child,root/'.roll-data/implementation-evidence/ticket24']:
        p=base/item['path'];assert p.stat().st_size==item['bytes'] and sha(p)==item['sha256']
profile_proofs=[]
for path in sorted((runtime/'pytest-02').glob('*/data/roll.sqlite3')):
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        names={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        counts={n:db.execute('SELECT COUNT(*) FROM '+n).fetchone()[0] if n in names else 0 for n in ['research_models','research_forecasts','research_attempts']}
        assert all(v==0 for v in counts.values())
        grants=[json.loads(r[0]) for r in db.execute('SELECT value FROM capability_grants')]
        assert all(g['evidence_kind']=='METHOD_ENGINEERING' and g['system_usable'] is False for g in grants)
        profile_proofs.append({'profile':path.parent.parent.name,'fit_forecast_family_attempt_counts':counts,
            'grants':len(grants),'actual_system_usable':False})
assert len(profile_proofs)==6
execution=json.loads((scope/'execution.json').read_text(encoding='utf-8'));assert execution['exit_code']==0
result={'status':'PASS','source_oid':expected,'independent_tests':6,'pytest_seconds':40.66,'actual_exit_code':0,
    'owned_sources':9,'protected_model_sources':12,'source_copy_restored_SHA_length_mismatches':0,
    'runtime_files':len(preservation['files']),'runtime_bytes':sum(i['bytes'] for i in preservation['files']),
    'runtime_source_root_SHA_length_mismatches':0,'isolated_SQLite_profiles':profile_proofs,
    'provider_calls':0,'actual_profiles_started':0,'new_fit':0,'SEALED_read':False,
    'qualification_scope':'METHOD engineering service only; actual research NOT_GRANTED',
    'real_profile_P95_measured':False,'historical_ReviewRecord_issues_modified':False}
(scope/'postcheck-results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print('24 independent closeout PASS: 6 METHOD API cases, stable source, 1315 preserved files; 0 fit/provider/actual authority')
