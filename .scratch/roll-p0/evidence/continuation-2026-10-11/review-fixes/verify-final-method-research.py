"""Opaque immutable readonly comparison of historical/final stopped METHOD rows."""
import hashlib
import json
from pathlib import Path
import sqlite3

SCOPE = Path(__file__).resolve().parent
manifest = json.loads((SCOPE / 'runtime-failed-forward-manifest.json').read_text())
snapshots = {}
row_hashes = {}
for label, key in (('historical', 'destination'), ('final_source', 'source')):
    path = Path(manifest[key]) / 'roll.sqlite3'
    wal = Path(str(path) + '-wal')
    assert not wal.exists() or wal.stat().st_size == 0
    with sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True) as db:
        names = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'research_%' ORDER BY name")]
        values = {}
        row_hashes[label] = {}
        for name in names:
            rows = sorted(hashlib.sha256(repr(tuple(row)).encode()).hexdigest() for row in db.execute('SELECT * FROM ' + name))
            row_hashes[label][name] = rows
            values[name] = {'rows': len(rows), 'opaque_rows_sha256': hashlib.sha256(json.dumps(rows).encode()).hexdigest()}
        snapshots[label] = values
unchanged = snapshots['historical'] == snapshots['final_source']
differences = {name: {'historical': snapshots['historical'].get(name), 'final_source': snapshots['final_source'].get(name)}
    for name in set(snapshots['historical']) | set(snapshots['final_source'])
    if snapshots['historical'].get(name) != snapshots['final_source'].get(name)}
original_rows_intact = all(set(rows).issubset(row_hashes['final_source'].get(name, []))
    for name, rows in row_hashes['historical'].items())
only_one_check_appended = (set(differences) == {'research_forward_checks'} and original_rows_intact
    and snapshots['final_source']['research_forward_checks']['rows'] == snapshots['historical']['research_forward_checks']['rows'] + 1)
accepted = unchanged or only_one_check_appended
result = {'status': 'PASS' if accepted else 'STOP_RESEARCH_DIFF', 'all_research_tables_opaque_rows_unchanged': unchanged,
    'all_original_research_rows_unchanged': original_rows_intact, 'one_diagnostic_forward_check_appended': only_one_check_appended,
    'table_count': len(snapshots['historical']), 'tables': snapshots['historical'],
    'changed_DB_scope': 'Host startup/backup/session lifecycle and one append-only forward check; all original research row values unchanged',
    'differences': differences, 'protected_SEALED_or_credentials_read': False}
(SCOPE / 'cleanup-research-invariance.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
print(json.dumps({'status': result['status'], 'differences': differences}))
assert accepted, 'Original research metadata changed: stop cleanup and inspect exact table delta'
