"""Independent full byte recheck; never open saved SQLite as a database."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib,json
root=Path('D:/dsh-proj/Roll')
out=Path(__file__).parent
manifest=json.loads((out/'runtime-preservation-manifest.json').read_text())
target=root/'.roll-data/implementation-evidence/ticket28/final-internal-v2'
def proof(path):
    file=Path('\\\\?\\'+str(path))
    with file.open('rb') as stream: digest=hashlib.file_digest(stream,'sha256').hexdigest()
    return {'bytes':file.stat().st_size,'sha256':digest}
def verify(row):
    expected={k:row[k] for k in ('bytes','sha256')}
    assert proof(root/row['source'])==proof(root/row['destination'])==expected,row['source']
    return True
with ThreadPoolExecutor(max_workers=8) as pool: checks=list(pool.map(verify,manifest))
long_target=Path('\\\\?\\'+str(target))
files={Path(str(p).removeprefix('\\\\?\\')).relative_to(root).as_posix() for p in long_target.rglob('*') if p.is_file()}
expected={r['destination'] for r in manifest}
assert files==expected,(files-expected,expected-files)
assert not any(p.name in {'channel.json','channel.lock','auth.json','.env'} for p in long_target.rglob('*'))
result={'status':'PASS','verified_files':len(checks),'both_sides':len(checks)*2,'bytes':sum(r['bytes'] for r in manifest),
    'hash_length_mismatch':0,'missing':0,'extra':0,'sqlite_opened':False,'private_configuration_opened_hashed_copied':False}
(out/'runtime-full-recheck.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result))
