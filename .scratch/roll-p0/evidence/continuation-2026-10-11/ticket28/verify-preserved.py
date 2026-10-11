"""Independent full byte recheck; never open saved SQLite as a database."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,sys
root=Path('D:/dsh-proj/Roll')
out=Path(__file__).parent
correction=len(sys.argv)>1 and sys.argv[1]=='length-correction'
current=len(sys.argv)>1 and sys.argv[1]=='current-composition'
assert len(sys.argv)==1 or (len(sys.argv)==2 and (correction or current))
prefix='current-runtime' if current else ('length-runtime' if correction else 'runtime')
manifest=json.loads((out/(prefix+'-preservation-manifest.json')).read_text())
target=root/'.roll-data/implementation-evidence/ticket28'/('current-composition' if current else ('length-correction' if correction else 'final-internal-v2'))
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
(out/(prefix+'-full-recheck.json')).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result))
