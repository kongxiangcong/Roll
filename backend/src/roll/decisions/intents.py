"""User execution declarations; actual facts remain Ledger.confirm's responsibility."""
import json
from decimal import Decimal
from uuid import uuid4
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from roll.accounts.ledger import encode, now, number, timestamp
from roll.accounts.fills import money
from roll.accounts.reconcile import UseCheck, use_check
from roll.decisions.actions import fingerprint


class PrepareIntent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision_id: str
    expected_evaluation_id: str
    expected_account_version: int
    expected_funding_version: int
    expected_grant_version: int
    price_yuan: str
    idempotency_key: str = Field(min_length=1, max_length=128)


class DeclareIntent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    state: Literal['OPERATION_PENDING', 'NOT_EXECUTED', 'RESOLVED']
    external_order_id: str | None = None
    broker_reflection: Literal['UNKNOWN', 'NOT_REFLECTED', 'CONFIRMED_REFLECTED'] = 'UNKNOWN'
    occurred_at: str | None = None
    reason: str | None = None
    idempotency_key: str = Field(min_length=1, max_length=128)


class Intents:
    def __init__(self, ledger, actions):
        self.ledger, self.actions = ledger, actions
        with ledger.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS execution_intents(id TEXT PRIMARY KEY, idem TEXT UNIQUE, fingerprint TEXT NOT NULL, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS execution_intent_events(id TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS action_fill_allocations(id TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS execution_intent_receipts(idem TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, value TEXT NOT NULL);
            ''')

    def listing(self, db=None):
        if db is None:
            with self.ledger.connection() as connection:
                connection.execute('BEGIN')
                value = self.listing(connection)
                connection.rollback()
                return value
        values = [json.loads(r[0]) for r in db.execute('SELECT value FROM execution_intents ORDER BY rowid')]
        version = self.ledger.account(db=db)['version']
        for value in values:
            value['effective_broker_reflection'] = ('UNKNOWN' if value['status'] == 'OPERATION_PENDING' and value.get('broker_reflection_account_version') != version else value['broker_reflection'])
        reserved = sum((Decimal(v['provisional_reservation_yuan']) for v in values if v['status'] not in {'NOT_EXECUTED', 'RESOLVED'} and v['effective_broker_reflection'] != 'CONFIRMED_REFLECTED'), Decimal(0))
        return {'intents': values, 'unreflected_reservation_yuan': format(reserved, '.2f'),
                'pending_attribution': any(v['effective_broker_reflection'] == 'UNKNOWN' for v in values if v['status'] == 'OPERATION_PENDING'),
                'broker_frozen_deducted_again': False}

    def prepare(self, command):
        content = fingerprint(command.model_dump())
        price = Decimal(number(command.price_yuan, 'price_yuan', 8))
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            current = self.actions.current(db=db)
            decision = next((d for d in current['decisions'] if d['decision_id'] == command.decision_id), None)
            evaluation = current['evaluation']
            if not decision or evaluation['evaluation_id'] != command.expected_evaluation_id:
                raise HTTPException(409, 'ACTION_NOT_CURRENT')
            boundary = self.actions.boundary(db)
            pending = [self.ledger.get_draft(r[0], db) for r in db.execute("SELECT d.id FROM account_drafts d WHERE status IN ('READY','QUARANTINED') AND NOT EXISTS(SELECT 1 FROM account_receipts r WHERE json_extract(r.receipt,'$.draft_id')=d.id)")]
            purpose = 'NEW_RISK' if decision['action'] in {'BUY', 'ADD'} else 'REDUCTION'
            fact_check = use_check(boundary['account'], pending, UseCheck(purpose=purpose, required_as_of=decision['data_cutoff']), timestamp, self.ledger.events(db))
            if not fact_check['allowed']: raise HTTPException(409, {'code': 'CURRENT_ACCOUNT_FACTS_RESTRICTED', 'check': fact_check})
            status = next(s for s in boundary['capabilities']['grant_statuses'] if s['grant']['grant_id'] == decision['grant_id'])
            if (command.expected_account_version != boundary['account']['version'] or command.expected_funding_version != boundary['funding']['version'] or command.expected_grant_version != status['grant']['version']):
                raise HTTPException(409, 'INTENT_DEPENDENCY_VERSION_CHANGED')
            if not Decimal(decision['price_lower_yuan']) <= price <= Decimal(decision['price_upper_yuan']):
                raise HTTPException(409, 'PRICE_OUTSIDE_ACTION_CONDITIONS')
            prior = db.execute('SELECT fingerprint,value FROM execution_intents WHERE idem=?', (command.idempotency_key,)).fetchone()
            if prior:
                if prior[0] != content: raise HTTPException(409, 'INTENT_IDEMPOTENCY_CONTENT_CONFLICT')
                db.commit()
                return json.loads(prior[1])
            listing = self.listing(db)
            active = [v for v in listing['intents'] if v['status'] not in {'NOT_EXECUTED', 'RESOLVED'}]
            if decision['action'] in {'BUY', 'ADD'} and (listing['pending_attribution'] or any(v['action'] in {'BUY', 'ADD'} for v in active)):
                raise HTTPException(409, 'ACTIVE_NEW_ENTRY_OR_UNKNOWN_EXTERNAL_ORDER')
            reservation = Decimal(decision['required_cash_yuan'])
            available = Decimal(boundary['account'].get('conservative_available', boundary['account'].get('broker_available')) or '0') - Decimal(boundary['funding'].get('cash_reserve', '0')) - Decimal(listing['unreflected_reservation_yuan'])
            if reservation > available: raise HTTPException(409, 'CURRENT_AVAILABLE_AFTER_INTENTS_INSUFFICIENT')
            at = now()
            value = {'intent_id': str(uuid4()), 'decision_id': decision['decision_id'], 'evaluation_id': evaluation['evaluation_id'],
                     'decision': decision, 'instrument': decision['instrument'], 'action': decision['action'], 'status': 'PREPARED',
                     'remaining_quantity': decision['quantity'], 'synced_quantity': '0', 'provisional_reservation_yuan': format(reservation, '.2f'),
                     'original_reservation_yuan': format(reservation, '.2f'),
                     'broker_reflection': 'NOT_REFLECTED', 'effective_broker_reflection': 'NOT_REFLECTED', 'broker_reflection_account_version': boundary['account']['version'], 'external_order_id': None, 'resolution': None,
                     'time_chain': {'decision_issued_at': evaluation['registered_at'], 'sent_at': None, 'delivered_at': None, 'read_at': None,
                                    'prepared_at': at, 'prepared_source': 'USER_PREPARE', 'occurred_at': None, 'reported_at': None, 'known_at': at},
                     'namespace': evaluation['namespace'], 'system_usable': evaluation['system_usable']}
            db.execute('INSERT INTO execution_intents VALUES(?,?,?,?)', (value['intent_id'], command.idempotency_key, content, encode(value)))
            self.event(db, 'INTENT_PREPARED', value['intent_id'], at)
            db.commit()
        return value

    def get(self, identifier, db):
        row = db.execute('SELECT value FROM execution_intents WHERE id=?', (identifier,)).fetchone()
        if not row: raise HTTPException(404, '执行意向不存在')
        return json.loads(row[0])

    def declare(self, identifier, command):
        if command.external_order_id is not None and (not command.external_order_id.strip() or len(command.external_order_id) > 128):
            raise HTTPException(422, 'EXTERNAL_ORDER_ID_MUST_BE_EXPLICIT_NONEMPTY')
        content = fingerprint({'intent_id': identifier, **command.model_dump()})
        occurred = timestamp(command.occurred_at, 'occurred_at') if command.occurred_at else None
        if command.broker_reflection == 'CONFIRMED_REFLECTED' and not command.external_order_id:
            raise HTTPException(422, 'BROKER_REFLECTION_REQUIRES_EXPLICIT_ORDER_ID')
        if command.state in {'NOT_EXECUTED', 'RESOLVED'} and not (command.reason or '').strip():
            raise HTTPException(422, 'EXPLICIT_RESOLUTION_REASON_REQUIRED')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior = db.execute('SELECT fingerprint,value FROM execution_intent_receipts WHERE idem=?', (command.idempotency_key,)).fetchone()
            if prior:
                if prior[0] != content: raise HTTPException(409, 'INTENT_IDEMPOTENCY_CONTENT_CONFLICT')
                return json.loads(prior[1])
            value = self.get(identifier, db)
            if value['status'] in {'NOT_EXECUTED', 'RESOLVED'} or (value['status'] == 'OPERATION_PENDING' and command.state == 'NOT_EXECUTED'):
                raise HTTPException(409, 'EXTERNAL_ORDER_CANNOT_BE_ASSUMED_CANCELLED')
            if command.state == 'RESOLVED' and value['status'] != 'OPERATION_PENDING':
                raise HTTPException(409, 'NO_PENDING_EXTERNAL_RESULT')
            if command.external_order_id and any(v['intent_id'] != identifier and v['external_order_id'] == command.external_order_id for v in self.listing(db)['intents']):
                raise HTTPException(409, 'EXTERNAL_ORDER_ALREADY_LINKED')
            at = now()
            value.update(status=command.state, external_order_id=command.external_order_id or value['external_order_id'],
                         broker_reflection=command.broker_reflection, effective_broker_reflection=command.broker_reflection,
                         broker_reflection_account_version=self.ledger.account(db=db)['version'], resolution=command.reason)
            value['time_chain'].update(occurred_at=occurred or value['time_chain']['occurred_at'], occurred_source='USER_DECLARED' if occurred or value['time_chain']['occurred_at'] else 'UNKNOWN', reported_at=at, known_at=at)
            if command.state in {'NOT_EXECUTED', 'RESOLVED'}: value['provisional_reservation_yuan'] = '0.00'
            db.execute('UPDATE execution_intents SET value=? WHERE id=?', (encode(value), identifier))
            db.execute('INSERT INTO execution_intent_receipts VALUES(?,?,?)', (command.idempotency_key, content, encode(value)))
            self.event(db, 'INTENT_' + command.state, identifier, at, declaration=command.model_dump())
            db.commit()
        return value

    def allocations(self):
        with self.ledger.connection() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT value FROM action_fill_allocations ORDER BY rowid')]

    def account_confirmed(self, db, command, events, receipt):
        """Called only inside Ledger's writer, before the one account commit."""
        fills = {e['payload']['record_id']: e for e in events if e['event_type'] in {'BUY_FILL', 'SELL_FILL'}}
        totals = {}
        for allocation in command.fill_allocations:
            quantity = Decimal(number(allocation.allocated_quantity, 'allocated_quantity', 8))
            if quantity <= 0 or allocation.association_status not in {'USER_CONFIRMED', 'UNKNOWN'}:
                raise HTTPException(422, 'INVALID_FILL_ALLOCATION')
            fill = fills.get(allocation.fill_record_id)
            if not fill: raise HTTPException(422, 'ALLOCATION_REQUIRES_FILL_IN_THIS_CONFIRMATION')
            intent = self.get(allocation.intent_id, db)
            payload = fill['payload']
            totals[allocation.fill_record_id] = totals.get(allocation.fill_record_id, Decimal(0)) + quantity
            if totals[allocation.fill_record_id] > Decimal(payload['quantity']): raise HTTPException(422, 'ALLOCATION_EXCEEDS_ACTUAL_FILL')
            matches = intent['instrument'] == payload['instrument'] and (intent['action'] in {'BUY', 'ADD'}) == (payload['direction'] == 'BUY')
            association = 'UNKNOWN' if allocation.association_status == 'UNKNOWN' else 'USER_CONFIRMED' if matches else 'CONTRARY'
            value = {'allocation_id': str(uuid4()), 'decision_id': intent['decision_id'], 'intent_id': intent['intent_id'],
                     'fill_event_id': fill['event_id'], 'fill_record_id': allocation.fill_record_id, 'allocated_quantity': format(quantity, 'f'),
                     'association_status': association, 'receipt_id': receipt['receipt_id'], 'account_version': receipt['account_version'],
                     'occurred_at': fill['effective_at'], 'known_at': fill['recorded_at'], 'reported_source': fill['source'],
                     'price': payload['price'], 'fee': payload['fee'], 'decision_time_chain': intent['time_chain']}
            db.execute('INSERT INTO action_fill_allocations VALUES(?,?)', (value['allocation_id'], encode(value)))
            if association == 'USER_CONFIRMED':
                synced = Decimal(intent['synced_quantity']) + quantity
                total = Decimal(intent['decision']['quantity'])
                remaining = max(Decimal(0), total - synced)
                intent.update(synced_quantity=format(synced, 'f'), remaining_quantity=format(remaining, 'f'),
                              provisional_reservation_yuan=money(Decimal(intent['original_reservation_yuan']) * remaining / total),
                              excess_quantity=format(max(Decimal(0), synced - total), 'f'), remaining_action_state='REEVALUATION_REQUIRED')
                # A complete reported allocation is not proof that an external order is closed.
                if intent['status'] == 'PREPARED': intent['status'] = 'OPERATION_PENDING'
                db.execute('UPDATE execution_intents SET value=? WHERE id=?', (encode(intent), intent['intent_id']))
            self.event(db, 'FILL_ALLOCATED', intent['intent_id'], receipt['confirmed_at'], allocation_id=value['allocation_id'])
        self.actions.current(db=db)

    def metrics(self):
        values = self.listing()['intents']
        return {'unfinished_execution_intents': {'status': 'CHECKED', 'value': sum(v['status'] not in {'NOT_EXECUTED', 'RESOLVED'} for v in values)},
                'partially_synced_intents': {'status': 'CHECKED', 'value': sum(Decimal(v['synced_quantity']) > 0 and Decimal(v['remaining_quantity']) > 0 for v in values)}}

    @staticmethod
    def event(db, kind, identifier, at, **fields):
        value = {'event_id': str(uuid4()), 'event_type': kind, 'intent_id': identifier, 'recorded_at': at, **fields}
        db.execute('INSERT INTO execution_intent_events VALUES(?,?)', (value['event_id'], encode(value)))
