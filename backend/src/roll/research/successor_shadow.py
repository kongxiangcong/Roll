"""Separate unvalidated v2 METHOD shadow; never changes v1 results or ACTUAL."""
import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from roll.accounts.ledger import encode, now
from roll.research.execution import fees, money
from roll.research.policy_successors import Money, Position, calculate
from roll.research.shadow import fingerprint


def source_fingerprint():
    sources = [Path(__file__), Path(__file__).with_name('policy_successors.py')]
    return fingerprint({p.name: hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest() for p in sources})


class SuccessorFreezeCommand(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    idempotency_key: str = Field(min_length=1, max_length=128)
    policy_fingerprint: str
    starting_session: int = Field(ge=0)
    cash_yuan: Money
    positions: list[Position] = Field(default_factory=list, max_length=30)
    basis: str = Field(min_length=1)


class DailyBar(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    instrument: str
    open_yuan: Money | None = None
    high_yuan: Money | None = None
    low_yuan: Money | None = None
    close_yuan: Money | None = None
    reference_close_yuan: Money | None = None
    volume_shares: int | None = Field(default=None, ge=0)
    completion: Literal['COMPLETE', 'INCOMPLETE', 'UNKNOWN']
    market_state: Literal['NORMAL', 'SUSPENDED', 'UNKNOWN']
    company_actions: Literal['NONE', 'UNKNOWN']


class Signal(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    instrument: str
    forecast_id: str
    probability: str | None = Field(default=None, pattern=r'^(?:0(?:\.\d{1,12})?|1(?:\.0{1,12})?)$')


class SuccessorAdvanceCommand(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    idempotency_key: str = Field(min_length=1, max_length=128)
    expected_revision: int = Field(ge=0)
    session: int = Field(ge=0)
    calendar_previous_session: int | None = Field(default=None, ge=0)
    source_snapshot_id: str = Field(min_length=1)
    evidence_kind: Literal['METHOD_CASE']
    bars: list[DailyBar] = Field(max_length=30)
    signals: list[Signal] = Field(default_factory=list, max_length=30)


def usable(bar):
    if not bar or bar['completion'] != 'COMPLETE' or bar['market_state'] != 'NORMAL' or bar['company_actions'] != 'NONE':
        return False
    if any(bar.get(k) is None for k in ['open_yuan', 'high_yuan', 'low_yuan', 'close_yuan', 'reference_close_yuan', 'volume_shares']):
        return False
    low, high = Decimal(bar['low_yuan']), Decimal(bar['high_yuan'])
    return low > 0 and Decimal(bar['reference_close_yuan']) > 0 and low <= min(Decimal(bar['open_yuan']), Decimal(bar['close_yuan'])) <= max(Decimal(bar['open_yuan']), Decimal(bar['close_yuan'])) <= high


def simulate(frozen, frames):
    cash = Decimal(frozen['baseline']['cash_yuan'])
    start = frozen['baseline']['starting_session']
    lots = [{**p, 'lot_id': 'BASELINE:'+p['position_id'], 'entry_session': start,
        'exit_session': p['original_exit_session'], 'baseline': True} for p in frozen['baseline']['positions']]
    pending, events, evaluations, history, gaps = [], [], [], [], []
    last_session = start
    costs, rules = frozen['costs'], frozen['rules']

    def charge(gross, side):
        return Decimal(fees(gross, costs, side)['total_yuan'])

    def execute(symbol, quantity, side, bar, point, bounds, session, order_id, target_lot_id=None):
        nonlocal cash
        if not usable(bar):
            return 'MISSING_OR_UNKNOWN_EXECUTION_INPUT'
        rule = rules[symbol]
        if bar['volume_shares'] < quantity:
            return 'INSUFFICIENT_REPORTED_VOLUME'
        tick = Decimal(rule['price_tick_yuan'])
        slip = Decimal(costs['slippage_each_side_rate'])
        price = (Decimal(bar[point]) * (1 + slip if side == 'BUY' else 1 - slip) / tick).quantize(Decimal('1'), rounding=ROUND_HALF_UP) * tick
        limit = Decimal(rule['normal_price_limit_percent']) / 100
        floor = (Decimal(bar['reference_close_yuan']) * (1-limit) / tick).quantize(Decimal('1'), rounding=ROUND_HALF_UP) * tick
        ceiling = (Decimal(bar['reference_close_yuan']) * (1+limit) / tick).quantize(Decimal('1'), rounding=ROUND_HALF_UP) * tick
        if not floor <= price <= ceiling or bounds and not Decimal(bounds[0]) <= price <= Decimal(bounds[1]):
            return 'OUTSIDE_FROZEN_PRICE_WINDOW'
        locked = ceiling if side == 'BUY' else floor
        if all(Decimal(bar[k]) == locked for k in ['open_yuan', 'high_yuan', 'low_yuan', 'close_yuan']):
            return 'LOCKED_PRICE_LIMIT'
        gross = price * quantity
        expense = charge(gross, side)
        if side == 'BUY':
            if gross + expense > cash:
                return 'CASH_CONSERVATION_REFUSAL'
            if any(not usable(bars.get(p['instrument'])) for p in lots):
                return 'OPEN_VALUATION_SUPPORT_UNKNOWN'
            opening_exposure = sum((Decimal(bars[p['instrument']]['open_yuan']) * p['quantity'] for p in lots), Decimal('0'))
            if opening_exposure + gross + expense > (cash + opening_exposure) * Decimal(frozen['policy']['maximum_gross_exposure']):
                return 'OPEN_EXPOSURE_LIMIT_RECHECK_FAILED'
            if quantity < int(rule['buy_minimum']) or (quantity-int(rule['buy_minimum'])) % int(rule['buy_increment']):
                return 'QUANTITY_RULE_RESTRICTED'
            cash -= gross + expense
            lots.append({'lot_id': order_id, 'position_id': order_id, 'instrument': symbol,
                'quantity': quantity, 'sellable_quantity': quantity, 'entry_session': session,
                'exit_session': session + frozen['design']['new_lot_horizon_sessions'],
                'original_exit_session': session + frozen['design']['new_lot_horizon_sessions'],
                'migration_id': None, 'baseline': False})
        else:
            eligible = [p for p in lots if p['instrument'] == symbol and p['entry_session'] < session and
                p['sellable_quantity'] is not None and (target_lot_id is None or p['lot_id'] == target_lot_id)]
            if sum(p['sellable_quantity'] for p in eligible) < quantity:
                return 'SELLABLE_QUANTITY_UNKNOWN_OR_INSUFFICIENT'
            remaining = quantity
            for lot in sorted(eligible, key=lambda p: (p['exit_session'], p['lot_id'])):
                take = min(remaining, lot['quantity'], lot['sellable_quantity'])
                lot['quantity'] -= take
                lot['sellable_quantity'] -= take
                remaining -= take
                if not lot['quantity']:
                    lots.remove(lot)
                if not remaining:
                    break
            cash += gross - expense
        events.append({'kind': side+'_FILL', 'order_id': order_id, 'instrument': symbol, 'quantity': quantity,
            'session': session, 'point': point, 'price_yuan': money(price), 'fees_yuan': money(expense),
            'cash_delta_yuan': money(-gross-expense if side == 'BUY' else gross-expense)})
        # OPEN and scheduled CLOSE fills have a known sequence in this engine.
        # Retain every fill event; the policy consumes the latest side at that session.
        history[:] = [h for h in history if (h['instrument'], h['completed_session']) != (symbol, session)]
        history.append({'instrument': symbol, 'action': 'BUY' if side == 'BUY' else 'EXIT', 'completed_session': session})
        return None

    for frame in frames:
        session = frame['session']
        bars = {b['instrument']: b for b in frame['bars']}
        signals = {s['instrument']: s for s in frame['signals']}
        if len(bars) != len(frame['bars']) or len(signals) != len(frame['signals']):
            raise HTTPException(422, 'DUPLICATE_SESSION_INSTRUMENT')
        if session <= last_session:
            raise HTTPException(409, 'SHADOW_SESSION_NOT_INCREASING')
        if (set(bars) | set(signals)) - set(rules):
            raise HTTPException(422, 'SUCCESSOR_INPUT_OUTSIDE_FROZEN_SCOPE')
        for symbol in rules:
            if not usable(bars.get(symbol)):
                gaps.append({'session': session, 'instrument': symbol, 'reason': 'MISSING_OR_UNKNOWN_EXECUTION_INPUT'})
        consecutive = session == last_session+1 and frame['calendar_previous_session'] == last_session
        if not consecutive:
            gaps.append({'session': session, 'reason': 'CONSECUTIVE_CALENDAR_COVERAGE_UNKNOWN'})
        for order in list(pending):
            if order['expected_session'] > session:
                continue
            reason = 'MISSED_NEXT_SESSION_NO_DISTANT_BAR_SUBSTITUTION' if not consecutive or order['expected_session'] != session else execute(
                order['instrument'], order['quantity'], order['side'], bars.get(order['instrument']),
                'open_yuan', order['bounds'], session, order['order_id'])
            if reason:
                events.append({'kind': 'NO_FILL', 'session': session, 'order_id': order['order_id'], 'reason': reason})
                gaps.append({'session': session, 'instrument': order['instrument'], 'reason': reason})
            pending.remove(order)
        # Original migration horizons remain separate lot-level CLOSE schedules.
        for lot in list(lots):
            if lot['exit_session'] <= session:
                reason = execute(lot['instrument'], lot['quantity'], 'SELL', bars.get(lot['instrument']),
                    'close_yuan', None, session, 'HORIZON:'+lot['lot_id'], target_lot_id=lot['lot_id'])
                if reason:
                    gaps.append({'session': session, 'instrument': lot['instrument'], 'reason': reason,
                        'original_exit_session': lot['exit_session']})
        exposure = Decimal('0')
        unknown_valuation = False
        aggregate, migrations = [], {}
        for symbol in sorted({p['instrument'] for p in lots}):
            local = [p for p in lots if p['instrument'] == symbol]
            bar = bars.get(symbol)
            if not usable(bar):
                unknown_valuation = True
            else:
                exposure += sum(p['quantity'] for p in local) * Decimal(bar['close_yuan'])
            sellable = None if any(p['sellable_quantity'] is None for p in local) else sum(p['sellable_quantity'] for p in local if p['entry_session'] < session)
            row = {'position_id': 'AGGREGATE:'+symbol, 'instrument': symbol,
                'quantity': sum(p['quantity'] for p in local), 'sellable_quantity': sellable,
                'original_exit_session': min(p['exit_session'] for p in local), 'migration_id': None}
            migrated = all(not p['baseline'] or frozen['migrations'][p['migration_id']]['effective_session'] <= session for p in local)
            if migrated:
                row['migration_id'] = 'DERIVED:'+symbol
                migrations[row['migration_id']] = {**row, 'effective_session': start,
                    'provenance': 'V2_INTERNAL_LOTS_KEEP_ORIGINAL_MIGRATION_AND_EACH_FILL_HORIZON'}
            aggregate.append(row)
        opportunities = []
        for symbol, signal in signals.items():
            bar, rule = bars.get(symbol), rules[symbol]
            upper = Decimal(bar['close_yuan']) * (1+Decimal(rule['normal_price_limit_percent'])/100) if usable(bar) else None
            opportunities.append({**signal, 'upper_price_yuan': money(upper) if upper else None,
                'fees_yuan': money(charge(upper*int(frozen['policy']['target_quantity']), 'BUY')) if upper else None,
                'buy_minimum': int(rule['buy_minimum']), 'buy_increment': int(rule['buy_increment'])})
        inputs = {'completed_session': session, 'cash_yuan': money(cash), 'reserved_yuan': '0.00',
            'nav_yuan': money(cash+exposure), 'current_exposure_yuan': money(exposure),
            'positions': aggregate, 'opportunities': opportunities, 'history': history}
        result = calculate({'policy': frozen['policy']}, inputs, migrations)
        for action in result['actions']:
            if action['action'] != 'REFUSE' and not usable(bars.get(action['instrument'])):
                action.update(action='REFUSE', quantity=0, target_quantity=action['current_quantity'], reserved_cash_yuan='0.00')
                action['reasons'].append('CURRENT_EXECUTION_SUPPORT_UNKNOWN')
            if unknown_valuation and action['action'] in {'BUY', 'ADD'}:
                action.update(action='REFUSE', quantity=0, target_quantity=action['current_quantity'], reserved_cash_yuan='0.00')
                action['reasons'].append('VALUATION_SUPPORT_UNKNOWN')
            if action['action'] in {'BUY', 'ADD', 'EXIT'}:
                bar = bars.get(action['instrument'])
                rule = rules[action['instrument']]
                if not usable(bar):
                    action.update(action='REFUSE', quantity=0, target_quantity=action['current_quantity'], reserved_cash_yuan='0.00')
                    action['reasons'].append('CURRENT_EXECUTION_SUPPORT_UNKNOWN')
                    continue
                limit = Decimal(rule['normal_price_limit_percent'])/100
                lower, upper = Decimal(bar['close_yuan'])*(1-limit), Decimal(bar['close_yuan'])*(1+limit)
                pending.append({'order_id': 'ORDER:'+frame['source_snapshot_id']+':'+action['instrument'],
                    'instrument': action['instrument'], 'quantity': action['quantity'],
                    'side': 'BUY' if action['action'] in {'BUY', 'ADD'} else 'SELL',
                    'expected_session': session+1, 'bounds': [money(lower), money(upper)],
                    'reserved_cash_yuan': action['reserved_cash_yuan']})
        evaluations.append({'session': session, 'source_snapshot_id': frame['source_snapshot_id'], 'actions': result['actions']})
        last_session = session
    reserved = sum((Decimal(p['reserved_cash_yuan']) for p in pending), Decimal('0'))
    return {'cash_yuan': money(cash), 'reserved_cash_yuan': money(reserved), 'positions': lots,
        'pending': pending, 'events': events, 'evaluations': evaluations, 'gaps': gaps,
        'last_session': last_session, 'revision': len(frames), 'namespace': 'SUCCESSOR_METHOD_SHADOW',
        'system_usable': False, 'capability': 'NOT_GRANTED', 'validation_status': 'UNVALIDATED',
        'validation_verdict': 'INCONCLUSIVE', 'real_forward_started_at': None}


class SuccessorShadow:
    def __init__(self, successors):
        self.successors = successors
        self.ledger = successors.ledger
        with self.ledger.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS research_successor_freezes(id TEXT PRIMARY KEY,
                    proposal_id TEXT UNIQUE, key TEXT, command_hash TEXT, value TEXT);
                CREATE TABLE IF NOT EXISTS research_successor_frames(freeze_id TEXT, revision INTEGER,
                    key TEXT, command_hash TEXT, value TEXT, PRIMARY KEY(freeze_id,revision), UNIQUE(freeze_id,key));
            ''')

    def freeze(self, proposal_id, command):
        proposal = self.successors.get(proposal_id)
        previous = self.successors.shadow.get(proposal['predecessor_freeze_id'])
        if proposal['policy_fingerprint'] != command.policy_fingerprint:
            raise HTTPException(409, 'SUCCESSOR_POLICY_FINGERPRINT_MISMATCH')
        content = fingerprint(command.model_dump(exclude={'idempotency_key'}))
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior = db.execute('SELECT key,command_hash,value FROM research_successor_freezes WHERE proposal_id=?', (proposal_id,)).fetchone()
            if prior:
                if prior[0] != command.idempotency_key or prior[1] != content:
                    raise HTTPException(409, 'SUCCESSOR_FREEZE_IMMUTABLE')
                return json.loads(prior[2])
            migrations = {}
            if len({p.instrument for p in command.positions}) != len(command.positions):
                raise HTTPException(422, 'DUPLICATE_BASELINE_INSTRUMENT')
            for p in command.positions:
                if p.added_lots or p.original_remaining_quantity not in (None, p.quantity):
                    raise HTTPException(422, 'SUCCESSOR_BASELINE_REQUIRES_ORIGINAL_MIGRATION_LOT')
                row = db.execute('SELECT value FROM research_policy_migrations WHERE id=? AND proposal_id=?', (p.migration_id, proposal_id)).fetchone()
                if not row:
                    raise HTTPException(409, 'BASELINE_MIGRATION_REQUIRED')
                migration = json.loads(row[0])
                if p.instrument not in previous['rules'] or any(migration[k] != getattr(p, k) for k in ['position_id', 'instrument', 'quantity', 'original_exit_session']):
                    raise HTTPException(409, 'BASELINE_MIGRATION_FACTS_MISMATCH')
                if p.original_exit_session <= command.starting_session:
                    raise HTTPException(422, 'BASELINE_HORIZON_MUST_BE_FUTURE')
                migrations[p.migration_id] = migration
            design = {'forecast_execution': 'NEXT_CONSECUTIVE_DECLARED_SESSION_OPEN_ONLY',
                'migration_horizon_execution': 'KEEP_ORIGINAL_LOT_HORIZON_CLOSE',
                'new_lot_horizon_sessions': int(proposal['policy']['horizon'].removeprefix('HORIZON_SESSION').removesuffix('_CLOSE')),
                'missing_session': 'NO_DISTANT_BAR_FILL_NO_RETROSPECTIVE_PREDICTION',
                'fees': 'INHERITED_RESEARCH_SCENARIO_NOT_ACTUAL_BROKER_TARIFF',
                'cash_flow_policy': 'NO_EXTERNAL_FLOWS', 'input_authority': 'UNTRUSTED_METHOD_SNAPSHOT',
                'validation': 'NEW_POLICY_ECONOMIC_AND_INDEPENDENT_CALIBRATION_NOT_CHECKED'}
            value = {'successor_freeze_id': str(uuid4()), 'proposal_id': proposal_id,
                'predecessor_freeze_id': previous['freeze_id'], 'predecessor_complete_protocol_fingerprint': previous['complete_protocol_fingerprint'],
                'policy': proposal['policy'], 'policy_fingerprint': proposal['policy_fingerprint'],
                'model_freeze_manifest': previous['model_freeze_manifest'],
                'model_artifact_fingerprints': previous['model_freeze']['artifact_fingerprints'],
                'costs': previous['design']['costs'], 'rules': previous['rules'], 'design': design,
                'source_fingerprint': source_fingerprint(), 'design_fingerprint': fingerprint(design),
                'baseline': command.model_dump(include={'starting_session','cash_yuan','positions'}), 'migrations': migrations,
                'namespace': 'SUCCESSOR_RESEARCH_FREEZE', 'system_usable': False, 'capability': 'NOT_GRANTED',
                'validation_status': 'UNVALIDATED', 'validation_verdict': 'INCONCLUSIVE',
                'complete_experiment_frozen': False, 'policy_and_simulation_frozen': True,
                'basis': command.basis, 'registered_at': now()}
            value['successor_fingerprint'] = fingerprint(value)
            db.execute('INSERT INTO research_successor_freezes VALUES(?,?,?,?,?)',
                (value['successor_freeze_id'], proposal_id, command.idempotency_key, content, encode(value)))
            db.commit()
            return value

    def get(self, freeze_id):
        with self.ledger.connection() as db:
            row = db.execute('SELECT value FROM research_successor_freezes WHERE id=?', (freeze_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'SUCCESSOR_FREEZE_NOT_FOUND')
        frozen = json.loads(row[0])
        proposal = self.successors.get(frozen['proposal_id'])
        if (fingerprint({k:v for k,v in frozen.items() if k != 'successor_fingerprint'}) != frozen['successor_fingerprint'] or
                frozen['source_fingerprint'] != source_fingerprint() or proposal['policy_fingerprint'] != frozen['policy_fingerprint']):
            raise HTTPException(409, 'SUCCESSOR_FREEZE_BINDING_MISMATCH')
        return frozen

    def frames(self, freeze_id, db, frozen):
        frames = []
        for revision, command_hash, raw in db.execute(
                'SELECT revision,command_hash,value FROM research_successor_frames WHERE freeze_id=? ORDER BY revision', (freeze_id,)):
            value = json.loads(raw)
            if (revision != len(frames)+1 or value['command']['expected_revision'] != len(frames) or
                    fingerprint(value['command']) != value['input_fingerprint'] or command_hash != value['input_fingerprint']):
                raise HTTPException(409, 'SUCCESSOR_FRAME_INPUT_BINDING_MISMATCH')
            result = simulate(frozen, [f['command'] for f in frames] + [value['command']])
            if value['result'] != result or fingerprint(result) != value['result_fingerprint']:
                raise HTTPException(409, 'SUCCESSOR_FRAME_RESULT_BINDING_MISMATCH')
            frames.append(value)
        return frames

    def current(self, freeze_id):
        frozen = self.get(freeze_id)
        with self.ledger.connection() as db:
            frames = self.frames(freeze_id, db, frozen)
        return simulate(frozen, [f['command'] for f in frames])

    def advance(self, freeze_id, command):
        frozen = self.get(freeze_id)
        content = fingerprint(command.model_dump(exclude={'idempotency_key'}))
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            frames = self.frames(freeze_id, db, frozen)
            prior = db.execute('SELECT command_hash,value FROM research_successor_frames WHERE freeze_id=? AND key=?', (freeze_id, command.idempotency_key)).fetchone()
            if prior:
                if prior[0] != content:
                    raise HTTPException(409, 'SUCCESSOR_ADVANCE_IDEMPOTENCY_CONFLICT')
                return json.loads(prior[1])['result']
            if len(frames) != command.expected_revision:
                raise HTTPException(409, 'SUCCESSOR_SHADOW_REVISION_CONFLICT')
            commands = [f['command'] for f in frames] + [command.model_dump(exclude={'idempotency_key'})]
            result = simulate(frozen, commands)
            value = {'command': commands[-1], 'result': result, 'input_fingerprint': content, 'result_fingerprint': fingerprint(result)}
            db.execute('INSERT INTO research_successor_frames VALUES(?,?,?,?,?)',
                (freeze_id, len(frames)+1, command.idempotency_key, content, encode(value)))
            db.commit()
            return result

    def replay(self, freeze_id):
        current = self.current(freeze_id)
        frozen = self.get(freeze_id)
        with self.ledger.connection() as db:
            frames = self.frames(freeze_id, db, frozen)
        if frames and (frames[-1]['result'] != current or frames[-1]['result_fingerprint'] != fingerprint(current)):
            raise HTTPException(409, 'SUCCESSOR_SHADOW_REPLAY_MISMATCH')
        return {'matches_original': True, 'namespace': current['namespace'], 'system_usable': False,
            'validation_status': 'UNVALIDATED', 'validation_verdict': 'INCONCLUSIVE', 'network_calls': 0}
