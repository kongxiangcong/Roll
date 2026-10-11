"""Append a new byte-verified METHOD capture; do not SQLite-open or alter old captures."""
import hashlib,json,shutil
from pathlib import Path
root=Path(__file__).resolve().parents[5]
folder=Path(__file__).parent
assert root==Path('D:/dsh-proj/Roll/.scratch/worktrees/codex-runner-scope')
index=Path('D:/dsh-proj/Roll/.roll-data/implementation-evidence/codex-runner-scope')
target=index/'runner-2026-10-11'
assert not target.exists()
browser=json.loads((root/'frontend/test-results/default/manifest.json').read_text(encoding='utf-8'))
runtime=Path(browser['data_root']);report=Path(browser['report_root'])
assert runtime.is_relative_to(root/'backend/.roll-data') and report.is_relative_to(root/'frontend/test-results')
assert browser['profile']=='DEFAULT_OFFLINE_SUBSET' and browser['exit_code']==0
shutil.copytree(report,folder/'browser-report')
shutil.copyfile(root/'frontend/test-results/default/manifest.json',folder/'browser-manifest.json')
sources={name:root/'.scratch'/name for name in ['crmr','crmg','crsf','crs25']}
sources['default-browser']=runtime
rows=[]
for name,source in sources.items():
    assert source.is_dir() and not source.is_symlink()
    for path in sorted(Path('\\\\?\\'+str(source)).rglob('*')):
        if not path.is_file():continue
        relative=path.relative_to(Path('\\\\?\\'+str(source)))
        output=Path('\\\\?\\'+str(target/name/relative))
        raw=path.read_bytes();output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(raw)
        assert output.read_bytes()==raw
        rows.append({'path':name+'/'+relative.as_posix(),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
value={'kind':'METHOD_CASE_ONLY','capture':str(target),'files':len(rows),'bytes':sum(r['bytes'] for r in rows),
       'mismatches':0,'inventory':rows}
receipt=json.dumps(value,indent=2).encode()
(target/'runtime-manifest.json').write_bytes(receipt)
(folder/'runtime-preservation.json').write_bytes(receipt)
summary={key:item for key,item in value.items() if key!='inventory'}
manifest=index/'manifest.jsonl'
old=manifest.read_bytes() if manifest.exists() else b''
assert not old or old.endswith(b'\n')
with manifest.open('ab') as stream:stream.write((json.dumps(summary)+'\n').encode())
assert manifest.read_bytes().startswith(old)
(folder/'root-manifest-append.json').write_text(json.dumps({'path':str(manifest),'prior_bytes':len(old),
    'prior_sha256':hashlib.sha256(old).hexdigest(),'bytes':manifest.stat().st_size,
    'sha256':hashlib.sha256(manifest.read_bytes()).hexdigest()},indent=2),encoding='utf-8',newline='\n')
print(json.dumps(summary))
