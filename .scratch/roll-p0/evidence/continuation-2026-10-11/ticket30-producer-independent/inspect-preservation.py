"""Full nonmutating collection of source/destination preservation differences."""
import hashlib
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

SCOPE=Path(__file__).resolve().parent
ROOT=SCOPE.parents[4]
CHILD=ROOT/'.scratch/worktrees/ticket30-producer'
EVIDENCE=CHILD/'.scratch/roll-p0/evidence/30-producer'
def info(p):
    digest=hashlib.sha256();size=0
    with p.open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):
            size+=len(block);digest.update(block)
    return {'sha256':digest.hexdigest(),'bytes':size}
def check(item):
    actual={key:info(Path('\\\\?\\'+item[key])) for key in ['source','destination']}
    expected={key:item[key] for key in ['bytes','sha256']}
    return None if all(value==expected for value in actual.values()) else {
        'source':item['source'],'destination':item['destination'],'expected':expected,'actual':actual}
differences=[];files=0;size=0
for prefix in ['runtime','composition']:
    manifest=json.loads((EVIDENCE/(prefix+'-preservation-manifest.json')).read_text(encoding='utf-8'))
    files+=len(manifest);size+=sum(i['bytes'] for i in manifest)
    with ThreadPoolExecutor(max_workers=8) as pool:
        differences += [r for r in pool.map(check,manifest) if r is not None]
    print(prefix+' complete diff inspection',flush=True)
result={'status':'FAIL' if differences else 'PASS','files':files,'bytes':size,
    'differences':differences,'SQL_connections_opened':False,'writes_to_profiles':False}
(SCOPE/'preservation-differences.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print('Complete preservation differences: '+str(len(differences)))
