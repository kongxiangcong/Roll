"""Read-only integrated source guard, before scoped evidence commit."""
from pathlib import Path
import hashlib,json,subprocess
SCOPE=Path(__file__).resolve().parent;ROOT=SCOPE.parents[4]
def info(p):
    h=hashlib.sha256();size=0
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b);size+=len(b)
    return {'sha256':h.hexdigest(),'bytes':size}
before=json.loads((SCOPE/'preflight-results.json').read_text())
for item in before['protected']:assert info(ROOT/item['path'])=={k:item[k] for k in ['sha256','bytes']}
for path,expected in before['own'].items():assert info(ROOT/path)==expected,path
assert info(ROOT/'.roll-data/reconstructed19-v1/roll.sqlite3')==before['original19_checksum_only']
issue=(ROOT/'.scratch/roll-p0/issues/31-engineering-delivery.md').read_text(encoding='utf-8')
assert '**Completion:** partial' in issue
tip=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
assert tip=='6c0f2d50403239bd022732a7e4592c79550891b2'
assert subprocess.run(['git','-C',str(ROOT),'merge-base','--is-ancestor',before['stable_oid'],tip]).returncode==0
result={'status':'PASS','merge_oid':tip,'source_oid':before['stable_oid'],'source_and_locks_root_MATCH_frozen':5,'protected_sources_raw_MATCH':15,'original19_checksum_only':before['original19_checksum_only'],'Completion31':'partial','no_push':True,'no_cleanup':True,'scope_only':'ticket31-independent'}
(SCOPE/'integration.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print('Integrated source, 15 protected and original19 checksum PASS')
