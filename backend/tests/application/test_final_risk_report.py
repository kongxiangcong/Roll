"""Saved METHOD research report projects actual risk SELL without invented fees."""
import pytest
from fastapi.testclient import TestClient
from roll.app import create_app
from report_method_app import copy_donor, FREEZE
from capability_method_app import save_package
from test_lifecycle_composition import risk_package
from test_action_risk_priority import method_clock, record
from test_reconcile import reconcile, broker_snapshot
from test_account import submit
from test_funding import funding
from test_capabilities import method_command
from test_intents import intent_command
from test_fills import fill


@pytest.mark.parametrize('price,action,quantity,nav', [('100', 'REDUCE', '100', '130000.10'), ('1000', 'EXIT', '300', '400000.10')])
def test_linked_risk_sell_report_exports_keep_unfrozen_proposal_fee_unknown(tmp_path, monkeypatch, price, action, quantity, nav):
    method_clock(monkeypatch)
    p = risk_package()
    p['account_version'] = p['loss_facts']['baseline_account_version'] = 3
    p['loss_facts'].update(baseline_assets=nav, net_assets=nav)
    p['action_packet']['risk_inputs']['quotes']['SSE:600000']['last'] = price
    file = save_package(tmp_path / 'qualification.json', p)
    directory = copy_donor(tmp_path.parent / ('risk-' + action))  # Short owned path; verified before any connection.
    with TestClient(create_app(directory, runtime_role='API', capability_method_file=file), raise_server_exceptions=False) as client:
        old_shadow = client.get('/api/research/shadow/' + FREEZE).json()
        snapshot = broker_snapshot(cash_balance='100000.10', income='0.00', expenses='0.00')
        snapshot.update(pending_items=[], withdrawable='100000.10', positions=[{'instrument': 'SSE:600000', 'quantity': '300', 'sellable_quantity': '300'}])
        command = reconcile(1, 'risk-report-alignment', snapshot)
        command['payload'].update(source='METHOD confirmed broker alignment', effective_at=p['required_as_of'])
        assert submit(client, command, 'align').status_code == 200
        assert submit(client, {'kind': 'ACCOUNT_DECLARATION', 'expected_account_version': 2, 'payload': {
            'effective_at': p['required_as_of'], 'source': 'METHOD confirmed account', 'record_id': 'risk-report-declaration',
            'scope': ['TRADES', 'ORDERS', 'CASH', 'EQUITY'], 'changes': 'NONE', 'basis': 'isolated facts'}}, 'declare').status_code == 200
        assert client.post('/api/funding/confirm', json=funding()).status_code == 200
        grant = client.post('/api/capabilities/grants', json={**method_command(), 'expected_account_version': 3,
            'allowed_actions': ['REDUCE', 'EXIT'], 'deployment_fingerprints': p['deployment_fingerprints']})
        assert grant.status_code == 201, grant.text
        evaluated = client.post('/api/actions/evaluate', json={})
        assert evaluated.status_code == 201, evaluated.text
        evaluation = evaluated.json()
        assert [(d['action'], d['quantity']) for d in evaluation['decisions']] == [(action, quantity)]
        assert 'fees_yuan' not in evaluation['decisions'][0]
        prepared = client.post('/api/intents/prepare', json={**intent_command(evaluation), 'price_yuan': price})
        assert prepared.status_code == 201, prepared.text
        intent = prepared.json()
        actual = fill(3, 'risk-sell', direction='SELL')
        actual['payload'].update(quantity=quantity, price=price, effective_at=p['required_as_of'])
        actual['payload']['fee']['amount'] = '7.00'
        drafted = client.post('/api/account/drafts', json=actual)
        assert drafted.status_code == 201, drafted.text
        confirmed = client.post('/api/account/confirm', json={'draft_id': drafted.json()['draft_id'], 'idempotency_key': 'risk-sell-confirm',
            'fill_allocations': [{'intent_id': intent['intent_id'], 'fill_record_id': 'risk-sell', 'allocated_quantity': quantity, 'association_status': 'USER_CONFIRMED'}]})
        assert confirmed.status_code == 200, confirmed.text
        params = {'decision_id': intent['decision_id'], 'evaluation_id': evaluation['evaluation_id'], 'intent_id': intent['intent_id']}
        url = '/api/research/reports/' + FREEZE
        response = client.get(url, params=params)
        record(tmp_path, 'risk-sell-report-response', {'status': response.status_code, 'body': response.text})
        assert response.status_code == 200, response.text
        report = response.json()
        diagnostic = report['execution_deviations'][0]['allocation_diagnostics'][0]
        assert diagnostic['proposal_fees_yuan'] is None
        assert diagnostic['proposal_fee_status'] == 'UNKNOWN'
        assert diagnostic['actual_full_fill_fee']['amount'] == '7.00'
        assert diagnostic['fee_comparison'] == 'PROPOSAL_FEE_UNKNOWN'
        assert report['prepare_allowed'] is False and report['system_usable'] is False
        assert client.get(url + '/export', params=params).json() == report
        text = client.get(url + '/export', params={**params, 'format': 'text'})
        assert text.status_code == 200
        assert 'PROPOSAL_FEE_UNKNOWN' in text.text and '"proposal_fees_yuan":null' in text.text
        assert client.get('/api/research/shadow/' + FREEZE).json() == old_shadow
