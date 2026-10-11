"""Station notices preserve their source message; viewing never implies reading."""
import json
import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from roll.accounts.ledger import encode, now


class ReadNotice(BaseModel):
    model_config = ConfigDict(extra='forbid')
    idempotency_key: str = Field(min_length=1, max_length=128)


class Notifications:
    def __init__(self, ledger, capabilities, channel):
        self.ledger, self.capabilities, self.channel = ledger, capabilities, channel
        with ledger.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS notification_records(id TEXT PRIMARY KEY, business_key TEXT UNIQUE, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS notification_events(id TEXT PRIMARY KEY, notification_id TEXT NOT NULL, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS notification_reads(id TEXT, idem TEXT, value TEXT NOT NULL, PRIMARY KEY(id,idem));
                CREATE TABLE IF NOT EXISTS notification_attempts(id TEXT PRIMARY KEY, notification_id TEXT NOT NULL, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS notification_retry_receipts(id TEXT, idem TEXT, value TEXT NOT NULL, PRIMARY KEY(id,idem));
            ''')

    @staticmethod
    def append(db, identifier, event_type, **fields):
        value = {'event_id': str(uuid4()), 'notification_id': identifier, 'event_type': event_type, 'known_at': now(), **fields}
        db.execute('INSERT INTO notification_events VALUES(?,?,?)', (value['event_id'], identifier, encode(value)))
        return value

    def attempts(self, identifier, db):
        values = [json.loads(r[0]) for r in db.execute('SELECT value FROM notification_attempts WHERE notification_id=? ORDER BY rowid', (identifier,))]
        for value in values:
            value['events'] = [json.loads(r[0]) for r in db.execute('SELECT value FROM notification_events WHERE notification_id=? ORDER BY rowid', (identifier,)) if json.loads(r[0]).get('attempt_id') == value['attempt_id']]
            value['result'] = next((e for e in reversed(value['events']) if e['event_type'] == 'ATTEMPT_RESULT'), None)
        return values

    def actions_published(self, db, evaluation):
        for decision in evaluation['decisions']:
            semantic = {k: decision.get(k) for k in ['instrument', 'action', 'quantity', 'grant_id', 'rule_id', 'basis_type']}
            semantic['policy'] = decision['dependencies']['policy_fingerprint']
            key = hashlib.sha256(encode(semantic).encode()).hexdigest()
            family = encode(['ACTION',decision['instrument'],decision['grant_id'],decision.get('basis_type')])
            prior = next((json.loads(r[0]) for r in db.execute('SELECT value FROM notification_records ORDER BY rowid DESC')
                          if json.loads(r[0]).get('semantic_family') == family), None)
            if prior and (prior['semantic_key'] != key or datetime.fromisoformat(prior['expires_at']) <= datetime.fromisoformat(now())): prior = None
            source = {'kind': 'ACTION', 'id': decision['decision_id'], 'version': evaluation['evaluation_id']}
            if prior:
                identifier = prior['notification_id']
            else:
                identifier = str(uuid4())
                value = {'notification_id': identifier, 'semantic_key': key, 'semantic_family':family, 'category': 'NEED_ACTION', 'severity': 'IMPORTANT',
                         'source': source, 'title': '当前动作需要查看', 'message': f"{decision['instrument']} · {decision['action']} · {decision['quantity']} 股；请打开核对当前条件。",
                         'occurred_at': evaluation['registered_at'], 'known_at': evaluation['registered_at'],
                         'expires_at': decision['expires_at'], 'evidence_kind': evaluation['namespace'],
                         'grant_id': decision['grant_id'], 'dependencies': decision['dependencies']}
                db.execute('INSERT INTO notification_records VALUES(?,?,?)', (identifier, decision['decision_id'], encode(value)))
            event_id = hashlib.sha256(encode([identifier, source]).encode()).hexdigest()
            event = {'event_id': event_id, 'notification_id': identifier, 'event_type': 'SOURCE_ASSOCIATED',
                     'source': source, 'known_at': evaluation['registered_at'], 'merged': prior is not None}
            db.execute('INSERT OR IGNORE INTO notification_events VALUES(?,?,?)', (event_id, identifier, encode(event)))

    def review_completed(self, db, task, result):
        # A completed local observation may produce at most one stage summary
        # per trading-date. There is no forced daily/offline notification.
        business = 'RUN_SUMMARY:' + task['inputs']['trading_date']
        row = db.execute('SELECT value FROM notification_records WHERE business_key=?', (business,)).fetchone()
        if row:
            value = json.loads(row[0])
        else:
            at = task['finished_at']
            value = {'notification_id':str(uuid4()),'category':'STAGE_SUMMARY','severity':'NORMAL',
                     'source':{'kind':'RUN_SUMMARY','id':result['snapshot_id'],'version':task['task_id']},
                     'title':'本阶段观察已记录','message':'本阶段观察已记录，请打开查看事实、缺项和适用边界；不构成交易建议。',
                     'occurred_at':result['observed_at'],'known_at':at,
                     'expires_at':(datetime.fromisoformat(at)+timedelta(hours=8)).isoformat(),
                     'evidence_kind':'HOST_OBSERVATION_SUMMARY'}
            db.execute('INSERT INTO notification_records VALUES(?,?,?)', (value['notification_id'], business, encode(value)))
        source = {'kind':'RUN_SUMMARY','id':result['snapshot_id'],'version':task['task_id']}
        event_id = hashlib.sha256(encode([value['notification_id'], source]).encode()).hexdigest()
        event = {'event_id':event_id,'notification_id':value['notification_id'],'event_type':'SOURCE_ASSOCIATED',
                 'source':source,'known_at':task['finished_at'],'merged':row is not None}
        db.execute('INSERT OR IGNORE INTO notification_events VALUES(?,?,?)', (event_id,value['notification_id'],encode(event)))

    def lifecycle_changed(self, db, event):
        at = event['recorded_at']
        source = {'kind': 'CAPABILITY_SCOPE_CHANGED', 'id': event['event_id'], 'version': event['version']}
        family = encode(['PERMISSION',event['scope'],event.get('grant_id')])
        severity = 'IMPORTANT' if event['reason_code'] in {'USER_PAUSE','USER_REVOKE'} and event['state'] not in {'REVOKED','EXPIRED'} else 'CRITICAL'
        semantic = encode([family,event['state'],event['reason_code'],severity])
        prior = next((json.loads(r[0]) for r in db.execute('SELECT value FROM notification_records ORDER BY rowid DESC') if json.loads(r[0]).get('semantic_family') == family), None)
        merged = bool(prior and prior['semantic_key'] == semantic and datetime.fromisoformat(prior['expires_at']) > datetime.fromisoformat(at))
        value = prior if merged else {'notification_id': str(uuid4()), 'category': 'NEED_SYNC_RECOVERY', 'severity': severity,
                 'source': source, 'message': event['reason'], 'title': '监控权限状态已变化',
                 'semantic_family':family,'semantic_key':semantic,
                 'occurred_at': event['effective_at'], 'known_at': at,
                 'expires_at': (datetime.fromisoformat(at) + timedelta(days=1)).isoformat(),
                 'evidence_kind': 'HOST_PERMISSION_EVENT', 'scope': event['scope'], 'grant_id': event.get('grant_id')}
        if not merged: db.execute('INSERT OR IGNORE INTO notification_records VALUES(?,?,?)', (value['notification_id'], event['event_id'], encode(value)))
        event_id = hashlib.sha256(encode([value['notification_id'], source]).encode()).hexdigest()
        linked = {'event_id':event_id,'notification_id':value['notification_id'],'event_type':'SOURCE_ASSOCIATED',
                  'source':source,'known_at':at,'merged':merged}
        db.execute('INSERT OR IGNORE INTO notification_events VALUES(?,?,?)', (event_id,value['notification_id'],encode(linked)))

    def action_invalidated(self, db, event):
        affected = []
        for row in db.execute('SELECT value FROM notification_records').fetchall():
            value = json.loads(row[0])
            if value['category'] != 'NEED_ACTION': continue
            links = [json.loads(r[0]) for r in db.execute('SELECT value FROM notification_events WHERE notification_id=?', (value['notification_id'],))]
            if value['source']['id'] != event['decision_id'] and not any(e.get('source', {}).get('id') == event['decision_id'] for e in links): continue
            attempts = self.attempts(value['notification_id'], db)
            self.append(db, value['notification_id'], 'SOURCE_INVALIDATED', source_event_id=event['event_id'],
                        decision_id=event['decision_id'], reasons=event['reasons'],
                        inflight=any(a['result'] is None and any(e['event_type'] == 'DISPATCH_STARTED' for e in a['events']) for a in attempts))
            affected.append(value['notification_id'])
        # A quote refresh closes the old action but is not itself a new major
        # risk. Current permission/funding/loss failures warrant a new reminder.
        critical = sorted(set(event['reasons']) - {'DATA_OR_LIST_CHANGE', 'PREVIOUSLY_INVALIDATED_REQUIRES_NEW_ACTION'})
        if not affected or not critical: return
        business = hashlib.sha256(encode(['ACTION_INVALIDATION', event['decision_id'], critical]).encode()).hexdigest()
        value = {'notification_id':str(uuid4()), 'category':'NEED_SYNC_RECOVERY','severity':'CRITICAL',
                 'source':{'kind':'ACTION_INVALIDATION','id':event['event_id'],'version':event['evaluation_id']},
                 'title':'原动作已经失效','message':'原动作已失效，请打开核对当前原因与条件；不要继续使用旧消息。',
                 'occurred_at':event['recorded_at'],'known_at':event['recorded_at'],
                 'expires_at':(datetime.fromisoformat(event['recorded_at'])+timedelta(days=1)).isoformat(),
                 'evidence_kind':'HOST_ACTION_INVALIDATION','reasons':critical,'related_notifications':affected}
        db.execute('INSERT OR IGNORE INTO notification_records VALUES(?,?,?)', (value['notification_id'], business, encode(value)))

    def record(self, identifier, db):
        row = db.execute('SELECT value FROM notification_records WHERE id=?', (identifier,)).fetchone()
        if row is None: raise HTTPException(404, 'NOTIFICATION_NOT_FOUND')
        return json.loads(row[0])

    def projection(self, value, db):
        read = db.execute('SELECT value FROM notification_reads WHERE id=? ORDER BY rowid LIMIT 1', (value['notification_id'],)).fetchone()
        attempts = self.attempts(value['notification_id'], db)
        dispatch = next((e for a in attempts for e in a['events'] if e['event_type'] == 'DISPATCH_STARTED'), None)
        accepted = next((a['result'] for a in attempts if a['result'] and a['result']['status'] == 'CHANNEL_ACCEPTED'), None)
        status = attempts[-1]['result']['status'] if attempts and attempts[-1]['result'] else ('INFLIGHT' if attempts else 'QUEUED' if self.channel.configuration()['enabled'] else 'CHANNEL_DISABLED')
        if not attempts and db.execute("SELECT 1 FROM notification_events WHERE notification_id=? AND json_extract(value,'$.event_type')='OUTBOUND_CLOSED'", (value['notification_id'],)).fetchone():
            status = 'OUTBOUND_CLOSED'
        return {**value, 'read_at': json.loads(read[0])['read_at'] if read else None,
                'read_source': 'EXPLICIT_STATION_READ' if read else 'UNKNOWN',
                'sent_at': None, 'sent_source': 'UNKNOWN', 'dispatch_started_at': dispatch['known_at'] if dispatch else None,
                'dispatch_started_source': 'HOST_ATTEMPT_STARTED' if dispatch else 'UNKNOWN',
                'publish_confirmed_at': accepted['known_at'] if accepted else None,
                'accepted_known_at': accepted['known_at'] if accepted else None,
                'accepted_occurred_at': datetime.fromtimestamp(accepted['provider_time'], timezone.utc).isoformat() if accepted and accepted.get('provider_time') is not None else None,
                'accepted_occurred_source': 'NTFY_REPORTED_TIME_UNVERIFIED_CLOCK' if accepted and accepted.get('provider_time') is not None else 'UNKNOWN',
                'delivered_at': None, 'delivery_source': 'UNKNOWN', 'external_status': status}

    def sync_facts(self, db, recovery):
        # Materialize only already persisted local facts. A crash between a
        # draft commit and notification creation is safe to resume by its ID.
        rows = db.execute("SELECT id,created_at,status FROM account_drafts d WHERE status IN ('READY','QUARANTINED') AND NOT EXISTS(SELECT 1 FROM account_receipts r WHERE json_extract(r.receipt,'$.draft_id')=d.id)").fetchall()
        for identifier, at, state in rows:
            source = {'kind':'ACCOUNT_DRAFT','id':identifier,'version':state}
            value = {'notification_id':str(uuid4()),'category':'NEED_SYNC_RECOVERY','severity':'IMPORTANT',
                     'source':source,'title':'账户事实等待核对','message':'已有账户草稿等待核对和明确确认；不影响你继续同步其他事实。',
                     'occurred_at':at,'known_at':now(),'source_known_at':at,
                     'expires_at':(datetime.fromisoformat(at)+timedelta(days=1)).isoformat(),'evidence_kind':'HOST_PENDING_ACCOUNT_FACT'}
            db.execute('INSERT OR IGNORE INTO notification_records VALUES(?,?,?)', (value['notification_id'],encode(source),encode(value)))
        for row in db.execute('SELECT value FROM execution_intents').fetchall():
            intent = json.loads(row[0])
            if intent['status'] != 'OPERATION_PENDING': continue
            at = intent['time_chain']['reported_at'] or intent['time_chain']['known_at']
            source = {'kind':'EXTERNAL_OPERATION_PENDING','id':intent['intent_id'],'version':at}
            business = 'EXTERNAL_PENDING:' + intent['intent_id']
            prior = db.execute('SELECT value FROM notification_records WHERE business_key=?', (business,)).fetchone()
            value = json.loads(prior[0]) if prior else {'notification_id':str(uuid4()),'category':'NEED_SYNC_RECOVERY','severity':'IMPORTANT',
                'source':source,'title':'外部操作仍待同步','message':'已有外部操作结果等待核对；暂停或撤回权限不会删除这条事实。',
                'occurred_at':intent['time_chain']['occurred_at'],'known_at':at,
                'expires_at':(datetime.fromisoformat(at)+timedelta(days=1)).isoformat(),'evidence_kind':'HOST_PENDING_EXTERNAL_FACT'}
            if not prior: db.execute('INSERT INTO notification_records VALUES(?,?,?)', (value['notification_id'],business,encode(value)))
            event_id = hashlib.sha256(encode([value['notification_id'],source]).encode()).hexdigest()
            db.execute('INSERT OR IGNORE INTO notification_events VALUES(?,?,?)', (event_id,value['notification_id'],encode({
                'event_id':event_id,'notification_id':value['notification_id'],'event_type':'SOURCE_ASSOCIATED','source':source,'known_at':at,'merged':prior is not None})))
        if recovery['state'] == 'RECOVERY_LOCK':
            at = recovery['locked_at']
            source = {'kind':'RECOVERY_LOCK','id':recovery['backup_id'],'version':at}
            value = {'notification_id':str(uuid4()),'category':'NEED_SYNC_RECOVERY','severity':'CRITICAL',
                'source':source,'title':'恢复后条件仍待核对','message':'本地恢复已进入保护状态；请核对当前账户、权限历史与资格，旧动作不能复活。',
                'occurred_at':at,'known_at':now(),'source_known_at':at,
                'expires_at':(datetime.fromisoformat(at)+timedelta(days=1)).isoformat(),'evidence_kind':'HOST_RECOVERY_LOCK'}
            db.execute('INSERT OR IGNORE INTO notification_records VALUES(?,?,?)', (value['notification_id'],encode(source),encode(value)))

    def listing(self):
        recovery = self.capabilities.recovery()
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            self.sync_facts(db, recovery)
            result = {'notifications': [self.projection(json.loads(r[0]), db) for r in db.execute('SELECT value FROM notification_records ORDER BY rowid DESC')]}
            db.commit()
            return result

    def current(self, identifier):
        self.capabilities.refresh_journal()
        recovery = self.capabilities.recovery()
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            value = self.record(identifier, db)
            projected = self.projection(value, db)
            links = [json.loads(r[0]) for r in db.execute('SELECT value FROM notification_events WHERE notification_id=? ORDER BY rowid', (identifier,))]
            state = 'EXPIRED' if datetime.fromisoformat(value['expires_at']) <= datetime.fromisoformat(now()) else 'CURRENT'
            current = None
            if value['source']['kind'] == 'ACTION':
                current = self.capabilities.actions.current(db=db)
                if state != 'EXPIRED' and not any(d['decision_id'] == value['source']['id'] for d in current['decisions']):
                    state = 'SUPERSEDED' if current['evaluation'] and current['evaluation']['evaluation_id'] != value['source']['version'] else 'INVALIDATED'
            elif value['source']['kind'] == 'CAPABILITY_SCOPE_CHANGED' and state != 'EXPIRED':
                if self.capabilities.lifecycle(db, value.get('grant_id'))['scopes'][value['scope']].get('event_id') != value['source']['id']: state = 'SUPERSEDED'
            elif value['source']['kind'] == 'ACCOUNT_DRAFT' and state != 'EXPIRED':
                if db.execute("SELECT 1 FROM account_receipts WHERE json_extract(receipt,'$.draft_id')=?", (value['source']['id'],)).fetchone() or self.ledger.get_draft(value['source']['id'],db)['status'] == 'RESOLVED': state = 'RESOLVED'
            elif value['source']['kind'] == 'EXTERNAL_OPERATION_PENDING' and state != 'EXPIRED':
                if self.capabilities.actions.execution_intents.get(value['source']['id'],db)['status'] != 'OPERATION_PENDING': state = 'RESOLVED'
            elif value['source']['kind'] == 'RECOVERY_LOCK' and state != 'EXPIRED':
                if recovery['state'] != 'RECOVERY_LOCK': state = 'RESOLVED'
                elif recovery.get('backup_id') != value['source']['id'] or recovery.get('locked_at') != value['source']['version']: state = 'SUPERSEDED'
            result = {'notification': value, **{k: projected[k] for k in ['read_at', 'delivered_at', 'external_status']},
                      'current_state': state, 'source_links': links, 'current_actions': current, 'prepare_allowed': False,
                      'attempts': self.attempts(identifier, db)}
            db.commit()
        self.capabilities.journal.reconcile_committed()
        return result

    def time_chain(self, decision_id, evaluation_id, intent_id=None):
        evaluation = self.capabilities.actions.get(evaluation_id)
        if not any(d['decision_id'] == decision_id for d in evaluation['decisions']): raise HTTPException(404, 'NOTIFICATION_DECISION_NOT_FOUND')
        with self.ledger.connection() as db:
            if intent_id:
                intent = self.capabilities.actions.execution_intents.get(intent_id, db)
                if intent['decision_id'] != decision_id or intent['evaluation_id'] != evaluation_id: raise HTTPException(409, 'NOTIFICATION_INTENT_SOURCE_MISMATCH')
                chain = dict(intent['time_chain'])
            else:
                chain = {'decision_issued_at': evaluation['registered_at'], 'decision_issued_source': 'HOST_PUBLICATION',
                         'sent_at': None, 'delivered_at': None, 'read_at': None, 'notification_source': 'UNKNOWN'}
            timeline = []
            for row in db.execute('SELECT value FROM notification_records ORDER BY rowid'):
                value = json.loads(row[0])
                associated = value['source'] == {'kind':'ACTION','id':decision_id,'version':evaluation_id}
                links = [json.loads(r[0]) for r in db.execute('SELECT value FROM notification_events WHERE notification_id=?', (value['notification_id'],))]
                if not associated and not any(e.get('source') == {'kind':'ACTION','id':decision_id,'version':evaluation_id} for e in links): continue
                projected = self.projection(value, db)
                item = {k: projected[k] for k in ['notification_id','sent_at','sent_source','dispatch_started_at','dispatch_started_source','publish_confirmed_at','accepted_known_at','accepted_occurred_at','accepted_occurred_source','delivered_at','delivery_source','read_at','read_source','external_status']}
                item.update(original_source_binding=associated, source_links=links, attempts=self.attempts(value['notification_id'], db))
                # Reading an old merged message does not prove the user read a
                # later action version. Preserve that distinction for reports.
                if not associated: item.update(read_at=None, read_source='OLDER_MESSAGE_ONLY')
                timeline.append(item)
            read = next((v for v in timeline if v['original_source_binding'] and v['read_at']), None)
            chain.update(sent_at=None, sent_source='UNKNOWN', delivered_at=None, delivery_source='UNKNOWN',
                         read_at=read['read_at'] if read else None, read_source='EXPLICIT_STATION_READ' if read else 'UNKNOWN',
                         notification_source='APPENDED_NOTIFICATION_EVIDENCE' if timeline else 'UNKNOWN')
            return {'decision_id':decision_id,'evaluation_id':evaluation_id,'intent_id':intent_id,
                    'time_chain':chain,'notification_timeline':timeline,'original_intent_mutated':False}

    def retry(self, identifier, command):
        self.capabilities.refresh_journal()
        recovery = self.capabilities.recovery()
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            notice = self.record(identifier, db)
            prior = db.execute('SELECT value FROM notification_retry_receipts WHERE id=? AND idem=?', (identifier, command.idempotency_key)).fetchone()
            if prior: return json.loads(prior[0])
            attempts = self.attempts(identifier, db)
            if not attempts or len(attempts) >= 2 or not attempts[-1]['result'] or attempts[-1]['result']['status'] == 'CHANNEL_ACCEPTED':
                raise HTTPException(409, 'NOTIFICATION_RETRY_NOT_AVAILABLE')
            if any(json.loads(r[0]).get('prior_attempt_id') == attempts[-1]['attempt_id'] for r in db.execute('SELECT value FROM notification_events WHERE notification_id=?', (identifier,))):
                raise HTTPException(409, 'NOTIFICATION_RETRY_ALREADY_REQUESTED')
            reasons, _ = self.send_eligibility(notice, db, recovery)
            if reasons: raise HTTPException(409, {'code': 'NOTIFICATION_NO_LONGER_CURRENT', 'reasons': reasons})
            receipt = self.append(db, identifier, 'RETRY_REQUESTED', prior_attempt_id=attempts[-1]['attempt_id'],
                                  possible_duplicate=attempts[-1]['result']['status'] == 'RESULT_UNKNOWN')
            db.execute('INSERT INTO notification_retry_receipts VALUES(?,?,?)', (identifier, command.idempotency_key, encode(receipt)))
            db.commit()
        self.capabilities.journal.reconcile_committed()
        return receipt

    def read(self, identifier, command):
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            self.record(identifier, db)
            prior = db.execute('SELECT value FROM notification_reads WHERE id=? AND idem=?', (identifier, command.idempotency_key)).fetchone()
            if prior: return json.loads(prior[0])
            value = {'event_id': str(uuid4()), 'notification_id': identifier, 'read_at': now(),
                     'read_source': 'EXPLICIT_STATION_READ', 'known_at': now()}
            db.execute('INSERT INTO notification_reads VALUES(?,?,?)', (identifier, command.idempotency_key, encode(value)))
            db.commit()
            return value

    def audit(self, db=None):
        if db is not None: return self.audit_snapshot(db)
        with self.ledger.connection() as db:
            return self.audit_snapshot(db)

    def audit_snapshot(self, db):
        events = [json.loads(r[0]) for r in db.execute('SELECT value FROM notification_events')]
        return {'business_notifications': db.execute('SELECT COUNT(*) FROM notification_records').fetchone()[0],
                    'transmission_attempts': db.execute('SELECT COUNT(*) FROM notification_attempts').fetchone()[0],
                    'merged_sources': sum(e['event_type'] == 'SOURCE_ASSOCIATED' and e.get('merged', False) for e in events),
                    'possible_duplicate_attempts': sum(e['event_type'] == 'RETRY_REQUESTED' and e['possible_duplicate'] for e in events),
                    'failed_attempts': sum(e['event_type'] == 'ATTEMPT_RESULT' and e['status'] in {'FAILED', 'NOT_SENT', 'NOT_DISPATCHED'} for e in events),
                    'unknown_attempts': sum(e['event_type'] == 'ATTEMPT_RESULT' and e['status'] == 'RESULT_UNKNOWN' for e in events),
                    'delivered': None, 'delivery_status': 'UNKNOWN'}

    def metrics(self, db=None):
        value = self.audit(db)
        return {'duplicate_notifications': {'status': 'CHECKED', 'value': value['merged_sources'],
                    'business_notifications': value['business_notifications'], 'transmission_attempts': value['transmission_attempts'],
                    'possible_duplicate_attempts': value['possible_duplicate_attempts'], 'unknown_attempts': value['unknown_attempts'],
                    'failed_attempts': value['failed_attempts'], 'delivery_status': 'UNKNOWN'}}

    def send_eligibility(self, notice, db, recovery):
        reasons = ['EXPIRED'] if datetime.fromisoformat(notice['expires_at']) <= datetime.fromisoformat(now()) else []
        source = notice['source']
        links = [json.loads(r[0]) for r in db.execute('SELECT value FROM notification_events WHERE notification_id=? ORDER BY rowid', (notice['notification_id'],))]
        source = next((e['source'] for e in reversed(links) if e['event_type'] == 'SOURCE_ASSOCIATED'), source)
        if source['kind'] == 'ACTION':
            current = self.capabilities.actions.current(db=db)
            if not any(d['decision_id'] == source['id'] and current['evaluation']['evaluation_id'] == source['version'] for d in current['decisions']):
                reasons.append('CURRENT_ACTION_RESTRICTED_OR_SUPERSEDED')
        elif source['kind'] == 'CAPABILITY_SCOPE_CHANGED':
            control = self.capabilities.lifecycle(db, notice.get('grant_id'))
            if control['scopes'][notice['scope']].get('event_id') != source['id']: reasons.append('PERMISSION_STATE_CHANGED')
        elif source['kind'] == 'ACCOUNT_DRAFT':
            row = db.execute('SELECT status FROM account_drafts WHERE id=?', (source['id'],)).fetchone()
            if row is None or row[0] not in {'READY','QUARANTINED'} or db.execute("SELECT 1 FROM account_receipts WHERE json_extract(receipt,'$.draft_id')=?", (source['id'],)).fetchone(): reasons.append('ACCOUNT_FACT_ALREADY_RESOLVED')
        elif source['kind'] == 'EXTERNAL_OPERATION_PENDING':
            if self.capabilities.actions.execution_intents.get(source['id'],db)['status'] != 'OPERATION_PENDING': reasons.append('EXTERNAL_OPERATION_ALREADY_RESOLVED')
        elif source['kind'] == 'RECOVERY_LOCK':
            if recovery['state'] != 'RECOVERY_LOCK' or recovery.get('backup_id') != source['id'] or recovery.get('locked_at') != source['version']: reasons.append('RECOVERY_STATE_CHANGED')
        return reasons, source

    def work(self, owner):
        recovery = self.capabilities.recovery()
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            self.sync_facts(db, recovery)
            for row in db.execute('SELECT value FROM notification_records').fetchall():
                identifier = json.loads(row[0])['notification_id']
                for attempt in self.attempts(identifier, db):
                    if attempt['owner'] != owner and attempt['result'] is None:
                        dispatched = any(e['event_type'] == 'DISPATCH_STARTED' for e in attempt['events'])
                        self.append(db, identifier, 'ATTEMPT_RESULT', attempt_id=attempt['attempt_id'],
                                    status='RESULT_UNKNOWN' if dispatched else 'NOT_DISPATCHED', error_code='PREVIOUS_WORKER_STOPPED_WITHOUT_RECEIPT')
            db.commit()
        configuration = self.channel.configuration()
        if not configuration['enabled']: return
        self.capabilities.refresh_journal()
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            notice = None
            for row in db.execute('SELECT value FROM notification_records ORDER BY rowid').fetchall():
                value = json.loads(row[0]); identifier = value['notification_id']
                attempts = self.attempts(identifier, db)
                events = [json.loads(r[0]) for r in db.execute('SELECT value FROM notification_events WHERE notification_id=?', (identifier,))]
                if any(e['event_type'] == 'OUTBOUND_CLOSED' for e in events): continue
                if attempts and (len(attempts) >= 2 or not attempts[-1]['result'] or not any(e['event_type'] == 'RETRY_REQUESTED' and e['prior_attempt_id'] == attempts[-1]['attempt_id'] for e in events)): continue
                reasons, source = self.send_eligibility(value, db, recovery)
                if reasons:
                    self.append(db, identifier, 'OUTBOUND_CLOSED', reasons=reasons)
                    continue
                if value['evidence_kind'] == 'METHOD_ENGINEERING' and self.channel.transport is None: continue
                notice = value; break
            if notice is None:
                db.commit()
                return
            body = {'title': notice['title'], 'message': notice['message'], 'priority': 4,
                    'click': configuration['app_base_url'] + '/#notification=' + notice['notification_id']}
            shortened = len(body['message'].encode('utf-8')) > 4096
            if shortened:
                body['message'] = notice['title'] + '。请打开查看完整记录与当前条件。'
            attempt = {'attempt_id': str(uuid4()), 'notification_id': notice['notification_id'], 'owner': owner,
                       'configuration_version': configuration['version'], 'claimed_at': now(), 'body': body,
                       'source': source, 'evidence_kind': notice['evidence_kind'],
                       'message_projection': 'SUMMARY_FOR_CHANNEL_BYTE_LIMIT' if shortened else 'ORIGINAL_NOTIFICATION_MESSAGE'}
            db.execute('INSERT INTO notification_attempts VALUES(?,?,?)', (attempt['attempt_id'], notice['notification_id'], encode(attempt)))
            db.commit()
        self.capabilities.journal.reconcile_committed()
        self.ledger.crash_point('notification_after_claim')
        # Claim is committed before network I/O. Recheck after that boundary,
        # outside any other writer; a later external race remains unknowable.
        self.capabilities.refresh_journal()
        latest_configuration = self.channel.configuration()
        latest_recovery = self.capabilities.recovery()
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            reasons, _ = self.send_eligibility(notice, db, latest_recovery)
            if not latest_configuration['enabled'] or latest_configuration['version'] != configuration['version']:
                reasons.append('CHANNEL_CONFIGURATION_CHANGED_AFTER_CLAIM')
            if reasons:
                self.append(db, notice['notification_id'], 'ATTEMPT_RESULT', attempt_id=attempt['attempt_id'],
                            status='NOT_DISPATCHED', error_code='CONDITIONS_CHANGED_BEFORE_DISPATCH', reasons=reasons)
                db.commit()
                self.capabilities.journal.reconcile_committed()
                return
            self.append(db, notice['notification_id'], 'DISPATCH_STARTED', attempt_id=attempt['attempt_id'])
            db.commit()
        result = self.channel.publish(configuration, body)
        self.ledger.crash_point('notification_after_accept_before_ack')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            self.append(db, notice['notification_id'], 'ATTEMPT_RESULT', attempt_id=attempt['attempt_id'], **result)
            db.commit()
