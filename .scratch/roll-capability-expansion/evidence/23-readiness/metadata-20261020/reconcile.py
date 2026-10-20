"""Reconcile the saved metadata only; never reopen stores or allocate budgets."""
import json
from pathlib import Path

root = Path(__file__).resolve().parent
audit = json.loads((root / 'audit-final.json').read_bytes())
protocols, attempts = {}, {}
for store in audit['stores']:
    for record in store.get('protocols', []):
        assert record['id'] not in protocols or protocols[record['id']] == record
        protocols[record['id']] = record
    for record in store.get('attempts', []):
        assert record['id'] not in attempts or attempts[record['id']] == record
        attempts[record['id']] = record
roots = set()
for protocol in protocols.values():
    current = protocol
    visited = set()
    while current['predecessor_id']:
        assert current['id'] not in visited
        visited.add(current['id'])
        current = protocols[current['predecessor_id']]
    roots.add(current['id'])
assert len(roots) == 1
fits = sum(a['category'] in ('PRIMARY_FIT', 'G5_NEIGHBOR') for a in attempts.values())
calibrations = sum(a['category'] == 'CALIBRATION' for a in attempts.values())
result = {'same_root': next(iter(roots)), 'protocol_count': len(protocols),
          'distinct_attempt_count': len(attempts), 'fit_records': fits,
          'calibration_records': calibrations, 'fit_remaining_upper_bound': max(0, 5-fits),
          'calibration_remaining': max(0, 1-calibrations),
          'admission_granted': False, 'snapshot_conflicts': [], 'network_calls': 0,
          'database_reads': 0, 'label_reads': 0}
(root / 'reconciliation.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
print(json.dumps(result, indent=2))
