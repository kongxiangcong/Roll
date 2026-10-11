from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib,json,os,stat,subprocess,time
ROOT=Path('D:/dsh-proj/Roll');TREE=ROOT/'.scratch/worktrees/ticket25'
OUT=Path('C:/Users/72449/.codex/visualizations/2026/10/10/01a126a2-cdcc-7d52-b24a-ad47b49bcc56')
CAPTURE=ROOT/'.roll-data/implementation-evidence/ticket25-cleanup-additional-2026-10-11'
BASE='roll-ticket25-cleanup-additional-'
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def git(repo,*args):return subprocess.check_output(['git','-C',str(repo),*args],text=True).strip()
def ordinary(path):
    info=Path('\\\\?\\'+str(path)).lstat()
    assert not info.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT,str(path)
    return info
def contained(path,base):
    path=Path(os.path.abspath(path));assert path.is_relative_to(base),str(path)
    return path
def private(path):return path.name.lower() in ['auth.json','secrets.json','.env']
def digest(path):
    assert not private(path),'Excluded private file digest attempted'
    ordinary(path)
    extended=Path('\\\\?\\'+str(path))
    with extended.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
    return {'path':str(path),'sha256':sha,'bytes':extended.stat().st_size}
def check(path,sha,size):
    value=digest(path);assert value['sha256']==sha and value['bytes']==size,str(path)
    return value
def fixture_provenance(tree,relative,definition):
    path=tree/relative;text=path.read_text(encoding='utf-8')
    assert git(tree,'ls-files','--error-unmatch',relative)==relative
    # Verify this tracked fixture body, never the runtime auth file.
    fragment=text.split('def '+definition+'(',1)[1].split('\ndef ',1)[0]
    assert "'auth.json'" in fragment and 'METHOD_CASE_ONLY' in fragment and 'ROLL_CODEX_AUTH_FILE' in fragment
    return {'path':str(path),'definition':definition,'sha256':digest(path)['sha256'],'provenance_only_not_runtime_contents':True}
started=time.time();source_head=git(TREE,'rev-parse','HEAD')
assert source_head=='759033c8bf87af1fecd7dff9021232b33542df0b'
assert git(TREE,'status','--porcelain=v1','--untracked-files=no')==''
root_start=git(ROOT,'rev-parse','HEAD')
mp=OUT/(BASE+'manifest.json')
manifest_check=check(mp,'24b5e32692348db6459ef14f96e546f9ed12373b79bdce012d5a713b49f2472d',8717987)
m=read(mp);assert Path(m['source_tree'])==TREE and Path(m['destination_namespace'])==CAPTURE
new=m['files'];assert len(new)==10108 and sum(r['bytes'] for r in new)==824294955
assert read(OUT/(BASE+'failures.json'))==[] and m['all_final_pairs_verified']
old={};old_manifest_guards=[]
for path in sorted((TREE/'.scratch/roll-p0/evidence/ticket25').glob('runtime-preservation*.json')):
    old_manifest_guards.append(digest(path));saved=read(path)
    for row in saved['files']:
        key=str(Path(row['source'])).lower()
        if key in old:assert old[key]==row,'Old manifest metadata conflict'
        old[key]=row
assert len(old)==3135 and sum(r['bytes'] for r in old.values())==264329777
assert len(old_manifest_guards)==5
ex=read(OUT/(BASE+'exclusions.json'));assert len(ex)==6
ex_paths=set();ex_metadata=[]
for row in ex:
    path=contained(row['source'],TREE)
    assert path.name=='auth.json' and row['relative']==path.relative_to(TREE).as_posix()
    assert row['contents_read'] is row['hashed'] is row['copied'] is False
    assert ordinary(path).st_size==row['bytes_metadata']==72
    if path.parent.name=='test_explicit_codex_works_with0':
        expected=('backend/tests/application/test_codex_only_scope.py','test_explicit_codex_works_with_legacy_settings_and_resave_preserves_history')
    elif path.parent.name=='test_archived_review_producer_0':
        expected=('backend/tests/application/test_capabilities.py','test_archived_review_producer_proof_reuse_detects_changed_original_input')
    else:raise AssertionError('Unrecognized private fixture provenance')
    assert row['fixture_provenance']['source']==expected[0]
    fixture=fixture_provenance(TREE,*expected)
    ex_paths.add(str(path).lower());ex_metadata.append({'path':str(path),'bytes_metadata':72,'fixture':fixture,'contents_read_hashed_copied':False})
t26=ROOT/'.scratch/worktrees/ticket26'
t26_auth=t26/'t26-final1/test_archived_review_producer_0/auth.json'
t26_m=read(t26/'.scratch/roll-p0/evidence/ticket26/runtime-preservation-manifest.json')
assert len(t26_m['excluded'])==1 and contained(t26/t26_m['excluded'][0]['path'],t26)==t26_auth
assert ordinary(t26_auth).st_size==72
t26_ex={'path':str(t26_auth),'bytes_metadata':72,'fixture':fixture_provenance(t26,'backend/tests/application/test_capabilities.py','test_archived_review_producer_proof_reuse_detects_changed_original_input'),'contents_read_hashed_copied':False}
bound=read(OUT/(BASE+'boundaries.json'));prefixes=[contained(p['path'],TREE) for p in bound['runtime_prefixes']]
assert len(prefixes)==58 and len(m['prefix_counts'])==46
for row in bound['ancestors']+bound['runtime_prefixes']:
    assert row['reparse'] is False;ordinary(Path(row['path']))
ordinary(CAPTURE)
# Verify each namespace's actual descendants without following directory links.
def filenames(base):
    result=[]
    for directory,dirs,names in os.walk('\\\\?\\'+str(base),followlinks=False):
        directory=directory[4:]
        for name in dirs:ordinary(Path(directory)/name)
        for name in names:
            p=Path(directory)/name;ordinary(p);result.append(p)
    return result
source_files=[p for base in prefixes for p in filenames(base)]
actual={str(p).lower() for p in source_files};assert len(actual)==len(source_files)==13249
all_rows=list(old.values())+new
all_keys={str(Path(r['source'])).lower() for r in all_rows}
assert len(all_keys)==13243 and not (set(old)&{str(Path(r['source'])).lower() for r in new})
assert not (all_keys&ex_paths) and actual==all_keys|ex_paths
destination_files=filenames(CAPTURE)
assert {str(p).lower() for p in destination_files}=={str(Path(r['destination'])).lower() for r in new}
assert len(destination_files)==10108
parents=set()
for rows,capture in [(list(old.values()),ROOT/'.roll-data/implementation-evidence/ticket25'),(new,CAPTURE)]:
    for r in rows:
        s=contained(r['source'],TREE);d=contained(r['destination'],capture)
        assert not private(s) and not private(d)
        if capture==CAPTURE:assert s.relative_to(TREE)==d.relative_to(CAPTURE)
        for p,base in [(s,TREE),(d,capture)]:
            cursor=p.parent
            while cursor.is_relative_to(base):parents.add(cursor);cursor=cursor.parent
for p in parents:ordinary(p)
print('BOUNDARIES_AND_COVERAGE_PASS_13243_PLUS_6_EXCLUDED; HASHING_26486_PAIRS',flush=True)
jobs=[(Path(r[k]),r['sha256'],r['bytes']) for r in all_rows for k in ['source','destination']]
with ThreadPoolExecutor(max_workers=8) as pool:
    futures=[pool.submit(check,*job) for job in jobs]
    completed=0
    for future in as_completed(futures):
        future.result();completed+=1
        if completed%4000==0:print(f'HASH_PROGRESS {completed}/{len(jobs)}',flush=True)
for r in new:assert Path('\\\\?\\'+r['source']).stat().st_mtime_ns==r['source_mtime_ns']
for r in old_manifest_guards:check(Path(r['path']),r['sha256'],r['bytes'])
protected=read(ROOT/'.scratch/roll-p0/evidence/codex-review-repairs-2026-10-11/source-final.json')[:15]
guards=[check(repo/r['path'],r['sha256'],r['bytes']) for r in protected for repo in [ROOT,TREE]]
actual19=check(ROOT/'.roll-data/reconstructed19-v1/roll.sqlite3','ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4',165814272)
allowed=[]
for r in m['protected_checks_before'][12:15]:allowed.append(check(Path(r['path']),r['expected_sha256'],r['expected_bytes']))
assert git(TREE,'rev-parse','HEAD')==source_head and git(TREE,'status','--porcelain=v1','--untracked-files=no')==''
process=read(OUT/'roll-ticket25-preservation-independent-process.json');assert process['query_succeeded'] and process['count']==0
result={'status':'ACCEPT_PRESERVATION_ONLY','root_before':root_start,'root_after':git(ROOT,'rev-parse','HEAD'),'source_head':source_head,'new_files':10108,'new_bytes':824294955,'old_union_files':3135,'old_union_bytes':264329777,'total_preserved_files':13243,'total_preserved_bytes':1088624732,'source_destination_sha_length_checks':len(jobs),'mismatches':0,'no_reparse_runtime_or_boundary':True,'uncovered_nonexcluded_runtime_files':0,'runtime_roots':58,'new_affected_prefixes':46,'source_mtimes_unchanged':True,'old_manifests_unchanged':old_manifest_guards,'new_manifest_original_hash':manifest_check,'protected15_root_source':guards,'original19_checksum_only':actual19,'allowed3_separate':allowed,'six25_exclusions_metadata_and_fixture':ex_metadata,'single26_exclusion_metadata_and_fixture':t26_ex,'exact_process_inventory':process,'sqlite_connections':0,'auth_files_read_hashed_copied':0,'tests_fits_provider_calls_git_mutations_deletions':0,'elapsed_seconds':round(time.time()-started,2)}
(OUT/'roll-ticket25-preservation-independent-results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['old_manifests_unchanged','protected15_root_source','six25_exclusions_metadata_and_fixture','single26_exclusion_metadata_and_fixture','allowed3_separate','exact_process_inventory']}),flush=True)
