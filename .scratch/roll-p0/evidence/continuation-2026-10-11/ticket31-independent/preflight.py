"""Read file bytes only; no saved profile is opened as SQLite."""
from pathlib import Path
import hashlib,json,subprocess,sys
from concurrent.futures import ThreadPoolExecutor
SCOPE=Path(__file__).resolve().parent
ROOT=SCOPE.parents[4]
CHILD=Path('C:/Users/72449/.codex/worktrees/ticket31-delivery/Roll')
OID='a19ce9b592aa0ae207255c40691cb6d76f1e6554'
def info(p):
    h=hashlib.sha256();size=0
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b);size+=len(b)
    return {'sha256':h.hexdigest(),'bytes':size}
def git(*a):return subprocess.check_output(['git','-C',str(CHILD),*a],text=True).strip()
assert git('rev-parse','HEAD')==OID
assert not git('status','--porcelain','--untracked-files=no')
assert subprocess.run(['git','-C',str(CHILD),'merge-base','--is-ancestor','2db3bd1',OID]).returncode==0
baseline=json.loads((ROOT/'.scratch/roll-p0/evidence/30-producer/source-composition-after.json').read_text())
protected=[]
for item in baseline['protected']:
    for base in (ROOT,CHILD):assert info(base/item['path'])==item['root'],item['path']
    protected.append({'path':item['path'],**item['root']})
assert len(protected)==15
original=info(ROOT/'.roll-data/reconstructed19-v1/roll.sqlite3')
assert original==baseline['original19_sqlite']
own={p:info(CHILD/p) for p in ['backend/src/roll/app.py','backend/src/roll/runtime/reviews.py','backend/src/roll/worker.py','backend/uv.lock','frontend/package-lock.json']}
base=ROOT/'.roll-data/implementation-evidence/31/worker-delivery'
def verify(pair):
    item,archive=pair;expected={'sha256':item['sha256'],'bytes':item['bytes']}
    errors=[]
    for kind,p in [('source',Path(item['source'])),('root',archive/item['archived'])]:
        try:actual=info(Path('\\\\?\\'+str(p)))
        except OSError as e:actual={'error':type(e).__name__}
        if actual!=expected:errors.append({'kind':kind,'path':str(p),'expected':expected,'actual':actual})
    return errors
summaries=[];differences=[]
for archive,count in [(base,4057),(base/'composition30',237)]:
    m=archive/'archive-manifest.json';manifest=json.loads(m.read_text())['files'];assert len(manifest)==count
    with ThreadPoolExecutor(max_workers=8) as pool:
        for diff in pool.map(verify,[(i,archive) for i in manifest]):differences.extend(diff)
    summaries.append({'manifest':str(m),'manifest_hash':info(m),'files':count,'bytes':sum(i['bytes'] for i in manifest)})
    print(str(count)+' source/root files checked',flush=True)
result={'status':'FAIL' if differences else 'PASS','stable_oid':OID,'protected':protected,'original19_checksum_only':original,'own':own,'preservation':summaries,'differences':differences,'SQL_connections_to_saved_profiles':0,'streaming_SHA_threads':8}
name='postflight-results.json' if '--after' in sys.argv else 'preflight-results.json'
if '--after' in sys.argv:
    before=json.loads((SCOPE/'preflight-results.json').read_text())
    assert before['own']==own and before['protected']==protected and before['original19_checksum_only']==original
(SCOPE/name).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
assert not differences,differences
print('Preflight protection and 4294 preservation files PASS',flush=True)
