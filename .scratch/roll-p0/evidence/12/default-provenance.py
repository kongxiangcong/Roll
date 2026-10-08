import hashlib
import json
import os
from pathlib import Path
import sqlite3

source = Path(os.environ['LOCALAPPDATA']) / 'Roll'
db = sqlite3.connect((source / 'roll.sqlite3').as_uri() + '?mode=ro', uri=True)
names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
counts = {name: db.execute('SELECT COUNT(*) FROM ' + name).fetchone()[0] for name in names}
events = [json.loads(r[0]) for r in db.execute('SELECT event FROM account_events')]
drafts = [json.loads(r[0]) for r in db.execute('SELECT command FROM account_drafts')]
runs = [json.loads(r[0]) for r in db.execute('SELECT value FROM retrieval_runs')]
expected = {'events_synthetic': len(events) == 3 and all(e['source'] == '脱敏券商快照' and e['effective_at'] == '2026-10-07T00:00:00+08:00' for e in events),
            'draft_synthetic': len(drafts) == 1 and drafts[0]['kind'] == 'BASELINE' and drafts[0]['payload']['cash_balance'] == '10000.00' and drafts[0]['payload']['positions'] == [{'instrument':'SSE:600519','quantity':'100','sellable_quantity':None,'reference_cost':None}],
            'run_synthetic': len(runs) == 1 and runs[0]['question'] == '核对来源' and runs[0]['error']['code'] == 'DEEPSEEK_AUTH_NOT_CONFIGURED' and not runs[0]['tools']}
db.close()
files = []
for path in source.rglob('*'):
    if path.is_file():
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        files.append({'path': str(path.relative_to(source)), 'sha256': sha, 'bytes': path.stat().st_size,
                      'created_at_epoch': path.stat().st_birthtime, 'modified_at_epoch': path.stat().st_mtime})
report = {'source': str(source), 'contents_copied': False, 'table_counts': counts, 'expected_test_predicates': expected, 'files': files}
(Path(__file__).parent / 'default-provenance.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False))
