"""Public API preregistration, maturity and single-endpoint tests; METHOD only."""
from copy import deepcopy
from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from roll.app import create_app
from roll.research.independent_validation import evaluate_endpoint
from roll.research.validation import combine, gate
from test_shadow import setup, freeze


@pytest.fixture(autouse=True)
def method_environment(monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')


def prepare(client, directory, clock):
    _, protocol, model, days = setup(client, directory)
    frozen = freeze(client, protocol, model).json()
    clock[0] = datetime.fromisoformat(days[110]+'T14:00:00+08:00')
    root = '/api/research/complete-freezes/'+frozen['freeze_id']
    forward = root+'/forward'
    independent = root+'/independent-validation'
    assert client.post(forward, json={'purpose': 'METHOD_VALIDATION', 'basis': 'METHOD only'}).status_code == 201
    command = {'expected_complete_protocol_fingerprint': frozen['complete_protocol_fingerprint'],
               'basis': 'Register before any outcome or prediction; one final look'}
    return frozen, days, forward, independent, command


def test_preregister_settle_compare_single_endpoint_and_offline_restart(tmp_path):
    clock = [datetime.fromisoformat('2026-06-01T14:00:00+08:00')]
    with TestClient(create_app(tmp_path, review_clock=lambda: clock[0])) as client:
        frozen, days, forward, path, command = prepare(client, tmp_path, clock)
        admission = client.get(path+'/admission').json()
        assert admission['admitted'] and not admission['sealed_read']
        assert admission['feasibility']['status'] == 'INFEASIBLE_FOR_PASS_UNDER_FROZEN_LIMITS'
        assert max(admission['feasibility']['mature_block_upper_bounds'].values()) < 30
        manifest_before = client.app.state.independent_validation.registry.attempt_manifest(frozen['protocol_id'])
        registered = client.post(path+'/plan', json=command)
        assert registered.status_code == 201, registered.text
        assert client.post(path+'/plan', json=command).json() == registered.json()
        assert client.post(path+'/plan', json={**command, 'basis': 'changed'}).status_code == 409
        assert client.post(path+'/plan', json={**command, 'independent': True}).status_code == 422
        assert client.post(path).status_code == 409  # No early look.
        clock[0] = datetime.fromisoformat(days[110]+'T16:00:00+08:00')
        checkpoint = client.post(forward+'/check', json={'basis': 'First METHOD prediction'})
        assert checkpoint.status_code == 201, checkpoint.text
        assert len(checkpoint.json()['samples']) == 1
        early = client.post(forward+'/settle', json={'basis': 'Still immature'}).json()
        assert len(early['unmatured']) == 1 and not early['mature']
        assert client.post(path).status_code == 409
        clock[0] = datetime.fromisoformat(days[130]+'T16:00:00+08:00')
        end = client.post(forward+'/stop', json={'kind': 'USER_STOP', 'basis': 'Fixed METHOD endpoint'})
        assert end.status_code == 200, end.text
        result = client.post(path)
        assert result.status_code == 201, result.text
        saved = result.json()
        assert saved['validation_verdict'] in {'FAIL', 'INCONCLUSIVE'}
        assert saved['gates']['G2']['status'] == 'PASS'
        assert len(saved['maturity']['mature']) == 1 and not saved['maturity']['unmatured']
        assert not saved['system_usable'] and saved['capability'] == 'NOT_GRANTED'
        assert set(saved['comparators']) == {'CASH', 'START_HOLD', 'MA5_MA20'}
        candidate_days = [p['date'] for p in saved['candidate']['curve']]
        assert all([p['date'] for p in b['curve']] == candidate_days for b in saved['comparators'].values())
        assert saved['comparators']['CASH']['cash_yuan'] == frozen['baseline']['cash_yuan']
        assert saved['final_look_count'] == 1
        assert client.post(path).json() == saved
        assert client.post(path+'/replay').json()['matches_original'] is True
        assert client.app.state.independent_validation.registry.attempt_manifest(frozen['protocol_id']) == manifest_before
        archive = client.app.state.independent_validation.shadow.checked_archive(saved['input_archive'])
        tampered = deepcopy(archive)
        tampered['assessment']['mature'][0]['label'] ^= 1
        assert evaluate_endpoint(tampered)['validation_verdict'] == 'FAIL'
        tampered = deepcopy(archive)
        tampered['forward']['samples'][0]['forecast']['probability'] = .123456
        assert evaluate_endpoint(tampered)['gates']['G2']['status'] == 'FAIL'
        tampered = deepcopy(archive)
        tampered['forward']['samples'][0]['recorded_at'] = registered.json()['registered_at']
        assert 'PREDICTION_PRECEDES_PREREGISTRATION' in evaluate_endpoint(tampered)['gates']['G1']['reasons']
        tampered = deepcopy(archive)
        tampered['forward']['namespace'] = 'FORWARD'
        assert evaluate_endpoint(tampered)['gates']['G1']['status'] == 'FAIL'
    with TestClient(create_app(tmp_path, review_clock=lambda: clock[0])) as client:
        assert client.get(path).json() == saved
        assert client.post(path).json() == saved
        assert client.post(path+'/replay').json() == {'matches_original': True, 'network_calls': 0,
            'additional_final_looks': 0, 'capability': 'NOT_GRANTED'}
        audits = client.app.state.independent_validation.registry.audit(frozen['protocol_id'])
        assert len([e for e in audits if e['action'] == 'INDEPENDENT_ENDPOINT_EVALUATED']) == 1


def test_no_posthoc_registration(tmp_path):
    clock = [datetime.fromisoformat('2026-06-01T14:00:00+08:00')]
    with TestClient(create_app(tmp_path, review_clock=lambda: clock[0])) as client:
        _, days, forward, path, command = prepare(client, tmp_path, clock)
        clock[0] = datetime.fromisoformat(days[110]+'T16:00:00+08:00')
        assert client.post(forward+'/check', json={'basis': 'Already exposed'}).status_code == 201
        assert not client.get(path+'/admission').json()['admitted']
        assert client.post(path+'/plan', json=command).status_code == 409


def test_empty_endpoint_is_inconclusive_and_has_no_invented_curve(tmp_path, monkeypatch):
    clock = [datetime.fromisoformat('2026-06-01T14:00:00+08:00')]
    with TestClient(create_app(tmp_path, review_clock=lambda: clock[0])) as client:
        _, _, forward, path, command = prepare(client, tmp_path, clock)
        assert client.post(path+'/plan', json=command).status_code == 201
        assert client.post(forward+'/stop', json={'kind': 'USER_STOP', 'basis': 'No samples'}).status_code == 200
        result = client.post(path)
        assert result.status_code == 201, result.text
        assert result.json()['validation_verdict'] == 'INCONCLUSIVE'
        assert result.json()['candidate'] is None and result.json()['comparators'] is None
        assert result.json()['gates']['G2']['status'] == 'INCONCLUSIVE'
        from roll.research import independent_validation
        monkeypatch.setattr(independent_validation, 'executor_code', lambda: 'changed')
        assert client.get(path).json() == result.json()
        assert client.post(path+'/replay').status_code == 409


def test_metadata_admission_does_not_open_protected_or_model_inputs(tmp_path, monkeypatch):
    clock = [datetime.fromisoformat('2026-06-01T14:00:00+08:00')]
    with TestClient(create_app(tmp_path, review_clock=lambda: clock[0])) as client:
        frozen, _, _, path, command = prepare(client, tmp_path, clock)
        executor = client.app.state.independent_validation
        original_raw = executor.evidence.raw
        def only_frozen_metadata(sha):
            assert sha == frozen['archive']['sha256'], 'Admission must not consume price/label payloads'
            return original_raw(sha)
        monkeypatch.setattr(executor.evidence, 'raw', only_frozen_metadata)
        assert client.get(path+'/admission').status_code == 200
        bad = client.post(path+'/plan', json={**command, 'expected_complete_protocol_fingerprint': 'wrong'})
        assert bad.status_code == 409
        original_plan = executor.forward.plan(frozen['freeze_id'])
        monkeypatch.setattr(executor.forward, 'plan', lambda _: {**original_plan, 'namespace': 'FORWARD'})
        admission = client.get(path+'/admission').json()
        assert not admission['admitted']
        assert 'FORWARD_START_OVERLAPS_FITTED_OR_PROTECTED_WINDOW' in admission['gaps']


@pytest.mark.parametrize('statuses,expected', [(['PASS', 'PASS'], 'PASS'),
    (['PASS', 'INCONCLUSIVE'], 'INCONCLUSIVE'), (['FAIL', 'INCONCLUSIVE'], 'FAIL')])
def test_gate_verdicts_do_not_confuse_engineering_and_statistical_success(statuses, expected):
    assert combine({str(i): gate(s, []) for i, s in enumerate(statuses)}) == expected
