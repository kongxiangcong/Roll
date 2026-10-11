"""Offline quote successor through the public caller and genuine isolated SQLite/archive."""
import hashlib
import json
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient
from roll.app import create_app
from test_sse_company_contract import clock, start, company, snap

PROOF = Path(__file__).resolve().parents[3] / '.scratch/roll-p0/evidence/30-sse-company-contract/runtime/source-assessment'
SHA = 'bc0971238819277c2b9d6773e341c6d12496adb7991fc897000974cbb2942403'

def predecessor(client):
    base = start(client)
    receipt = client.post(base + '/sse-company-contract', json={'basis': 'METHOD offline fixed official originals'}).json()
    return base, receipt

def test_fixed_public_original_adds_exact_price_successor_without_rewriting_receipt(tmp_path, monkeypatch):
    clock(monkeypatch, '2026-10-11T19:00:00+08:00')
    monkeypatch.setattr('roll.market.sse_price_quotes.now', lambda: '2026-10-11T19:00:00+08:00')
    raw = (PROOF / (SHA + '.raw')).read_bytes()
    assert len(raw) == 409 and hashlib.sha256(raw).hexdigest() == SHA
    calls = []
    def supplier(request):
        calls.append(request)
        return httpx.Response(200, content=raw if request.url.host == 'yunhq.sse.com.cn' else json.dumps(company()).encode())
    with TestClient(create_app(tmp_path, market_transport=httpx.MockTransport(supplier), runtime_role='API')) as client:
        base, source = predecessor(client)
        response = client.post(base + '/sse-price-quotes', json={'source_receipt_id': source['receipt_id'], 'basis': 'Explicit offline price successor'})
        assert response.status_code == 201, response.text
        assessment = response.json()
        quote = assessment['quote_fact']
        assert {k: quote[k] for k in ['last', 'open', 'prev_close', 'high', 'low']} == {
            'last': '42.5100', 'open': '41.4500', 'prev_close': '41.8900', 'high': '42.6600', 'low': '41.0600'}
        assert quote['turnover_ratio_raw'] == '151' and quote['turnover_percent_document_exact'] == '1.51'
        assert quote['raw_hash'] == SHA and quote['document_js_hash'] == source['quote_fact']['document_js_hash']
        assert quote['kind'] == 'QUOTE' and quote['session_scope'] == 'UNKNOWN' and not quote['model_daily_input_allowed']
        assert assessment['source_receipt_id'] == source['receipt_id'] and assessment['network_calls'] == 0
        assert not assessment['system_usable'] and assessment['capability'] == 'NOT_GRANTED'
        assert client.get(base + '/sse-company-contract-receipts').json() == [source]
        assert client.get(base + '/sse-price-quotes').json() == [assessment]
        assert len(calls) == 2

def method_clock(monkeypatch, stamp='2026-10-11T19:00:00+08:00'):
    clock(monkeypatch, stamp)
    monkeypatch.setattr('roll.market.sse_price_quotes.now', lambda: stamp)

def test_explicit_packet_consumes_only_pinned_successor_ids_and_keeps_old_packet_replay(tmp_path, monkeypatch):
    method_clock(monkeypatch)
    calls = []
    def supplier(request):
        calls.append(request)
        return httpx.Response(200, json=snap() if request.url.host == 'yunhq.sse.com.cn' else company())
    transport = httpx.MockTransport(supplier)
    with TestClient(create_app(tmp_path, market_transport=transport, runtime_role='API')) as client:
        base, source = predecessor(client)
        old = client.post(base + '/post-close-packets', json={'basis': 'Existing daily packet before price successor'}).json()
        assert 'last' not in old['source_contract_facts'][0]
        a = client.post(base + '/sse-price-quotes', json={'source_receipt_id': source['receipt_id'], 'basis': 'First explicit derivation'}).json()
        response = client.post(base + '/sse-price-packets', json={
            'source_receipt_id': source['receipt_id'], 'predecessor_packet_id': old['packet_id'],
            'assessment_ids': [a['assessment_id']], 'basis': 'Pinned quote consumer beside original daily inputs'})
        assert response.status_code == 201, response.text
        packet = response.json()
        assert packet['packet_type'] == 'PRICE_SUCCESSOR' and packet['predecessor'] == old
        assert packet['assessment_ids'] == [a['assessment_id']] and packet['quote_facts'] == [a['quote_fact']]
        assert not packet['forward_admissible'] and not packet['system_usable']
        assert not packet['quote_states'][0]['current_quote_available']
        later = client.post(base + '/sse-price-quotes', json={'source_receipt_id': source['receipt_id'], 'basis': 'Same cutoff later explicit derivation'}).json()
        assert later['assessment_id'] != a['assessment_id']
        assert client.get(base + '/sse-price-packets/' + packet['packet_id']).json() == packet
        for saved in [old, packet]:
            replay = client.post('/api/research/post-close-packets/' + saved['packet_id'] + '/replay')
            assert replay.status_code == 200 and replay.json()['matches_original'], replay.text
        gaps = client.get(base + '/source-gaps').json()
        assert len(gaps['price_quote_assessments']) == 2 and not gaps['price_quote_current']['current_quote_available']
        assert 'QUOTE_NOT_CURRENT_HOST_DATE' in gaps['price_quote_current']['gaps']
        assert client.get(base + '/sse-company-contract-receipts').json() == [source]
        assert len(calls) == 2 and client.get('/api/account').json()['version'] == 0
    with TestClient(create_app(tmp_path, market_transport=transport, runtime_role='API')) as client:
        assert client.get(base + '/sse-price-packets/' + packet['packet_id']).json() == packet
        assert client.post('/api/research/post-close-packets/' + packet['packet_id'] + '/replay').json()['matches_original']
        assert len(calls) == 2

@pytest.mark.parametrize('index,value,reason', [
    (1, 0, 'SSE_PRICE_NONPOSITIVE:last'), (6, -1, 'SSE_CLIENT_NUMERIC_VALUE_INVALID'),
    (7, None, 'SSE_CLIENT_NUMERIC_VALUE_UNPROVEN'), (10, 40, 'SSE_PRICE_OHLC_INVALID'),
    (11, 46, 'SSE_PRICE_OHLC_INVALID'), (1, 46, 'SSE_PRICE_OHLC_INVALID'),
    (13, None, 'SSE_CLIENT_NUMERIC_VALUE_UNPROVEN'), (13, True, 'SSE_CLIENT_NUMERIC_VALUE_UNPROVEN'),
])
def test_invalid_price_and_turnover_refuse_successor_without_mutating_source(tmp_path, monkeypatch, index, value, reason):
    method_clock(monkeypatch)
    quote = snap(); quote['snap'][index] = value
    def supplier(request):
        return httpx.Response(200, json=quote if request.url.host == 'yunhq.sse.com.cn' else company())
    with TestClient(create_app(tmp_path, market_transport=httpx.MockTransport(supplier), runtime_role='API')) as client:
        base, source = predecessor(client)
        response = client.post(base + '/sse-price-quotes', json={'source_receipt_id': source['receipt_id'], 'basis': 'Refuse unsupported raw price'})
        assert response.status_code == 409 and reason in response.text, response.text
        assert client.get(base + '/sse-price-quotes').json() == []
        assert client.get(base + '/sse-company-contract-receipts').json() == [source]

@pytest.mark.parametrize('date_value', [20261012, 20260230, None])
def test_missing_invalid_and_future_reported_date_cannot_create_price_successor(tmp_path, monkeypatch, date_value):
    method_clock(monkeypatch)
    quote = snap(); quote['date'] = date_value
    def supplier(request): return httpx.Response(200, json=quote if request.url.host == 'yunhq.sse.com.cn' else company())
    with TestClient(create_app(tmp_path, market_transport=httpx.MockTransport(supplier), runtime_role='API')) as client:
        base, source = predecessor(client)
        assert source['quote_fact'] is None
        response = client.post(base + '/sse-price-quotes', json={'source_receipt_id': source['receipt_id'], 'basis': 'No usable dated source quote'})
        assert response.status_code == 409 and 'SSE_PRICE_SOURCE_QUOTE_MISSING' in response.text
        assert client.get(base + '/sse-price-quotes').json() == []

@pytest.mark.parametrize('phase,current_expected', [('E110    ', True), (' P1 ', False)])
def test_current_host_day_and_p1_are_quote_display_only_not_daily_authority(tmp_path, monkeypatch, phase, current_expected):
    method_clock(monkeypatch, '2026-10-12T19:00:00+08:00')
    quote = snap(); quote['date'] = 20261012; quote['snap'][12] = phase
    # Previous day's close may be outside today's traded OHLC range.
    quote['snap'][7] = 100
    def supplier(request): return httpx.Response(200, json=quote if request.url.host == 'yunhq.sse.com.cn' else company())
    with TestClient(create_app(tmp_path, market_transport=httpx.MockTransport(supplier), runtime_role='API')) as client:
        base, source = predecessor(client)
        response = client.post(base + '/sse-price-quotes', json={'source_receipt_id': source['receipt_id'], 'basis': 'METHOD same-day client quote display'})
        assert response.status_code == 201, response.text
        current = client.get(base + '/sse-price-quotes/current').json()
        assert current['current_quote_available'] is current_expected
        assert current['quote_fact']['prev_close'] == '100' and current['quote_fact']['tradephase_original'] == phase
        assert not current['system_usable'] and not current['model_daily_input_allowed']
        assert current['quote_fact']['completion_state'] == current['quote_fact']['session_scope'] == 'UNKNOWN'
        assert 'QUOTE_NOT_COMPLETE_DAILY_INPUT' in current['gaps']
        assert (('OFFICIAL_CLIENT_P1_PRICE_DISPLAY_WITHHELD' in current['gaps']) is (not current_expected))

def test_exact_decimal_price_and_percent_do_not_round_at_binary_or_display_precision(tmp_path, monkeypatch):
    method_clock(monkeypatch)
    raw = json.dumps(snap()).replace('44.01', '44.010000000000000000000000000001').replace('125,', '12345678901234567890.123456,').encode()
    def supplier(request): return httpx.Response(200, content=raw if request.url.host == 'yunhq.sse.com.cn' else json.dumps(company()).encode())
    with TestClient(create_app(tmp_path, market_transport=httpx.MockTransport(supplier), runtime_role='API')) as client:
        base, source = predecessor(client)
        response = client.post(base + '/sse-price-quotes', json={'source_receipt_id': source['receipt_id'], 'basis': 'Literal precision beyond binary float'})
        assert response.status_code == 201, response.text
        q = response.json()['quote_fact']
        assert q['last'] == '44.010000000000000000000000000001'
        assert q['turnover_ratio_raw'] == '12345678901234567890.123456'
        assert q['turnover_percent_document_exact'] == '123456789012345678.90123456'

@pytest.mark.parametrize('role', ['snap', 'js', 'source_receipt', 'assessment', 'packet'])
def test_original_dependency_damage_refuses_successor_query_and_replay(tmp_path, monkeypatch, role):
    method_clock(monkeypatch)
    def supplier(request): return httpx.Response(200, json=snap() if request.url.host == 'yunhq.sse.com.cn' else company())
    app = create_app(tmp_path, market_transport=httpx.MockTransport(supplier), runtime_role='API')
    with TestClient(app) as client:
        base, source = predecessor(client)
        old = client.post(base + '/post-close-packets', json={'basis': 'Original inputs with known source'}).json()
        a = client.post(base + '/sse-price-quotes', json={'source_receipt_id': source['receipt_id'], 'basis': 'Source-bound quote derivation'}).json()
        packet = client.post(base + '/sse-price-packets', json={'source_receipt_id': source['receipt_id'],
            'predecessor_packet_id': old['packet_id'], 'assessment_ids': [a['assessment_id']], 'basis': 'Exact dependency consumer'}).json()
        hashes = {'snap': source['responses']['snap']['archive']['sha256'], 'js': source['quote_fact']['document_js_hash'],
                  'source_receipt': source['archive']['sha256'], 'assessment': a['archive']['sha256'], 'packet': packet['archive']['sha256']}
        # Explicitly accepted narrow seam: damage only this scenario's genuine archive.
        app.state.evidence.raw(hashes[role]).write_bytes(b'owned scenario corruption')
        assert client.get(base + '/sse-price-packets/' + packet['packet_id']).status_code == 409
        assert client.post('/api/research/post-close-packets/' + packet['packet_id'] + '/replay').status_code == 409
        if role != 'packet': assert client.get(base + '/sse-price-quotes').status_code == 409

def test_future_assessment_and_client_flags_refuse(tmp_path, monkeypatch):
    method_clock(monkeypatch)
    def supplier(request): return httpx.Response(200, json=snap() if request.url.host == 'yunhq.sse.com.cn' else company())
    with TestClient(create_app(tmp_path, market_transport=httpx.MockTransport(supplier), runtime_role='API')) as client:
        base, source = predecessor(client)
        old = client.post(base + '/post-close-packets', json={'basis': 'Original known source at initial cutoff'}).json()
        command = {'source_receipt_id': source['receipt_id'], 'basis': 'Explicit no client authority flags'}
        for flag in ['complete', 'system_usable', 'current', 'actual', 'knowledge_cutoff']:
            assert client.post(base + '/sse-price-quotes', json={**command, flag: True}).status_code == 422
        method_clock(monkeypatch, '2026-10-11T20:00:00+08:00')
        later = client.post(base + '/sse-price-quotes', json=command).json()
        method_clock(monkeypatch)
        p = {**command, 'predecessor_packet_id': old['packet_id'], 'assessment_ids': [later['assessment_id']]}
        response = client.post(base + '/sse-price-packets', json=p)
        assert response.status_code == 409 and 'SSE_PRICE_ASSESSMENT_NOT_KNOWN' in response.text
        assert client.get(base + '/sse-price-quotes').json() == []
        assert client.post('/api/research/post-close-packets/' + old['packet_id'] + '/replay').json()['matches_original']

def test_nonobject_refused_source_returns_typed_price_refusal_instead_of_server_error(tmp_path, monkeypatch):
    method_clock(monkeypatch)
    def supplier(request): return httpx.Response(200, json=[] if request.url.host == 'yunhq.sse.com.cn' else company())
    with TestClient(create_app(tmp_path, market_transport=httpx.MockTransport(supplier), runtime_role='API'), raise_server_exceptions=False) as client:
        base, source = predecessor(client)
        assert source['quote_fact'] is None
        response = client.post(base + '/sse-price-quotes', json={'source_receipt_id': source['receipt_id'], 'basis': 'Typed refused source dependency'})
        assert response.status_code == 409 and 'SSE_PRICE_SOURCE_QUOTE_MISSING' in response.text, response.text

def test_packet_requires_unique_known_assessments_bound_to_its_original_source(tmp_path, monkeypatch):
    method_clock(monkeypatch)
    def supplier(request): return httpx.Response(200, json=snap() if request.url.host == 'yunhq.sse.com.cn' else company())
    with TestClient(create_app(tmp_path, market_transport=httpx.MockTransport(supplier), runtime_role='API')) as client:
        base, source = predecessor(client)
        old = client.post(base + '/post-close-packets', json={'basis': 'Known first source in predecessor'}).json()
        a = client.post(base + '/sse-price-quotes', json={'source_receipt_id': source['receipt_id'], 'basis': 'Known first price assessment'}).json()
        other = client.post(base + '/sse-company-contract', json={'basis': 'Separate known source receipt identity'}).json()
        other_a = client.post(base + '/sse-price-quotes', json={'source_receipt_id': other['receipt_id'], 'basis': 'Separate known price assessment'}).json()
        command = {'source_receipt_id': source['receipt_id'], 'predecessor_packet_id': old['packet_id'],
                   'assessment_ids': [a['assessment_id']], 'basis': 'Literal original source binding'}
        for ids, reason in [([a['assessment_id'], a['assessment_id']], 'SSE_PRICE_ASSESSMENT_NOT_KNOWN'),
                            (['missing'], 'SSE_PRICE_ASSESSMENT_NOT_KNOWN'),
                            ([other_a['assessment_id']], 'PRICE_ASSESSMENT_SOURCE_MISMATCH')]:
            response = client.post(base + '/sse-price-packets', json={**command, 'assessment_ids': ids})
            assert response.status_code == 409 and reason in response.text, response.text
        response = client.post(base + '/sse-price-packets', json={**command, 'source_receipt_id': other['receipt_id'], 'assessment_ids': [other_a['assessment_id']]})
        assert response.status_code == 409 and 'PRICE_PREDECESSOR_SOURCE_MISMATCH' in response.text
        assert client.post(base + '/sse-price-packets', json={**command, 'assessment_ids': []}).status_code == 422
        assert client.post('/api/research/post-close-packets/' + old['packet_id'] + '/replay').json()['matches_original']
