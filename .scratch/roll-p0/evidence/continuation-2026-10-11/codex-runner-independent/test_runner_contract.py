"""Current default selection and preserved archive contracts; METHOD profiles only."""
import json, os, subprocess, sys
from pathlib import Path
from fastapi.testclient import TestClient
from codex_scope_method_app import factory


def test_default_collect_literal_current_and_historical_boundary():
    backend = Path(os.environ['RUNNER_SOURCE']) / 'backend'
    collected = subprocess.run([sys.executable, '-B', '-m', 'pytest', '--collect-only', '-q', '-p', 'no:cacheprovider'],
        cwd=backend, capture_output=True, text=True, timeout=60)
    assert collected.returncode == 0, collected.stdout + collected.stderr
    nodes = [line for line in collected.stdout.splitlines() if '.py::' in line]
    assert len(nodes) == 591
    assert '3 deselected' in collected.stdout
    excluded = ['test_backend_switch.py::', 'test_deepseek_evidence.py::', 'test_deepseek_process.py::',
        '::test_cross_backend_retry_rejects_revised_archive_and_preserves_original',
        '::test_deepseek_sdk_review_uses_the_same_material_contract_and_freezes_runtime_versions']
    assert not [node for node in nodes if any(name in node for name in excluded)]
    for name in ['test_codex_only_scope.py::', '::test_cancel_timeout_retry_and_acquisition_share_the_same_frozen_execution_slot',
        '::test_agent_child_preserves_explicit_fuyao_adjustment_source[CODEX]',
        '::test_codex_retry_rejects_revised_archive_and_preserves_original',
        "test_host_derived_evidence_deficits_cannot_be_self_signed", 'test_capabilities.py::']:
        assert any(name in node for node in nodes), name
    explicit = subprocess.run([sys.executable, '-B', '-m', 'pytest', '--collect-only', '-q', '-p', 'no:cacheprovider',
        'tests/application/test_backend_switch.py', 'tests/application/test_deepseek_evidence.py', 'tests/recovery/test_deepseek_process.py'],
        cwd=backend, capture_output=True, text=True, timeout=60)
    assert explicit.returncode == 5, explicit.stdout + explicit.stderr
    assert not [line for line in explicit.stdout.splitlines() if '.py::' in line]
    assert 'deselected' in explicit.stdout
    output = Path(os.environ['RUNNER_RECEIPT'])
    (output / 'default-collect.log').write_text(collected.stdout + collected.stderr, encoding='utf-8')
    (output / 'explicit-historical-collect.log').write_text(explicit.stdout + explicit.stderr, encoding='utf-8')


def test_fresh_method_legacy_get_cancel_and_current_ds_refusal(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    monkeypatch.setenv('ROLL_DATA_DIR', str(tmp_path / 'data'))
    with TestClient(factory()) as client:
        original = client.get('/api/data/runs/legacy-deepseek-method').json()
        history = client.get('/api/agents/settings/history').json()
        before = client.get('/api/account').json()
        assert original['backend'] == 'DEEPSEEK' and original['status'] == 'CANCELLED'
        settings = client.get('/api/agents/settings').json()
        assert settings['supported_backends'] == ['CODEX'] and settings['resave_required'] is True
        for url, command in [('/api/agents/settings', {'backend': 'DEEPSEEK', 'expected_version': 1}),
            ('/api/data/requests/missing/deepseek', {'question': 'method-only'}),
            ('/api/data/requests/missing/agent', {'question': 'method-only'}),
            ('/api/research/review-materials/missing/reviews', {'expected_material_fingerprint': 'missing'})]:
            response = client.post(url, json=command)
            assert response.status_code == 403, response.text
            assert response.json()['detail']['code'] == 'BACKEND_OUTSIDE_CURRENT_SCOPE'
        assert client.get('/api/agents/settings/history').json() == history
        cancelled = client.post('/api/data/runs/legacy-deepseek-method/cancel', json={})
        assert cancelled.status_code == 200
        assert cancelled.json() == {'run_id': 'legacy-deepseek-method', 'status': 'CANCELLED', 'cancel_requested': False}
        assert client.get('/api/data/runs/legacy-deepseek-method').json() == original
        saved = client.post('/api/agents/settings', json={'backend': 'CODEX', 'expected_version': 1})
        assert saved.status_code == 200 and saved.json()['version'] == 2
        assert client.get('/api/data/runs/legacy-deepseek-method').json() == original
        assert client.get('/api/agents/settings/history').json()[1:] == history
        assert client.get('/api/account').json() == before
        assert client.get('/api/data/runs').json() == [original]
