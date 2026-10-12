from pathlib import Path
import hashlib, json, subprocess, concurrent.futures, math
from roll.decisions.capabilities import source_inventory

root = Path('D:/dsh-proj/Roll')
source = Path.cwd().resolve()
out = root / '.scratch/roll-p0/evidence/continuation-2026-10-11/ticket25-independent/decision-states'
ev = source / '.scratch/roll-p0/evidence/ticket25'
old = json.loads((ev / 'runtime-preservation-handoff.json').read_text(encoding='utf-8'))
latest = json.loads((ev / 'runtime-preservation-latest.json').read_text(encoding='utf-8'))
guard = json.loads((ev / 'source-guard-latest.json').read_text(encoding='utf-8'))
bench = json.loads((ev / 'benchmark-results.json').read_text(encoding='utf-8'))

def check(path, sha, size):
    path = Path(path).resolve()
    with path.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    assert actual == sha and path.stat().st_size == size, str(path)
    return {'path': str(path), 'sha256': actual, 'bytes': size}

assert len(old['files']) == 1934 and len(latest['files']) == 3135
prior = {row['destination']: row for row in old['files']}
current = {row['destination']: row for row in latest['files']}
assert len(prior) == 1934 and len(current) == 3135
assert all(current[path] == row for path, row in prior.items())
added = [row for path, row in current.items() if path not in prior]
assert len(added) == 1201
jobs = []
for row in added:
    s, d = Path(row['source']).resolve(), Path(row['destination']).resolve()
    assert s.is_relative_to(source / '.scratch')
    assert d.is_relative_to(root / '.roll-data/implementation-evidence/ticket25')
    assert not any(word in s.name.lower() for word in ['auth.json', '.env', 'credential', 'token'])
    jobs.extend([(s, row['sha256'], row['bytes']), (d, row['sha256'], row['bytes'])])
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    archives = list(pool.map(lambda args: check(*args), jobs))
protected = json.loads((root / '.scratch/roll-p0/evidence/codex-review-repairs-2026-10-11/source-final.json').read_text(encoding='utf-8'))[:15]
protected_checks = [check(repo / row['path'], row['sha256'], row['bytes']) for row in protected for repo in [source, root]]
original = guard['original_database']
database = check(root / original['path'], original['sha256'], original['bytes'])
artifacts = [check(row['path'], row['sha256'], row['bytes']) for row in guard['allowed_model_artifacts_unchanged']]
assert source_inventory() == guard['application_sources'] == bench['application_sources']
samples = bench['samples_seconds']
assert len(samples) == len(bench['numeric_layer_seconds']) == len(bench['application_layer_seconds']) == 21
p95 = sorted(samples)[math.ceil(len(samples) * .95) - 1]
assert abs(p95 - bench['nearest_rank_p95_seconds']) < 1e-10
assert all(abs(t - n - a) < 1e-7 for t, n, a in zip(samples, bench['numeric_layer_seconds'], bench['application_layer_seconds']))
result = {'source_oid': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'previous_1934_manifest_entries_unchanged': True, 'new_archive_files': 1201,
    'new_archive_bytes': sum(row['bytes'] for row in added), 'source_destination_checks': len(archives), 'mismatches': 0,
    'new_archive_hashes': archives, 'protected_15_root_source': protected_checks,
    'original19_checksum_only': database, 'allowed_model_artifacts': artifacts,
    'final_source_inventory_matches_guard_and_benchmark': True,
    'implementer_benchmark_receipt_review_only': {'samples': 21, 'p95_seconds': p95, 'stage_sum_consistent': True, 'independent_benchmark_reruns': 0}}
(out / 'integrity.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k not in ['new_archive_hashes', 'protected_15_root_source', 'allowed_model_artifacts']}, ensure_ascii=False))
