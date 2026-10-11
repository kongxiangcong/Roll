"""Local permission high-water evidence survives restoring an older database.

Pending files are never committed revocations. Confirmation requires a matching
committed SQLite row; unknown/missing commits keep recovery locked.
"""
import hashlib
import json
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from roll.accounts.ledger import encode, now
from roll.runtime.backups import persist


def sha(value): return hashlib.sha256(encode(value).encode()).hexdigest()


class LifecycleJournal:
    def __init__(self, ledger):
        self.ledger = ledger
        self.root = Path(ledger.path).parent / 'backups/capability-journal'

    def initialize(self):
        anchor = self.root / 'origin.json'
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS capability_journal_origin(id INTEGER PRIMARY KEY, fingerprint TEXT NOT NULL)')
            if anchor.exists(): return
            empty = not db.execute('SELECT 1 FROM capability_grants LIMIT 1').fetchone()
            if empty and not (self.root.parent / 'recovery-lock.json').exists():
                value = {'format': 'ROLL-CAPABILITY-JOURNAL-1', 'origin_id': str(uuid4()),
                    'origin': 'EMPTY_LOCAL_PERMISSION_HISTORY', 'recorded_at': now()}
                persist(anchor, encode(value).encode())
                db.execute('INSERT INTO capability_journal_origin VALUES(1,?)', (sha(value),))

    def stage(self, event):
        try:
            self._stage(event)
        except OSError as error:
            lock_path = self.root.parent / 'recovery-lock.json'
            prior = json.loads(lock_path.read_text(encoding='utf-8')) if lock_path.exists() else {}
            persist(lock_path, encode({**prior, 'state': 'RECOVERY_LOCK',
                'locked_at': prior.get('locked_at') or now(), 'formal_actions_allowed': False,
                'old_notifications_allowed': False, 'observation_allowed': True,
                'old_active_records': 'HISTORY_ONLY', 'possibly_missing_revocations': 'UNVERIFIED',
                'permission_journal_error': 'WRITE_FAILED_UNCONFIRMED'}).encode())
            raise HTTPException(503, 'CAPABILITY_JOURNAL_WRITE_FAILED') from error

    def _stage(self, event):
        value = {'format': 'ROLL-CAPABILITY-JOURNAL-1', 'state': 'PENDING_COMMIT',
                 'event': event, 'event_sha256': sha(event), 'prepared_at': now()}
        path = self.root / 'pending' / (event['event_id'] + '.json')
        if path.exists():
            if json.loads(path.read_text(encoding='utf-8'))['event_sha256'] != value['event_sha256']:
                raise RuntimeError('CAPABILITY_JOURNAL_EVENT_CONFLICT')
        else: persist(path, encode(value).encode())

    def reconcile_committed(self, db=None):
        if db is None:
            # Serialize append-once confirmations across native processes too.
            # A concurrent confirmer must not replace an existing receipt.
            with self.ledger.connection() as connection:
                connection.execute('BEGIN IMMEDIATE')
                self.reconcile_committed(connection)
                connection.commit()
            return
        # Called with a writer obtained before classification, and without any
        # new event writes. Rows seen here were committed by the prior writer.
        for path in (self.root / 'pending').glob('*.json'):
            value = json.loads(path.read_text(encoding='utf-8'))
            event = value['event']
            if sha(event) != value['event_sha256']: raise RuntimeError('CAPABILITY_JOURNAL_CORRUPT')
            receipt = self.root / 'committed' / path.name
            if receipt.exists(): continue
            row = db.execute('SELECT value FROM capability_events WHERE id=?', (event['event_id'],)).fetchone()
            if row is not None and json.loads(row[0]) == event:
                persist(receipt, encode({'state': 'COMMITTED', 'event_id': event['event_id'],
                    'event_sha256': value['event_sha256'], 'confirmed_from': 'MATCHING_COMMITTED_SQLITE_ROW',
                    'observed_at': now()}).encode())

    def status(self):
        confirmed, unknown = [], []
        if (self.root / 'pending').is_file():
            unknown.append({'state': 'JOURNAL_STORAGE_UNAVAILABLE'})
        for path in sorted((self.root / 'pending').glob('*.json')):
            value = json.loads(path.read_text(encoding='utf-8'))
            event = value['event']
            if sha(event) != value['event_sha256']: raise RuntimeError('CAPABILITY_JOURNAL_CORRUPT')
            receipt_path = self.root / 'committed' / path.name
            receipt = json.loads(receipt_path.read_text(encoding='utf-8')) if receipt_path.exists() else None
            if receipt and receipt.get('state') == 'COMMITTED' and receipt.get('event_sha256') == value['event_sha256']:
                confirmed.append(event)
            else: unknown.append({'event_id': event['event_id'], 'pending_event_sha256': value['event_sha256'], 'state': 'UNCONFIRMED'})
        confirmed.sort(key=lambda e:(e['version'],e['event_id']))
        anchor = self.root / 'origin.json'
        origin = json.loads(anchor.read_text(encoding='utf-8')) if anchor.exists() else None
        with self.ledger.connection() as db:
            row = db.execute('SELECT fingerprint FROM capability_journal_origin WHERE id=1').fetchone()
        known = bool(origin and origin.get('origin') == 'EMPTY_LOCAL_PERMISSION_HISTORY' and row and row[0] == sha(origin))
        return {'confirmed_events': confirmed, 'unknown': unknown, 'history_known': known,
                'fingerprint': sha({'origin': origin, 'database_origin': row[0] if row else None,
                    'confirmed': confirmed, 'unknown': unknown})}
