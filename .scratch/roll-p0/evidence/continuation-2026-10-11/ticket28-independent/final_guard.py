"""Fresh guard, root parent-owned dirty documents explicitly retained."""
import json,hashlib,subprocess,sys
from pathlib import Path
root=Path('D:/dsh-proj/Roll');source=root/'.scratch/worktrees/ticket28';out=root/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket28-independent';base=json.loads((out/'integrity.json').read_bytes())
def git(repo,*a):return subprocess.check_output(['git','-C',str(repo),*a])
def proof(p):
    with p.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
    return {'path':str(p),'bytes':p.stat().st_size,'sha256':sha}
rows=base['protected15_root_source']+[base['original19_checksum_only']]+base['source109_raw_git_identity']
for r in rows:
    got=proof(Path(r['path']));assert got['bytes']==r['bytes'] and got['sha256']==r['sha256'],r['path']
assert git(source,'rev-parse','HEAD').decode().strip()==base['source_head']
assert not git(source,'diff','--name-only') and not git(source,'diff','--cached','--name-only') and not git(root,'diff','--cached','--name-only')
dirty=git(root,'diff','--name-only').decode().splitlines();allowed={'.scratch/roll-p0/execution-status.md','.scratch/roll-p0/requirements-traceability.md'}
assert set(dirty)<=allowed,dirty
snapshot=[proof(root/p) for p in dirty];stage=sys.argv[1] if len(sys.argv)>1 else 'before'
if stage=='postmerge':
    for r in json.loads((out/'parent-dirty-documents-before.json').read_bytes()):assert proof(Path(r['path']))==r,r['path']
else:(out/'parent-dirty-documents-before.json').write_text(json.dumps(snapshot,indent=2)+'\n',encoding='utf-8')
identities=[]
if stage=='postmerge':
    for r in base['source109_raw_git_identity']:
        rel=Path(r['path']).relative_to(source).as_posix()
        assert git(root,'rev-parse','HEAD:'+rel).decode().strip()==r['git_blob'] and (root/rel).read_bytes()==Path(r['path']).read_bytes(),rel
        identities.append(rel)
r={'source_head':base['source_head'],'root_head':git(root,'rev-parse','HEAD').decode().strip(),'source109_raw_unchanged':True,'root_source_raw_git_identity':identities,'protected15_original19_checksum_unchanged':True,'checked_byte_items':len(rows),'parent_owned_dirty_documents':snapshot,'index_clean':True,'saved_sqlite_connections':0,'actual_ntfy_provider_calls':0}
(out/('final-'+stage+'.json')).write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8');print(json.dumps(r))
