"""One-time authoring copy; runtime does not rewrite or exec old source."""
from pathlib import Path
root=Path(__file__).resolve().parents[4];folder=root/'backend/src/roll/research'
source=(folder/'successor_shadow.py').read_text(encoding='utf-8')
body='def simulate('+source.split('def simulate(',1)[1].split('\n\n\nclass SuccessorShadow:',1)[0]
def replace(old,new):
    global body
    assert body.count(old)==1,old
    body=body.replace(old,new)
replace('def simulate(frozen, frames):', '''def simulate(frozen, frames, scenario=None):
    scenario=scenario or {'delay':'NEXT_OPEN','fill_fraction':'1'}
    delay=scenario['delay'];fraction=Decimal(scenario['fill_fraction'])
    if delay not in {'NEXT_OPEN','NEXT_CLOSE','ONE_MORE_SESSION_OPEN','OUTSIDE_ALLOWED_PRICE_NO_FILL'} or fraction not in {Decimal('0'),Decimal('0.50'),Decimal('1')}:
        raise ValueError('UNREGISTERED_ENTRY_STRESS_SCENARIO')
    default=delay=='NEXT_OPEN' and fraction==1
    attempts=[]''')
replace("Decimal(bars[p['instrument']]['open_yuan'])", "Decimal(bars[p['instrument']][point])")
replace("return 'OPEN_EXPOSURE_LIMIT_RECHECK_FAILED'", "return 'CLOSE_EXPOSURE_LIMIT_RECHECK_FAILED' if point=='close_yuan' else 'OPEN_EXPOSURE_LIMIT_RECHECK_FAILED'")
old='''        for order in list(pending):
            if order['expected_session'] > session:
                continue
            reason = 'MISSED_NEXT_SESSION_NO_DISTANT_BAR_SUBSTITUTION' if not consecutive or order['expected_session'] != session else execute(
                order['instrument'], order['quantity'], order['side'], bars.get(order['instrument']),
                'open_yuan', order['bounds'], session, order['order_id'])
            if reason:
                events.append({'kind': 'NO_FILL', 'session': session, 'order_id': order['order_id'], 'reason': reason})
                gaps.append({'session': session, 'instrument': order['instrument'], 'reason': reason})
            pending.remove(order)'''
new='''        def attempt(order):
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
            else:attempt(order)'''
replace(old,new)
replace("        exposure = Decimal('0')", "        for order in close_entries:attempt(order)\n        exposure = Decimal('0')")
replace("'cash_yuan': money(cash), 'reserved_yuan': '0.00',", "'cash_yuan': money(cash), 'reserved_yuan': money(sum((Decimal(o['reserved_cash_yuan']) for o in pending if o['side']=='BUY'),Decimal(0))) if not default else '0.00',")
replace("        for action in result['actions']:", """        for action in result['actions']:
            if not default and action['action'] in {'BUY','ADD'} and any(o['side']=='BUY' and o['instrument']==action['instrument'] for o in pending):
                action.update(action='REFUSE',quantity=0,target_quantity=action['current_quantity'],reserved_cash_yuan='0.00')
                action['reasons'].append('WAIT_FOR_REGISTERED_PENDING_ENTRY_ATTEMPT')""")
replace("'expected_session': session+1,", "'expected_session': session+(2 if not default and action['action'] in {'BUY','ADD'} and delay=='ONE_MORE_SESSION_OPEN' else 1),")
replace("    return {'cash_yuan': money(cash)", "    output={'cash_yuan': money(cash)")
body+="\n    if not default:output['entry_stress_trace']=attempts\n    return output\n"
header='''"""Versioned METHOD entry-only extension; old fingerprinted engine stays intact.

Default branch is a source copy with exact-state parity checked on every saved
prefix. Alternate orders use the separately archived entry-stress-v1 contract.
"""
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException
from roll.research.execution import fees,money
from roll.research.policy_successors import calculate
from roll.research.successor_shadow import usable


'''
(folder/'successor_entry_engine.py').write_text(header+body,encoding='utf-8',newline='\n')
