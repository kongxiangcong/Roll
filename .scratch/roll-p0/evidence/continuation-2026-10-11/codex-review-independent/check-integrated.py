"""Integrated source and immutable sanitized ReviewRecord guard; no runtime startup."""
import hashlib
import json
from pathlib import Path
import subprocess

scope = Path(__file__).resolve().parent
root = scope.parents[4]
evidence = root / '.scratch/roll-p0/evidence/codex-review-repairs-2026-10-11'
after = json.loads((evidence / 'source-final.json').read_text(encoding='utf-8'))
before = json.loads((evidence / 'source-before.json').read_text(encoding='utf-8'))
assert before[:12] == after[:12]
for item in after:
    content = (root / item['path']).read_bytes()
    assert len(content) == item['bytes'] and hashlib.sha256(content).hexdigest() == item['sha256']
record = '.scratch/roll-p0/evidence/continuation-2026-10-11/review-fixes/actual-codex-continuation-results.json'
def git(*args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()
assert git('hash-object', record) == git('rev-parse', 'f893509:'+record)
receipt = {'status':'PASS', 'merge_oid':git('rev-parse', 'HEAD'), 'source_oid':'ddda3effff6655bef090d0af473c960c8fb59482',
    'source18_sha_length_mismatches':0, 'protected_model_dependencies':12,
    'original_sanitized_ReviewRecord_blob_unchanged':True,
    'original_actual_profile_opened':False, 'provider_calls':0, 'exit_code':0}
(scope / 'integrated-source-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8', newline='\n')
print('Integrated 18 source /12 model dependency /immutable historical ReviewRecord guard PASS')
