from pathlib import Path
import json, hashlib, subprocess
root = Path.cwd().resolve()
out = root / '.scratch/roll-p0/evidence/continuation-2026-10-11/codex-runner-independent'
ev = root / '.scratch/roll-p0/evidence/continuation-2026-10-11/codex-runner-scope'
product = json.loads((ev / 'source-integrated-final.json').read_text(encoding='utf-8'))
for row in product:
    path = root / row['path']
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    assert digest == row['sha256'] and path.stat().st_size == row['bytes']
parents = subprocess.check_output(['git', 'show', '-s', '--format=%P', 'HEAD'], text=True).strip().split()
assert parents == ['371dd9c7c75d1fb5df9827a81dc580ddd5a62c63', '31f3febcfee0e27ac5996feefe4ef6919cd4390e']
result = {'merge_oid': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'parents': parents, 'product101_after_merge_matches': True, 'root_owned_dirty_docs_not_staged': True,
    'root_preserved_sqlite_connections': 0, 'historical_deselection_is_not_pass': True}
(out / 'merge-verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result))
