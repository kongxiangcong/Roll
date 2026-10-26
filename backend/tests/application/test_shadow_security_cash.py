"""Literal and differential multi-security examples, independent of fitted returns."""
from copy import deepcopy
import pytest
from roll.research.shadow import simulate
from test_shadow_record_close import record_close_case


@pytest.mark.parametrize('ex_index', [1, 20])
def test_other_security_distribution_does_not_change_entry_or_exit(ex_index):
    frozen, inputs, forecasts, days = record_close_case()
    inputs['cash_events'] = []
    expected = simulate(frozen, inputs, forecasts, days[-1])
    changed = deepcopy(inputs)
    changed['cash_events'] = [{'instrument': 'SSE:600519', 'ex_date': days[ex_index],
        'record_date': days[ex_index-1], 'cash_payment_date': days[-1],
        'gross_cash_yuan_per_eligible_share': '50'}]
    assert simulate(frozen, changed, forecasts, days[-1]) == expected
    assert expected['cash_yuan'] == '100000.00'
    assert [e['kind'] for e in expected['events']] == ['BUY_FILL', 'SELL_FILL']


def test_own_ex_dividend_entry_band_is_hand_calculated():
    frozen, inputs, forecasts, days = record_close_case(record_index=0)
    inputs['cash_events'][0]['gross_cash_yuan_per_eligible_share'] = '10'
    inputs['facts'][1].update(open='90', close='90', high='91', low='89')
    result = simulate(frozen, inputs, forecasts, days[1])
    order = result['opportunities'][0]
    assert (order['lower_yuan'], order['upper_yuan']) == ('81.00', '99.00')
    assert order['required_cash_yuan'] == '19800.00'
    assert result['cash_yuan'] == '82000.00'
    assert result['nav_yuan'] == '100000.00'
    assert not result['entitlements']  # Acquired after record close.


def test_legacy_missing_symbol_is_only_accepted_for_single_name():
    frozen, inputs, forecasts, days = record_close_case(record_index=1)
    expected = simulate(frozen, inputs, forecasts, days[-1])
    del inputs['cash_events'][0]['instrument']
    assert simulate(frozen, inputs, forecasts, days[-1]) == expected
    frozen['scope']['instruments'].append('SSE:600519')
    with pytest.raises(ValueError, match='AMBIGUOUS_CASH_EVENT_INSTRUMENT'):
        simulate(frozen, inputs, forecasts, days[-1])
