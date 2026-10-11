"""Literal comparator trajectories at the agreed financial calculation seam."""
from datetime import date, timedelta
from decimal import Decimal
import pytest

from roll.research.shadow import simulate
from roll.research.validation import continuous_checks
from test_shadow_record_close import record_close_case


def comparator_case(prices):
    frozen, inputs, _, _ = record_close_case()
    first = date(2026, 1, 1)
    days = [(first + timedelta(days=i)).isoformat() for i in range(len(prices))]
    example = inputs['facts'][0]
    inputs['facts'] = [{**example, 'trade_date': day, 'open': str(price), 'close': str(price),
                        'high': str(price + Decimal('1')), 'low': str(price - Decimal('1'))}
                       for day, price in zip(days, prices)]
    inputs['sessions'] = days[20:]
    inputs['cash_events'] = []
    return frozen, inputs, days


def test_already_above_ma_without_an_upcross_never_enters_or_reenters():
    # 20 known preceding observations, then 65 observed slots. Both prior/current
    # MA5 stay above MA20; there is no crossing inside the observed window.
    frozen, inputs, days = comparator_case([Decimal('100') + Decimal('.1') * i for i in range(85)])
    result = simulate(frozen, inputs, [], days[-1], 'MA5_MA20')
    assert result['events'] == []
    assert result['opportunities'] == []
    assert result['cash_yuan'] == result['nav_yuan'] == '100000.00'
    assert result['positions'] == []


def test_equality_to_positive_cross_enters_once_and_keeps_frozen_20_session_exit():
    frozen, inputs, days = comparator_case([Decimal('100')] * 20 + [Decimal('100') + Decimal('.1') * (i+1) for i in range(65)])
    result = simulate(frozen, inputs, [], days[-1], 'MA5_MA20')
    assert [(e['kind'], e['date'], e['quantity'], e['price_yuan']) for e in result['events']] == [
        ('BUY_FILL', '2026-01-22', '200', '100.20'),
        ('SELL_FILL', '2026-02-10', '200', '102.10')]
    assert len(result['opportunities']) == 1
    assert result['cash_yuan'] == result['nav_yuan'] == '100380.00'
    assert result['positions'] == []


@pytest.mark.parametrize('bad_history', ['absent', 'unknown', 'unfinished'])
def test_missing_or_unusable_crossing_history_never_manufactures_an_entry(bad_history):
    frozen, inputs, days = comparator_case([Decimal('100')] * 20 + [Decimal('100') + Decimal('.1') * (i+1) for i in range(65)])
    if bad_history == 'absent':
        inputs['facts'].pop(20)
    elif bad_history == 'unknown':
        inputs['facts'][20]['execution_evidence'] = {**inputs['facts'][20]['execution_evidence'], 'state': 'UNKNOWN'}
    else:
        inputs['facts'][20]['completion_state'] = 'UNFINISHED'
    result = simulate(frozen, inputs, [], days[-1], 'MA5_MA20')
    assert result['events'] == []
    assert result['opportunities'] == []
    assert result['nav_yuan'] == '100000.00'


def test_comparison_reports_measured_exposure_and_occupied_time_differences():
    frozen, inputs, days = comparator_case([Decimal('100')] * 85)
    frozen['policy']['exit'] = 'HORIZON_SESSION20_CLOSE'
    frozen['design'].update(primary_objective={'risk_constraints': {
        'maximum_drawdown': '.10', 'maximum_simulated_gross_exposure': '.50',
        'minimum_decision_coverage': '.20', 'candidate_drawdown_excess_over_risk_matched_baseline': '.02'},
        'minimum_improvement_nav_return': '.0025'}, statistics={'minimum_effective_time_blocks': 30})
    candidate = simulate(frozen, inputs, [], days[-1])
    reference = simulate(frozen, inputs, [], days[-1], 'START_HOLD')
    result = continuous_checks(frozen, candidate, {'START_HOLD': reference})
    baseline = result['comparisons']['START_HOLD']['baseline_exposure']
    assert baseline['maximum_gross_exposure'] == .2
    assert baseline['average_gross_exposure'] == pytest.approx(.19692307692307692)
    assert baseline['occupied_session_fraction'] == pytest.approx(.9846153846153847)
    difference = result['comparisons']['START_HOLD']['position_difference']
    assert difference['average_gross_exposure'] == pytest.approx(-.19692307692307692)
    assert difference['maximum_gross_exposure'] == -.2
    assert difference['occupied_session_fraction'] == pytest.approx(-.9846153846153847)
    assert result['comparisons']['START_HOLD']['risk_matching'] == 'COMMON_CONSTRAINTS_DO_NOT_ESTABLISH_REALIZED_RISK_MATCHING'
