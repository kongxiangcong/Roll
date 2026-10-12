"""Bytewise append of only this slice's exact owned runtime union; no DB opens."""
import hashlib
import json
import os
import shutil
from pathlib import Path
folder=Path(__file__).resolve().parent;repo=folder.parents[3]
target=Path('D:/dsh-proj/Roll/.roll-data/implementation-evidence/continuation-ticket30-sse-company-actions')
names=['t30a-actual','t30a-actual-consumer','t30a-assess-green','t30a-assess-green-clock','t30a-assess-red',
    't30a-bound-green','t30a-bound-red','t30a-cancel-red','t30a-composition','t30a-composition-corrected',
    't30a-final-composition','t30a-final-raw','t30a-guards','t30a-packet-green','t30a-packet-red',
    't30a-raw-green','t30a-raw-red']
sources={name:repo/'.scratch'/name for name in names}
sources['public-source-assessment-dump']=folder/'runtime/source-assessment'
if (repo/'.pytest_cache').exists():sources['pytest-cache-final']=repo/'.pytest_cache'
assert set(names)=={p.name for p in (repo/'.scratch').glob('t30a-*') if p.is_dir()}
assert not target.exists(),'New preservation namespace only; no overwrite of an old manifest.'
prefix=chr(92)*2+'?'+chr(92)
def extended(path):return Path(prefix+str(path.resolve()))
def ordinary(path):return str(path).removeprefix(prefix)
def digest(path):
    sha=hashlib.sha256();size=0
    with path.open('rb') as stream:
        while block:=stream.read(1048576):sha.update(block);size+=len(block)
    return {'sha256':sha.hexdigest(),'bytes':size}
records=[]
for name,plain in sources.items():
    source=extended(plain)
    assert source.is_dir() and not source.is_symlink() and not source.is_junction()
    for current,directories,files in os.walk(source):
        current=Path(current)
        for directory in directories:
            entry=current/directory;assert not entry.is_symlink() and not entry.is_junction()
        for filename in files:
            origin=current/filename;assert not origin.is_symlink() and not origin.is_junction()
            destination=extended(target/name)/origin.relative_to(source)
            expected=digest(origin);destination.parent.mkdir(parents=True,exist_ok=True)
            assert not destination.exists();shutil.copyfile(origin,destination)
            assert digest(origin)==expected and digest(destination)==expected
            records.append({'source':ordinary(origin),'destination':ordinary(destination),**expected})
receipt={'scope':'NINTH_OWNED_EXACT_RUNTIME_UNION_NEW_NAMESPACE_BYTEWISE_ONLY',
    'files':len(records),'bytes':sum(r['bytes'] for r in records),'sha_or_length_mismatches':0,
    'target':str(target),'source_union':{name:str(path) for name,path in sources.items()},
    'actual_attempts':2,'actual_budget_closed':True,'preservation_network_calls':0,'sqlite_opened':False,
    'previous_preservation_namespaces_read_or_written':False,'original_or_private_root_profiles_opened':False,
    'dispositions':{
        'seventeen_t30a_runtime_directories':'PRESERVED_COMPLETE_EACH_FILE_SHA_LENGTH',
        'ninth_public_source_assessment_runtime_dump':'PRESERVED_COMPLETE_AND_TWO_RAWS_TRACKED_BINARY',
        'own_current_pytest_cache':'PRESERVED_COMPLETE_IF_PRESENT',
        'older_t30_runtime_and_evidence_directories':'RETAIN_UNCHANGED_PRIOR_MANIFESTS_NOT_OPENED_OR_CLEANED',
        'own_backend_venv_frontend_node_modules_links':'SHARED_REFERENCES_ONLY_NOT_TRAVERSED_OR_OWNED',
        'root_original_or_private_profiles':'NO_NINTH_WRITES_NO_DB_OPEN_OR_SCAN',
        'original19':'NAMED_BYTEWISE_CHECKSUM_ONLY',
        'tracked_source_and_evidence':'SCOPED_GIT_COMMITS_NO_PUSH',
        'worktree':'RETAINED_PENDING_INDEPENDENT_ACCEPTANCE_NO_CLEANUP'}}
for filename,value in [('runtime-preservation-manifest.json',records),('runtime-preservation-receipt.json',receipt)]:
    output=folder/filename;assert not output.exists()
    output.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({key:receipt[key] for key in ['files','bytes','sha_or_length_mismatches']}))
