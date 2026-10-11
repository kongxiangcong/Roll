from pathlib import Path
import json, hashlib, sqlite3, subprocess
from roll.decisions.capabilities import source_inventory

root = Path('D:/dsh-proj/Roll')
source = Path.cwd().resolve()
out = root / '.scratch/roll-p0/evidence/continuation-2026-10-11/ticket25-independent/decision-states'
ev = source / '.scratch/roll-p0/evidence/ticket25'
states = json.loads((ev / 'runtime-preservation-states.json').read_text(encoding='utf-8'))
latest = json.loads((ev / 'runtime-preservation-latest.json').read_text(encoding='utf-8'))
current = {row['destination']: row for row in latest['files']}
assert len(states['files']) == 2922 and len(current) == 3135
assert all(current[row['destination']] == row for row in states['files'])
assert latest['file_count'] == len(current)
runtime = root / '.roll-data/r25states'
databases = sorted(runtime.glob('*/data/roll.sqlite3'))
assert len(databases) == 3
proofs = []
for database in databases:
    assert database.is_relative_to(runtime)
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as db:
        basis = db.execute('SELECT fingerprint,sources FROM capability_method_basis WHERE id=1').fetchone()
        assert json.loads(basis[1]) == source_inventory()
        proofs.append({'owned_database': str(database), 'method_fingerprint': basis[0], 'sources_match_final': True,
                       'immutable_evaluations': db.execute('SELECT count(*) FROM action_evaluations').fetchone()[0]})
files = []
for path in sorted(runtime.rglob('*')):
    if path.is_file():
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        files.append({'path': str(path), 'sha256': digest, 'bytes': path.stat().st_size})
result = {'source_oid': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
          'owned_runtime_root': str(runtime), 'file_count': len(files), 'total_bytes': sum(row['bytes'] for row in files),
          'files': files, 'fresh_owned_method_source_proofs': proofs,
          'overall_source_manifest_files': 3135, 'previous_2922_manifest_entries_unchanged': True,
          'new_final_stage_files': 213, 'only_owned_sqlite_opened': True,
          'actual_profile_sqlite_connections': 0, 'provider_calls': 0, 'training_fits': 0}
(out / 'owned-runtime-manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k != 'files'}, ensure_ascii=False))
