from pathlib import Path
import json, hashlib, subprocess
from roll.decisions.capabilities import source_inventory

root = Path.cwd().resolve()
out = root / '.scratch/roll-p0/evidence/continuation-2026-10-11/ticket25-independent/decision-states'
guard = json.loads((root / '.scratch/roll-p0/evidence/ticket25/source-guard-latest.json').read_text(encoding='utf-8'))
assert source_inventory() == guard['application_sources']
protected = json.loads((root / '.scratch/roll-p0/evidence/codex-review-repairs-2026-10-11/source-final.json').read_text(encoding='utf-8'))[:15]
for row in protected:
    path = root / row['path']
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    assert digest == row['sha256'] and path.stat().st_size == row['bytes']
merge = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
parents = subprocess.check_output(['git', 'show', '-s', '--format=%P', 'HEAD'], text=True).strip().split()
assert parents == ['28fd34dd77f42ec3288d50cf58c6295196a6cff3', '759033c8bf87af1fecd7dff9021232b33542df0b']
result = {'source_oid': parents[1], 'merge_oid': merge, 'merge_parents': parents,
          'root_source_inventory_matches_independently_checked_source': True, 'protected_15_root_after_merge': True,
          'original19_sqlite_not_opened': True, 'new_actual_http_calls': 0, 'new_benchmark_runs': 0}
(out / 'merge-verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result))
