"""Final byte/source guards, preserved database never connected."""
import json,hashlib,subprocess,sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
root=Path('D:/dsh-proj/Roll');source=root/'.scratch/worktrees/ticket30-producer'
out=root/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket30-stock-independent'
base=json.loads((out/'integrity.json').read_bytes())
def git(repo,*args):return subprocess.check_output(['git','-C',str(repo),*args])
def check(row):
    p=Path(row['path'])
    with p.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
    assert p.stat().st_size==row['bytes'] and sha==row['sha256'],str(p)
    return row
rows=base['protected15_root_source']+base['owned_source_raw_git_identity']+base['actual_raw_git_identity']+base['fixed_public_dependencies']+[base['source_mapping'],base['original19_checksum_only']]
with ThreadPoolExecutor(max_workers=8) as pool:checks=list(pool.map(check,rows))
assert git(source,'rev-parse','HEAD').decode().strip()==base['source_head']
for repo in [source,root]:
    assert git(repo,'diff','--name-only')==b'' and git(repo,'diff','--cached','--name-only')==b''
result={'source_head':base['source_head'],'root_head':git(root,'rev-parse','HEAD').decode().strip(),
    'protected15_root_source_unchanged':True,'original19_checksum_only_unchanged':True,
    'owned9_sources_raw_unchanged':True,'actual_two_originals_fixed_public_dependencies_and_mapping_unchanged':True,
    'checked_byte_items':len(checks),'root_source_tracked_index_clean':True,'preserved_sqlite_connections':0,'actual_network_calls':0}
if len(sys.argv)>1 and sys.argv[1]=='postmerge':
    identities=[]
    for row in base['owned_source_raw_git_identity']+base['actual_raw_git_identity']+base['fixed_public_dependencies']:
        relative=Path(row['path']).relative_to(source).as_posix()
        assert git(root,'rev-parse','HEAD:'+relative).decode().strip()==row['git_blob']
        assert (root/relative).read_bytes()==Path(row['path']).read_bytes(),relative
        identities.append(relative)
    result['merged_root_source_raw_git_equal']=identities
name='final-guard-'+(sys.argv[1] if len(sys.argv)>1 else 'before-merge')+'.json'
(out/name).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result))
