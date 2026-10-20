"""Bounded read-only metadata audit, no labels, result metrics or source archives."""
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

repo = Path(__file__).resolve().parents[5]
out = Path(__file__).resolve().parent
stores = [
    repo / '.roll-data/reconstructed19-v1/roll.sqlite3',
    repo / '.roll-data/reconstructed19/roll.sqlite3',
    Path('C:/Users/72449/AppData/Local/Roll/roll.sqlite3'),
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


results = []
for path in stores:
    row = {'path': str(path), 'exists': path.exists()}
    if not path.exists():
        results.append(row)
        continue
    before = digest(path)
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'research_protocols', 'research_attempts', 'research_datasets', 'research_events'} <= tables:
            row['state'] = 'RESEARCH_SCHEMA_NOT_PRESENT'
        else:
            for table, bound in [('research_protocols', 100), ('research_attempts', 100)]:
                assert db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] <= bound, table
            protocols = [dict(zip(['id', 'predecessor_id', 'dataset_id', 'fingerprint'], r)) for r in db.execute(
                """SELECT id,json_extract(value,'$.predecessor_id'),json_extract(value,'$.dataset_id'),
                json_extract(value,'$.protocol_fingerprint') FROM research_protocols""")]
            attempts = [dict(zip(['id', 'protocol_id', 'category', 'status', 'started_at'], r)) for r in db.execute(
                """SELECT id,protocol_id,json_extract(value,'$.category'),json_extract(value,'$.status'),
                json_extract(value,'$.started_at') FROM research_attempts""")]
            terminal = db.execute("""SELECT json_extract(value,'$.attempt_id'),json_extract(value,'$.status')
                FROM research_events WHERE json_extract(value,'$.action') IN ('ATTEMPT_FINISHED','ATTEMPT_INTERRUPTED')
                ORDER BY ordinal LIMIT 201""").fetchall()
            assert len(terminal) <= 200
            statuses = dict(terminal)
            for attempt in attempts:
                attempt['terminal_status'] = statuses.get(attempt['id'], 'NO_TERMINAL_EVENT')
            datasets = []
            for identifier in sorted({p['dataset_id'] for p in protocols if p['dataset_id']}):
                metadata = db.execute("""SELECT id,json_extract(value,'$.source_evidence_kind'),
                    json_extract(value,'$.data_use'),json_extract(value,'$.source_origin'),
                    json_extract(value,'$.data_fingerprint') FROM research_datasets WHERE id=?""", (identifier,)).fetchone()
                datasets.append(dict(zip(['id', 'source_evidence_kind', 'data_use', 'source_origin', 'fingerprint'], metadata)))
            by_id = {p['id']: p for p in protocols}
            families = {}
            for protocol in protocols:
                current = protocol['id']
                visited = set()
                while by_id[current]['predecessor_id']:
                    assert current not in visited, 'CYCLIC_LINEAGE'
                    visited.add(current)
                    current = by_id[current]['predecessor_id']
                families.setdefault(current, []).append(protocol['id'])
            budgets = []
            for root, members in families.items():
                own = [a for a in attempts if a['protocol_id'] in members]
                fits = sum(a['category'] in ('PRIMARY_FIT', 'G5_NEIGHBOR') for a in own)
                cal = sum(a['category'] == 'CALIBRATION' for a in own)
                budgets.append({'root': root, 'members': members, 'fit_records': fits,
                                'unreserved_fit_limit_remaining': max(0, 5-fits),
                                'calibration_records': cal, 'calibration_remaining': max(0, 1-cal),
                                'feature_reservations': 'NOT_EVALUATED_NOT_A_FIT_ADMISSION'})
            row.update(state='METADATA_READ', protocols=protocols, attempts=attempts, datasets=datasets, families=budgets)
        db.rollback()
    row.update(db_sha256_before=before, db_sha256_after=digest(path))
    row['main_db_bytes_unchanged'] = row['db_sha256_before'] == row['db_sha256_after']
    results.append(row)
result = {'observed_at': datetime.now(timezone.utc).isoformat(), 'stores': results,
          'network_calls': 0, 'label_reads': 0, 'archive_reads': 0, 'fit_calls': 0,
          'scope': 'Named stores only. Copies are not separate budgets; no admission or authority granted.'}
(out/'audit-final.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
print(json.dumps([{'path': r['path'], 'exists': r['exists'], 'state': r.get('state'),
                  'families': r.get('families'), 'unchanged': r.get('main_db_bytes_unchanged')} for r in results], indent=2))
