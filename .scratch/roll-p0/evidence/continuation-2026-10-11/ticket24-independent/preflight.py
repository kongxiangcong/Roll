"""Stable source/runtime acceptance preflight. Static source copy only; no Host."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

scope=Path(__file__).resolve().parent
root=scope.parents[4]
child=root/'.scratch/worktrees/ticket24'
evidence=child/'.scratch/roll-p0/evidence/24'
runtime=root/'.roll-data/implementation-evidence/ticket24-independent'
expected=sys.argv[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git','-C',str(child),*args],text=True).strip()
assert git('rev-parse','HEAD')==expected,'Child final OID differs'
assert not git('status','--porcelain','--untracked-files=no'),'Child tracked dirty'
sources=json.loads((evidence/'source-receipt.json').read_text(encoding='utf-8'))
for item in sources['owned_sources']:
    p=child/item['path'];raw=p.read_bytes()
    assert hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest()==item['normalized_sha256']
    assert len(raw)==item['bytes']
assert len(sources['protected_sources'])==12 and sources['protected_all_unchanged']
for item in sources['protected_sources']:
    assert item['unchanged'] and item['baseline_sha256']==item['current_sha256']
    for base in [child,root]:
        assert hashlib.sha256((base/item['path']).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==item['baseline_sha256']
manifest=json.loads((evidence/'runtime-preservation-manifest.json').read_text(encoding='utf-8'))
preserved=json.loads((evidence/'runtime-preservation-receipt.json').read_text(encoding='utf-8'))
assert sha(evidence/'runtime-preservation-manifest.json')==preserved['source_manifest_sha256']
assert preserved['file_count']==len(manifest['files']) and preserved['sha_mismatches']==preserved['length_mismatches']==preserved['missing_files']==preserved['extra_files']==0
destination=root/manifest['destination_suggestion']
assert destination.resolve().is_relative_to((root/'.roll-data/implementation-evidence/ticket24').resolve())
assert destination.is_dir(),'Final runtime copy handoff missing'
for item in manifest['files']:
    relative=Path(item['path']);assert not relative.is_absolute() and '..' not in relative.parts
    for base in [child,destination]:
        p=base/relative
        assert p.stat().st_size==item['bytes'] and sha(p)==item['sha256'],str(relative)
source=child/'backend/src';target=runtime/'source'
assert not target.exists(),'Never overwrite prior independent source'
copies=[]
for path in sorted((source/'roll').rglob('*')):
    if not path.is_file() or '__pycache__' in path.parts:continue
    assert not path.is_symlink() and path.name not in {'.env','auth.json'}
    relative=path.relative_to(source);to=target/relative
    to.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,to)
    assert sha(path)==sha(to)
    copies.append({'path':str(relative).replace('\\','/'),'bytes':path.stat().st_size,'sha256':sha(path)})
lock=child/'backend/uv.lock';to=runtime/'uv.lock'
shutil.copyfile(lock,to);assert sha(lock)==sha(to)
receipt={'status':'PASS','stable_oid':expected,'owned_source_count':len(sources['owned_sources']),
    'protected_model_sources':12,'runtime_files':len(manifest['files']),'runtime_bytes':sum(i['bytes'] for i in manifest['files']),
    'runtime_source_root_SHA_length_mismatches':0,'source_copy':str(target),'copied_source_files':copies,
    'source_copy_dependency_lock':{'bytes':to.stat().st_size,'sha256':sha(to)},
    'actual_profile_started':False,'provider_calls':0,'synthetic_auth_fixture_not_real_credentials':True,'exit_code':0}
(scope/'preflight-results.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
print('24 preflight PASS: stable source, 12 model guards, preserved runtime, isolated source copy; no Host')
