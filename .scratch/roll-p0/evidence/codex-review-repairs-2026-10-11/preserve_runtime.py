"""Preserve these completed METHOD runtime profiles without replacing archives."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

root=Path(__file__).resolve().parents[4]
name=sys.argv[1]
sources={'old-method':root/'.scratch/old-comparator-method',
         'new-method':root/'.scratch/crapi/test_repaired_comparator_and_s0',
         'final-method':root/'.scratch/crfinal/test_repaired_comparator_and_s0'}
source=sources[name].resolve()
destination=Path('D:/dsh-proj/Roll/.roll-data/implementation-evidence/codex-review-fixes')/name
assert source.is_dir() and not destination.exists()
files=[]
for original in sorted(source.rglob('*')):
    if not original.is_file():continue
    assert original.name!='.env'
    relative=original.relative_to(source)
    target=destination/relative
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(original,target)
    content=original.read_bytes();copied=target.read_bytes()
    assert copied==content
    files.append({'path':relative.as_posix(),'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()})
assert files
result={'source':str(source),'destination':str(destination),'files':files,'file_count':len(files),
        'bytes':sum(r['bytes'] for r in files),'sha256_and_length_mismatches':0,'evidence_kind':'METHOD_CASE'}
(Path(__file__).parent/('runtime-'+name+'-manifest.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({key:value for key,value in result.items() if key!='files'}))
