"""Frozen numerical methods; arithmetic verification never establishes real validity.

The moving-block construction follows Kunsch (1989), doi:10.1214/aos/1176347265.
Finite samples cannot establish its stationarity/weak-dependence assumptions.
"""
import hashlib
import math
import random
from pathlib import Path
from statistics import fmean
from roll.accounts.ledger import encode


def fingerprint():
    return hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def rounded(value):
    return round(value, 15) if value is not None else None


def paired_block_interval(date_scores, block_sessions=20, replicates=2000, seed=1701):
    """Resample consecutive calendar-date groups jointly, keeping same-day names together.

    Caller supplies one aligned score per security/date, including missing sessions.
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
        if not scores or any(v is None for v in scores.values()):
            return {**result, 'status': 'INCOMPLETE_ALIGNED_CALENDAR_SCORES'}
        group = [float(v) for v in scores.values()]
        if any(not math.isfinite(v) for v in group):
            raise ValueError('NONFINITE_PAIRED_SCORE')
        values.append(fmean(group))
    if len(values) < block_sessions:
        return {**result, 'status': 'INSUFFICIENT_CALENDAR_SUPPORT'}
    rng = random.Random(seed)
    estimates = []
    for _ in range(replicates):
        sampled = []
        while len(sampled) < len(values):
            start = rng.randrange(len(values)-block_sessions+1)
            sampled.extend(values[start:start+block_sessions])
        estimates.append(fmean(sampled[:len(values)]))
    estimates.sort()
    return {**result, 'status': 'CONDITIONAL_NUMERICAL_INTERVAL', 'mean': rounded(fmean(values)),
            'lower_95': rounded(estimates[math.floor(.05*(replicates-1))]),
            'upper_95': rounded(estimates[math.ceil(.95*(replicates-1))])}


def probability_summary(records, sessions, threshold=.60):
    """Descriptive mature losses/support, deduplicated by logical forecast event.

    AUC, occupied-bin counts and raw date/block upper bounds are not qualifications.
    Input admission/maturity evidence and dependent uncertainty belong to validation.
    """
    if sessions != sorted(set(sessions)):
        raise ValueError('CALENDAR_SESSIONS_MUST_BE_UNIQUE_AND_ORDERED')
    unique = {}
    immature = duplicates = clipped = 0
    for record in records:
        if not record.get('mature') or record.get('label') not in (0, 1):
            immature += 1
            continue
        key = record.get('canonical_key') or encode([record['instrument'], record['observation_date'],
                                                   record.get('event'), record.get('horizon_sessions', 20)])
        p = float(record['probability']); base = float(record['baseline_probability'])
        if not all(math.isfinite(v) and 0 <= v <= 1 for v in (p, base)):
            raise ValueError('INVALID_PROBABILITY')
        item = {**record, 'probability': p, 'baseline_probability': base}
        if key in unique:
            if any(unique[key][k] != item[k] for k in ('probability', 'baseline_probability', 'label')):
                raise ValueError('CONFLICTING_DUPLICATE_FORECAST_EVENT')
            duplicates += 1
        else:
            unique[key] = item
    rows = list(unique.values())
    dates = sorted({r['observation_date'] for r in rows})
    if any(day not in sessions for day in dates):
        raise ValueError('OBSERVATION_OUTSIDE_DECLARED_CALENDAR')
    bins = []
    for index in range(5):
        group = [r for r in rows if min(4, int(r['probability']*5)) == index]
        if group:
            bins.append({'bin': index, 'count': len(group),
                         'mean_probability': rounded(fmean(r['probability'] for r in group)),
                         'observed_frequency': rounded(fmean(r['label'] for r in group)),
                         'support_at_least20': len(group) >= 20})
    positive = [r['probability'] for r in rows if r['label'] == 1]
    negative = [r['probability'] for r in rows if r['label'] == 0]
    auc = sum(1 if p > n else .5 if p == n else 0 for p in positive for n in negative)/(len(positive)*len(negative)) if positive and negative else None
    losses = []; baseline_losses = []; selected = [r for r in rows if r['probability'] >= threshold]
    for r in rows:
        p = max(1e-15, min(1-1e-15, r['probability']))
        base = max(1e-15, min(1-1e-15, r['baseline_probability']))
        clipped += p != r['probability']
        y = r['label']
        losses.append(-(y*math.log(p)+(1-y)*math.log1p(-p)))
        baseline_losses.append(-(y*math.log(base)+(1-y)*math.log1p(-base)))
    return {'mature_unique': len(rows), 'excluded_unmatured_or_unknown': immature,
            'duplicate_event_count': duplicates, 'unique_observation_dates': len(dates),
            'effective_time_block_upper_bound': len(dates)//20,
            'brier': rounded(fmean((r['probability']-r['label'])**2 for r in rows)) if rows else None,
            'baseline_brier': rounded(fmean((r['baseline_probability']-r['label'])**2 for r in rows)) if rows else None,
            'log_loss': rounded(fmean(losses)) if rows else None,
            'baseline_log_loss': rounded(fmean(baseline_losses)) if rows else None,
            'log_probability_clip_epsilon': '1e-15', 'clipped_prediction_count': clipped,
            'auc': rounded(auc), 'reliability_bins': bins, 'selected_mature': len(selected),
            'selected_brier': rounded(fmean((r['probability']-r['label'])**2 for r in selected)) if selected else None,
            'statistical_pass': False, 'uncertainty': 'DESCRIPTIVE_ONLY_DEPENDENT_CONFIRMATION_REQUIRED'}


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


def method_manifest(design):
    """Persist executable arithmetic checks before inspecting confirmation outcomes."""
    statistics = design['statistics']
    if statistics['dependency_sensitivity_block_sessions'] != [20, 40] or statistics['pass_look_count'] != 1:
        raise ValueError('STATISTICAL_METHOD_NOT_SUPPORTED_BY_FROZEN_IMPLEMENTATION')
    dates = [f'{i:04}' for i in range(80)]
    constant = paired_block_interval([{'date': day, 'scores': {'A': .005, 'B': .005}} for day in dates])
    crossing = paired_block_interval([{'date': day, 'scores': {'A': .02 if i < 40 else -.02}} for i, day in enumerate(dates)])
    records = [{'canonical_key': str(i), 'instrument': 'A', 'observation_date': day,
                'probability': .2 if i < 20 else .8, 'baseline_probability': .5,
                'label': 0 if i < 20 else 1, 'mature': True} for i, day in enumerate(dates[:40])]
    losses = probability_summary([*records, records[0]], dates)
    constant40 = paired_block_interval([{'date': day, 'scores': {'A': .005}} for day in dates], block_sessions=40)
    nav = continuous_summary([{'nav_yuan': '100'}, {'nav_yuan': '90'}, {'nav_yuan': '110'}])
    missing = continuous_summary([{'nav_yuan': '100'}, {'nav_yuan': None}])
    checks = (constant['lower_95'] == .005 and constant40['lower_95'] == .005
              and losses['brier'] == .04 and losses['auc'] == 1 and losses['duplicate_event_count'] == 1
              and crossing['lower_95'] < 0 < crossing['upper_95']
              and nav['net_return'] == .1 and nav['maximum_drawdown'] == .1
              and missing['net_return'] is None)
    if not checks:
        raise ValueError('STATISTICAL_ARITHMETIC_METHOD_CHECK_FAILED')
    return {'version': '20-statistical-method-v1', 'code_fingerprint': fingerprint(),
            'algorithm_checks_passed': True, 'configuration': statistics,
            'worked_examples': {'constant_paired_improvement': constant, 'constant40_sensitivity': constant40,
                                'known_binary_losses': losses, 'boundary_crossing': crossing,
                                'continuous_nav': nav, 'missing_valuation': missing},
            'real_sampling_assumptions_verified': False, 'confers_statistical_pass': False,
            'limitations': ['Real stationarity, weak dependence and finite-sample coverage require independent evidence and review.',
                           'Date-block support is an upper bound; same-day names and repeated forecasts are not independent samples.',
                           'Calibration-fit data cannot establish independent calibration validity.'],
            'reference': 'https://doi.org/10.1214/aos/1176347265'}
