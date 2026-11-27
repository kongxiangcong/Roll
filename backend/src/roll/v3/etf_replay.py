"""Persist ETF report context so local readers can recompute by reference."""

from hashlib import sha256
import json

from roll.v3.etf_basket import prepare_etf_report, read_etf_report
from roll.v3.market import get_snapshot, persist_snapshot
from roll.v3.storage import database, ensure_schema, json_text


_SCHEMA = """
CREATE TABLE IF NOT EXISTS etf_frozen_report (
    report_id TEXT PRIMARY KEY,
    snapshot_id TEXT NOT NULL REFERENCES data_snapshot(snapshot_id),
    manifest TEXT NOT NULL
);
"""


def freeze_etf_report(data_dir, **options):
    """Atomically store the DataSnapshot and exact basket used for a readable report."""
    with database(data_dir, write=True) as db:
        ensure_schema(db, _SCHEMA)
        context = prepare_etf_report(data_dir, db=db, **options)
        snapshot = persist_snapshot(data_dir, context['snapshot'], db=db)
        context['snapshot'] = snapshot
        report = read_etf_report(data_dir, context, db=db)
        manifest = json_text({key: value for key, value in context.items() if key != 'snapshot'})
        report_id = sha256(f"{snapshot['snapshot_id']}\n{manifest}".encode()).hexdigest()
        db.execute('INSERT OR IGNORE INTO etf_frozen_report VALUES (?, ?, ?)',
                   (report_id, snapshot['snapshot_id'], manifest))
    return {**report, 'report_id': report_id}


def load_frozen_etf_report(data_dir, report_id, *, db):
    """Resolve an immutable report reference and its source DataSnapshot."""
    ensure_schema(db, _SCHEMA)
    row = db.execute('SELECT snapshot_id, manifest FROM etf_frozen_report WHERE report_id=?',
                     (report_id,)).fetchone()
    if row is None:
        raise ValueError(f'ETF 报表快照不存在 {report_id}')
    return {**json.loads(row['manifest']), 'snapshot': get_snapshot(data_dir, row['snapshot_id'], db=db)}


def replay_etf_report(data_dir, report_id):
    with database(data_dir) as db:
        context = load_frozen_etf_report(data_dir, report_id, db=db)
        report = read_etf_report(data_dir, context, db=db)
    return {**report, 'report_id': report_id}
