"""Descriptive statistics for locally reconstructed return and probability series."""
import math
import random
from statistics import fmean


def rounded(value):
    return round(value, 15) if value is not None else None


def paired_block_interval(date_scores, block_sessions=20, replicates=2000, seed=1701, conditional=False):
    """Resample consecutive calendar-date groups jointly, keeping same-day names together.

    Caller supplies one aligned score per security/date, including missing sessions.
    Conditional subsets use empty scores for observed nonmembership, not None.
    Member score sums/counts are jointly resampled without compressing calendar time.
    Each endpoint is one-sided 95%; together they form a central 90% range.
    """
    if block_sessions not in (20, 40) or replicates != 2000 or seed != 1701:
        raise ValueError('UNREGISTERED_RESAMPLING_CONFIGURATION')
    dates = [row['date'] for row in date_scores]
    if dates != sorted(set(dates)):
        raise ValueError('CALENDAR_SCORES_MUST_BE_UNIQUE_AND_ORDERED')
    result = {'calendar_sessions': len(dates), 'block_sessions': block_sessions,
              'effective_block_upper_bound': len(dates)//block_sessions,
              'replicates': replicates, 'seed': seed, 'lower_95': None, 'upper_95': None,
              'interval_kind': 'ONE_SIDED_95_ENDPOINTS_CENTRAL_90_RANGE',
              'assumptions_verified': False, 'statistical_pass': False}
    values = []
    for row in date_scores:
        scores = row['scores']
        if (not scores and not conditional) or any(v is None for v in scores.values()):
            return {**result, 'status': 'INCOMPLETE_ALIGNED_CALENDAR_SCORES'}
        group = [float(v) for v in scores.values()]
        if any(not math.isfinite(v) for v in group):
            raise ValueError('NONFINITE_PAIRED_SCORE')
        values.append((sum(group),len(group)) if conditional else fmean(group))
    if conditional:
        member_days=sum(count>0 for _,count in values)
        result.update(member_calendar_sessions=member_days, member_count=sum(count for _,count in values),
            calendar_effective_block_upper_bound=len(dates)//block_sessions,
            effective_block_upper_bound=member_days//block_sessions,
            estimand='CONDITIONAL_MEMBER_SCORE_SUM_OVER_MEMBER_COUNT')
        if not result['member_count']:
            return {**result, 'status':'INSUFFICIENT_MEMBER_SUPPORT'}
    if len(values) < block_sessions:
        return {**result, 'status': 'INSUFFICIENT_CALENDAR_SUPPORT'}
    rng = random.Random(seed)
    estimates = []
    for _ in range(replicates):
        sampled = []
        while len(sampled) < len(values):
            start = rng.randrange(len(values)-block_sessions+1)
            sampled.extend(values[start:start+block_sessions])
        if conditional:
            selected=sampled[:len(values)];count=sum(count for _,count in selected)
            if not count:
                return {**result,'status':'INSUFFICIENT_RESAMPLED_MEMBER_SUPPORT'}
            estimates.append(sum(total for total,_ in selected)/count)
        else:
            estimates.append(fmean(sampled[:len(values)]))
    estimates.sort()
    estimate=sum(total for total,_ in values)/result['member_count'] if conditional else fmean(values)
    return {**result, 'status': 'CONDITIONAL_NUMERICAL_INTERVAL', 'mean': rounded(estimate),
            'lower_95': rounded(estimates[math.floor(.05*(replicates-1))]),
            'upper_95': rounded(estimates[math.ceil(.95*(replicates-1))])}


def continuous_summary(curve):
    """NAV-only return/drawdown from one constrained cash/inventory trajectory."""
    if not curve or any(row.get('nav_yuan') is None for row in curve):
        return {'status': 'VALUATION_INCOMPLETE', 'net_return': None, 'maximum_drawdown': None}
    values = [float(row['nav_yuan']) for row in curve]
    if any(not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError('NONPOSITIVE_OR_NONFINITE_CONTINUOUS_NAV')
    peak = values[0]; maximum = 0
    for value in values:
        peak = max(peak, value); maximum = max(maximum, 1-value/peak)
    return {'status': 'DESCRIPTIVE_CONTINUOUS_NAV', 'net_return': rounded(values[-1]/values[0]-1),
            'maximum_drawdown': rounded(maximum), 'statistical_pass': False}


def brier(predictions):
    losses = [(p - outcome) ** 2 for p, outcome in predictions if p is not None and outcome is not None]
    return fmean(losses) if losses else None
