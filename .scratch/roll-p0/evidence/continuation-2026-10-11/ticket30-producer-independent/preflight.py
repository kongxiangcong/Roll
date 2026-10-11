"""Read-only stable-source, original19 checksum and both retained runtime checks."""
import hashlib
import json
from pathlib import Path
import subprocess
from concurrent.futures import ThreadPoolExecutor

SCOPE=Path(__file__).resolve().parent
ROOT=SCOPE.parents[4]
CHILD=ROOT/'.scratch/worktrees/ticket30-producer'
EVIDENCE=CHILD/'.scratch/roll-p0/evidence/30-producer'
OID='c67378800ab35ec791d7d817f66465edab3aaef7'
def git(*args):return subprocess.check_output(['git','-C',str(CHILD),*args],text=True).strip()
def info(path):
    digest=hashlib.sha256();size=0
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            digest.update(block);size+=len(block)
    return {'sha256':digest.hexdigest(),'bytes':size}
assert git('rev-parse','HEAD')==OID and not git('status','--porcelain','--untracked-files=no')
assert subprocess.run(['git','-C',str(CHILD),'merge-base','--is-ancestor','580b801',OID]).returncode==0
source=json.loads((EVIDENCE/'source-composition-after.json').read_text(encoding='utf-8'))
assert source==json.loads((EVIDENCE/'source-composition-before.json').read_text(encoding='utf-8'))
assert len(source['protected'])==15 and len(source['own'])==6
for item in source['protected']:
    assert item['root']==item['worktree']
    for base in [ROOT,CHILD]:assert info(base/item['path'])==item['root'],item['path']
for name,expected in source['own'].items():assert info(CHILD/name)==expected,name
assert info(ROOT/'.roll-data/reconstructed19-v1/roll.sqlite3')==source['original19_sqlite']
assert source['original19_sqlite']['sha256']=='ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4'
preserved=[]
def verify(item):
    for key in ['source','destination']:
        path=Path('\\\\?\\'+item[key])
        assert info(path)=={'sha256':item['sha256'],'bytes':item['bytes']},item[key]
    return 1
for prefix,count,size in [('runtime',13891,1269967416),('composition',98,16859917)]:
    manifest=json.loads((EVIDENCE/(prefix+'-preservation-manifest.json')).read_text(encoding='utf-8'))
    receipt=json.loads((EVIDENCE/(prefix+'-preservation-receipt.json')).read_text(encoding='utf-8'))
    assert len(manifest)==count==receipt['files'] and sum(i['bytes'] for i in manifest)==size==receipt['bytes']
    assert receipt['sha_or_length_mismatches']==0
    with ThreadPoolExecutor(max_workers=8) as pool:
        completed=sum(pool.map(verify,manifest))
    assert completed==count
    print(prefix+' all '+str(completed)+' source/destination files PASS',flush=True)
    preserved.append({'manifest':prefix,'files':count,'bytes':size,'SHA_length_mismatches':0})
result={'status':'PASS','stable_oid':OID,'protected_raw_sources':15,'protected_model_sources':12,
    'owned_raw_sources':6,'original19_checksum_only':source['original19_sqlite'],'actual_DB_opened':False,
    'preservation':preserved,'provider_calls':0,'verifier_workers':8,'streaming_SHA_block_bytes':1048576,
    'full_independent_restart_after_serial_partial':True}
(SCOPE/'preflight-results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print('Preflight PASS: stable 6 sources / 15 protected, original19 checksum unchanged, 13989 preserved files / 0 mismatches')
