"""Read-only report seam; real registered historical METHOD archives, no fit/forecast."""
from fastapi.testclient import TestClient
from roll.app import create_app
from report_method_app import copy_donor, FREEZE
from test_valuation import quote_transport, acquire, publish
from test_account import submit
from test_fills import fill, fee_adjustment
from datetime import datetime, timedelta
from test_reviews import wait_result
from test_actions import action_package
from capability_method_app import save_package
from test_capabilities import method_command
from test_funding import funding
from test_reconcile import reconcile, broker_snapshot
from test_intents import intent_command
from test_capability_monitoring import monitored_package
import pytest
import httpx
import time
import json
import os
from pathlib import Path


def capture(name, payload):
    if output := os.environ.get('ROLL_REPORT_EVIDENCE_DIR'):
        directory = Path(output); directory.mkdir(parents=True, exist_ok=True)
        (directory / (name + '.json')).write_text(json.dumps({'evidence_kind': 'METHOD_CASE_PUBLIC_API_REAL_SQLITE',
            'donor': 'PINNED_193_BYTE_COPY_ONLY', 'new_fit_forecast_replay_advance_sealed_calls': 0,
            'actual_external_provider_calls': 0, 'result': payload}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def test_unexecuted_reason_and_unlinked_actual_trade_are_not_retroactive_research_qualification(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = action_package(); p['account_version'] = p['loss_facts']['baseline_account_version'] = 3
    file = save_package(tmp_path / 'qualification.json', p)
    with TestClient(create_app(copy_donor(tmp_path / 'data'), runtime_role='API', capability_method_file=file)) as client:
        original = client.get('/api/research/shadow/' + FREEZE).json()
        evaluation = prepare_copied_actual(client, p)
        intent = client.post('/api/intents/prepare', json=intent_command(evaluation)).json()
        resolution = client.post('/api/intents/' + intent['intent_id'] + '/declare', json={
            'state': 'NOT_EXECUTED', 'reason': 'METHOD user chose not to place this order', 'idempotency_key': 'unexecuted'})
        assert resolution.status_code == 200, resolution.text
        trade = fill(3, 'self-directed-after-research', fee_status='PROVISIONAL')
        trade['payload'].update(quantity='100', price='10.10', effective_at=p['required_as_of'])
        assert submit(client, trade, 'unlinked').status_code == 200
        params = {'decision_id': intent['decision_id'], 'evaluation_id': intent['evaluation_id'], 'intent_id': intent['intent_id']}
        report = client.get('/api/research/reports/' + FREEZE, params=params).json()
        assert report['execution_deviations'][0]['unexecuted_reason'] == resolution.json()['resolution']
        assert report['execution_deviations'][0]['allocations'] == []
        assert report['execution']['unlinked_fills'][0]['record_id'] == 'self-directed-after-research'
        assert report['execution']['unlinked_association'] == 'UNKNOWN'
        assert report['qualification']['capability'] == 'NOT_GRANTED' and report['prepare_allowed'] is False
        assert client.get('/api/research/shadow/' + FREEZE).json() == original
        capture('unexecuted-unlinked', report)


def test_report_preserves_actual_28_worker_attempt_receipt_without_inventing_delivery_or_read(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = action_package(); p['account_version'] = p['loss_facts']['baseline_account_version'] = 3
    file = save_package(tmp_path / 'qualification.json', p)
    calls = []
    def accepted(request):
        calls.append(str(request.url))
        return httpx.Response(200, json={'id': 'method-report-outbound', 'event': 'message'})
    with TestClient(create_app(copy_donor(tmp_path / 'data'), capability_method_file=file,
            notification_transport=httpx.MockTransport(accepted))) as client:
        evaluation = prepare_copied_actual(client, p)
        intent = client.post('/api/intents/prepare', json=intent_command(evaluation)).json()
        configured = client.post('/api/notification-channel', json={'expected_version': 0, 'enabled': True,
            'server': 'https://ntfy.example.test', 'topic': 'method-report-only', 'app_base_url': 'http://127.0.0.1:5291'})
        assert configured.status_code == 200, configured.text
        for _ in range(200):
            notice = next(n for n in client.get('/api/notifications').json()['notifications'] if n['category'] == 'NEED_ACTION')
            if notice['external_status'] == 'CHANNEL_ACCEPTED': break
            time.sleep(.05)
        else: raise AssertionError(notice)
        params = {'decision_id': intent['decision_id'], 'evaluation_id': intent['evaluation_id'], 'intent_id': intent['intent_id']}
        original_chain = client.get('/api/notifications/time-chain', params=params).json()
        report = client.get('/api/research/reports/' + FREEZE, params=params).json()
        chain = report['execution']['notification_chain']
        assert chain == original_chain
        timeline = chain['notification_timeline'][0]
        assert timeline['dispatch_started_at'] and timeline['publish_confirmed_at'] and timeline['accepted_known_at']
        assert timeline['accepted_occurred_at'] is None
        assert chain['time_chain']['sent_at'] is None and chain['time_chain']['delivered_at'] is None and chain['time_chain']['read_at'] is None
        assert calls and all(url.startswith('https://ntfy.example.test/') for url in calls)
        assert report['execution']['response_seconds'] is None
        read = client.post('/api/notifications/' + notice['notification_id'] + '/read', json={'idempotency_key': 'report-read'})
        assert read.status_code == 200, read.text
        after = client.get('/api/research/reports/' + FREEZE, params=params).json()
        assert after['execution']['notification_chain']['time_chain']['read_source'] == 'EXPLICIT_STATION_READ'
        assert after['execution']['response_seconds'] is None
        assert client.get('/api/intents').json()['intents'][0]['time_chain'] == intent['time_chain']
        capture('outbound-original-and-explicit-station-read', {'original': report, 'after_explicit_read': after})


def test_report_and_exports_refuse_a_changed_saved_shadow_input_archive_without_replay(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    directory = copy_donor(tmp_path / 'data')
    with TestClient(create_app(directory, runtime_role='API')) as client:
        state = client.get('/api/research/shadow/' + FREEZE).json()
        original = client.get('/api/research/reports/' + FREEZE).json()
        artifact = directory / state['input_archive']['path']
        artifact.write_bytes(artifact.read_bytes() + b'\n')
        assert client.get('/api/research/reports/' + FREEZE).status_code == 409
        assert client.get('/api/research/reports/' + FREEZE + '/export').status_code == 409
        assert client.get('/api/research/shadow/' + FREEZE).json() == state
        assert original['platform']['recomputed'] is False


@pytest.mark.parametrize('missing,expected_reason', [(0, 'PRICE_OUTSIDE_FROZEN_WINDOW'), (5, 'REQUIRED_FEATURE_COVERAGE_BELOW80_PERCENT')])
def test_report_reads_registered_execution_misfit_and_missing_support_without_new_check_or_grant(tmp_path, monkeypatch, missing, expected_reason):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = monitored_package(20, missing=missing)
    p['account_version'] = p['loss_facts']['baseline_account_version'] = 3
    file = save_package(tmp_path / 'qualification.json', p)
    with TestClient(create_app(copy_donor(tmp_path / 'data'), runtime_role='API', capability_method_file=file)) as client:
        evaluation = prepare_copied_actual(client, p)
        if missing == 0:
            intent = client.post('/api/intents/prepare', json=intent_command(evaluation)).json()
            actual = fill(3, 'report-outside-band')
            actual['payload'].update(instrument=intent['instrument'], quantity='100', price='155.00', effective_at=p['required_as_of'])
            actual['payload']['fee']['amount'] = '7.00'
            draft = client.post('/api/account/drafts', json=actual)
            assert draft.status_code == 201, draft.text
            confirmation = client.post('/api/account/confirm', json={'draft_id': draft.json()['draft_id'], 'idempotency_key': 'outside',
                'fill_allocations': [{'intent_id': intent['intent_id'], 'fill_record_id': 'report-outside-band',
                    'allocated_quantity': '100', 'association_status': 'USER_CONFIRMED'}]})
            assert confirmation.status_code == 200, confirmation.text
        response = client.post('/api/capabilities/monitoring/check', json={'grant_id': evaluation['decisions'][0]['grant_id'],
            'basis': 'source-bound METHOD existing registered monitoring fixture'})
        assert response.status_code == 201, response.text
        check = response.json()
        assert check['status'] == 'RESTRICTED' and expected_reason in check['reasons'], check
        correction = client.post('/api/capabilities/corrections', json={'monitoring_check_id': check['check_id'],
            'category': 'EXECUTION_ASSUMPTION' if missing == 0 else 'DATA_REPAIR',
            'error_source': expected_reason, 'expected_improvement': 'restore source coverage or register successor assumptions',
            'affected_modules': ['execution' if missing == 0 else 'data'], 'validation_plan': 'verify source and rerun registered regression',
            'changes_frozen': False, 'idempotency_key': 'report-review'})
        assert correction.status_code == 201, correction.text
        before = {path: client.get(path).json() for path in ['/api/capabilities/monitoring', '/api/capabilities/grants', '/api/capabilities/events']}
        params = {'monitoring_check_id': check['check_id']}
        url = '/api/research/reports/' + FREEZE
        report = client.get(url, params=params).json()
        assert report['monitoring']['checks'] == [check]
        assert report['monitoring']['corrections'] == [correction.json()]
        assert report['monitoring']['same_strategy'] is False
        assert check['reference']['bounds']['x'] == pytest.approx([.99, 98.01])
        assert check['confirmation_pass_look'] is False and check['historic_verdict_mutated'] is False
        assert client.get(url + '/export', params=params).json() == report
        assert expected_reason in client.get(url + '/export', params={**params, 'format': 'text'}).text
        assert client.get(url, params=params).json() == report
        assert {path: client.get(path).json() for path in before} == before
        capture('monitoring-missing-' + str(missing), report)


def prepare_copied_actual(client, p):
    snapshot = broker_snapshot(cash_balance='100000.10', income='0.00', expenses='0.00')
    snapshot['pending_items'] = []
    snapshot['withdrawable'] = '100000.10'
    snapshot['positions'] = [{'instrument': row['instrument'], 'quantity': '0', 'sellable_quantity': '0'}
                             for row in client.get('/api/account').json()['positions']]
    alignment = reconcile(1, 'METHOD-report-alignment', snapshot)
    alignment['payload'].update(source='METHOD isolated broker alignment', effective_at=p['required_as_of'])
    result = submit(client, alignment, 'report-alignment')
    assert result.status_code == 200, result.text
    declaration = {'kind': 'ACCOUNT_DECLARATION', 'expected_account_version': 2, 'payload': {
        'effective_at': p['required_as_of'], 'source': 'METHOD isolated user', 'record_id': 'report-declaration',
        'scope': ['TRADES', 'ORDERS', 'CASH', 'EQUITY'], 'changes': 'NONE', 'basis': 'isolated current facts'}}
    assert submit(client, declaration, 'report-declaration').status_code == 200
    for instrument in p['scope']['instruments']:
        listing = client.get('/api/market/list').json()
        if instrument not in {m['instrument'] for m in listing['members']}:
            assert client.post('/api/market/watch', json={'instrument': instrument, 'operation': 'ADD',
                'expected_list_version': listing['version']}).status_code == 200
    assert client.post('/api/funding/confirm', json=funding(single_exposure='40000.00')).status_code == 200
    command = {**method_command(), 'scope': p['scope'], 'expected_account_version': 3, 'allowed_actions': ['BUY']}
    response = client.post('/api/capabilities/grants', json=command)
    assert response.status_code == 201, response.text
    response = client.post('/api/actions/evaluate', json={})
    assert response.status_code == 201 and response.json()['decisions'], response.text
    return response.json()


def test_report_projects_real_partial_allocation_and_registered_notification_chain_without_causal_claim(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = action_package()
    p['account_version'] = p['loss_facts']['baseline_account_version'] = 3
    file = save_package(tmp_path / 'qualification.json', p)
    with TestClient(create_app(copy_donor(tmp_path / 'data'), runtime_role='API', capability_method_file=file)) as client:
        old_shadow = client.get('/api/research/shadow/' + FREEZE).json()
        evaluation = prepare_copied_actual(client, p)
        response = client.post('/api/intents/prepare', json=intent_command(evaluation))
        assert response.status_code == 201, response.text
        intent = response.json()
        later = (datetime.fromisoformat(p['required_as_of']) + timedelta(minutes=7)).isoformat()
        class ReportClock(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime.fromisoformat(later).astimezone(tz)
        monkeypatch.setattr('roll.accounts.ledger.datetime', ReportClock)
        monkeypatch.setattr('roll.accounts.ledger.now', lambda: later)
        monkeypatch.setattr('roll.decisions.intents.now', lambda: later)
        pending = client.post('/api/intents/' + intent['intent_id'] + '/declare', json={
            'state': 'OPERATION_PENDING', 'occurred_at': p['required_as_of'], 'external_order_id': 'METHOD-order',
            'idempotency_key': 'report-pending'})
        assert pending.status_code == 200, pending.text
        command = fill(3, 'report-partial')
        occurred = (datetime.fromisoformat(p['required_as_of']) + timedelta(minutes=2)).isoformat()
        command['payload'].update(instrument=intent['instrument'], quantity='100', price='140.00', effective_at=occurred)
        draft = client.post('/api/account/drafts', json=command)
        assert draft.status_code == 201, draft.text
        confirmed = client.post('/api/account/confirm', json={'draft_id': draft.json()['draft_id'],
            'idempotency_key': 'report-partial', 'fill_allocations': [{'intent_id': intent['intent_id'],
                'fill_record_id': 'report-partial', 'allocated_quantity': '100', 'association_status': 'USER_CONFIRMED'}]})
        assert confirmed.status_code == 200, confirmed.text
        params = {'decision_id': intent['decision_id'], 'evaluation_id': evaluation['evaluation_id'], 'intent_id': intent['intent_id']}
        chain = client.get('/api/notifications/time-chain', params=params)
        assert chain.status_code == 200, chain.text
        url = '/api/research/reports/' + FREEZE
        report = client.get(url, params=params).json()
        assert report['execution']['notification_chain'] == chain.json()
        deviation = report['execution_deviations'][0]
        assert deviation['proposal']['quantity'] == '200'
        assert deviation['remaining_quantity'] == '100'
        assert deviation['allocations'][0]['allocated_quantity'] == '100'
        assert deviation['allocations'][0]['association_status'] == 'USER_CONFIRMED'
        assert deviation['allocation_diagnostics'][0]['reported_after_occurrence']['seconds'] == 300
        assert deviation['allocation_diagnostics'][0]['price_in_proposal_window'] is True
        assert deviation['allocation_diagnostics'][0]['fee_comparison'] == 'PARTIAL_FILL_NOT_FULL_PROPOSAL'
        assert deviation['same_strategy'] is False
        assert report['execution']['response_seconds'] is None
        assert report['comparison']['causal_attribution'] is False
        assert client.get(url + '/export', params=params).json() == report
        assert 'USER_CONFIRMED' in client.get(url + '/export', params={**params, 'format': 'text'}).text
        assert client.get(url, params={'decision_id': intent['decision_id']}).status_code == 422
        assert client.get(url, params={**params, 'evaluation_id': 'unknown'}).status_code == 404
        assert client.get('/api/research/shadow/' + FREEZE).json() == old_shadow
        capture('partial-fill-late-report-300-seconds', report)


def test_run_audit_counts_existing_shadow_records_and_locates_their_saved_revisions(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    clock = lambda: datetime.fromisoformat('2026-10-07T10:00:00+08:00')
    with TestClient(create_app(copy_donor(tmp_path / 'data'), review_clock=clock)) as client:
        response = client.post('/api/reviews/tasks', json={'mode': 'ON_DEMAND'})
        assert response.status_code == 202, response.text
        task = wait_result(client, response.json()['task_id'])
        metric = client.get('/api/reviews/audits/' + task['audit_id']).json()['metrics']['shadow_records']
        assert metric['status'] == 'CHECKED', metric
        assert metric['value'] == 2
        assert [r['revision'] for r in metric['records']] == [1, 2]
        assert all(r['freeze_id'] == FREEZE and r['namespace'] == 'SHADOW' for r in metric['records'])
        assert metric['account_conditional_records'] == 1
        assert client.get('/api/research/reports/' + FREEZE).json()['platform']['state']['revision'] == 2
        capture('runtime-shadow-records', metric)


def test_json_text_curve_and_research_link_share_sources_without_any_formal_outlet(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    with TestClient(create_app(copy_donor(tmp_path / 'data'), runtime_role='API')) as client:
        url = '/api/research/reports/' + FREEZE
        original = client.get(url).json()
        response = client.get(url + '/export?format=json')
        assert response.status_code == 200, response.text
        assert response.headers['content-disposition'].startswith('attachment;')
        assert response.json() == original
        text = client.get(url + '/export?format=text')
        assert text.status_code == 200 and text.headers['content-type'].startswith('text/plain')
        assert all(label in text.text for label in ['ACTUAL', 'HISTORICAL', 'SHADOW', 'ACCOUNT_CONDITIONAL', FREEZE, 'NOT_COMPARABLE', 'NOT_GRANTED'])
        assert original['curves']['SHADOW']['points'] == original['platform']['state']['curve']
        assert original['curves']['HISTORICAL']['continuous_performance'] is False
        assert original['curves']['ACCOUNT_CONDITIONAL']['continuous_performance'] is False
        assert original['research_link'] == '/#research=' + FREEZE
        assert original['notification_allowed'] is False
        assert client.post('/api/actions/evaluate', json={'report_id': FREEZE, 'probability': '.99'}).status_code == 422
        refused = client.post('/api/intents/prepare', json={'decision_id': FREEZE,
            'expected_evaluation_id': FREEZE, 'expected_account_version': 1,
            'expected_funding_version': 0, 'expected_grant_version': 0,
            'price_yuan': '10', 'idempotency_key': 'research-not-intent'})
        assert refused.status_code in {404, 409}, refused.text
        assert client.post('/api/notifications', json={'source': 'RESEARCH', 'report_id': FREEZE, 'action': 'BUY'}).status_code == 405
        assert client.get('/api/intents').json()['intents'] == []
        assert client.get('/api/notifications').json()['notifications'] == []
        assert client.post('/api/formal/evaluate', json={}).status_code == 403
        assert client.get(url).json() == original


def test_saved_actual_nav_uses_held_shares_and_preserves_the_original_snapshot_after_late_fees(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    with TestClient(create_app(copy_donor(tmp_path / 'data'), runtime_role='API', market_transport=quote_transport())) as client:
        original = client.get('/api/research/shadow/' + FREEZE).json()
        account = client.get('/api/account').json()
        assert account['version'] == 1 and account['cash_balance'] == '100000.10'
        assert account['positions'][0]['quantity'] == '300'
        acquire(client)  # fixed METHOD quote12, no source HTTP/provider
        valuation = publish(client)
        assert valuation['facts']['net_assets'] == '103600.10'
        selected = '/api/research/reports/' + FREEZE + '?valuation_id=' + valuation['valuation_id']
        response = client.get(selected)
        assert response.status_code == 200, response.text
        report = response.json()
        assert report['actual']['valuation'] == valuation
        assert report['actual']['net_assets'] == '103600.10'
        assert report['comparison']['status'] == 'NOT_COMPARABLE'
        command = fill(1, 'late-fee-fill', fee_status='PROVISIONAL')
        command['payload'].update(quantity='100', price='10.10', effective_at='2026-10-07T12:00:00+08:00')
        assert submit(client, command, 'partial-fill').status_code == 200
        pending = publish(client)
        assert pending['facts']['net_assets'] is None
        assert submit(client, fee_adjustment(2, '5.00', 'late-fee-fill'), 'fee').status_code == 200
        current = publish(client)
        assert current['facts']['net_assets'] == '103785.10'
        assert client.get(selected).json() == report
        assert client.get('/api/research/reports/' + FREEZE + '?valuation_id=' + current['valuation_id']).json()['actual']['net_assets'] == '103785.10'
        assert client.get('/api/research/shadow/' + FREEZE).json() == original
        capture('actual-saved-nav-late-fees', {'original_report': report, 'pending_fees': pending, 'current_valuation': current})

def test_saved_report_keeps_four_namespaces_and_never_turns_cash_into_actual_nav(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    directory = copy_donor(tmp_path / 'data')
    with TestClient(create_app(directory, runtime_role='API')) as client:
        shadow = client.get('/api/research/shadow/' + FREEZE)
        assert shadow.status_code == 200, shadow.text
        assert shadow.json()['revision'] == 2
        original = shadow.json()
        query = client.get('/api/research/reports/' + FREEZE)
        assert query.status_code == 200, query.text
        report = query.json()
        assert report['source_kind'] == 'RESEARCH'
        assert set(report['namespaces']) == {'ACTUAL', 'HISTORICAL', 'SHADOW', 'ACCOUNT_CONDITIONAL'}
        assert report['platform']['state'] == original
        assert report['actual']['valuation'] is None
        assert report['actual']['net_assets'] is None
        assert report['comparison']['status'] == 'NOT_COMPARABLE'
        assert report['system_usable'] is False and report['prepare_allowed'] is False
        assert report['qualification']['capability'] == 'NOT_GRANTED'
        assert client.get('/api/research/shadow/' + FREEZE).json() == original
