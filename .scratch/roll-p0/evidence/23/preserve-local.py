"""Copy only stopped ticket23-owned evidence; verify every byte, omit auth."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[4]
DEST=Path(r'D:\dsh-proj\Roll\.roll-data\implementation-evidence\23')
EVIDENCE=Path(__file__).resolve().parent

def preserve(source, target, excludes=()):
    rows=[]
    omitted=[]
    for path in sorted(source.rglob('*')):
        if not path.is_file():continue
        relative=path.relative_to(source).as_posix()
        if relative in excludes:
            omitted.append({'path':relative,'reason':'synthetic METHOD credential excluded'})
            continue
        raw=path.read_bytes()
        sha=hashlib.sha256(raw).hexdigest()
        output=target/relative
        output.parent.mkdir(parents=True,exist_ok=True)
        if output.exists():assert output.read_bytes()==raw, str(output)
        else:shutil.copyfile(path,output)
        copied=output.read_bytes()
        assert len(copied)==len(raw) and hashlib.sha256(copied).hexdigest()==sha
        rows.append({'path':relative,'bytes':len(raw),'sha256':sha})
    return {'source':str(source),'destination':str(target),'files':rows,
            'file_count':len(rows),'total_bytes':sum(r['bytes'] for r in rows),
            'mismatches':0,'excluded':omitted}

browser=preserve(ROOT/'.roll-data/browser-final',DEST/'browser-method-final',
                 {'tasks/browser-review-method/auth.json'})
approval=preserve(EVIDENCE/'provider-materials',DEST/'provider-approval/provider-materials')
for name in ['provider-material-manifest.json','actual-material.json','actual-copy-manifest.json']:
    raw=(EVIDENCE/name).read_bytes()
    output=DEST/'provider-approval'/name
    output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():assert output.read_bytes()==raw
    else:output.write_bytes(raw)
    assert output.read_bytes()==raw
    approval['files'].append({'path':'../'+name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
approval['file_count']=len(approval['files'])
approval['total_bytes']=sum(r['bytes'] for r in approval['files'])
(EVIDENCE/'preservation-manifest.json').write_text(json.dumps({'browser':browser,'provider_approval_local_only':approval},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'browser_files':browser['file_count'],'approval_files':approval['file_count'],'mismatches':0,'external_transmissions':0}))
