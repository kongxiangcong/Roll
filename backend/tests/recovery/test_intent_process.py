import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime

import httpx
import pytest
from test_account_process import free_port


class IntentServer:
    def __init__(self, directory, fault=None):
        self.directory = directory
        port = free_port()
        backend = Path(__file__).resolve().parents[2]
        env = {**os.environ, 'ROLL_DATA_DIR': str(directory), 'ROLL_ENV': 'test', 'PYTHONDONTWRITEBYTECODE': '1',
               'PYTHONPATH': os.pathsep.join(str(backend / p) for p in ['src', 'tests/support', 'tests/application'])}
        env.pop('ROLL_TEST_CRASH_POINT', None)
        if fault: env['ROLL_TEST_CRASH_POINT'] = fault
        self.log = open(directory.parent / f'intent-{port}.log', 'w', encoding='utf-8')
        self.process = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', '-m', 'uvicorn', 'intent_method_app:factory', '--factory', '--host', '127.0.0.1', '--port', str(port)], cwd=backend, env=env, stdout=self.log, stderr=subprocess.STDOUT)
        self.client = httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=30)
        for _ in range(200):
            try:
                if self.client.get('/api/health').status_code == 200: return
            except httpx.TransportError: pass
            if self.process.poll() is not None: break
            time.sleep(.1)
        self.stop()
        raise AssertionError('isolated METHOD process failed to start')

    def stop(self):
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=10)
        self.client.close()
        self.log.close()


@pytest.mark.parametrize('fault,committed', [('before_commit', False), ('after_commit', True), ('after_receipt', True)])
def test_actual_process_commit_keeps_fill_allocation_intent_and_action_invalidation_together(tmp_path, fault, committed):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tests/application'))
    from test_actions import prepare
    from test_intents import intent_command
    from test_fills import fill
    directory = tmp_path / 'data'
    server = IntentServer(directory)
    try:
        p = json.loads((tmp_path / 'qualification.json').read_text(encoding='utf-8'))['package']
        import capability_method_app
        capability_method_app.ANCHOR = datetime.fromisoformat(p['required_as_of'])
        client = server.client
        prepare(client, p)
        evaluation = client.post('/api/actions/evaluate', json={}).json()
        intent = client.post('/api/intents/prepare', json=intent_command(evaluation)).json()
        actual = fill(evaluation['account_version'], 'crash-partial')
        actual['payload'].update(quantity='100', price='140.00', effective_at=p['required_as_of'])
        draft = client.post('/api/account/drafts', json=actual).json()
        command = {'draft_id': draft['draft_id'], 'idempotency_key': 'crash-fill', 'fill_allocations': [
            {'intent_id': intent['intent_id'], 'fill_record_id': 'crash-partial', 'allocated_quantity': '100', 'association_status': 'USER_CONFIRMED'}]}
    finally: server.stop()
    failing = IntentServer(directory, None if fault == 'after_receipt' else fault)
    try:
        if fault == 'after_receipt':
            original = failing.client.post('/api/account/confirm', json=command)
            assert original.status_code == 200
        else:
            with pytest.raises(httpx.TransportError): failing.client.post('/api/account/confirm', json=command)
            assert failing.process.wait(timeout=10) == 86
    finally: failing.stop()
    recovered = IntentServer(directory)
    try:
        client = recovered.client
        # Read the immutable event log before opening current actions, which can append invalidations.
        events = client.get('/api/actions/events').json()
        assert any(e['event_type'] == 'ACTION_INVALIDATED' for e in events) is committed
        assert len(client.get('/api/intents/allocations').json()) == int(committed)
        assert client.get('/api/account').json()['version'] == evaluation['account_version'] + int(committed)
        assert client.get('/api/intents').json()['intents'][0]['synced_quantity'] == ('100' if committed else '0')
        receipt = client.post('/api/account/confirm', json=command)
        assert receipt.status_code == 200, receipt.text
        assert client.post('/api/account/confirm', json=command).json() == receipt.json()
        assert len(client.get('/api/intents/allocations').json()) == 1
        assert client.get('/api/account').json()['positions'][0]['quantity'] == '100'
        assert client.get('/api/actions/current').json()['decisions'] == []
    finally: recovered.stop()
