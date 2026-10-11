"""Two public callers and real SQLite; only the actual empty cursor fetch is paused."""
import sqlite3
from threading import Event, Lock
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from roll.app import create_app
from capability_method_app import save_package
from test_actions import action_package, prepare
from test_intents import intent_command
from test_action_risk_priority import method_clock, record


def test_same_key_commit_between_first_receipt_and_legacy_lookup_recovers_original(tmp_path, monkeypatch):
    method_clock(monkeypatch)
    p = action_package()
    file = save_package(tmp_path / 'qualification.json', p)
    directory = tmp_path / 'data'
    with TestClient(create_app(directory, capability_method_file=file, runtime_role='API')) as client:
        prepare(client, p)
        evaluation = client.post('/api/actions/evaluate', json={}).json()
        command = intent_command(evaluation)
        reached, release = Event(), Event()
        lock = Lock()
        armed = [True]
        real_connect = sqlite3.connect

        class PausedCursor:
            def __init__(self, cursor): self.cursor = cursor
            def fetchone(self):
                value = self.cursor.fetchone()
                assert value is None  # The real first read found no receipt.
                reached.set()
                assert release.wait(15), 'Second public caller did not finish'
                return value

        class RealConnection(sqlite3.Connection):
            def execute(self, sql, parameters=()):
                cursor = super().execute(sql, parameters)
                if sql == 'SELECT fingerprint,value FROM execution_intent_prepare_receipts WHERE idem=?' and parameters == (command['idempotency_key'],):
                    with lock:
                        if armed[0]:
                            armed[0] = False
                            return PausedCursor(cursor)
                return cursor

        def connect(database, *args, **kwargs):
            if str(database) == str(directory / 'roll.sqlite3'): kwargs['factory'] = RealConnection
            return real_connect(database, *args, **kwargs)

        monkeypatch.setattr(sqlite3, 'connect', connect)
        with ThreadPoolExecutor(max_workers=1) as executor:
            first = executor.submit(client.post, '/api/intents/prepare', json=command)
            assert reached.wait(10)
            try:
                second = client.post('/api/intents/prepare', json=command)
                assert second.status_code == 201, second.text
            finally:
                release.set()
            response = first.result(timeout=15)
        record(tmp_path, 'concurrent-responses', {'first_status': response.status_code, 'first': response.json(), 'second_status': second.status_code, 'second': second.json()})
        assert response.status_code == 201, response.text
        assert response.json() == second.json()
        listing = client.get('/api/intents').json()
        assert len(listing['intents']) == 1
        assert listing['unreflected_reservation_yuan'] == '30005.00'
