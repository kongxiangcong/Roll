from fastapi.testclient import TestClient
from roll.app import create_app


def request(client, **changes):
    data = dict(instrument='SSE:600362', entry_date='2013-07-23', exit_date='2013-07-25',
                quantity=100, consumer_cutoff='2026-10-09T16:00:00+08:00')
    data.update(changes)
    return client.post('/api/research/cash-rights/assess', json=data)


def test_registered_cash_dividend_is_receivable_before_payment_not_account_cash(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        before = client.get('/api/account').json()
        response = request(client)
        assert response.status_code == 200, response.text
        result = response.json()
        event = result['events'][0]
        assert event['gross_entitlement_yuan'] == '50.00'
        assert event['final_tax_yuan'] == '10.00'
        assert event['net_entitlement_yuan'] == '40.00'
        assert event['cash_paid_by_exit_yuan'] == '0.00'
        assert event['net_receivable_at_exit_yuan'] == '40.00'
        assert result['scorable'] is False
        assert result['coverage'] == 'INCOMPLETE'
        assert result['account_authority'] == 'NONE'
        assert client.get('/api/account').json() == before


def test_record_close_entitlement_does_not_use_ex_reference_deduction(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        result = request(client, entry_date='2024-07-23', exit_date='2024-07-25').json()
        event = result['events'][0]
        assert event['gross_cash_yuan_per_eligible_share'] == '0.60'
        assert event['differentiated_ex_reference_deduction_yuan_per_listed_share'] == '0.5970'
        assert event['gross_entitlement_yuan'] == '60.00'
        assert event['final_tax_yuan'] == '12.00'
        assert event['cash_paid_by_exit_yuan'] == '60.00'
        assert event['supplementary_tax_liability_yuan'] == '12.00'
        assert event['net_economic_entitlement_yuan'] == '48.00'
        assert request(client, entry_date='2024-07-24', exit_date='2024-07-25').json()['events'] == []
        assert request(client, entry_date='2024-07-22', exit_date='2024-07-23').json()['events'] == []


def test_natural_month_and_year_include_anniversary_exit_and_pre2015_long_tax(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        # Independent boundary literals: June23 to July23 is exactly one natural month.
        short = request(client, entry_date='2024-06-23', exit_date='2024-07-23').json()
        assert short['events'] == []  # Exit at record open forfeits this dividend.
        for entry, exit, expected in [
            ('2024-06-24','2024-07-24','0.20'),
            ('2024-06-24','2024-07-25','0.10'),
            ('2023-07-25','2024-07-25','0.10'),
            ('2023-07-25','2024-07-26','0'),
            ('2012-07-25','2013-07-26','0.05')]:
            result = request(client, entry_date=entry, exit_date=exit).json()
            assert result['events'][-1]['final_tax_rate'] == expected


def test_unresolved_calendar_anniversary_and_same_day_payment_are_not_silently_filled(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        unknown = request(client, entry_date='2024-01-31', exit_date='2024-07-25').json()
        assert 'TAX_CALENDAR_ANNIVERSARY_UNDEFINED' in unknown['blockers']
        assert unknown['events'][0]['final_tax_yuan'] is None
        same_day = request(client, entry_date='2024-07-23', exit_date='2024-07-24').json()['events'][0]
        assert same_day['cash_payment_at_exit_open'] == 'INTRADAY_UNKNOWN'
        assert same_day['cash_paid_by_exit_yuan'] == '0.00'
        assert same_day['net_receivable_at_exit_yuan'] == '48.00'


def test_cutoff_and_scope_do_not_certify_past_available_or_complete_no_action(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        past = request(client, consumer_cutoff='2013-07-30T16:00:00+08:00').json()
        assert past['events'] == []
        assert 'SOURCE_NOT_RECEIVED_AT_CONSUMER_CUTOFF' in past['blockers']
        current = request(client).json()['events'][0]
        assert current['historical_prediction_admissibility'] == 'NOT_ESTABLISHED'
        assert current['source']['received_at'].startswith('2026-10-09')
        assert current['source']['publication_precision'] == 'DATE'
        outside = request(client, instrument='SSE:600000').json()
        assert outside['scorable'] is False
        assert outside['coverage'] == 'UNKNOWN'
        for changes in [dict(quantity=True),dict(quantity=0),dict(quantity=1.5),
                        dict(consumer_cutoff='2026-10-09T16:00:00'),
                        dict(exit_date='2013-07-23'),dict(consumer_cutoff='2013-07-24T16:00:00+08:00'),
                        dict(coverage_verified=True)]:
            assert request(client, **changes).status_code == 422


def test_changed_original_is_rejected_and_restart_replays_same_reference(tmp_path, monkeypatch):
    from pathlib import Path
    import shutil
    import roll.research.corporate_actions as rights
    reference = tmp_path / 'deployment-reference'
    shutil.copytree(rights.REFERENCE, reference)
    monkeypatch.setattr(rights, 'REFERENCE', reference)
    with TestClient(create_app(tmp_path / 'runtime')) as client:
        expected = request(client).json()
    with TestClient(create_app(tmp_path / 'runtime')) as client:
        assert request(client).json() == expected
        original = next(reference.glob('*.pdf'))
        raw = original.read_bytes()
        original.write_bytes(raw + b'changed')
        response = request(client)
        assert response.status_code == 409
        assert response.json()['detail']['code'] == 'CASH_RIGHTS_SOURCE_INTEGRITY_FAILED'
        original.write_bytes(raw)
        (reference/'sources.json').write_bytes(b'{}')
        assert request(client).status_code == 409


def test_missing_manifest_returns_actionable_integrity_failure(tmp_path, monkeypatch):
    import roll.research.corporate_actions as rights
    monkeypatch.setattr(rights, 'REFERENCE', tmp_path / 'missing-source-directory')
    with TestClient(create_app(tmp_path / 'runtime'), raise_server_exceptions=False) as client:
        response = request(client)
        assert response.status_code == 409, response.text
        assert response.json()['detail']['code'] == 'CASH_RIGHTS_SOURCE_INTEGRITY_FAILED'


def test_cutoff_day_uses_exchange_timezone_not_request_timezone(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        #00:30 Shanghai July25, still July24 UTC; source retrieval not yet available.
        response = request(client, consumer_cutoff='2013-07-24T16:30:00+00:00')
        assert response.status_code == 200, response.text
        assert response.json()['scorable'] is False


def test_cent_rounding_conserves_final_tax_and_payment_withholding(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        event = request(client, quantity=1, exit_date='2013-08-01').json()['events'][0]
        assert event['final_tax_yuan'] == '0.10'
        assert event['initial_payment_withholding_yuan'] == '0.03'
        assert event['supplementary_tax_liability_yuan'] == '0.07'
        assert event['cash_paid_by_exit_yuan'] == '0.47'
        assert event['net_economic_entitlement_yuan'] == '0.40'


def test_pre2015_registration_retains_old_tax_after2015_policy_change(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        result = request(client, entry_date='2015-07-15', exit_date='2016-07-18').json()
        event = result['events'][0]
        assert event['record_date'] == '2015-07-16'
        assert event['tax_regime'] == '2012_85'
        assert event['final_tax_rate'] == '0.05'
        assert event['final_tax_yuan'] == '1.00'
        assert event['net_economic_entitlement_yuan'] == '19.00'
