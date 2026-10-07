from fastapi.testclient import TestClient
from roll.app import create_app
import pytest


def establish(client, instruments=None):
    draft = client.post('/api/account/drafts', json={
        'kind': 'BASELINE', 'expected_account_version': 0,
        'payload': {'effective_at': '2026-10-07T00:00:00+08:00', 'source': '脱敏券商快照',
                    'cash_balance': '10000.00', 'broker_available': None, 'broker_frozen': None,
                    'withdrawable': None, 'permission_profile': [],
                    'positions': [{'instrument': i, 'quantity': '100', 'sellable_quantity': None,
                                   'reference_cost': None} for i in instruments or ['BSE:920001']]}})
    assert draft.status_code == 201, draft.text
    response = client.post('/api/account/confirm', json={
        'draft_id': draft.json()['draft_id'], 'idempotency_key': 'baseline'})
    assert response.status_code == 200, response.text


def test_holdings_watch_edits_and_membership_versions_survive_restart(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        initial = client.get('/api/market/list').json()
        assert initial['account_version'] == 1
        assert initial['members'][0]['instrument'] == 'BSE:920001'
        assert initial['members'][0]['holding']['quantity'] == '100'
        added = client.post('/api/market/watch', json={
            'operation': 'ADD', 'instrument': 'SSE:600519',
            'expected_list_version': initial['version']})
        assert added.status_code == 200, added.text
        after = added.json()
        assert after['version'] > initial['version']
        assert [m['instrument'] for m in after['members']] == ['BSE:920001', 'SSE:600519']
        assert client.get(f"/api/market/list/versions/{initial['version']}").json() == initial
        removed = client.post('/api/market/watch', json={
            'operation': 'REMOVE', 'instrument': 'BSE:920001',
            'expected_list_version': after['version']})
        assert removed.status_code == 200
        assert removed.json()['members'][0]['holding']['quantity'] == '100'
    with TestClient(create_app(tmp_path)) as client:
        current = client.get('/api/market/list').json()
        assert len(current['members']) == 2
        assert client.get(f"/api/market/list/versions/{initial['version']}").json() == initial


def test_explicit_identity_and_account_permission_remain_distinct(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client, ['SSE:600519', 'BSE:920001'])
        initial = client.get('/api/market/list').json()
        sse = next(m for m in initial['members'] if m['instrument'] == 'SSE:600519')
        assert sse['identity']['board'] == 'UNKNOWN'  # no code/name guesses
        assert sse['rule']['implementation_status'] == 'UNSUPPORTED'
        response = client.post('/api/market/identities', json={
            'instrument': 'SSE:600519', 'exchange': 'SSE', 'board': 'MAIN',
            'instrument_type': 'STOCK', 'name': '贵州茅台', 'basis': '脱敏券商证券详情明确主板A股',
            'effective_at': '2026-10-07T00:00:00+08:00'})
        assert response.status_code == 200, response.text
        current = client.get('/api/market/list').json()
        sse = next(m for m in current['members'] if m['instrument'] == 'SSE:600519')
        assert sse['rule']['implementation_status'] == 'ADAPTED'
        assert sse['rule']['normal_price_limit_percent'] == '10'
        assert sse['account_permission']['status'] == 'UNKNOWN'
        assert sse['current_status']['state'] == 'UNKNOWN'
        assert 'ACCOUNT_PERMISSION_UNKNOWN' in sse['limitations']
        assert 'CURRENT_STATUS_UNKNOWN' in sse['limitations']
        assert sse['holding']['quantity'] == '100'
        assert sse['identity']['source']['kind'] == 'USER_CONFIRMED'
        assert client.get(f"/api/market/list/versions/{initial['version']}").json() == initial


def test_overflow_never_hides_assets_and_scope_rejects_external_stocks_and_indices(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client, [f'BSE:{920000+n}' for n in range(21)])
        listing = client.get('/api/market/list').json()
        assert len(listing['members']) == 21 and listing['over_limit'] is True
        assert client.post('/api/market/watch', json={'operation': 'ADD', 'instrument': 'SSE:600519',
            'expected_list_version': listing['version']}).json()['detail']['code'] == 'WATCH_LIMIT'
        external = client.post('/api/market/scope/check', json={
            'instruments': ['SSE:600519'], 'purpose': 'OBSERVATION'})
        assert external.status_code == 403
        assert external.json()['detail']['code'] == 'OUTSIDE_FINITE_LIST'
        assert client.post('/api/market/scope/check', json={
            'instruments': ['BSE:920001'], 'purpose': 'OBSERVATION'}).status_code == 200
        assert client.post('/api/market/watch', json={'operation': 'ADD', 'instrument': 'SSE:000001',
            'expected_list_version': listing['version']}).status_code == 422
        assert all(i['trading_capability'] == 'NONE' for i in listing['background_indices'])
        assert client.post('/api/market/scope/check', json={
            'instruments': ['SSE:000001'], 'purpose': 'RESEARCH'}).status_code == 403


@pytest.mark.parametrize('exchange', ['SSE', 'SZSE'])
def test_archived_exchange_calendar_handles_holidays_stages_timezones_and_gaps(tmp_path, exchange):
    with TestClient(create_app(tmp_path)) as client:
        holiday = client.get('/api/market/calendar', params={'exchange': exchange, 'date': '2026-10-07'}).json()
        assert holiday['is_trading_day'] is False and holiday['phase'] == 'CLOSED'
        assert holiday['next_trading_day'] == '2026-10-08'
        weekend = client.get('/api/market/calendar', params={'exchange': exchange, 'date': '2026-10-10'}).json()
        assert weekend['reason'] == 'WEEKEND'  # a government makeup workday is not an exchange session
        lunch = client.get('/api/market/calendar', params={'exchange': exchange, 'date': '2026-10-08',
            'at': '2026-10-08T04:00:00Z'}).json()
        assert lunch['phase'] == 'LUNCH_BREAK' and lunch['timezone'] == 'Asia/Shanghai'
        fixed = client.get('/api/market/calendar', params={'exchange': exchange, 'date': '2026-10-08',
            'at': '2026-10-08T15:10:00+08:00'}).json()
        assert fixed['phase'] == 'FIXED_PRICE'
        assert client.get('/api/market/calendar', params={'exchange': exchange, 'date': '2027-01-01'}).json()['is_trading_day'] is None
        assert client.get('/api/market/calendar', params={'exchange': 'BSE', 'date': '2026-10-08'}).json()['coverage'] == 'UNKNOWN'
        assert client.get('/api/market/calendar', params={'exchange': exchange, 'date': '2026-10-08',
            'at': '2026-10-08T12:00:00'}).status_code == 422
        source = holiday['source']
        raw = client.get(f"/api/market/sources/{source['id']}/raw")
        import hashlib
        assert raw.status_code == 200
        assert hashlib.sha256(raw.content).hexdigest() == source['sha256']
        assert '10月7日' in raw.content.decode('utf-8')


def test_rule_versions_remainder_limits_and_resale_follow_only_known_calendar(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        star = client.get('/api/market/rules', params={'exchange': 'SSE', 'board': 'STAR', 'date': '2026-10-08'}).json()
        assert star['buy_minimum'] == '200' and star['buy_increment'] == '1'
        assert star['limit_order_maximum'] == '100000' and star['price_tick_yuan'] == '0.01'
        assert star['normal_price_limit_percent'] == '20'
        chinext = client.get('/api/market/rules', params={'exchange': 'SZSE', 'board': 'CHINEXT'}).json()
        assert chinext['buy_increment'] == '100' and chinext['limit_order_maximum'] == '300000'
        old = client.get('/api/market/rules', params={'exchange': 'SSE', 'board': 'MAIN', 'date': '2026-07-05'}).json()
        assert old['implementation_status'] == 'UNSUPPORTED'
        result = client.get('/api/market/resale-date', params={
            'exchange': 'SSE', 'board': 'MAIN', 'buy_date': '2026-09-30'}).json()
        assert result['earliest_sell_date'] == '2026-10-08'  # holiday and actual T+1 session
        missing = client.get('/api/market/resale-date', params={
            'exchange': 'SSE', 'board': 'MAIN', 'buy_date': '2026-12-31'}).json()
        assert missing['earliest_sell_date'] is None


def test_unopened_account_transitions_preserve_membership_and_identity_knowledge_time(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client, ['SSE:600519'])
        # Two confirmations occur without opening the market page.
        for version, state in [(1, 'NOT_OPEN'), (2, 'OPEN')]:
            draft = client.post('/api/account/drafts', json={'kind': 'PERMISSIONS',
                'expected_account_version': version, 'payload': {
                    'effective_at': '2026-10-07T00:00:00+08:00', 'source': '券商权限快照',
                    'permission_profile': [{'market': 'SSE', 'board': 'MAIN', 'status': state, 'basis': '用户确认'}]}})
            assert client.post('/api/account/confirm', json={'draft_id': draft.json()['draft_id'],
                'idempotency_key': f'permissions-{version}'}).status_code == 200
        client.post('/api/market/identities', json={'instrument': 'SSE:600519', 'exchange': 'SSE',
            'board': 'MAIN', 'instrument_type': 'STOCK', 'name': '已核对证券', 'basis': '证券详情',
            'effective_at': '2026-10-07T00:00:00+08:00'})
        history = client.get('/api/market/history').json()['account_membership_history']
        assert [h['account_version'] for h in history] == [3, 2, 1]
        assert all(h['members'][0]['instrument'] == 'SSE:600519' for h in history)
        assert all(h['members'][0]['identity'] is None for h in history)
        current = client.get('/api/market/list').json()
        assert current['members'][0]['account_permission']['status'] == 'OPEN'
        assert current['members'][0]['new_trade_use'] == 'RESTRICTED'
        conflict = client.post('/api/market/watch', json={'operation': 'ADD',
            'instrument': 'SZSE:000001', 'expected_list_version': 0})
        assert conflict.status_code == 409 and conflict.json()['detail']['code'] == 'LIST_VERSION_CONFLICT'


def test_unopened_actual_fill_membership_transitions_are_not_retroactive_market_observations(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client, ['SSE:600519'])
        for version, instrument, direction, quantity in [(1, 'SSE:600000', 'BUY', '300'), (2, 'SSE:600519', 'SELL', '100')]:
            draft = client.post('/api/account/drafts', json={'kind': 'FILL', 'expected_account_version': version,
                'payload': {'effective_at': '2026-10-07T11:00:00+08:00', 'source': '脱敏真实成交回报',
                    'instrument': instrument, 'direction': direction, 'quantity': quantity, 'price': '10.00',
                    'record_id': f'membership-{version}', 'fill_id': f'membership-{version}', 'order_id': None,
                    'behavior_context': 'NO_RECOMMENDATION', 'broker_available_after': None,
                    'fee': {'status': 'KNOWN', 'amount': '5.00', 'reserve_amount': None, 'basis': '券商回报'}}})
            assert draft.status_code == 201 and draft.json()['status'] == 'READY', draft.text
            assert client.post('/api/account/confirm', json={'draft_id': draft.json()['draft_id'],
                'idempotency_key': f'membership-{version}'}).status_code == 200
        history = client.get('/api/market/history').json()['account_membership_history']
        by_version = {h['account_version']: h for h in history}
        assert [[m['instrument'] for m in by_version[v]['members']] for v in [1, 2, 3]] == [
            ['SSE:600519'], ['SSE:600000', 'SSE:600519'], ['SSE:600000']]
        from datetime import datetime
        assert all(datetime.fromisoformat(h['materialized_at']) >= datetime.fromisoformat(h['confirmed_at']) for h in history)
        assert all(h['basis'] == 'CONFIRMED_ACCOUNT_VERSION' for h in history)
        assert all(m['identity'] is None for h in history for m in h['members'])
        assert all('price' not in h and 'coverage' not in h and 'forecast' not in h for h in history)
        assert client.get('/api/market/list').json()['members'][0]['holding']['quantity'] == '300'


