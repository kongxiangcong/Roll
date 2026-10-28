import json

import httpx
import pytest
from fastapi.testclient import TestClient
from roll.app import create_app
from roll.market.sse_daily import HISTORY_REFERENCE, HISTORY_DAILY_SQL, UNIT_SHA, LIMIT

DAY = '2026-10-14'
STAMP = DAY + 'T18:00:00+08:00'


def response_body():
    value = json.loads((HISTORY_REFERENCE / 'a51334316a941c30047614138f201d3dd3d988a453fa754b8673ae1fd74bb113.raw').read_bytes())
    value['result'][0]['TX_DATE'] = '20261014'
    return value


def clock(monkeypatch, stamp=STAMP):
    for module in ['roll.market.sse_daily', 'roll.market.post_close_packet', 'roll.research.prospective', 'roll.market.evidence']:
        monkeypatch.setattr(module + '.now', lambda: stamp)


def start(client):
    value = client.post('/api/research/collections', json={'instrument': 'SSE:600362', 'basis': 'METHOD isolated daily statistic'}).json()
    policy = next(p for p in client.get('/api/research/collection-sources').json() if p['id'] == 'sse-dated-daily-statistic')
    assert client.post('/api/research/collection-sources/' + policy['id'] + '/policy', json={
        'enabled': True, 'expected_revision': policy['revision'], 'basis': 'Explicit METHOD source capture scope'}).status_code == 200
    return '/api/research/collections/' + value['plan_id']


def capture(client, base):
    return client.post(base + '/sse-daily/check', json={'basis': 'Host-day official statistic bounded capture'})


def test_daily_original_decimal_units_and_restart_once(tmp_path, monkeypatch):
    clock(monkeypatch); calls = []
    def supplier(request):
        calls.append(request)
        assert dict(request.url.params) == {'sqlId': HISTORY_DAILY_SQL, 'SEC_CODE': '600362',
            'TX_DATE': DAY, 'TX_DATE_MON': '', 'TX_DATE_YEAR': ''}
        return httpx.Response(200, json=response_body())
    transport = httpx.MockTransport(supplier)
    with TestClient(create_app(tmp_path, market_transport=transport, runtime_role='API')) as client:
        base = start(client); result = capture(client, base)
        assert result.status_code == 201, result.text
        saved = result.json(); fact = saved['fact']
        assert fact['volume_shares'] == '128845200.00' and fact['amount_yuan'] == '7005041400.00'
        assert fact['unit_source_hash'] == UNIT_SHA and fact['trade_date'] == DAY
        assert fact['received_at'] == fact['known_at'] == STAMP
        assert not fact['model_daily_input_allowed'] and not saved['system_usable']
        assert saved['evidence_kind'] == 'METHOD_CASE' and saved['forward_started_at'] is None
        assert saved['capture_plan']['retries'] == 0 and saved['network_calls'] == 1
        assert capture(client, base).json() == saved
        assert client.get(base + '/sse-daily-receipts').json() == [saved]
        assert client.post(base + '/post-close-packets', json={'basis': 'Register original input dependencies'}).status_code == 201
        gaps = client.get(base + '/source-gaps')
        assert gaps.status_code == 200, gaps.text
        assert gaps.json()['dated_daily_receipts'] == [saved]
        assert client.get('/api/account').json()['version'] == 0
    with TestClient(create_app(tmp_path, market_transport=transport, runtime_role='API')) as client:
        assert capture(client, base).json() == saved
    assert len(calls) == 1


@pytest.mark.parametrize('variant', ['wrong_date', 'empty', 'nonobject', 'numeric', 'error', 'prefix'])
def test_failed_raw_receipt_keeps_original_and_consumes_once(tmp_path, monkeypatch, variant):
    clock(monkeypatch); calls = []
    value = response_body()
    if variant == 'wrong_date': value['result'][0]['TX_DATE'] = '20261013'
    if variant == 'empty': value['result'] = []
    if variant == 'nonobject': value = []
    if variant == 'numeric': value['result'][0]['CLOSE_PRICE'] = 54.92
    if variant == 'error': value['actionErrors'] = ['upstream failure']
    body = b'x' * (LIMIT + 1) if variant == 'prefix' else json.dumps(value).encode()
    def supplier(request):
        calls.append(request)
        return httpx.Response(200, content=body)
    with TestClient(create_app(tmp_path, market_transport=httpx.MockTransport(supplier), runtime_role='API')) as client:
        base = start(client); result = capture(client, base)
        assert result.status_code == 201, result.text
        saved = result.json()
        assert saved['fact'] is None and saved['status'] == 'FAILED'
        archive = saved['response']['archive']
        assert client.app.state.evidence.raw(archive['sha256']).read_bytes() == body[:LIMIT]
        assert saved['response']['original_complete'] is (variant != 'prefix')
        assert capture(client, base).json() == saved and len(calls) == 1


@pytest.mark.parametrize('role', ['raw', 'units', 'receipt', 'plan'])
def test_damaged_dependency_rejects_query_and_retry(tmp_path, monkeypatch, role):
    clock(monkeypatch)
    with TestClient(create_app(tmp_path, market_transport=httpx.MockTransport(lambda _: httpx.Response(200, json=response_body())), runtime_role='API')) as client:
        base = start(client); saved = capture(client, base).json()
        sha = {'raw': saved['response']['archive']['sha256'], 'units': UNIT_SHA,
               'receipt': saved['archive']['sha256'], 'plan': saved['capture_plan_archive']['sha256']}[role]
        client.app.state.evidence.raw(sha).write_bytes(b'damaged method original')
        assert client.get(base + '/sse-daily-receipts').status_code == 409
        assert capture(client, base).status_code == 409


@pytest.mark.parametrize('stamp', [DAY + 'T14:00:00+08:00', '2026-10-17T18:00:00+08:00'])
def test_preclose_and_nontrading_refuse_before_request(tmp_path, monkeypatch, stamp):
    clock(monkeypatch, stamp); calls = []
    with TestClient(create_app(tmp_path, market_transport=httpx.MockTransport(lambda r: calls.append(r)), runtime_role='API')) as client:
        base = start(client)
        assert capture(client, base).status_code == 409
    assert calls == []


def test_pinned_daily_packet_replay_keeps_old_packet_and_original_ids(tmp_path, monkeypatch):
    clock(monkeypatch); calls = []
    monkeypatch.setattr('roll.market.post_close_packet.now', lambda: STAMP)
    def supplier(request):
        calls.append(request); return httpx.Response(200, json=response_body())
    with TestClient(create_app(tmp_path, market_transport=httpx.MockTransport(supplier), runtime_role='API')) as client:
        base = start(client); receipt = capture(client, base).json()
        predecessor = client.post(base + '/post-close-packets', json={'basis': 'Old packet before daily successor'}).json()
        result = client.post(base + '/sse-daily-packets', json={'predecessor_packet_id': predecessor['packet_id'],
            'receipt_ids': [receipt['receipt_id']], 'basis': 'Fixed daily source IDs'})
        assert result.status_code == 201, result.text
        saved = result.json()
        assert saved['predecessor'] == predecessor and saved['daily_statistic_facts'] == [receipt['fact']]
        assert not saved['forward_admissible'] and saved['forward_started_at'] is None
        assert client.post('/api/research/post-close-packets/' + saved['packet_id'] + '/replay').json()['matches_original']
        assert client.post('/api/research/post-close-packets/' + predecessor['packet_id'] + '/replay').json()['matches_original']
        for ids in [[receipt['receipt_id']] * 2, ['missing-receipt']]:
            assert client.post(base + '/sse-daily-packets', json={'predecessor_packet_id': predecessor['packet_id'],
                'receipt_ids': ids, 'basis': 'Invalid fixed IDs'}).status_code == 409
    with TestClient(create_app(tmp_path, market_transport=httpx.MockTransport(supplier), runtime_role='API')) as client:
        assert client.get(base + '/sse-daily-packets/' + saved['packet_id']).json() == saved
        assert len(calls) == 1


def test_existing_worker_uses_same_once_job_and_respects_disabled_source(tmp_path, monkeypatch):
    clock(monkeypatch); calls = []
    with TestClient(create_app(tmp_path, market_transport=httpx.MockTransport(lambda r: calls.append(r) or httpx.Response(200, json=response_body())), runtime_role='API')) as client:
        base = start(client); daily = client.app.state.dated_daily
        daily.work(); daily.last_worker_check = None; daily.work()
        assert len(calls) == 1 and capture(client, base).json()['network_calls'] == 1
        clock(monkeypatch, '2026-10-15T18:00:00+08:00')
        policy = next(p for p in client.get('/api/research/collection-sources').json() if p['id'] == 'sse-dated-daily-statistic')
        result = client.post('/api/research/collection-sources/' + policy['id'] + '/policy', json={
            'enabled': False, 'expected_revision': policy['revision'], 'basis': 'Disable source before next worker day'})
        assert result.status_code == 200, result.text
        daily.last_worker_check = None; daily.work()
        assert len(calls) == 1 and daily.worker_gaps
