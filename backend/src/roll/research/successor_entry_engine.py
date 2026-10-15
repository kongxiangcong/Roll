"""Versioned METHOD entry-only extension; old fingerprinted engine stays intact.

Default branch is a source copy with exact-state parity checked on every saved
prefix. Alternate orders use the separately archived entry-stress-v1 contract.
"""
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException
from roll.research.execution import fees,money
from roll.research.policy_successors import calculate
from roll.research.successor_shadow import usable


def simulate(frozen, frames, scenario=None):
    scenario=scenario or {'delay':'NEXT_OPEN','fill_fraction':'1'}
    delay=scenario['delay'];fraction=Decimal(scenario['fill_fraction'])
    if delay not in {'NEXT_OPEN','NEXT_CLOSE','ONE_MORE_SESSION_OPEN','OUTSIDE_ALLOWED_PRICE_NO_FILL'} or fraction not in {Decimal('0'),Decimal('0.50'),Decimal('1')}:
        raise ValueError('UNREGISTERED_ENTRY_STRESS_SCENARIO')
    default=delay=='NEXT_OPEN' and fraction==1
    attempts=[]
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
            opening_exposure = sum((Decimal(bars[p['instrument']][point]) * p['quantity'] for p in lots), Decimal('0'))
            if opening_exposure + gross + expense > (cash + opening_exposure) * Decimal(frozen['policy']['maximum_gross_exposure']):
                return 'CLOSE_EXPOSURE_LIMIT_RECHECK_FAILED' if point=='close_yuan' else 'OPEN_EXPOSURE_LIMIT_RECHECK_FAILED'
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
        def attempt(order):
            entry=order['side']=='BUY' and not default
            point='close_yuan' if entry and delay=='NEXT_CLOSE' else 'open_yuan'
            quantity=order['quantity']
            reason='MISSED_NEXT_SESSION_NO_DISTANT_BAR_SUBSTITUTION' if not consecutive or order['expected_session']!=session or order.get('coverage_broken') else None
            if entry and not reason:
                increment=int(rules[order['instrument']]['buy_increment'])
                quantity=int(Decimal(quantity)*fraction//increment)*increment
                if delay=='OUTSIDE_ALLOWED_PRICE_NO_FILL':reason='OUTSIDE_FROZEN_PRICE_WINDOW'
                elif fraction==0:reason='DECLARED_MISSED_FILL'
                elif quantity<int(rules[order['instrument']]['buy_minimum']):reason='PARTIAL_BELOW_MINIMUM_LOT'
            if not reason:reason=execute(order['instrument'],quantity,order['side'],bars.get(order['instrument']),point,order['bounds'],session,order['order_id'])
            if reason:
                events.append({'kind':'NO_FILL','session':session,'order_id':order['order_id'],'reason':reason})
                gaps.append({'session':session,'instrument':order['instrument'],'reason':reason})
            if entry:attempts.append({'session':session,'order_id':order['order_id'],'point':point,'requested_quantity':order['quantity'],
                'filled_quantity':0 if reason else quantity,'released_remainder_quantity':order['quantity']-(0 if reason else quantity),
                'released_reservation_yuan':order['reserved_cash_yuan'],'reason':reason,'automatic_resubmit':False})
            pending.remove(order)

        close_entries=[]
        for order in list(pending):
            if not default and order['side']=='BUY' and not consecutive:order['coverage_broken']=True
            if order['expected_session']>session:continue
            if not default and order['side']=='BUY' and delay=='NEXT_CLOSE':close_entries.append(order)
            else:attempt(order)
        # Original migration horizons remain separate lot-level CLOSE schedules.
        for lot in list(lots):
            if lot['exit_session'] <= session:
                reason = execute(lot['instrument'], lot['quantity'], 'SELL', bars.get(lot['instrument']),
                    'close_yuan', None, session, 'HORIZON:'+lot['lot_id'], target_lot_id=lot['lot_id'])
                if reason:
                    gaps.append({'session': session, 'instrument': lot['instrument'], 'reason': reason,
                        'original_exit_session': lot['exit_session']})
        for order in close_entries:attempt(order)
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
        inputs = {'completed_session': session, 'cash_yuan': money(cash), 'reserved_yuan': money(sum((Decimal(o['reserved_cash_yuan']) for o in pending if o['side']=='BUY'),Decimal(0))) if not default else '0.00',
            'nav_yuan': money(cash+exposure), 'current_exposure_yuan': money(exposure),
            'positions': aggregate, 'opportunities': opportunities, 'history': history}
        result = calculate({'policy': frozen['policy']}, inputs, migrations)
        for action in result['actions']:
            if not default and action['action'] in {'BUY','ADD'} and any(o['side']=='BUY' and o['instrument']==action['instrument'] for o in pending):
                action.update(action='REFUSE',quantity=0,target_quantity=action['current_quantity'],reserved_cash_yuan='0.00')
                action['reasons'].append('WAIT_FOR_REGISTERED_PENDING_ENTRY_ATTEMPT')
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
                    'expected_session': session+(2 if not default and action['action'] in {'BUY','ADD'} and delay=='ONE_MORE_SESSION_OPEN' else 1), 'bounds': [money(lower), money(upper)],
                    'reserved_cash_yuan': action['reserved_cash_yuan']})
        evaluations.append({'session': session, 'source_snapshot_id': frame['source_snapshot_id'], 'actions': result['actions']})
        last_session = session
    reserved = sum((Decimal(p['reserved_cash_yuan']) for p in pending), Decimal('0'))
    output={'cash_yuan': money(cash), 'reserved_cash_yuan': money(reserved), 'positions': lots,
        'pending': pending, 'events': events, 'evaluations': evaluations, 'gaps': gaps,
        'last_session': last_session, 'revision': len(frames), 'namespace': 'SUCCESSOR_METHOD_SHADOW',
        'system_usable': False, 'capability': 'NOT_GRANTED', 'validation_status': 'UNVALIDATED',
        'validation_verdict': 'INCONCLUSIVE', 'real_forward_started_at': None}
    if not default:output['entry_stress_trace']=attempts
    return output
