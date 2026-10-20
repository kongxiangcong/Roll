"""Bounded live acceptance; never writes account facts, fills, grants or funds."""
import argparse
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['before', 'configure', 'check'])
    parser.add_argument('--url', default='http://127.0.0.1:8010/api')
    parser.add_argument('--output', type=Path, default=Path('.scratch/roll-daily-use/live.json'))
    args = parser.parse_args()
    saved = json.loads(args.output.read_text(encoding='utf-8')) if args.output.exists() else {}
    with httpx.Client(base_url=args.url+'/', timeout=60, trust_env=False) as client:
        def call(path, data=None):
            result = client.get(path) if data is None else client.post(path, json=data)
            result.raise_for_status()
            return result.json()

        account = call('account')
        fingerprint = hashlib.sha256(json.dumps(account, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        base = 'observation-updates/SSE:600362'
        if args.mode == 'before':
            saved['account_before_sha256'] = fingerprint
            backup = call('runtime/backups', {})
            saved['backup_created'] = bool(backup)
        elif args.mode == 'configure':
            listing = call('market/list')
            if not any(row['instrument'] == 'SSE:600362' for row in listing['members']):
                call('market/watch', {'operation': 'ADD', 'instrument': 'SSE:600362', 'expected_list_version': listing['version']})
            value = call(base)
            for source in value['sources']:
                if not source['enabled']:
                    call('research/collection-sources/'+source['id']+'/policy',
                         {'enabled': True, 'expected_revision': source['revision'],
                          'basis': '2026-10-20 用户授权江西铜业单股日常使用与持续更新'})
            call(base+'/settings', {'expected_revision': value['settings']['revision'],
                'enabled': True, 'news_postclose': True, 'financial_postclose': True,
                'market_postclose': True, 'news_refresh': True, 'classify': False, 'profile': 'legacy',
                'basis': '2026-10-20 用户授权单股日常闭环；模型验证独立，不启动训练或正式建议'})
            saved['jobs'] = {}
            for kind in ('MARKET', 'FINANCIAL', 'NEWS'):
                job = call(base+'/requests', {'kind': kind, 'refresh_sources': True,
                    'idempotency_key': 'daily-live-'+str(uuid4()), 'basis': '单股日常交付的一次有限真实刷新'})
                saved['jobs'][kind] = job['job_id']
        else:
            saved['results'] = {}
            for kind, identifier in saved.get('jobs', {}).items():
                job = call('observation-update-jobs/'+identifier)
                saved['results'][kind] = {key: job.get(key) for key in
                    ('status', 'error', 'errors', 'result', 'created_at', 'finished_at', 'observation_id', 'cache_reused')}
            value = call(base)
            saved['worker'] = value['worker']['worker_state']
            saved['settings'] = value['settings']
            saved['account_unchanged'] = fingerprint == saved.get('account_before_sha256')
            saved['formal_state'] = call('today')['technical_capability']['state']
            saved['api'] = call('health')['status']
            financial = call('market/financial/SSE:600362/observations')['current']
            news = call('market/news/SSE:600362')
            saved['data_summary'] = {
                'financial_periods': len(financial['periods']),
                'latest_financial_period': financial['latest_period'],
                'financial_status': financial['status'],
                'news_facts': len(news['facts']),
                'unique_news_events': news['unique_event_count'],
                'observation_count': len(value['observations']),
                'pending_jobs': sum(job['status'] in ('QUEUED', 'RUNNING') for job in value['jobs']),
                'latest_news_source_errors': news['runs'][0].get('errors', []) if news['runs'] else [],
            }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'mode': args.mode, 'output': str(args.output), 'account_unchanged': saved.get('account_unchanged'),
                          'worker': saved.get('worker'), 'results': saved.get('results')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
