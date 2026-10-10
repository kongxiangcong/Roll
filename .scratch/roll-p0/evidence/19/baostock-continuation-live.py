"""Opt-in, bounded public-API acquisition for the one authorized research stock.

No broker history/account mutation, sealed partition reads, or automatic retry.
Provider originals remain in the host runtime directory; the output is a summary.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import sys

import httpx

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'backend' / 'src'))
from roll.config import load_runtime_environment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8010')
    parser.add_argument('--output', required=True)
    parser.add_argument('--baostock-auth-mode', choices=['API_KEY', 'PUBLIC'], default='API_KEY')
    parser.add_argument('--sources', nargs='+', choices=['BAOSTOCK', 'FUYAO'], default=['BAOSTOCK', 'FUYAO'])
    parser.add_argument('--predecessor-protocol-id')
    args = parser.parse_args()
    if args.base_url not in {'http://127.0.0.1:8010', 'http://127.0.0.1:8190'}:
        raise ValueError('EXPLICIT_LOCAL_HOST_ONLY')
    os.environ['ROLL_ENV_FILE'] = str(ROOT / '.env')
    load_runtime_environment()
    secrets = [os.environ.get(k, '') for k in ['BAOSTOCK_API_KEY', 'FUYAO_API_KEY', 'DEEPSEEK_API_KEY']]
    secrets = [s.encode() for s in secrets if s]
    report = {'started_at': datetime.now(timezone.utc).isoformat(), 'instrument': 'SSE:600362',
              'requested_range': ['2023-01-01', '2026-10-08'], 'runs': [],
              'baostock_auth_mode': args.baostock_auth_mode,
              'sources_requested': args.sources,
              'sealed_results_read': False, 'broker_history_required': False}
    output = Path(args.output)
    raw_by_source = {}

    def save():
        encoded = json.dumps(report, ensure_ascii=False, indent=2).encode()
        if any(secret in encoded for secret in secrets):
            raise ValueError('SECRET_REFLECTION_REFUSED')
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(encoded + b'\n')

    with httpx.Client(base_url=args.base_url, timeout=75, trust_env=False) as client:
        def get(path):
            r = client.get(path)
            r.raise_for_status()
            return r.json()

        def post(path, value=None):
            r = client.post(path, json=value)
            r.raise_for_status()
            return r.json()

        account_before = get('/api/account')
        for source in args.sources:
            command = {'instruments': ['SSE:600362'], 'purpose': 'RESEARCH',
                       'start_date': '2023-01-01', 'end_date': '2026-10-08',
                       'groups': ['DAILY', 'STATUS', 'CALENDAR', 'ADJUSTMENTS'] if source == 'BAOSTOCK'
                                 else ['DAILY', 'ADJUSTMENTS'],
                       'daily_source': source, 'adjustment_source': source,
                       'max_calls': 30, 'timeout_seconds': 60}
            if source == 'BAOSTOCK':
                command.update(status_source='BAOSTOCK', calendar_source='BAOSTOCK',
                               baostock_auth_mode=args.baostock_auth_mode)
            request = post('/api/data/requests', command)
            run = post('/api/data/requests/' + request['request_id'] + '/retrieve')
            item = {'source': source, 'request_id': request['request_id'], 'run_id': run['run_id'],
                    'status': run['status'], 'started_at': run['started_at'],
                    'finished_at': run.get('finished_at'), 'tools': run.get('tools', []),
                    'snapshot_id': run.get('snapshot_id')}
            report['runs'].append(item)
            save()
            if not run.get('snapshot_id'):
                continue
            snapshot = get('/api/data/snapshots/' + run['snapshot_id'])
            facts = snapshot['facts']
            daily = [f for f in facts if f['group'] == 'DAILY' and f.get('adjustment') == 'RAW']
            raw_by_source[source] = {f['trade_date']: f for f in daily}
            item.update(fact_counts=dict(Counter(f['group'] for f in facts)),
                        raw_daily_count=len(daily), raw_daily_first=min((f['trade_date'] for f in daily), default=None),
                        raw_daily_last=max((f['trade_date'] for f in daily), default=None),
                        missing_amount_rows=sum(f.get('amount_yuan') is None for f in daily),
                        unknown_volume_unit_rows=sum(f.get('volume_unit') != 'SHARE' for f in daily),
                        basic_error_rows=sum(bool(f.get('errors')) for f in daily),
                        source_gaps=snapshot['gaps'], source_coverage=snapshot['coverage'])
            archives = snapshot['archives'] + [snapshot['parquet']]
            verified = []
            for archive in archives:
                raw = client.get('/api/data/archives/' + archive['sha256'])
                raw.raise_for_status()
                if hashlib.sha256(raw.content).hexdigest() != archive['sha256']:
                    raise ValueError('LIVE_ARCHIVE_HASH_MISMATCH')
                if any(secret in raw.content for secret in secrets):
                    raise ValueError('LIVE_ARCHIVE_SECRET_REFLECTION')
                verified.append({'sha256': archive['sha256'], 'bytes': len(raw.content), 'kind': archive['kind']})
                if archive.get('decoded_hash'):
                    decoded = client.get('/api/data/archives/' + archive['decoded_hash'])
                    decoded.raise_for_status()
                    if hashlib.sha256(decoded.content).hexdigest() != archive['decoded_hash']:
                        raise ValueError('LIVE_DECODED_HASH_MISMATCH')
                    if any(secret in decoded.content for secret in secrets):
                        raise ValueError('LIVE_DECODED_SECRET_REFLECTION')
                    verified.append({'sha256': archive['decoded_hash'], 'bytes': len(decoded.content), 'kind': 'SDK_DECODED'})
            item['verified_archives'] = verified
            replay = post('/api/data/runs/' + run['run_id'] + '/replay')
            item['replay'] = {'network_calls': replay['network_calls'], 'replay_kind': replay['replay_kind'],
                              'facts_match_original': replay['facts'] == facts,
                              'observations_match_original': replay['observations'] == snapshot['observations']}
            if replay['network_calls'] != 0 or not item['replay']['facts_match_original']:
                raise ValueError('LIVE_REPLAY_MISMATCH')
            if daily:
                dataset = post('/api/research/datasets', {'source_run_id': run['run_id'],
                               'basis': '江西铜业授权历史采集；核验原件覆盖，不将本次补拉认定为历史决策时可得'})
                item['dataset_id'] = dataset['dataset_id']
                item['dataset_coverage'] = dataset['coverage']
                item['training_readiness'] = dataset['training_readiness']
                item['partition_states'] = dataset['partitions']
                if source == 'BAOSTOCK':
                    protocol_command = {'dataset_id': dataset['dataset_id'],
                                        'basis': '真实覆盖预检；不临时划训练窗或接触封存结果'}
                    if args.predecessor_protocol_id:
                        protocol_command['predecessor_id'] = args.predecessor_protocol_id
                    protocol = post('/api/research/protocols', protocol_command)
                    fit = post('/api/research/protocols/' + protocol['protocol_id'] + '/models',
                               {'basis': '票19真实支持预检；不以METHOD或占位概率替代'})
                    item['protocol_id'] = protocol['protocol_id']
                    item['protocol_status'] = protocol['status']
                    item['predecessor_protocol_id'] = protocol.get('predecessor_id')
                    item['model_preflight'] = {k: fit.get(k) for k in
                                             ['model_run_id', 'attempt_id', 'status', 'reasons',
                                              'forecast_probability', 'model_artifact', 'calibrator_artifact',
                                              'capability', 'forward_started_at']}
            save()
        if set(raw_by_source) == {'BAOSTOCK', 'FUYAO'}:
            left, right = raw_by_source['BAOSTOCK'], raw_by_source['FUYAO']
            overlap = sorted(set(left) & set(right))
            fields = ['open', 'high', 'low', 'close', 'volume_shares', 'amount_yuan']
            comparison = {'overlap_days': len(overlap), 'independent_upstream_verified': False, 'fields': {}}
            for field in fields:
                comparable = [d for d in overlap if left[d].get(field) is not None and right[d].get(field) is not None]
                mismatches = [d for d in comparable if Decimal(str(left[d][field])) != Decimal(str(right[d][field]))]
                comparison['fields'][field] = {'comparable_days': len(comparable), 'equal_days': len(comparable) - len(mismatches),
                                               'different_days': len(mismatches), 'first_different_dates': mismatches[:5]}
            report['raw_source_comparison'] = comparison
        report['account_unchanged'] = get('/api/account') == account_before
        if not report['account_unchanged']:
            raise ValueError('ACCOUNT_CHANGED_DURING_READ_ONLY_RESEARCH')
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        save()
    print(json.dumps({'output': str(output), 'sources': [{'source': r['source'], 'status': r['status'],
                      'raw_daily_count': r.get('raw_daily_count', 0)} for r in report['runs']],
                      'account_unchanged': report['account_unchanged']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
