"""Read the running deployment's actual forward prerequisites. Never starts a clock."""
import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx


def inspect_deployment(client):
    checked = datetime.now(timezone.utc)
    result = {'checked_at': checked.isoformat(), 'mode': 'READ_ONLY_DEPLOYMENT_PREFLIGHT',
              'network_source_calls': 0, 'state_mutations': 0, 'capability': 'NOT_GRANTED',
              'protocols': [], 'collections': [], 'blockers': []}
    result['health'] = client.get('/api/health').raise_for_status().json()
    worker = client.get('/api/reviews/health').raise_for_status().json()
    result['worker_state'] = worker.get('worker_state')
    result['backup_status'] = client.get('/api/runtime/backups/status').raise_for_status().json()
    protocols = client.get('/api/research/protocols').raise_for_status().json()
    for protocol in protocols:
        pid = protocol['protocol_id']; base = '/api/research/protocols/' + pid
        models = client.get(base + '/models').raise_for_status().json()
        freezes = client.get(base + '/complete-freezes').raise_for_status().json()
        item = {'protocol_id': pid, 'models': [{'model_run_id': m.get('model_run_id'),
                    'model_freeze_status': m.get('model_freeze_status'), 'calibrator_fit_status': m.get('calibrator_fit_status'),
                    'status': m.get('status'),
                    'evidence_kind': m.get('evidence_kind'), 'data_use': m.get('data_use')} for m in models],
                'complete_freezes': [], 'forward_started_at': protocol.get('forward_started_at')}
        if not freezes: result['blockers'].append('COMPLETE_EXPERIMENT_FREEZE_MISSING:' + pid)
        if not any(m.get('model_freeze_status') == 'FROZEN' for m in models):
            result['blockers'].append('FROZEN_MODEL_MISSING_IN_THIS_DEPLOYMENT:' + pid)
        for frozen in freezes:
            fid = frozen['freeze_id']; path = '/api/research/complete-freezes/' + fid
            validations = client.get(path + '/validations').raise_for_status().json()
            state = client.get(path + '/forward')
            if state.status_code == 404:
                forward = {'status': 'NOT_REGISTERED', 'forward_started_at': None}
            else:
                full = state.raise_for_status().json()
                forward = {k: full.get(k) for k in ['status', 'forward_started_at', 'forward_deadline', 'namespace']}
                forward['latest_gaps'] = (full.get('checks') or [{}])[-1].get('gaps', [])
            failures = [{'validation_id': v.get('validation_id'), 'purpose': v.get('purpose'),
                         'verdict': v.get('validation_verdict')} for v in validations if v.get('validation_verdict') == 'FAIL']
            item['complete_freezes'].append({'freeze_id': fid, 'evidence_kind': frozen.get('evidence_kind'),
                                             'forward': forward, 'recorded_failures': failures})
            if failures: result['blockers'].append('RECORDED_HARD_FAILURE_REQUIRES_PROTOCOL_DISPOSITION:' + fid)
        result['protocols'].append(item)
    plans = client.get('/api/research/collections').raise_for_status().json()
    if not plans: result['blockers'].append('REAL_COLLECTION_PLAN_MISSING_IN_THIS_DEPLOYMENT')
    for plan in plans:
        pid = plan['plan_id']; base = '/api/research/collections/' + pid
        response = client.get(base + '/source-gaps')
        if response.status_code == 200:
            gaps = response.json()
            summary = {k: gaps.get(k) for k in ['forward_admissible', 'gaps', 'source_gaps']}
        else:
            summary = {'forward_admissible': False, 'query_status': response.status_code,
                       'gaps': ['SOURCE_GAPS_QUERY_REFUSED'], 'detail': response.json().get('detail')}
        result['collections'].append({'plan_id': pid, 'instrument': plan['instrument'], **summary})
        if not summary['forward_admissible']: result['blockers'].append('COMPLETE_CURRENT_INPUT_NOT_ADMITTED:' + pid)
    # This is a possible future checkpoint only, never a promised or actual start.
    local = checked.astimezone(ZoneInfo('Asia/Shanghai')); next_checkpoint = None
    for offset in range(10):
        day = local.date() + timedelta(days=offset)
        checkpoint = datetime.combine(day, datetime.min.time(), tzinfo=local.tzinfo).replace(hour=15, minute=5)
        if checkpoint <= local: continue
        calendar = client.get('/api/market/calendar', params={'exchange': 'SSE', 'date': day.isoformat()}).raise_for_status().json()
        if calendar.get('is_trading_day') is True:
            next_checkpoint = checkpoint.isoformat(); break
    result['next_possible_checkpoint_if_preregistered_and_inputs_admitted'] = next_checkpoint
    result['clock_started'] = any(p['forward_started_at'] for p in result['protocols'])
    result['blockers'] = sorted(set(result['blockers']))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--api-url', default='http://127.0.0.1:8010')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with httpx.Client(base_url=args.api_url, timeout=10, follow_redirects=False) as client:
        value = inspect_deployment(client)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'clock_started': value['clock_started'], 'blockers': value['blockers'],
        'next_possible_checkpoint': value['next_possible_checkpoint_if_preregistered_and_inputs_admitted']}, ensure_ascii=False))


if __name__ == '__main__': main()
