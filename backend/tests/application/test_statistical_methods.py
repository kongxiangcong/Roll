"""Executable method bindings are checked at the accepted complete-freeze API seam."""
from fastapi.testclient import TestClient
from roll.app import create_app
from test_shadow import setup, freeze


def test_complete_freeze_preserves_executable_statistics_checks_separate_from_real_validity(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        _, protocol, model, _ = setup(client, tmp_path)
        response = freeze(client, protocol, model)
        assert response.status_code == 201, response.text
        frozen = response.json()
        methods = frozen['statistical_methods']
        assert len(frozen['fingerprints']['validation_code']) == 64
        assert methods['algorithm_checks_passed'] is True
        assert methods['worked_examples']['constant_paired_improvement']['lower_95'] == .005
        assert methods['worked_examples']['known_binary_losses']['brier'] == .04
        assert methods['worked_examples']['known_binary_losses']['auc'] == 1.0
        assert methods['worked_examples']['known_binary_losses']['selected_mature'] == 20
        assert methods['worked_examples']['known_binary_losses']['duplicate_event_count'] == 1
        assert methods['worked_examples']['constant40_sensitivity']['lower_95'] == .005
        assert methods['worked_examples']['continuous_nav']['net_return'] == .1
        assert methods['worked_examples']['continuous_nav']['maximum_drawdown'] == .1
        assert methods['worked_examples']['missing_valuation']['net_return'] is None
        assert methods['worked_examples']['boundary_crossing']['lower_95'] < 0
        assert methods['worked_examples']['boundary_crossing']['upper_95'] > 0
        assert methods['real_sampling_assumptions_verified'] is False
        assert methods['confers_statistical_pass'] is False
        assert client.get('/api/research/complete-freezes/'+frozen['freeze_id']).json()['statistical_methods'] == methods
        assert frozen['capability'] == 'NOT_GRANTED'
