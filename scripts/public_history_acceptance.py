"""Real localhost SOHU acquisition, immutable import, restart, and offline replay.

Uses a fresh research-only runtime with an empty account; no credentials,
Fuyao/BaoStock, label calculation, model fit, or sealed-input reads.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import socket
import time
import uuid

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--source', type=Path, help='Managed implementation checkout to validate before integration')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = args.source.resolve() if args.source else root
    if not (source / 'backend/src/roll/app.py').is_file():
        raise ValueError('Roll source checkout required')
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    log = (directory / 'http-process.log').open('ab')
    environment = {**os.environ, 'ROLL_ENV': 'test', 'ROLL_DATA_DIR': str(directory),
                   'PYTHONPATH': str(source / 'backend/src')}
    environment.pop('ROLL_ENV_FILE', None)
    token = uuid.uuid4().hex
    environment['ROLL_ACCEPTANCE_TOKEN'] = token
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', args.port))
        port = probe.getsockname()[1]
    report = {'started_at': datetime.now(timezone.utc).isoformat(), 'instrument': 'SSE:600362',
              'data_directory': str(directory), 'source_checkout': str(source), 'steps': [], 'process_ids': [],
              'real_market_acquisition': True, 'credentials_used': False,
              'sealed_results_read': False, 'labels_computed': False, 'models_fitted': False}
    process = None
    base = f'http://127.0.0.1:{port}'
    client = httpx.Client(base_url=base, timeout=70, trust_env=False)
    def call(method, path, value=None, expected=200):
        response = client.request(method, '/api' + path, json=value)
        if response.status_code != expected:
            raise RuntimeError(f'{path}: expected {expected}, received {response.status_code}: {response.text[:400]}')
        report['steps'].append({'method': method, 'path': path, 'status': response.status_code})
        return response.json()
    def start():
        child = '''import os
from pathlib import Path
import uvicorn
from roll.app import create_app
app = create_app()
@app.get('/api/_acceptance/identity')
def acceptance_identity():
    return {'token': os.environ['ROLL_ACCEPTANCE_TOKEN'], 'directory': str(Path(os.environ['ROLL_DATA_DIR']).resolve()), 'pid': os.getpid()}
uvicorn.run(app, host='127.0.0.1', port=int(os.environ['ROLL_ACCEPTANCE_PORT']))
'''
        environment['ROLL_ACCEPTANCE_PORT'] = str(port)
        instance = subprocess.Popen([str(root / 'backend/.venv/Scripts/python.exe'), '-B', '-X', 'utf8',
            '-c', child],
            cwd=source / 'backend', env=environment, stdout=log, stderr=subprocess.STDOUT)
        report['process_ids'].append(instance.pid)
        try:
            for _ in range(200):
                if instance.poll() is not None:
                    raise RuntimeError('Local host failed; inspect http-process.log')
                try:
                    response = client.get('/api/_acceptance/identity')
                    identity = response.json() if response.status_code == 200 else None
                    if (isinstance(identity, dict) and identity.get('token') == token
                            and identity.get('directory') == str(directory) and identity.get('pid') == instance.pid
                            and instance.poll() is None):
                        report.setdefault('listener_ownership', []).append(identity)
                        return instance
                except httpx.TransportError:
                    pass
                time.sleep(.1)
            raise RuntimeError('Local host startup deadline')
        except BaseException:
            if instance.poll() is None:
                instance.terminate()
                instance.wait(timeout=10)
            raise
    try:
        process = start()
        account = call('GET', '/account')
        assert account['version'] == 0
        listing = call('GET', '/market/list')
        call('POST', '/market/watch', {'operation': 'ADD', 'instrument': 'SSE:600362', 'expected_list_version': listing['version']})
        call('POST', '/market/identities', {'instrument': 'SSE:600362', 'exchange': 'SSE', 'board': 'MAIN',
             'instrument_type': 'STOCK', 'name': '江西铜业', 'effective_at': datetime.now(timezone.utc).isoformat(),
             'basis': 'Research-only identity supported by official company 600362 A-share disclosures; no account permission'})
        request = call('POST', '/data/requests', {'instruments': ['SSE:600362'], 'groups': ['DAILY'],
            'purpose': 'RESEARCH', 'start_date': '2013-01-01', 'end_date': '2025-12-31',
            'daily_source': 'SOHU', 'max_calls': 2, 'timeout_seconds': 60}, expected=201)
        run = call('POST', f'/data/requests/{request["request_id"]}/retrieve')
        report['request'] = request
        report['run'] = run
        assert run.get('snapshot_id') and run['status'] in {'COMPLETE', 'PARTIAL'}
        snapshot = call('GET', f'/data/snapshots/{run["snapshot_id"]}')
        daily = [row for row in snapshot['facts'] if row['group'] == 'DAILY']
        assert len(daily) >= 3000 and all(row['adjustment'] == 'RAW' for row in daily)
        assert all(row['source_id'].startswith('sohu') for row in daily)
        assert all(row['volume_unit'] == 'SHARE' and row['amount_yuan'] is not None for row in daily)
        dataset = call('POST', '/research/datasets', {'source_run_id': run['run_id'],
            'basis': 'Actual SOHU RAW source coverage only; current retrospective history is not historical availability proof'}, expected=201)
        assert dataset['training_readiness']['state'] == 'BLOCKED'
        assert 'HISTORICAL_POINT_IN_TIME_NOT_PROVEN' in dataset['training_readiness']['blockers']
        assert dataset['scope']['source_account_authority'] == 'NONE; MARKET_DATA_ONLY'
        call('GET', f'/research/datasets/{dataset["dataset_id"]}/partitions/DEVELOPMENT', expected=409)
        call('GET', f'/research/datasets/{dataset["dataset_id"]}/partitions/SEALED', expected=403)
        checked = []
        for original in snapshot['archives'] + [snapshot['parquet']]:
            response = client.get('/api/data/archives/' + original['sha256'])
            assert response.status_code == 200 and hashlib.sha256(response.content).hexdigest() == original['sha256']
            assert response.headers.get('x-content-type-options') == 'nosniff'
            checked.append({'sha256': original['sha256'], 'bytes': len(response.content)})
        report['archives_verified'] = checked
        report['dataset'] = dataset
        report['daily_summary'] = {'rows': len(daily), 'first_date': min(r['trade_date'] for r in daily),
            'last_date': max(r['trade_date'] for r in daily), 'error_counts': dict(Counter(error for r in daily for error in r.get('errors', []))),
            'unknown_amount_rows': sum(r.get('amount_yuan') is None for r in daily)}
        original_replay = call('POST', f'/data/runs/{run["run_id"]}/replay')
        assert original_replay['network_calls'] == 0
        process.terminate()
        process.wait(timeout=15)
        process = start()
        assert call('GET', f'/research/datasets/{dataset["dataset_id"]}') == dataset
        restarted_replay = call('POST', f'/data/runs/{run["run_id"]}/replay')
        assert restarted_replay == original_replay and restarted_replay['network_calls'] == 0
        assert call('GET', '/account') == account
        capability = call('GET', '/capabilities')
        assert capability['state'] == 'UNGRANTED'
        report.update(passed=True, replay_network_calls=0, account_unchanged=True,
                      capability_state=capability['state'], finished_at=datetime.now(timezone.utc).isoformat())
    finally:
        if process and process.poll() is None:
            process.terminate()
            process.wait(timeout=15)
        client.close()
        log.close()
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': report['passed'], 'daily': report['daily_summary'], 'replay_network_calls': 0}))


if __name__ == '__main__':
    main()
