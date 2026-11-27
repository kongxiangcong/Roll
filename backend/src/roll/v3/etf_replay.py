"""Persist ETF report context so local readers can recompute by reference."""

from datetime import date
from hashlib import sha256
import json

from roll.market.calendar import is_session
from roll.v3.etf_basket import prepare_etf_report, read_etf_report
from roll.v3.etf_disclosures import etf_disclosure_day_cutoff
from roll.v3.market import get_snapshot, persist_snapshot, utc_timestamp
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


def load_frozen_etf_report(data_dir, report_id, *, trade_date=None, db):
    """Resolve an immutable report reference and its source DataSnapshot."""
    ensure_schema(db, _SCHEMA)
    row = db.execute('SELECT snapshot_id, manifest FROM etf_frozen_report WHERE report_id=?',
                     (report_id,)).fetchone()
    if row is None:
        raise ValueError(f'ETF 报表快照不存在 {report_id}')
    context = {**json.loads(row['manifest']), 'snapshot': get_snapshot(data_dir, row['snapshot_id'], db=db)}
    if trade_date is not None and trade_date != context['trade_date']:
        if trade_date > context['trade_date'] or not is_session(date.fromisoformat(trade_date)):
            raise ValueError('请选择快照观察日或之前的交易日')
        context['trade_date'] = trade_date
        if 'disclosure_cutoff' in context:
            context['disclosure_cutoff'] = min(
                context['disclosure_cutoff'], utc_timestamp(etf_disclosure_day_cutoff(trade_date)),
            )
    return context


def replay_etf_report(data_dir, report_id, *, trade_date=None):
    with database(data_dir) as db:
        context = load_frozen_etf_report(data_dir, report_id, trade_date=trade_date, db=db)
        report = read_etf_report(data_dir, context, db=db)
    return {**report, 'report_id': report_id}
