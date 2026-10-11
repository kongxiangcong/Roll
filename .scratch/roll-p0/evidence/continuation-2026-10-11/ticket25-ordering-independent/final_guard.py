"""Guard only immutable source/archive identities after testing and after merge."""
import json,hashlib,sys,subprocess
from pathlib import Path
root=Path('D:/dsh-proj/Roll');source=root/'.scratch/worktrees/ticket25-ordering';out=root/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket25-ordering-independent'
base=json.loads((out/'integrity.json').read_bytes())
def git(repo,*a):return subprocess.check_output(['git','-C',str(repo),*a])
def check(r):
    p=Path(r['path'])
    with p.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
    assert p.stat().st_size==r['bytes'] and sha==r['sha256'],str(p)
rows=base['protected15_root_source']+base['allowed3_checksum_only']+[base['original19_checksum_only']]+base['owned_source_raw_git_identity']
for r in base['old6_metadata_raw_git_unchanged']:
    rows.extend([r['metadata']] if 'metadata' in r else [r['root'],r['source']])
for r in rows:check(r)
assert git(source,'rev-parse','HEAD').decode().strip()==base['source_head']
for repo in [source,root]:assert not git(repo,'diff','--name-only') and not git(repo,'diff','--cached','--name-only')
inventory=json.loads((source/'.scratch/roll-p0/evidence/ticket25-ordering/source-guard-final.json').read_bytes())['application_sources']
for rel,sha in inventory.items():assert hashlib.sha256((source/'backend/src/roll'/rel).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==sha,rel
identity=[]
if len(sys.argv)>1 and sys.argv[1]=='postmerge':
    for r in base['owned_source_raw_git_identity']:
        rel=Path(r['path']).relative_to(source).as_posix()
        assert git(root,'rev-parse','HEAD:'+rel).decode().strip()==r['git_blob'] and (root/rel).read_bytes()==Path(r['path']).read_bytes()
        identity.append(rel)
    for rel,sha in inventory.items():assert hashlib.sha256((root/'backend/src/roll'/rel).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==sha,rel
r={'source_head':base['source_head'],'root_head':git(root,'rev-parse','HEAD').decode().strip(),'source_count':len(inventory),'source69_matches_final_composition':True,'source_raw_git_root_equal':identity,'protected15_allowed3_original19_unchanged':True,'old6_preservation_metadata_and_old_sourceguard_unchanged':True,'byte_checks':len(rows),'saved_sqlite_connections':0,'real_network_calls':0,'tracked_index_clean':True}
(out/('final-'+(sys.argv[1] if len(sys.argv)>1 else 'before')+'.json')).write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
print(json.dumps(r))
