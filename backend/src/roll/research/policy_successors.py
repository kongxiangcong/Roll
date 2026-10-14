"""Unvalidated policy proposals: no ACTUAL writer or capability consumer."""
import json
from decimal import Decimal
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from roll.accounts.ledger import encode, now
from roll.research.shadow import fingerprint


class SuccessorCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    predecessor_freeze_id: str
    predecessor_policy_fingerprint: str = Field(pattern=r'^[0-9a-f]{64}$')
    version: str = Field(min_length=1, max_length=100)
    idempotency_key: str = Field(min_length=1, max_length=128)
    basis: str = Field(min_length=1)


Money = Annotated[str, Field(pattern=r'^\d{1,18}(?:\.\d{1,2})?$')]


class MigrationCommand(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    idempotency_key: str = Field(min_length=1, max_length=128)
    position_id: str = Field(min_length=1)
    instrument: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    original_exit_session: int = Field(ge=0)
    effective_session: int = Field(ge=0)
    basis: str = Field(min_length=1)


class Position(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    position_id: str = Field(min_length=1)
    instrument: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    sellable_quantity: int | None = Field(default=None, ge=0)
    original_exit_session: int = Field(ge=0)
    migration_id: str | None = None


class Opportunity(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    instrument: str = Field(min_length=1)
    forecast_id: str = Field(min_length=1)
    probability: str | None = Field(default=None, pattern=r'^(?:0(?:\.\d{1,12})?|1(?:\.0{1,12})?)$')
    upper_price_yuan: Money | None = None
    fees_yuan: Money | None = None
    buy_minimum: int | None = Field(default=None, gt=0)
    buy_increment: int | None = Field(default=None, gt=0)


class ActionHistory(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    instrument: str = Field(min_length=1)
    action: Literal['BUY', 'ADD', 'EXIT', 'REDUCE']
    completed_session: int = Field(ge=0)


class PolicyEvaluation(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    idempotency_key: str = Field(min_length=1, max_length=128)
    completed_session: int = Field(ge=0)
    cash_yuan: Money
    reserved_yuan: Money
    nav_yuan: Money
    current_exposure_yuan: Money
    positions: list[Position] = Field(default_factory=list)
    opportunities: list[Opportunity] = Field(default_factory=list)
    history: list[ActionHistory] = Field(default_factory=list)

    @field_validator('positions', 'opportunities')
    @classmethod
    def unique_instruments(cls, rows):
        if len({row.instrument for row in rows}) != len(rows):
            raise ValueError('Duplicate instrument')
        return rows


def calculate(proposal, inputs, migrations):
    """Sample inputs stay untrusted; output is never a formal Decision."""
    policy = proposal['policy']
    cash = max(Decimal('0'), Decimal(inputs['cash_yuan']) - Decimal(inputs['reserved_yuan']))
    exposure = Decimal(inputs['current_exposure_yuan'])
    cap = Decimal(inputs['nav_yuan']) * Decimal(policy['maximum_gross_exposure'])
    session = inputs['completed_session']
    positions = {p['instrument']: p for p in inputs['positions']}
    signals = {s['instrument']: s for s in inputs['opportunities']}
    if any(h['completed_session'] > session for h in inputs['history']):
        raise HTTPException(422, 'FUTURE_ACTION_HISTORY')
    history_slots = [(h['instrument'], h['completed_session']) for h in inputs['history']]
    if len(set(history_slots)) != len(history_slots):
        raise HTTPException(422, 'AMBIGUOUS_ACTION_HISTORY')
    # Risk-reducing research clauses are evaluated first, without funding proceeds.
    symbols = sorted(set(positions) | set(signals), key=lambda symbol: (
        0 if symbol in positions else 1,
        -Decimal(signals.get(symbol, {}).get('probability') or '0'), symbol,
        signals.get(symbol, {}).get('forecast_id', '')))
    actions = []
    new_entry = False
    for symbol in symbols:
        p, signal = positions.get(symbol), signals.get(symbol)
        quantity = p['quantity'] if p else 0
        probability = Decimal(signal['probability']) if signal and signal['probability'] is not None else None
        reasons = []
        action, amount = 'REFUSE', 0
        migration = migrations.get(p.get('migration_id')) if p else None
        if migration:
            if any(migration[key] != p[key] for key in ['position_id', 'instrument', 'quantity', 'original_exit_session']):
                raise HTTPException(409, 'POSITION_MIGRATION_FACTS_MISMATCH')
            if migration['effective_session'] > session:
                raise HTTPException(409, 'POSITION_MIGRATION_NOT_YET_EFFECTIVE')
        bound = bool(p and migration and all(migration[key] == p[key] for key in
            ['position_id', 'instrument', 'quantity', 'original_exit_session']) and migration['effective_session'] <= session)
        if p and session >= p['original_exit_session']:
            action, amount = 'EXIT', quantity
            reasons.append('ORIGINAL_HORIZON_REACHED')
        elif probability is None:
            reasons.append('PREDICTION_SUPPORT_UNKNOWN_NO_DEFAULT_HOLD')
        elif p and probability < Decimal(policy['support_threshold']):
            action, amount = 'EXIT', quantity
            reasons.append('UNVALIDATED_LOW_SUPPORT_EXIT_CLAUSE')
        elif p and quantity >= int(policy['target_quantity']):
            action = 'HOLD'
            reasons.append('SUPPORTED_POSITION_AT_OR_ABOVE_TARGET_NO_AUTOMATIC_RESIZE')
        elif probability < Decimal(policy['entry_threshold']):
            action = 'WAIT'
            reasons.append('BELOW_INHERITED_ENTRY_THRESHOLD')
        else:
            action, amount = ('ADD' if p else 'BUY'), int(policy['target_quantity']) - quantity
            if p and not bound:
                reasons.append('POSITION_MIGRATION_REQUIRED')
                action, amount = 'REFUSE', 0
        if action in {'EXIT', 'REDUCE'} and (p['sellable_quantity'] is None or p['sellable_quantity'] < amount):
            reasons.append('SELLABLE_QUANTITY_UNKNOWN_OR_INSUFFICIENT')
            action, amount = 'REFUSE', 0
        last = max((h for h in inputs['history'] if h['instrument'] == symbol),
            key=lambda h: h['completed_session'], default=None)
        if last and action in {'BUY', 'ADD', 'EXIT', 'REDUCE'}:
            buying = action in {'BUY', 'ADD'}
            if buying != (last['action'] in {'BUY', 'ADD'}) and session - last['completed_session'] <= policy['reversal_cooldown_completed_sessions']:
                reasons.append('OPPOSITE_ACTION_COOLDOWN')
                action, amount = 'REFUSE', 0
        required = Decimal('0')
        if action in {'BUY', 'ADD'}:
            if any(signal.get(k) is None for k in ['upper_price_yuan', 'fees_yuan', 'buy_minimum', 'buy_increment']):
                reasons.append('PRICE_FEES_OR_QUANTITY_RULE_UNKNOWN')
            elif Decimal(signal['upper_price_yuan']) <= 0:
                reasons.append('NONPOSITIVE_UPPER_PRICE')
            elif amount < signal['buy_minimum'] or (amount - signal['buy_minimum']) % signal['buy_increment']:
                reasons.append('QUANTITY_RULE_RESTRICTED')
            else:
                required = Decimal(signal['upper_price_yuan']) * amount + Decimal(signal['fees_yuan'])
                if required > cash:
                    reasons.append('JOINT_CASH_BUDGET')
                if exposure + required > cap:
                    reasons.append('INHERITED_EXPOSURE_CAP')
                if not p and new_entry:
                    reasons.append('ONE_NEW_ENTRY_LIMIT')
            if reasons:
                action, amount, required = 'REFUSE', 0, Decimal('0')
            else:
                cash -= required
                exposure += required
                if not p:
                    new_entry = True
        actions.append({'instrument': symbol, 'forecast_id': signal.get('forecast_id') if signal else None,
            'action': action, 'quantity': amount, 'current_quantity': quantity,
            'target_quantity': quantity + amount if action in {'BUY', 'ADD'} else quantity - amount if action == 'EXIT' else quantity,
            'reserved_cash_yuan': format(required, '.2f'), 'reasons': reasons,
            'original_exit_session': p['original_exit_session'] if p else None,
            'migration_id': migration['migration_id'] if bound else None})
    actions.sort(key=lambda row: 0 if row['action'] in {'EXIT', 'REDUCE'} else 1)
    return {'actions': actions, 'available_cash_after_reservations_yuan': format(cash, '.2f'),
        'exposure_after_reservations_yuan': format(exposure, '.2f'), 'planned_sale_proceeds_yuan': '0.00'}


class PolicySuccessors:
    def __init__(self, shadow):
        self.shadow = shadow
        self.ledger = shadow.ledger
        with self.ledger.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS research_policy_successors(
                    id TEXT PRIMARY KEY, version TEXT UNIQUE, key TEXT UNIQUE,
                    command_hash TEXT, value TEXT);
                CREATE TABLE IF NOT EXISTS research_policy_migrations(
                    id TEXT PRIMARY KEY, proposal_id TEXT, position_id TEXT, key TEXT,
                    command_hash TEXT, value TEXT, UNIQUE(proposal_id,key), UNIQUE(proposal_id,position_id));
                CREATE TABLE IF NOT EXISTS research_policy_evaluations(
                    id TEXT PRIMARY KEY, proposal_id TEXT, key TEXT,
                    command_hash TEXT, value TEXT, UNIQUE(proposal_id,key));
            ''')

    def register(self, command):
        frozen = self.shadow.get(command.predecessor_freeze_id)
        original = frozen['policy']
        if fingerprint(original) != command.predecessor_policy_fingerprint:
            raise HTTPException(409, 'PREDECESSOR_POLICY_FINGERPRINT_MISMATCH')
        if original['version'] != '20-policy-v1':
            raise HTTPException(409, 'UNSUPPORTED_PREDECESSOR_POLICY')
        if command.version == original['version']:
            raise HTTPException(422, 'SUCCESSOR_REQUIRES_NEW_VERSION')
        command_hash = fingerprint(command.model_dump(exclude={'idempotency_key'}))
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior = db.execute('SELECT command_hash,value FROM research_policy_successors WHERE key=?', (command.idempotency_key,)).fetchone()
            if prior:
                if prior[0] != command_hash:
                    raise HTTPException(409, 'POLICY_IDEMPOTENCY_CONFLICT')
                return json.loads(prior[1])
            if db.execute('SELECT 1 FROM research_policy_successors WHERE version=?', (command.version,)).fetchone():
                raise HTTPException(409, 'POLICY_VERSION_IMMUTABLE')
            policy = {'version': command.version, 'entry_threshold': original['probability_threshold'],
                'support_threshold': original['probability_threshold'], 'target_quantity': original['quantity'],
                'maximum_gross_exposure': original['maximum_gross_exposure'],
                'horizon': original['exit'], 'low_support_exit': 'PROPOSED_EXIT_BELOW_SUPPORT',
                'reversal_cooldown_completed_sessions': 1,
                'migration': 'EXPLICIT_POSITION_BINDING_KEEP_ORIGINAL_EXIT_SESSION',
                'ordering': 'risk_reductions_then_existing_positions_then_descending_probability_then_instrument_then_forecast_id',
                'predecessor_entry_ordering': original['ordering'], 'joint_budget': original['joint_budget'],
                'one_new_entry': True, 'planned_sale_proceeds': 'NEVER_AVAILABLE'}
            value = {'proposal_id': str(uuid4()), 'namespace': 'RESEARCH_POLICY_PROPOSAL',
                'capability': 'NOT_GRANTED', 'system_usable': False, 'validation_status': 'UNVALIDATED',
                'predecessor_freeze_id': frozen['freeze_id'],
                'predecessor_complete_protocol_fingerprint': frozen['complete_protocol_fingerprint'],
                'predecessor_policy_fingerprint': command.predecessor_policy_fingerprint,
                'policy': policy, 'policy_fingerprint': fingerprint(policy), 'basis': command.basis,
                'required_before_formal_use': ['NEW_COMPLETE_EXPERIMENT_FREEZE', 'INDEPENDENT_VALIDATION', 'MATCHING_CURRENT_GRANT'],
                'registered_at': now()}
            db.execute('INSERT INTO research_policy_successors VALUES(?,?,?,?,?)',
                (value['proposal_id'], command.version, command.idempotency_key, command_hash, encode(value)))
            db.commit()
            return value

    def get(self, proposal_id):
        with self.ledger.connection() as db:
            row = db.execute('SELECT value FROM research_policy_successors WHERE id=?', (proposal_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'RESEARCH_POLICY_PROPOSAL_NOT_FOUND')
        value = json.loads(row[0])
        frozen = self.shadow.get(value['predecessor_freeze_id'])
        if (fingerprint(value['policy']) != value['policy_fingerprint'] or
                frozen['complete_protocol_fingerprint'] != value['predecessor_complete_protocol_fingerprint']):
            raise HTTPException(409, 'POLICY_PROPOSAL_BINDING_MISMATCH')
        return value

    def migrate(self, proposal_id, command):
        proposal = self.get(proposal_id)
        content = fingerprint(command.model_dump(exclude={'idempotency_key'}))
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior = db.execute('SELECT command_hash,value FROM research_policy_migrations WHERE proposal_id=? AND key=?',
                (proposal_id, command.idempotency_key)).fetchone()
            if prior:
                if prior[0] != content:
                    raise HTTPException(409, 'MIGRATION_IDEMPOTENCY_CONFLICT')
                return json.loads(prior[1])
            if db.execute('SELECT 1 FROM research_policy_migrations WHERE proposal_id=? AND position_id=?',
                    (proposal_id, command.position_id)).fetchone():
                raise HTTPException(409, 'POSITION_MIGRATION_IMMUTABLE')
            value = {**command.model_dump(exclude={'idempotency_key'}), 'migration_id': str(uuid4()),
                'proposal_id': proposal_id, 'policy_fingerprint': proposal['policy_fingerprint'],
                'namespace': 'RESEARCH_POLICY_PROPOSAL', 'system_usable': False, 'registered_at': now()}
            db.execute('INSERT INTO research_policy_migrations VALUES(?,?,?,?,?,?)',
                (value['migration_id'], proposal_id, command.position_id, command.idempotency_key, content, encode(value)))
            db.commit()
            return value

    def evaluate(self, proposal_id, command):
        proposal = self.get(proposal_id)
        inputs = command.model_dump(exclude={'idempotency_key'})
        content = fingerprint(inputs)
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior = db.execute('SELECT command_hash,value FROM research_policy_evaluations WHERE proposal_id=? AND key=?',
                (proposal_id, command.idempotency_key)).fetchone()
            if prior:
                if prior[0] != content:
                    raise HTTPException(409, 'POLICY_EVALUATION_IDEMPOTENCY_CONFLICT')
                return json.loads(prior[1])
            identifiers = {p.migration_id for p in command.positions if p.migration_id}
            migrations = {}
            for identifier in identifiers:
                row = db.execute('SELECT value FROM research_policy_migrations WHERE id=? AND proposal_id=?',
                    (identifier, proposal_id)).fetchone()
                if not row:
                    raise HTTPException(409, 'POSITION_MIGRATION_NOT_BOUND_TO_PROPOSAL')
                migrations[identifier] = json.loads(row[0])
            result = calculate(proposal, inputs, migrations)
            value = {**result, 'evaluation_id': str(uuid4()), 'proposal_id': proposal_id,
                'namespace': 'RESEARCH_POLICY_PROPOSAL', 'system_usable': False, 'capability': 'NOT_GRANTED',
                'input_authority': 'UNTRUSTED_RESEARCH_SAMPLE', 'validation_status': 'UNVALIDATED',
                'policy_fingerprint': proposal['policy_fingerprint'], 'inputs': inputs,
                'input_fingerprint': content, 'migrations': migrations, 'recorded_at': now()}
            value['result_fingerprint'] = fingerprint(result)
            db.execute('INSERT INTO research_policy_evaluations VALUES(?,?,?,?,?)',
                (value['evaluation_id'], proposal_id, command.idempotency_key, content, encode(value)))
            db.commit()
            return value

    def evaluation(self, proposal_id, evaluation_id):
        proposal = self.get(proposal_id)
        with self.ledger.connection() as db:
            row = db.execute('SELECT value FROM research_policy_evaluations WHERE id=? AND proposal_id=?',
                (evaluation_id, proposal_id)).fetchone()
        if not row:
            raise HTTPException(404, 'RESEARCH_POLICY_EVALUATION_NOT_FOUND')
        value = json.loads(row[0])
        if (fingerprint(value['inputs']) != value['input_fingerprint'] or
                value['policy_fingerprint'] != proposal['policy_fingerprint']):
            raise HTTPException(409, 'POLICY_EVALUATION_BINDING_MISMATCH')
        result = calculate(proposal, value['inputs'], value['migrations'])
        if fingerprint(result) != value['result_fingerprint'] or any(value[k] != v for k, v in result.items()):
            raise HTTPException(409, 'POLICY_EVALUATION_RESULT_MISMATCH')
        return value

    def replay(self, proposal_id, evaluation_id):
        value = self.evaluation(proposal_id, evaluation_id)
        return {'evaluation_id': evaluation_id, 'matches_original': True,
            'namespace': value['namespace'], 'system_usable': False, 'capability': 'NOT_GRANTED',
            'result_fingerprint': value['result_fingerprint']}
