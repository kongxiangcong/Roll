"""Real localhost SOHU acquisition, immutable import, restart, and offline replay.

Uses a fresh research-only runtime with an empty account; no credentials,
Fuyao/BaoStock, label calculation, model fit, or sealed-input reads.
"""
import argparse
import errno
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import socket
import signal
import sys
import time
import uuid

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--source', type=Path, help='Managed implementation checkout to validate before integration')
    parser.add_argument('--lifecycle-only', action='store_true', help='Verify isolated startup/stop/restart without market networking')
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
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', args.port))
        port = probe.getsockname()[1]
    report = {'started_at': datetime.now(timezone.utc).isoformat(), 'instrument': 'SSE:600362',
              'data_directory': str(directory), 'source_checkout': str(source), 'http_port': port, 'steps': [], 'process_ids': [],
              'real_market_acquisition': not args.lifecycle_only, 'credentials_used': False,
              'sealed_results_read': False, 'labels_computed': False, 'models_fitted': False}
    process = None
    base = f'http://127.0.0.1:{port}'
    client = httpx.Client(base_url=base, timeout=70, trust_env=False)
    owned = {}
    def call(method, path, value=None, expected=200):
        response = client.request(method, '/api' + path, json=value)
        if response.status_code != expected:
            raise RuntimeError(f'{path}: expected {expected}, received {response.status_code}: {response.text[:400]}')
        report['steps'].append({'method': method, 'path': path, 'status': response.status_code})
        return response.json()
    def receipt_for(instance):
        expected = owned[instance.pid]
        path = expected['receipt']
        if not path.exists():
            return None
        identity = json.loads(path.read_text(encoding='utf-8'))
        if (not isinstance(identity, dict) or identity.get('token') != expected['token']
                or identity.get('directory') != str(directory) or type(identity.get('pid')) is not int
                or identity['pid'] <= 0):
            raise RuntimeError('Owned child startup receipt mismatch')
        return identity
    def stop(instance, ready=False):
        if owned[instance.pid].get('stopped'):
            return
        identity = receipt_for(instance)
        graceful = False
        try:
            if ready and identity and instance.poll() is None:
                response = client.post('/api/_acceptance/stop', headers={'X-Roll-Acceptance-Token': identity['token']}, timeout=5)
                if response.status_code != 200:
                    raise RuntimeError('Owned child rejected shutdown')
                instance.wait(timeout=15)
                graceful = True
        except (httpx.TransportError, subprocess.TimeoutExpired, RuntimeError):
            pass
        if not graceful:
            if identity:
                try:
                    os.kill(identity['pid'], signal.SIGTERM)
                except OSError as error:
                    if error.errno != errno.ESRCH and getattr(error, 'winerror', None) != 87:
                        raise
            if instance.poll() is None:
                instance.terminate()
            instance.wait(timeout=10)
        for _ in range(50):
            with socket.socket() as probe:
                if probe.connect_ex(('127.0.0.1', port)) != 0:
                    report.setdefault('shutdowns', []).append({'launcher_pid': instance.pid,
                        'actual_pid': identity['pid'] if identity else None, 'graceful': graceful, 'listener_closed': True})
                    owned[instance.pid]['stopped'] = True
                    return
            time.sleep(.1)
        raise RuntimeError('Listener still open after owned child shutdown')
    def start():
        token = uuid.uuid4().hex
        receipt = directory / ('startup-' + token + '.json')
        child = '''import os,json
from pathlib import Path
identity = {'token': os.environ['ROLL_ACCEPTANCE_TOKEN'], 'directory': str(Path(os.environ['ROLL_DATA_DIR']).resolve()), 'pid': os.getpid()}
receipt = Path(os.environ['ROLL_ACCEPTANCE_RECEIPT'])
temporary = receipt.with_suffix('.tmp')
with temporary.open('x', encoding='utf-8') as stream:
    json.dump(identity, stream)
    stream.flush()
    os.fsync(stream.fileno())
os.replace(temporary, receipt)
import uvicorn
from fastapi import Header,HTTPException
from secrets import compare_digest
from roll.app import create_app
app = create_app()
@app.get('/api/_acceptance/identity')
def acceptance_identity():
    return identity
@app.post('/api/_acceptance/stop')
def acceptance_stop(x_roll_acceptance_token: str = Header(default='')):
    if not compare_digest(x_roll_acceptance_token, identity['token']):
        raise HTTPException(403, 'Acceptance token required')
    server.should_exit = True
    return {'stopping': True, 'pid': identity['pid']}
server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=int(os.environ['ROLL_ACCEPTANCE_PORT'])))
server.run()
'''
        environment['ROLL_ACCEPTANCE_PORT'] = str(port)
        environment['ROLL_ACCEPTANCE_TOKEN'] = token
        environment['ROLL_ACCEPTANCE_RECEIPT'] = str(receipt)
        instance = subprocess.Popen([sys.executable, '-B', '-X', 'utf8',
            '-c', child],
            cwd=source / 'backend', env=environment, stdout=log, stderr=subprocess.STDOUT)
        report['process_ids'].append(instance.pid)
        owned[instance.pid] = {'receipt': receipt, 'token': token}
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if instance.poll() is not None:
                    raise RuntimeError('Local host failed; inspect http-process.log')
                try:
                    response = client.get('/api/_acceptance/identity', timeout=1)
                    identity = response.json() if response.status_code == 200 else None
                    expected = receipt_for(instance)
                    if (expected is not None and identity == expected
                            and instance.poll() is None):
                        report.setdefault('listener_ownership', []).append(identity)
                        return instance
                except httpx.TransportError:
                    pass
                time.sleep(.1)
            raise RuntimeError('Local host startup deadline')
        except BaseException:
            stop(instance)
            raise
    try:
        process = start()
        account = call('GET', '/account')
        assert account['version'] == 0
        if args.lifecycle_only:
            response = client.post('/api/_acceptance/stop', headers={'X-Roll-Acceptance-Token': 'wrong-token'})
            assert response.status_code == 403 and process.poll() is None
            report['unauthenticated_shutdown_status'] = response.status_code
            stop(process, ready=True)
            process = start()
            assert call('GET', '/account') == account
            identities = report['listener_ownership']
            assert identities[0]['pid'] != identities[1]['pid'] and identities[0]['token'] != identities[1]['token']
            report.update(passed=True, account_unchanged=True, finished_at=datetime.now(timezone.utc).isoformat())
            return
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
        stop(process, ready=True)
        process = start()
        assert report['listener_ownership'][0]['pid'] != report['listener_ownership'][1]['pid']
        assert report['listener_ownership'][0]['token'] != report['listener_ownership'][1]['token']
        assert call('GET', f'/research/datasets/{dataset["dataset_id"]}') == dataset
        restarted_replay = call('POST', f'/data/runs/{run["run_id"]}/replay')
        assert restarted_replay == original_replay and restarted_replay['network_calls'] == 0
        assert call('GET', '/account') == account
        capability = call('GET', '/capabilities')
        assert capability['state'] == 'UNGRANTED'
        report.update(passed=True, replay_network_calls=0, account_unchanged=True,
                      capability_state=capability['state'], finished_at=datetime.now(timezone.utc).isoformat())
    finally:
        try:
            if process:
                stop(process, ready=True)
        finally:
            client.close()
            log.close()
            args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': report['passed'], 'daily': report['daily_summary'], 'replay_network_calls': 0}))


if __name__ == '__main__':
    main()
