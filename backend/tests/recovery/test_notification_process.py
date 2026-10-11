"""Real owned OS worker + loopback receiver; never actual ntfy acceptance."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import pytest
from test_account_process import Server
from test_worker_process import launch_worker, wait_for


@pytest.mark.parametrize('fault,expected,received_count', [
    ('notification_after_claim', 'NOT_DISPATCHED', 0),
    ('notification_after_accept_before_ack', 'RESULT_UNKNOWN', 1),
])
def test_real_worker_crash_recovers_exact_unknown_without_duplicate_business_or_auto_resend(tmp_path, monkeypatch, fault, expected, received_count):
    monkeypatch.setenv('ROLL_ENV', 'test')
    monkeypatch.setenv('ROLL_RUNTIME_ROLE', 'API')
    monkeypatch.delenv('ROLL_ENV_FILE', raising=False)
    received = []
    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers['content-length']))))
            raw = json.dumps({'id':'method-loopback-receipt','event':'message'}).encode()
            self.send_response(200); self.send_header('content-length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
        def log_message(self, *_): pass
    receiver = ThreadingHTTPServer(('127.0.0.1', 0), Receiver)
    thread = threading.Thread(target=receiver.serve_forever, daemon=True); thread.start()
    api = Server(tmp_path / 'data')
    workers = []
    try:
        receipt = api.client.post('/api/capabilities/lifecycle', json={'scope':'ALL_MONITOR','state':'SUSPENDED',
            'reason_code':'USER_PAUSE','reason':'METHOD暂停仍允许事实恢复通知','expected_version':0,'idempotency_key':'pause'})
        assert receipt.status_code == 200, receipt.text
        configured = api.client.post('/api/notification-channel', json={'expected_version':0,'enabled':True,
            'server':f'http://127.0.0.1:{receiver.server_port}','topic':'method-loopback','app_base_url':'http://127.0.0.1:5173'})
        assert configured.status_code == 200
        monkeypatch.setenv('ROLL_TEST_CRASH_POINT', fault)
        worker, log = launch_worker(tmp_path / 'data', tmp_path / 'worker-crash.log'); workers.append((worker, log))
        assert worker.wait(timeout=30) == 86
        assert len(received) == received_count
        before = api.client.get('/api/notifications').json()['notifications']
        assert len(before) == 1
        monkeypatch.delenv('ROLL_TEST_CRASH_POINT')
        restarted, log = launch_worker(tmp_path / 'data', tmp_path / 'worker-recovered.log'); workers.append((restarted, log))
        after = wait_for(lambda:api.client.get('/api/notifications').json()['notifications'], lambda v:v[0]['external_status'] == expected, restarted)
        assert after[0]['notification_id'] == before[0]['notification_id']
        assert after[0]['delivered_at'] is None and after[0]['read_at'] is None
        current = api.client.get('/api/notifications/' + after[0]['notification_id'] + '/current').json()
        assert len(current['attempts']) == 1 and current['attempts'][0]['result']['status'] == expected
        assert api.client.get('/api/notifications/audit').json()['transmission_attempts'] == 1
        assert len(received) == received_count
        assert api.client.get('/api/account').json()['version'] == 0
    finally:
        for process, log in workers:
            if process.poll() is None: process.kill(); process.wait(timeout=10)
            log.close()
        api.stop(); receiver.shutdown(); receiver.server_close(); thread.join(timeout=5)
