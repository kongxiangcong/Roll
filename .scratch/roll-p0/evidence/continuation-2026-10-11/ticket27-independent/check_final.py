"""No database connections: final source/original19 byte guards and Git boundary."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,subprocess,sys
root=Path('D:/dsh-proj/Roll');source=root/'.scratch/worktrees/ticket27'
out=root/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket27-independent'
base=json.loads((out/'integrity.json').read_text())
def git(repo,*args):return subprocess.check_output(['git','-C',str(repo),*args])
def check(row):
    p=Path(row['path'])
    with p.open('rb') as f:s=hashlib.file_digest(f,'sha256').hexdigest()
    assert p.stat().st_size==row['bytes'] and s==row['sha256'],str(p)
    return row
items=base['protected15_root_source']+base['current_product111_raw_unchanged']+[base['original19_checksum_only']]
with ThreadPoolExecutor(max_workers=8) as pool:checked=list(pool.map(check,items))
assert git(source,'rev-parse','HEAD').decode().strip()==base['stable_source']
assert git(source,'diff','--name-only')==b'' and git(source,'diff','--cached','--name-only')==b''
assert git(root,'diff','--name-only')==b'' and git(root,'diff','--cached','--name-only')==b''
os_test='backend/tests/recovery/test_lifecycle_process.py'
native=git(source,'show','ec21794149ceab92dab87742c56c0678bd051f75:'+os_test)
assert native==git(source,'show','HEAD:'+os_test)
result={'source_head':base['stable_source'],'root_head':git(root,'rev-parse','HEAD').decode().strip(),
    'protected_source_and_root15_unchanged':True,'original19_checksum_only_unchanged':True,
    'product111_unchanged':True,'checked_byte_items':len(checked),'source_tracked_index_clean':True,'root_tracked_index_clean':True,
    'native_process_test_checkpoint_blob_unchanged':{'path':os_test,'sha256':hashlib.sha256(native).hexdigest()},
    'preserved_sqlite_connections_during_guard':0,'actual_http':0,'fits':0,'source_OS_cases_rerun':False}
if len(sys.argv)>2 and sys.argv[2]=='postmerge':
    identities=[]
    for row in base['source_git_identity']:
        path=row['path'];rootblob=git(root,'rev-parse','HEAD:'+path).decode().strip()
        assert rootblob==row['git_blob'],path
        raw=(root/path).read_bytes();expected=(source/path).read_bytes()
        assert raw==expected,path
        identities.append({'path':path,'git_blob':rootblob,'raw_sha256':hashlib.sha256(raw).hexdigest()})
    result['merged_product111_root_source_raw_and_git_equal']=identities
(out/(sys.argv[1] if len(sys.argv)>1 else 'final-guard.json')).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result))
