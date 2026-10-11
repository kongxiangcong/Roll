"""Opaque verified copy of the closed public pre-repair runtime; never opens SQLite."""
from pathlib import Path
import hashlib, json, shutil
own = Path(__file__).resolve().parents[4]
source = own / '.fr/pr/test_prepare_retry_returns_ori0/data'
target = Path('D:/dsh-proj/Roll/.roll-data/implementation-evidence/final-review-fix/legacy-profile')
assert source.resolve().is_relative_to(own.resolve()) and not target.exists()
assert target.resolve().is_relative_to(Path('D:/dsh-proj/Roll/.roll-data/implementation-evidence/final-review-fix').resolve())
def long(path): return '\\\\?\\' + str(path.resolve())
entries=[]
for file in sorted(source.rglob('*')):
    if not file.is_file(): continue
    assert file.name.lower() not in {'auth.json','credentials.json','.env','channel.json'} and not file.name.lower().startswith('.env')
    relative=file.relative_to(source).as_posix()
    original=Path(long(file)).read_bytes()
    destination=target/relative
    Path(long(destination.parent)).mkdir(parents=True,exist_ok=True)
    shutil.copyfile(long(file),long(destination))
    assert Path(long(destination)).read_bytes()==original and Path(long(file)).read_bytes()==original
    entries.append({'path':relative,'bytes':len(original),'sha256':hashlib.sha256(original).hexdigest()})
record=json.loads((source.parent/'original-prepare.json').read_text(encoding='utf-8'))
value={'source':str(source),'target':str(target),'source_stage':'red-prepare before separate receipt table',
       'connections_to_source_or_preserved_SQLite':0,'files':len(entries),'bytes':sum(e['bytes'] for e in entries),
       'double_end_mismatches':0,'entries':entries,'public_original_prepare':record}
out=Path(__file__).with_name('legacy-profile-manifest.json')
assert not out.exists()
out.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'files':value['files'],'bytes':value['bytes'],'manifest_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'double_end_mismatches':0}))
