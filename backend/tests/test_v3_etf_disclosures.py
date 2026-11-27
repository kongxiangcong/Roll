"""Verify public ETF disclosure reads using original materials and separate synthetic cases."""

from pathlib import Path

from roll.v3.cli import run


PROOF = Path(__file__).with_name('fixtures') / 'etf_disclosures_510300.json'
DAY = '2026-11-27'
AFTER_RECEIPT = '2026-11-27T17:00:00+08:00'
CLI = ('market', 'etf', 'disclosures')


def test_disclosure_snapshot_replays_original_date_only_evidence_at_shanghai_midnight(tmp_path):
    assert run((*CLI, 'import', str(PROOF)), data_dir=tmp_path)['appended'] == 3
    assert run((*CLI, 'import', str(PROOF)), data_dir=tmp_path)['appended'] == 0
    snapshot = run((*CLI, 'freeze', '--end', DAY, '--as-of', AFTER_RECEIPT,
                    '--use-mode', 'RECONSTRUCTED_RESEARCH'), data_dir=tmp_path)['snapshot_id']

    def read(day, cutoff):
        return run((*CLI, 'read', snapshot, '--date', day, '--cutoff', cutoff), data_dir=tmp_path)

    assert not read('2026-03-31', '2026-03-31T23:59:59+08:00')['rule_pool']['members']
    first_available = read('2026-04-01', '2026-04-01T00:00:00+08:00')
    assert [fund['symbol'] for fund in first_available['rule_pool']['members']] == ['510300.SH']
    fund = first_available['funds']['510300.SH']
    assert {row['holder']: (row['shares'], row['listed_shares_pct']) for row in fund['holders']} == {
        '中央汇金投资有限责任公司': ('35654598859', '40.14'),
        '中央汇金资产管理有限责任公司': ('37858474974', '42.62'),
    }
    assert fund['latest_report']['disclosed_at'] is None
    assert fund['latest_report']['selected_available_at'] == '2026-03-31T16:00:00.000000+00:00'
    assert fund['latest_report']['source_ref'].endswith('510300_20260331_W6CZ.pdf')

    later = read(DAY, AFTER_RECEIPT)
    fund = later['funds']['510300.SH']
    assert fund['latest_report']['report_period_end'] == '2026-06-30'
    assert fund['latest_report']['comparable_named_holders'] is False
    assert fund['basis_report']['report_period_end'] == '2025-12-31'
    assert all(row['current_shares'] is None for row in fund['holders'])
    assert fund['events'] == []
    event, = later['events']
    assert event['scope'] == 'etf_category'
    assert event['source_ref'].endswith('1002841.shtml')
    assert all(event[field] is None for field in ('symbol', 'index_code', 'event_trade_date', 'amount_cny', 'shares'))

    assert read('2025-04-07', '2025-04-07T23:59:59+08:00')['events'] == []
    assert len(read('2025-04-08', '2025-04-08T00:00:00+08:00')['events']) == 1


def test_live_disclosures_respect_receipt_and_publication_and_keep_old_snapshot(tmp_path):
    import json

    run((*CLI, 'import', str(PROOF)), data_dir=tmp_path)
    original = run((*CLI, 'freeze', '--end', DAY, '--as-of', AFTER_RECEIPT),
                   data_dir=tmp_path)['snapshot_id']

    def read(snapshot, cutoff):
        return run((*CLI, 'read', snapshot, '--date', DAY, '--cutoff', cutoff), data_dir=tmp_path)

    before_receipt = read(original, '2026-11-27T15:32:37+08:00')
    assert not before_receipt['rule_pool']['members']
    assert before_receipt['funds']['510300.SH']['latest_report'] is None
    assert before_receipt['events'][0]['scope'] == 'etf_category'
    on_receipt = read(original, '2026-11-27T15:32:38+08:00')
    assert on_receipt['funds']['510300.SH']['basis_report']['report_id'] == '510300-2025-annual'
    assert not on_receipt['rule_pool']['members']

    def synthetic_report(symbol, names, received, disclosed, revision='v1'):
        return {
            'series': 'etf_holding_report', 'item_id': f'synthetic-{symbol}', 'symbol': symbol,
            'trade_date': '2026-09-30', 'source': 'fund_manager',
            'source_ref': f'https://example.test/synthetic/{symbol}',
            'available_evidence': '合成时点测试', 'received_at': f'{DAY}T{received}+08:00',
            'available_at': f'{DAY}T{disclosed}+08:00', 'revision': revision,
            'payload': {'title': '合成定期报告', 'comparable_named_holders': True,
                        'holders': [{'holder': name} for name in names]},
        }

    name = '中央汇金投资有限责任公司'
    fixture = tmp_path / 'synthetic.json'
    fixture.write_text(json.dumps([
        synthetic_report('510300.SH', [name], '16:10:00', '16:15:00'),
        synthetic_report('510230.SH', [name], '16:10:00', '16:15:00'),
        synthetic_report('510300.SH', [name + '（代持）'], '16:30:00', '16:25:00', 'v2'),
    ]), encoding='utf-8')
    run((*CLI, 'import', str(fixture)), data_dir=tmp_path)
    revised = run((*CLI, 'freeze', '--end', DAY, '--as-of', AFTER_RECEIPT),
                  data_dir=tmp_path)['snapshot_id']

    previous = read(revised, f'{DAY}T16:14:59+08:00')
    assert previous['funds']['510300.SH']['basis_report']['report_id'] == '510300-2025-annual'
    updated = read(revised, f'{DAY}T16:15:00+08:00')
    assert [row['symbol'] for row in updated['rule_pool']['members']] == ['510300.SH']
    assert updated['funds']['510230.SH']['holders'][0]['status'] == 'listed'
    known, absent = updated['funds']['510300.SH']['holders']
    assert (known['holder'], known['status'], known['shares']) == (name, 'listed', None)
    assert (absent['status'], absent['shares'], absent['current_shares']) == ('not_listed_in_report', None, None)
    assert read(revised, f'{DAY}T16:29:59+08:00')['rule_pool']['member_count'] == 1
    replaced = read(revised, f'{DAY}T16:30:00+08:00')
    assert not replaced['rule_pool']['members']
    assert {row['status'] for row in replaced['funds']['510300.SH']['holders']} == {'not_listed_in_report'}
    assert read(original, AFTER_RECEIPT)['rule_pool']['member_count'] == 1


def test_daily_workbench_shows_fixed_and_as_of_rule_pool_with_separate_evidence(tmp_path):
    import json

    from fastapi.testclient import TestClient

    from roll.v3.web import create_app

    run((*CLI, 'import', str(PROOF)), data_dir=tmp_path)
    data = [{
        'symbol': '510300.SH', 'series': series, 'trade_date': day, 'source': source,
        'source_ref': 'https://example.test/synthetic-etf-flow',
        'available_evidence': '合成的全体持有人基金输入',
        'received_at': f'{DAY}T15:40:00+08:00', 'unit': unit,
        'payload': {'value': value, 'verified': True},
    } for series, day, source, unit, value in [
        ('etf_shares', '2026-11-26', 'sse', '份', '100000000'),
        ('etf_shares', DAY, 'sse', '份', '200000000'),
        ('etf_nav', DAY, 'fuyao', '元/份', '2'),
    ]]
    flow = tmp_path / 'synthetic-flow.json'
    flow.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    run(('market', 'etf', 'import', str(flow)), data_dir=tmp_path)
    with TestClient(create_app(tmp_path)) as browser:
        result = browser.get('/api/market/etf', params={'trade_date': DAY, 'as_of': AFTER_RECEIPT})
        assert result.is_success, result.text
        report = result.json()
        older = browser.get('/api/market/etf', params={
            'trade_date': '2026-11-26', 'as_of': '2026-11-26T23:59:59+08:00',
        }).json()

    assert report['summary']['expected_count'] == 35
    assert report['summary']['flow_cny'] == '200000000'
    rules = report['comparison_baskets']['disclosed']
    assert rules['basket']['version'] == 'huijin-disclosed-wide-v1'
    assert rules['summary']['expected_count'] == 1
    assert rules['summary']['flow_cny'] == '200000000'
    assert [fund['symbol'] for fund in rules['funds']] == ['510300.SH']
    disclosure = report['disclosures']['funds']['510300.SH']
    assert disclosure['basis_report']['report_period_end'] == '2025-12-31'
    assert disclosure['events'] == []
    assert report['disclosures']['events'][0]['scope'] == 'etf_category'
    assert older['comparison_baskets']['disclosed']['summary']['expected_count'] == 0
    assert older['disclosures']['event_status'] == 'no_verified_event'


def test_frozen_daily_report_pins_disclosure_receipts_and_rule_pool(tmp_path):
    from fastapi.testclient import TestClient

    from roll.v3.web import create_app

    params = {'trade_date': DAY, 'as_of': AFTER_RECEIPT}
    with TestClient(create_app(tmp_path)) as browser:
        response = browser.post('/api/market/etf/reports', json=params)
        assert response.is_success, response.text
        frozen = response.json()
        assert frozen['snapshot']['selection_rules_version'] == 'market-etf-disclosures-v1'
        assert frozen['disclosures']['rule_pool']['member_count'] == 0
        assert frozen['disclosures']['events'] == []

        run((*CLI, 'import', str(PROOF)), data_dir=tmp_path)
        current = browser.get('/api/market/etf', params=params).json()
        assert current['disclosures']['rule_pool']['member_count'] == 1
        assert current['disclosures']['events'][0]['scope'] == 'etf_category'
        assert browser.get(f"/api/market/etf/reports/{frozen['report_id']}").json() == frozen
