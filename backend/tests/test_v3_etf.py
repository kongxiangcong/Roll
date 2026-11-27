import json

from roll.v3.cli import run


def command(data_dir, *args):
    return run(['market', 'etf', *args], data_dir=data_dir)


def observation(series, date, value, source, **extra):
    unit = {'etf_shares': '份', 'etf_nav': '元/份', 'etf_split': '新份/旧份'}[series]
    item = {
        'series': series, 'symbol': '159915.SZ', 'trade_date': date, 'source': source,
        'source_ref': f'https://example.org/{source}/{date}',
        'available_evidence': '合成测试记录',
        'received_at': '2025-07-22T20:00:00+08:00', 'unit': unit,
        'payload': {'value': value, 'verified': True},
    }
    return {**item, **extra}


def ingest(data_dir, *rows):
    path = data_dir / 'observations.json'
    path.write_text(json.dumps(rows), encoding='utf-8')
    return command(data_dir, 'import', str(path))


def freeze(data_dir, day='2025-07-22', *options):
    return command(data_dir, 'freeze', '159915.SZ', '--start', day, '--end', day,
                   *options)['snapshot_id']


def read(data_dir, snapshot_id, day='2025-07-22', *options):
    return command(data_dir, 'read', snapshot_id, '159915.SZ', '--date', day, *options)


def test_etf_cli_applies_verified_split_and_keeps_frozen_input_after_revision(tmp_path):
    first = observation('etf_shares', '2025-07-21', '1000000', 'szse')
    last = observation('etf_shares', '2025-07-22', '2050000', 'szse')
    nav = observation('etf_nav', '2025-07-22', '1.2', 'fuyao')
    split = observation('etf_split', '2025-07-22', '2', 'fund_manager')

    assert ingest(tmp_path, first, last, nav, split)['appended'] == 4
    initial = freeze(tmp_path)
    assert ingest(tmp_path, first, last, nav, split)['appended'] == 0
    day = read(tmp_path, initial)
    assert day['previous_trade_date'] == '2025-07-21'
    assert day['comparable_previous_shares'] == '2000000'
    assert day['flow_cny'] == '60000.0'
    assert day['assets_cny'] == '2460000.0'
    assert day['inputs']['split']['selected']['source_ref'] == split['source_ref']

    correction = {**last, 'payload': {'value': '2000000', 'verified': True}}
    assert ingest(tmp_path, correction)['appended'] == 1
    changed = read(tmp_path, freeze(tmp_path))
    assert changed['flow_cny'] == '0.0'
    assert read(tmp_path, initial) == day


def test_etf_cli_sync_keeps_exchange_rows_when_nav_fails_and_resumes_only_missing_source(tmp_path, monkeypatch):
    import httpx

    requests = []

    def transport(request):
        requests.append(request)
        if request.url.host == 'query.sse.com.cn':
            assert 'X-api-key' not in request.headers
            day = request.url.params['STAT_DATE']
            value = {'2026-11-24': '5580000.00', '2026-11-25': '5592468.77', '2026-11-26': '5610288.77'}[day]
            return httpx.Response(200, json={'result': [
                {'STAT_DATE': day, 'SEC_CODE': '510300', 'TOT_VOL': value},
            ]})
        assert request.url.host == 'fuyao.aicubes.cn'
        assert request.url.params['nav_type'] == 'unit'
        nav_requests = sum(request.url.host == 'fuyao.aicubes.cn' for request in requests)
        if nav_requests == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={'code': 0, 'data': {'item': [
            {'nav_date': 1795536000000, 'unit_nav': '3.9718'},
            {'nav_date': 1795622400000, 'unit_nav': '3.9741'},
        ]}})

    create_client = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda: create_client(transport=httpx.MockTransport(transport)))
    monkeypatch.setenv('ROLL_ENV', 'test')
    monkeypatch.setenv('FUYAO_API_KEY', 'test-fixture')
    args = ('sync', '510300.SH', '--start', '2026-11-25', '--end', '2026-11-26')
    incomplete = command(tmp_path, *args)
    assert incomplete['appended'] >= 2
    assert {failure['source'] for failure in incomplete['failures']} == {'fuyao'}
    total_shares_requests = sum(request.url.host == 'query.sse.com.cn' for request in requests)
    reloaded = command(tmp_path, *args)
    assert not reloaded['failures']
    assert reloaded['appended'] == 2
    assert sum(request.url.host == 'query.sse.com.cn' for request in requests) == total_shares_requests
    assert reloaded['paid_requests'] == 0

    day = command(tmp_path, 'read', reloaded['snapshot']['snapshot_id'], '510300.SH', '--date', '2026-11-26')
    assert day['flow_cny'] == '708184620.000000'
    observed = day['inputs']['shares']['selected']
    assert observed['payload']['raw_value'] == '5610288.77'
    assert observed['payload']['raw_unit'] == '万份'
    assert observed['available_at'] is None
    assert observed['received_at'] > '2026-11-26T00:00:00'


def test_etf_cli_preserves_reported_dates_and_uses_only_resolved_verified_sources(tmp_path):
    prior = observation('etf_shares', '2025-07-21', '38081454936', 'szse')
    current = observation('etf_shares', '2025-07-22', '38055454936', 'szse')
    nav = observation('etf_nav', '2025-07-22', '2.5', 'fuyao')
    secondary = [
        observation('etf_shares', day, value, 'investoday', quality='date_mismatch')
        for day, value in [('2025-07-21', '38061454936'), ('2025-07-22', '38081454936')]
    ]
    ingest(tmp_path, prior, current, nav)
    ingest(tmp_path, *secondary)
    day = read(tmp_path, freeze(tmp_path))
    assert day['flow_cny'] == '-65000000.0'
    for field, offset in [('previous_shares', 0), ('shares', 1)]:
        field_inputs = day['inputs'][field]
        assert field_inputs['selected']['source'] == 'szse'
        alternative = next(row for row in field_inputs['candidates'] if row['source'] == 'investoday')
        assert alternative['payload']['source_date'] == secondary[offset]['trade_date']
        assert alternative['payload']['value'] == secondary[offset]['payload']['value']
        assert alternative['selection_quality'] == 'date_mismatch'
        assert alternative['difference'] == 'value_mismatch'

    ingest(tmp_path, {**current, 'withdrawn': True})
    missing = read(tmp_path, freeze(tmp_path))
    assert missing['flow_cny'] is None
    assert missing['missing']['shares'] == 'unverified'

    ingest(tmp_path, observation('etf_shares', '2025-07-22', '38055454936', 'source-a'))
    supplemented = read(tmp_path, freeze(tmp_path))
    assert supplemented['flow_cny'] == '-65000000.0'
    assert supplemented['inputs']['shares']['selected']['source'] == 'source-a'

    ingest(tmp_path, observation('etf_shares', '2025-07-22', '38071454936', 'source-b'))
    conflict = read(tmp_path, freeze(tmp_path))
    assert conflict['flow_cny'] is None
    assert conflict['missing']['shares'] == 'conflict'


def test_etf_cli_crosses_weekend_and_blocks_an_unverified_conversion(tmp_path):
    prior = observation('etf_shares', '2025-07-18', '1000000', 'szse')
    current = observation('etf_shares', '2025-07-21', '2000000', 'szse',
                          payload={'value': '2000000', 'verified': True, 'split_required': True})
    nav = observation('etf_nav', '2025-07-21', '1.2', 'fuyao')
    ingest(tmp_path, prior, current, nav)

    day = read(tmp_path, freeze(tmp_path, '2025-07-21'), '2025-07-21')
    assert day['previous_trade_date'] == '2025-07-18'
    assert day['flow_cny'] is None
    assert day['assets_cny'] == '2400000.0'
    assert day['missing'] == {'split': 'conversion_basis_unverified'}


def test_etf_cli_distinguishes_actual_receipt_and_date_only_disclosure_reconstruction(tmp_path):
    def filed(series, day, value, source):
        return observation(series, day, value, source, received_at='2025-07-24T20:00:00+08:00',
                           payload={'value': value, 'verified': True, 'disclosed_date': day})

    ingest(tmp_path, filed('etf_shares', '2025-07-21', '1000000', 'szse'),
           filed('etf_shares', '2025-07-22', '1500000', 'szse'),
           filed('etf_nav', '2025-07-22', '2', 'fuyao'))
    actual = freeze(tmp_path)
    history = freeze(tmp_path, '2025-07-22', '--use-mode', 'RECONSTRUCTED_RESEARCH')
    evening = ('--cutoff', '2025-07-22T23:59:59+08:00')
    next_day = ('--cutoff', '2025-07-23T00:00:00+08:00')

    assert read(tmp_path, actual, '2025-07-22', *next_day)['flow_cny'] is None
    assert read(tmp_path, history, '2025-07-22', *evening)['flow_cny'] is None
    day = read(tmp_path, history, '2025-07-22', *next_day)
    assert day['flow_cny'] == '1000000'
    assert day['inputs']['nav']['selected']['available_at'] is None
    assert day['inputs']['nav']['selected']['payload']['disclosed_date'] == '2025-07-22'
