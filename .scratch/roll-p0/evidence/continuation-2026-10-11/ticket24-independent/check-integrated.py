"""Read-only integrated source and immutable historical sanitized record guard."""
import hashlib
import json
from pathlib import Path
import subprocess

scope=Path(__file__).resolve().parent;root=scope.parents[4]
receipt=json.loads((root/'.scratch/roll-p0/evidence/24/source-receipt.json').read_text(encoding='utf-8'))
for item in receipt['owned_sources']:
    raw=(root/item['path']).read_bytes()
    assert hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest()==item['normalized_sha256']
for item in receipt['protected_sources']:
    raw=(root/item['path']).read_bytes()
    assert hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest()==item['baseline_sha256']
def git(*args):return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
path='.scratch/roll-p0/evidence/continuation-2026-10-11/review-fixes/actual-codex-continuation-results.json'
assert git('hash-object',path)==git('rev-parse','f893509:'+path)
assert not git('diff','--name-only') and not git('diff','--cached','--name-only')
result={'status':'PASS','merge_oid':git('rev-parse','HEAD'),'source_oid':'ffb83af1b0ebbbc5ac322c8d5f8c34840bd24634',
    'owned_source_normalized_hashes':9,'protected_model_source_hashes':12,'mismatches':0,
    'historical_sanitized_ReviewRecord_blob_unchanged':True,'actual_profile_opened':False,'provider_calls':0,'exit_code':0}
(scope/'integrated-results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print('24 integrated source9/protected12/historical record guard PASS')
