"""Independent public forward API acceptance in a brand-new METHOD profile."""
import hashlib
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from roll.app import create_app

root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(root / 'backend/tests/application'))
from test_shadow import setup, freeze

profile = Path(sys.argv[1]).resolve()
if profile.exists():
    raise RuntimeError('Preserve earlier profiles; independent runtime must be new')
profile.mkdir(parents=True)
directory = profile / 'runtime'
os.environ['ROLL_ENV'] = 'test'
os.environ['ROLL_CODEX_AUTH_FILE'] = str(profile / 'no-provider-auth.json')
for key in ('DEEPSEEK_API_KEY', 'ROLL_DEEPSEEK_API_KEY_FILE', 'ROLL_TEST_CRASH_POINT'):
    os.environ.pop(key, None)
clock = [datetime.fromisoformat('2026-06-10T14:00:00+08:00')]


def post(client, path, data, status=201):
    response = client.post(path, json=data)
    assert response.status_code == status, (path, response.status_code, response.text)
    return response.json()


with TestClient(create_app(directory, review_clock=lambda: clock[0])) as client:
    _, protocol, model, dates = setup(client, directory)
    frozen = freeze(client, protocol, model, baseline={'cash_yuan': '1.00', 'positions': []}).json()
    path = '/api/research/complete-freezes/' + frozen['freeze_id'] + '/forward'
    clock[0] = datetime.fromisoformat(dates[110] + 'T14:00:00+08:00')
    # Real namespace and client clock spoofing cannot promote METHOD evidence.
    post(client, path, {'purpose': 'RESEARCH', 'basis': 'METHOD cannot become real'}, 409)
    post(client, path, {'purpose': 'METHOD_VALIDATION', 'basis': 'No client clock', 'started_at': clock[0].isoformat()}, 422)
    registered = post(client, path, {'purpose': 'METHOD_VALIDATION', 'basis': 'Independent bounded engineering'})
    assert registered['namespace'] == 'METHOD_CASE' and registered['started_at'] is None
    early = post(client, path + '/check', {'basis': 'Before registered checkpoint'})
    assert early['samples'] == [] and early['method_started_at'] is None
    assert 'POST_CLOSE_CHECKPOINT_NOT_REACHED' in early['checks'][-1]['gaps']
    backup = post(client, '/api/runtime/backups', {})
    package = client.get('/api/runtime/backups/' + backup['backup_id'] + '/export').content
    clock[0] = datetime.fromisoformat(dates[110] + 'T16:00:00+08:00')
    first = post(client, path + '/check', {'basis': 'First persisted METHOD prediction'})
    sample = first['samples'][0]
    assert sample['action']['action'] == 'REFUSE'
    assert sample['confirmatory_sample'] is False and sample['statistical_pass_check'] is False
    assert first['method_started_at'] == clock[0].isoformat() and first['forward_started_at'] is None
    assert first['method_deadline'] == client.get('/api/research/deadline-preview', params={'start': first['method_started_at']}).json()['deadline']
    for basis in ('Different task key', 'Changed snapshot basis', 'Repeated checkpoint'):
        assert post(client, path + '/check', {'basis': basis})['samples'] == [sample]
    assert first['shadow']['revision'] == 1
    assessment = post(client, path + '/settle', {'basis': 'Observation result unavailable'})
    assert len(assessment['unmatured']) == 1 and assessment['unmatured'][0]['label'] is None
    clock[0] = clock[0].astimezone(timezone.utc)
    post(client, path + '/settle', {'basis': 'Equivalent UTC instant'})
    assert post(client, path + '/replay', {}, 200)['matches_original'] is True
    clock[0] = datetime.fromisoformat(dates[113] + 'T16:00:00+08:00')
    second = post(client, path + '/check', {'basis': 'Return after absent trading days'})
    assert len(second['samples']) == 2 and second['method_deadline'] == first['method_deadline']
    assert set(dates[111:113]).issubset({g['trading_date'] for g in second['missing_checkpoints']})
    clock[0] = datetime.fromisoformat(dates[133] + 'T16:00:00+08:00')
    mature = post(client, path + '/settle', {'basis': 'Mature previously saved refusal only'})
    assert len(mature['mature']) == 2 and mature['unmatured'] == []
    assert all(r['diagnostic_only'] and not r['continuous_return_included'] for r in mature['mature'])
    assert mature['shadow']['cash_yuan'] == '1.00' and mature['shadow']['events'] == []
    clock[0] = datetime.fromisoformat(dates[139] + 'T16:00:00+08:00')
    last = post(client, path + '/check', {'basis': 'Available context, later outcome missing'})
    assert len(last['samples']) == 3
    clock[0] = datetime.fromisoformat(dates[159] + 'T16:00:00+08:00')
    missing = post(client, path + '/settle', {'basis': 'Mature does not imply complete outcome'})
    assert any(r['sample_id'] == last['samples'][-1]['sample_id'] and r['label'] is None and r['reason'] == 'MATURE_RESULT_EVIDENCE_NOT_COMPLETE' for r in missing['unscorable'])
    assert post(client, path + '/replay', {}, 200)['matches_original'] is True
    clock[0] = datetime.fromisoformat(first['method_deadline'])
    closed = post(client, path + '/check', {'basis': 'Original inclusive deadline'})
    assert closed['status'] == 'CLOSED' and closed['endpoint']['cutoff'] == first['method_deadline']
    assert closed['endpoint']['preliminary_verdict'] == 'INCONCLUSIVE'
    assert closed['endpoint']['validation_status'] == 'INCOMPLETE' and closed['endpoint']['review_status'] == 'PENDING'
    assert closed['endpoint']['capability'] == 'NOT_GRANTED' and closed['endpoint']['statistical_pass_checks_added'] == 0
    clock[0] = clock[0].replace(hour=17)
    after = post(client, path + '/check', {'basis': 'Later receipt cannot extend endpoint'})
    assert after['endpoint'] == closed['endpoint'] and after['samples'] == closed['samples']
    post(client, path + '/stop', {'kind': 'EARLY_PASS', 'basis': 'No optional PASS look'}, 422)
    for start, deadline in [('2025-11-30T16:00:00+08:00', '2026-02-28T16:00:00+08:00'), ('2023-11-30T16:00:00+08:00', '2024-02-29T16:00:00+08:00'), ('2026-01-31T16:00:00+08:00', '2026-04-30T16:00:00+08:00')]:
        preview = client.get('/api/research/deadline-preview', params={'start': start}).json()
        assert preview['deadline'] == deadline and preview['actual_forward_start'] is False
    original_protocol = client.get('/api/research/protocols/' + protocol['protocol_id']).json()
    assert all(original_protocol.get(k) is None for k in ('forward_started_at', 'forward_deadline', 'forward_ended_at'))
    assert client.get('/api/account').json()['version'] == 0

with TestClient(create_app(directory, review_clock=lambda: clock[0])) as client:
    restarted = client.get(path).json()
    assert restarted['samples'] == closed['samples'] and restarted['endpoint'] == closed['endpoint']
    replay = post(client, path + '/replay', {}, 200)
    assert replay['matches_original'] is True and replay['network_calls'] == 0
    owned_archive = (directory / sample['archive']['path']).resolve()
    assert owned_archive.is_relative_to(directory)
    original = owned_archive.read_bytes()
    owned_archive.write_bytes(original + b' ')
    try:
        post(client, path + '/replay', {}, 409)
        post(client, path + '/check', {'basis': 'Corrupt sample cannot bypass closed state'}, 409)
    finally:
        owned_archive.write_bytes(original)
    assert post(client, path + '/replay', {}, 200)['matches_original'] is True

restored = profile / 'restored'
with TestClient(create_app(restored, review_clock=lambda: clock[0])) as client:
    response = client.post('/api/runtime/restores', content=package)
    assert response.status_code == 202, response.text
with TestClient(create_app(restored, review_clock=lambda: clock[0])) as client:
    assert client.get('/api/runtime/backups/status').json()['recovery']['state'] == 'RECOVERY_LOCK'
    refusal = post(client, path + '/check', {'basis': 'No restored-plan backfill'}, 409)
    assert refusal['detail']['code'] == 'FORWARD_RECOVERY_LOCK'
    state = client.get(path).json()
    assert state['samples'] == [] and state['method_started_at'] is None and state['forward_started_at'] is None

print(json.dumps({'status': 'PASS', 'evidence_kind': 'METHOD_CASE', 'source_merge': '6215a71e73185a6fe015aefa40fb0d00347f665a',
    'profile': str(profile), 'freeze_id': frozen['freeze_id'], 'protocol_id': protocol['protocol_id'],
    'same_day_unique_samples': 1, 'final_samples': 3, 'month_end_and_leap_year': True,
    'missing_days_no_backfill': True, 'mature_refusals_diagnostic_only': True,
    'mature_missing_unscorable_null_label': True, 'deadline_not_extended': True,
    'restart_replay_network_calls': 0, 'corrupt_sample_refused': True, 'restore_lock_no_start': True,
    'actual_forward_started_at': None, 'real_namespace_refused': True, 'account_version': 0,
    'capability': 'NOT_GRANTED', 'actual_provider_calls': 0}))
