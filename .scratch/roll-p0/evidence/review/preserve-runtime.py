"""Exact, task-owned stopped review runtimes; no discovery or deletion."""
import hashlib,json,shutil,stat,sys,os
from pathlib import Path
from datetime import datetime,timezone

workspace=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(workspace/'backend'/'src'))
from roll.agents.codex_process import owner_alive
source_parent=(workspace/'backend'/'.roll-data').resolve()
target_parent=source_parent/'implementation-evidence'/'review-fixes'
owned=['iR','iG','pR','fR','lifecycle-final','owner-final2','e2e-default-qO4qis']
records=[];owners=[];excluded=[]
def io_path(path):return Path('\\\\?\\'+str(path)) if os.name=='nt' else path
for name in owned:
    source=(source_parent/name).resolve()
    assert source.parent==source_parent and source.is_dir()
    source_io=io_path(source)
    for marker in source_io.rglob('.host-*.json'):
        owner=json.loads(marker.read_text(encoding='utf-8'))
        assert not owner_alive({'host_owner':owner}),f'active owned host: {marker}'
        owners.append({'marker':str(marker),'host_owner':owner,'alive':False})
    for path_io in sorted(source_io.rglob('*')):
        assert not path_io.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
        path_io.resolve().relative_to(source_io.resolve())
        if not path_io.is_file():continue
        relative=path_io.relative_to(source_io)
        path=source/relative
        if path.name.lower() in {'auth.json','api-key.txt','deepseek-key.txt'}:
            excluded.append(str(path));continue
        original=path_io.read_bytes();digest=hashlib.sha256(original).hexdigest()
        target=target_parent/name/relative
        target_io=io_path(target)
        target_io.parent.mkdir(parents=True,exist_ok=True)
        if target_io.exists():assert target_io.read_bytes()==original
        else:shutil.copyfile(io_path(path),target_io)
        retained=target_io.read_bytes()
        assert len(retained)==len(original) and hashlib.sha256(retained).hexdigest()==digest
        records.append({'source':str(path),'destination':str(target),'bytes':len(original),'sha256':digest})
result={'checked_at':datetime.now(timezone.utc).isoformat(),'scope':'Exact seven task-owned stopped runtimes; new full-suite active directory excluded',
    'source_roots':[str(source_parent/n) for n in owned],'target_root':str(target_parent),
    'host_markers':owners,'credential_files_excluded':excluded,'copies':records,
    'files':len(records),'bytes':sum(r['bytes'] for r in records),'mismatches':0}
(workspace/'.scratch/roll-p0/evidence/review/runtime-preservation.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
print(json.dumps({k:result[k] for k in ['target_root','files','bytes','mismatches','credential_files_excluded']},ensure_ascii=False))
