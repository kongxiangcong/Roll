"""Combine separate real acquisition receipts; compare immutable RAW facts locally."""
import json
from decimal import Decimal
from pathlib import Path

import httpx


def main():
    folder = Path(__file__).resolve().parent
    old = json.loads((folder/'baostock-real-acquisition-initial.json').read_text(encoding='utf-8'))
    new = json.loads((folder/'baostock-real-acquisition-repaired.json').read_text(encoding='utf-8'))
    fuyao = next(r for r in old['runs'] if r['source'] == 'FUYAO')
    bao = next(r for r in new['runs'] if r['source'] == 'BAOSTOCK')
    assert fuyao['status'] in {'COMPLETE', 'PARTIAL'} and bao['status'] in {'COMPLETE', 'PARTIAL'}
    assert old['account_unchanged'] and new['account_unchanged']
    report = dict(new)
    report['runs'] = [bao, fuyao]
    report['receipt_files'] = ['baostock-real-acquisition-initial.json', 'baostock-real-acquisition-repaired.json']
    report['combined_receipts'] = True
    report['provider_requests_in_combine'] = 0
    with httpx.Client(base_url='http://127.0.0.1:8010', timeout=60, trust_env=False) as client:
        facts = []
        for run in [bao, fuyao]:
            response = client.get('/api/data/snapshots/'+run['snapshot_id'])
            response.raise_for_status()
            daily = [f for f in response.json()['facts'] if f['group'] == 'DAILY' and f.get('adjustment') == 'RAW']
            assert len(daily) == run['raw_daily_count']
            facts.append({f['trade_date']:f for f in daily})
    left, right = facts
    overlap = sorted(set(left) & set(right))
    comparison = {'overlap_days':len(overlap), 'independent_upstream_verified':False, 'fields':{}}
    for field in ['open', 'high', 'low', 'close', 'volume_shares', 'amount_yuan']:
        comparable = [d for d in overlap if left[d].get(field) is not None and right[d].get(field) is not None]
        mismatches = [d for d in comparable if Decimal(str(left[d][field])) != Decimal(str(right[d][field]))]
        comparison['fields'][field] = {'comparable_days':len(comparable), 'equal_days':len(comparable)-len(mismatches),
                                       'different_days':len(mismatches), 'first_different_dates':mismatches[:5]}
    report['raw_source_comparison'] = comparison
    (folder/'baostock-real-acquisition.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'source_counts':{r['source']:r['raw_daily_count'] for r in report['runs']},
                      'overlap_days':len(overlap), 'provider_requests':0}))


if __name__ == '__main__':
    main()
