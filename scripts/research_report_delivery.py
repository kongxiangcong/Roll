"""Deliver an existing, newly frozen CAL experiment through Roll's public API.

Never fit, change a freeze, read SEALED, or reset a continuous account. Run once
per new freeze. An interrupted report render can be retried with --render-only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import httpx


def checked(response):
    response.raise_for_status()
    return response.json()


def deliver(client, freeze_id, *, render_only=False):
    frozen = checked(client.get('/api/research/complete-freezes/' + freeze_id))
    model = checked(client.get('/api/research/models/' + frozen['model_run_id']))
    # Fetch content-addressed original input before creating any forecast.
    response = client.get('/api/data/archives/' + model['input_archive']['sha256'])
    response.raise_for_status()
    if hashlib.sha256(response.content).hexdigest() != model['input_archive']['sha256']:
        raise ValueError('MODEL_INPUT_ARCHIVE_HASH_MISMATCH')
    original = response.json()
    part = original['parts']['CALIBRATION']
    window = frozen['design']['windows']['CALIBRATION']
    days = sorted({r['trade_date'] for r in part['facts']
                   if window['first_date'] <= r['trade_date'] <= window['last_date']})
    if not days or len(days) > 1000:
        raise ValueError('CAL_REPORT_WINDOW_REQUIRES_1_TO_1000_OBSERVATIONS')
    path = '/api/research/shadow/' + freeze_id
    state = checked(client.get(path))
    exclusions, forecasts = [], []
    if not render_only:
        if state['revision']:
            raise ValueError('NEW_FREEZE_REQUIRED; use --render-only for saved state')
        for day in days:
            response = client.post('/api/research/models/' + model['model_run_id'] + '/forecasts',
                json={'observation_date': day, 'basis': 'Stage 5 complete CAL descriptive report; no independent test'})
            reason = response.json().get('detail') if response.status_code == 409 else None
            if isinstance(reason, str) and reason in {'FEATURE_LOOKBACK_INSUFFICIENT', 'OBSERVATION_DAY_MISSING',
                          'FEATURE_INPUT_NOT_COMPLETE_RAW_SHARE', 'FEATURE_NONPOSITIVE_OR_UNKNOWN'}:
                exclusions.append({'date': day, 'reason': reason})
            else:
                forecasts.append(checked(response)['forecast_id'])
        if not forecasts:
            raise ValueError('NO_SUPPORTED_FROZEN_FORECASTS; no ledger advanced')
        state = checked(client.post(path + '/advance', json={'through_date': days[-1],
            'forecast_ids': forecasts, 'expected_revision': 0}))
    replay = checked(client.post(path + '/replay'))
    if not replay['matches_original']:
        raise ValueError('SAVED_CONTINUOUS_REPLAY_MISMATCH')
    # Source, ledger and plots are immutable server-side artifacts, not stdout claims.
    report = checked(client.post('/api/research/reports/' + freeze_id + '/performance', json={
        'expected_shadow_revision': state['revision'],
        'idempotency_key': 'stage5-revision-' + str(state['revision']),
        'basis': 'Descriptive saved CAL continuous ledger; independent validity unproven'}))
    return {'freeze_id': freeze_id, 'evidence_kind': frozen['evidence_kind'],
        'forecast_count_created': len(forecasts), 'excluded_feature_dates': exclusions,
        'render_only': render_only, 'revision': state['revision'], 'replay': replay,
        'performance_report': report, 'capability': 'NOT_GRANTED',
        'interpretation': 'CAL_DESCRIPTIVE_ONLY_NOT_INDEPENDENT_VALIDATION'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8010')
    parser.add_argument('--freeze-id', required=True)
    parser.add_argument('--render-only', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with httpx.Client(base_url=args.url, timeout=120, trust_env=False) as client:
        result = deliver(client, args.freeze_id, render_only=args.render_only)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
