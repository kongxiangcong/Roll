"""Literal cash-rights examples at the agreed narrow financial calculation seam."""
from datetime import date, timedelta

from roll.research.shadow import simulate


def record_close_case(record_index=20, blocked_exit=False):
    days = [(date(2026, 1, 1) + timedelta(days=i)).isoformat() for i in range(23)]
    rule = {'state': 'CONFIRMED_NORMAL', 'company_actions': 'CONFIRMED_NONE',
            'price_tick_yuan': '0.01', 'normal_price_limit_percent': '10'}
    rows = [{'trade_date': day, 'instrument': 'SSE:600362', 'open': '100', 'close': '100',
             'high': '101', 'low': '99', 'volume_shares': '10000', 'errors': [],
             'completion_state': 'COMPLETE_REPORTED_HISTORICAL', 'execution_evidence': rule}
            for day in days]
    if blocked_exit:
        rows[20]['execution_evidence'] = {**rule, 'state': 'UNKNOWN'}
    frozen = {'baseline': {'cash_yuan': '100000.00', 'positions': []},
              'scope': {'instruments': ['SSE:600362']}, 'rules': {'SSE:600362': rule},
              'fingerprints': {'model': 'METHOD_LITERAL'},
              'policy': {'quantity': '200', 'probability_threshold': '.60', 'maximum_gross_exposure': '.50'},
              'design': {'event': 'METHOD_CASH', 'costs': {'minimum_commission_yuan': '0',
                  'commission_scenario_rate': '0', 'transfer_each_side_rate': '0', 'stamp_sell_rate': '0',
                  'extra_regulatory_charge': '0', 'slippage_each_side_rate': '0'}}}
    inputs = {'facts': rows, 'sessions': days, 'statutory': {}, 'cash_events': [
        {'instrument': 'SSE:600362', 'record_date': days[record_index], 'ex_date': days[record_index + 1],
         'cash_payment_date': days[22], 'gross_cash_yuan_per_eligible_share': '1'}]}
    forecasts = [{'instrument': 'SSE:600362', 'forecast_id': 'one',
                  'observation_cutoff': days[0], 'probability': .8}]
    return frozen, inputs, forecasts, days


def test_record_close_sale_has_no_dividend_entitlement_or_tax():
    frozen, inputs, forecasts, days = record_close_case()
    result = simulate(frozen, inputs, forecasts, days[22])
    assert result['cash_yuan'] == result['nav_yuan'] == '100000.00'
    assert result['realized_gain_yuan'] == '0.00'
    assert result['entitlements'] == []
    assert [(event['kind'], event['cash_delta_yuan']) for event in result['events']] == [
        ('BUY_FILL', '-20000.00'), ('SELL_FILL', '20000.00')]


def test_blocked_record_close_exit_keeps_eligible_holding_until_actual_sale():
    frozen, inputs, forecasts, days = record_close_case(blocked_exit=True)
    record_close = simulate(frozen, inputs, forecasts, days[20])
    assert record_close['cash_yuan'] == '80000.00'
    assert record_close['nav_yuan'] == '100200.00'
    assert record_close['curve'][-1]['receivable_yuan'] == '200.00'
    assert len(record_close['positions']) == len(record_close['entitlements']) == 1
    assert not record_close['entitlements'][0]['paid']
    assert record_close['entitlements'][0]['tax'] is None
    paid = simulate(frozen, inputs, forecasts, days[22])
    assert paid['cash_yuan'] == paid['nav_yuan'] == '100160.00'
    assert paid['entitlements'][0]['tax'] == '40.00'
    assert paid['positions'] == []


def test_record_date_buy_qualifies_and_later_sale_keeps_unpaid_entitlement():
    frozen, inputs, forecasts, days = record_close_case(record_index=1)
    bought = simulate(frozen, inputs, forecasts, days[1])
    assert bought['cash_yuan'] == '80000.00'
    assert bought['nav_yuan'] == '100200.00'
    assert len(bought['entitlements']) == 1
    assert not bought['entitlements'][0]['paid'] and bought['entitlements'][0]['tax'] is None
    sold = simulate(frozen, inputs, forecasts, days[20])
    assert sold['cash_yuan'] == '99960.00'
    assert sold['nav_yuan'] == '100160.00'
    assert sold['curve'][-1]['receivable_yuan'] == '200.00'
    assert not sold['entitlements'][0]['paid'] and sold['entitlements'][0]['tax'] == '40.00'
    assert sold['positions'] == []
    assert not any(event['kind'] == 'CASH_DISTRIBUTION' for event in sold['events'])
    paid = simulate(frozen, inputs, forecasts, days[22])
    assert paid['cash_yuan'] == paid['nav_yuan'] == '100160.00'
    assert paid['curve'][-1]['receivable_yuan'] == '0.00'
    assert len([event for event in paid['events'] if event['kind'] == 'CASH_DISTRIBUTION']) == 1
