"""Literal dependent subset arithmetic, separate from confirmation validity."""
from datetime import date, timedelta
import pytest

from roll.research.validation import probability_checks
from roll.research.statistics import paired_block_interval


def probability_case(count=1200):
    days = [(date(2020, 1, 1) + timedelta(days=i)).isoformat() for i in range(count)]
    forecasts = [{'forecast_id': str(i), 'instrument': 'METHOD:A', 'observation_cutoff': day,
                  'probability': .2 if i % 2 == 0 else .8} for i, day in enumerate(days)]
    outcomes = {str(i): {'label': i % 2, 'scoreable': True, 'maturity_date': days[-1]}
                for i in range(count)}
    frozen = {'design': {'event': 'METHOD_BINARY', 'statistics': {'minimum_effective_time_blocks': 30}},
              'policy': {'probability_threshold': '.60'}}
    original = {'model': {'model_run_id': 'METHOD_LITERAL'}, 'model_artifact': {'base_rate': .5},
                'replay': {'forecasts': forecasts, 'through_date': days[-1],
                           'inputs': {'sessions': days, 'counterfactuals': outcomes}}}
    return frozen, original


def test_observed_nonmembers_retain_calendar_and_have_conditional_intervals():
    frozen, original = probability_case()
    result = probability_checks(frozen, original)
    assert result['unobserved_checkpoint_sessions'] == 0
    assert result['selected_mature'] == 600
    for interval in result['selected_dependent_loss_intervals']:
        assert interval['status'] == 'CONDITIONAL_NUMERICAL_INTERVAL'
        assert interval['calendar_sessions'] == 1200
        assert interval['member_calendar_sessions'] == 600
        assert interval['effective_block_upper_bound'] == (30 if interval['block_sessions'] == 20 else 15)
        assert interval['mean'] == interval['lower_95'] == interval['upper_95'] == .21
    for bin_result, error in zip(result['reliability_bins'], [.2, -.2]):
        assert bin_result['count'] == 600
        for interval in bin_result['dependent_probability_error_intervals']:
            assert interval['status'] == 'CONDITIONAL_NUMERICAL_INTERVAL'
            assert interval['calendar_sessions'] == 1200
            assert interval['mean'] == interval['lower_95'] == interval['upper_95'] == error
    assert result['statistical_pass'] is False
    assert result['independent_calibration_test'] is False


def test_unequal_same_day_members_use_joint_score_sum_and_member_count():
    scores = [{'date':f'{i:04}', 'scores':({'A':.1} if i%3==0 else {'A':.4,'B':.4} if i%3==1 else {})} for i in range(120)]
    for block in [20,40]:
        result = paired_block_interval(scores,block_sessions=block,conditional=True)
        assert result['status'] == 'CONDITIONAL_NUMERICAL_INTERVAL'
        assert result['calendar_sessions'] == 120
        assert result['member_calendar_sessions'] == 80
        assert result['member_count'] == 120
        assert result['mean'] == .3
        assert result['lower_95'] < .3 < result['upper_95']
        assert paired_block_interval(scores,block_sessions=block,conditional=True) == result
        assert result['assumptions_verified'] is result['statistical_pass'] is False


def test_empty_subset_and_zero_resample_denominator_remain_insufficient():
    scores = [{'date':f'{i:04}', 'scores':{}} for i in range(80)]
    empty = paired_block_interval(scores,conditional=True)
    assert empty['status'] == 'INSUFFICIENT_MEMBER_SUPPORT'
    assert empty['effective_block_upper_bound'] == 0 and empty['lower_95'] is None
    scores[0]['scores'] = {'A':.2}
    sparse = paired_block_interval(scores,conditional=True)
    assert sparse['status'] == 'INSUFFICIENT_RESAMPLED_MEMBER_SUPPORT'
    assert sparse['effective_block_upper_bound'] == 0
    assert sparse['lower_95'] is sparse['upper_95'] is None


@pytest.mark.parametrize('missing',['checkpoint','unknown_label','unmatured','unknown_same_day_member'])
def test_genuinely_unavailable_evidence_remains_missing_for_all_subsets(missing):
    frozen, original = probability_case(80)
    replay=original['replay']
    if missing == 'checkpoint':
        replay['forecasts'].pop(20)
    elif missing == 'unknown_same_day_member':
        replay['forecasts'].append({**replay['forecasts'][20], 'forecast_id':'unknown-other', 'instrument':'METHOD:B'})
    elif missing == 'unknown_label':
        replay['inputs']['counterfactuals']['20']['label'] = None
    else:
        replay['inputs']['counterfactuals']['20']['maturity_date'] = '2099-01-01'
    result = probability_checks(frozen, original)
    assert result['unobserved_checkpoint_sessions'] == 1
    for intervals in [result['dependent_brier_improvement_intervals'],result['selected_dependent_loss_intervals'],
                      *[b['dependent_probability_error_intervals'] for b in result['reliability_bins']]]:
        assert all(r['status']=='INCOMPLETE_ALIGNED_CALENDAR_SCORES' and r['lower_95'] is None for r in intervals)


def test_repeated_forecast_events_do_not_add_subset_support():
    frozen, original = probability_case(80)
    original['replay']['forecasts'].append(dict(original['replay']['forecasts'][1]))
    result = probability_checks(frozen, original)
    assert result['duplicate_event_count'] == 1
    assert result['selected_mature'] == 40
    assert all(i['member_count']==i['member_calendar_sessions']==40 for i in result['selected_dependent_loss_intervals'])
