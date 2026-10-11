"""Public current source receipt, exact document-bound conversion, genuine own archive."""
import hashlib
import json
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient
from roll.app import create_app

SQL = 'COMMON_SSE_CP_GPJCTPZ_GPLB_GPGK_GSGK_C'
SELECT = 'name,last,chg_rate,change,amount,volume,open,prev_close,ask,bid,high,low,tradephase,turnover_ratio,totalValue,amp_rate,circulating,up_limit,down_limit,fp_volume,fp_amount,cpxxprodusta,cpxxlmttype,fp_phase'

def clock(monkeypatch, stamp='2026-10-11T18:00:00+08:00'):
    for module in ['roll.market.post_close_packet', 'roll.market.sse_company_contract', 'roll.research.prospective', 'roll.market.evidence']:
        monkeypatch.setattr(module + '.now', lambda: stamp)

def snap():
    return {'code': '600362', 'date': 20261009, 'time': 150004,
            'snap': ['江西铜业', 44.01, 1, .44, 1234567.89, 12345, 43, 43.57,
                     [], [], 45, 42, ' E1 ', 125, 0, 3, 0, 48, 39, None, 0, 'opaque-status', 'opaque-limit', '']}

def company():
    return {'sqlId': SQL, 'isPagination': 'false', 'result': [{
        'COMPANY_CODE': '600362', 'A_STOCK_CODE': '600362', 'SEC_TYPE': '主板A',
        'STATE_CODE_A_DESC': '上市', 'A_LIST_DATE': '2002-01-11', 'STATUS_A': 'opaque'}]}

def start(client):
    response = client.post('/api/research/collections', json={'instrument': 'SSE:600362', 'basis': 'METHOD isolated source contract'})
    assert response.status_code == 201, response.text
    return '/api/research/collections/' + response.json()['plan_id']

def test_document_bound_units_and_company_state_are_distinct_from_complete_status(tmp_path, monkeypatch):
    clock(monkeypatch)
    calls = []
    raw_snap = json.dumps(snap()).encode()
    raw_company = json.dumps(company(), ensure_ascii=False).encode()
    def supplier(request):
        calls.append(request)
        return httpx.Response(200, content=raw_snap if request.url.host == 'yunhq.sse.com.cn' else raw_company)
    with TestClient(create_app(tmp_path, market_transport=httpx.MockTransport(supplier), runtime_role='API')) as client:
        base = start(client)
        response = client.post(base + '/sse-company-contract', json={'basis': 'Exact official company renderer assessment'})
        assert response.status_code == 201, response.text
        receipt = response.json()
        assert len(calls) == receipt['network_calls'] == 2
        assert calls[0].url.port == 32042 and calls[0].url.path == '/v1/sh1/snap/600362'
        assert dict(calls[0].url.params) == {'select': SELECT}
        assert dict(calls[1].url.params) == {'sqlId': SQL, 'COMPANY_CODE': '600362', 'isPagination': 'false'}
        quote = receipt['quote_fact']
        assert quote['volume_raw'] == '12345' and quote['display_volume_hands_exact'] == '123.45'
        assert quote['amount_raw'] == '1234567.89' and quote['display_amount_10000_cny_exact'] == '123.456789'
        assert quote['unit_basis'] == 'OFFICIAL_CLIENT_TRANSFORM_DOCUMENT_BOUND'
        assert quote['tradephase_original'] == ' E1 ' and quote['tradephase_compact'] == 'E1'
        assert quote['tradephase_first'] == 'E' and quote['tradephase_display'] == '闭市'
        assert quote['fp_volume_raw'] is None and quote['fp_amount_raw'] == '0'
        assert quote['turnover_scope'] == 'UNKNOWN' and not quote['model_daily_input_allowed']
        state = receipt['company_fact']
        assert state['company_state_reported'] == '上市' and state['listing_date_reported'] == '2002-01-11'
        assert state['risk_warning'] is None and state['listing_stage'] is None and state['suspension'] is None
        assert not receipt['system_usable'] and not receipt['complete_status_verified']
        assert receipt['forward_started_at'] is None and receipt['capability'] == 'NOT_GRANTED'
        for role, raw in [('snap', raw_snap), ('company', raw_company)]:
            archived = receipt['responses'][role]['archive']
            assert archived['sha256'] == hashlib.sha256(raw).hexdigest()
            assert client.get('/api/data/archives/' + archived['sha256']).content == raw
        assert client.get(base + '/sse-company-contract-receipts').json() == [receipt]
        assert client.get('/api/account').json()['version'] == 0

def test_saved_actual_snap_and_company_are_method_replay_with_friday_date_and_unknown_full_status(tmp_path, monkeypatch):
    clock(monkeypatch, '2026-10-11T19:00:00+08:00')
    proof = Path(__file__).resolve().parents[3] / '.scratch/roll-p0/evidence/30-sse-company-contract/runtime/source-assessment'
    names = {'snap': 'bc0971238819277c2b9d6773e341c6d12496adb7991fc897000974cbb2942403',
             'company': '4e4bd76727f03b989b98f923c65c2d3d99816f6683172dba4ab7e148b6c2fb7a'}
    raws = {role: (proof / (sha + '.raw')).read_bytes() for role, sha in names.items()}
    assert {role: hashlib.sha256(raw).hexdigest() for role, raw in raws.items()} == names
    calls = []
    def supplier(request):
        calls.append(request)
        return httpx.Response(200, content=raws['snap' if request.url.host == 'yunhq.sse.com.cn' else 'company'])
    with TestClient(create_app(tmp_path, market_transport=httpx.MockTransport(supplier), runtime_role='API')) as client:
        base = start(client)
        old = client.post(base + '/post-close-packets', json={'basis': 'Before source assessment'}).json()
        receipt = client.post(base + '/sse-company-contract', json={'basis': 'Saved public originals offline; METHOD known-time after real receipt'}).json()
        assert receipt['evidence_kind'] == 'METHOD_CASE' and receipt['network_calls'] == 2
        quote, state = receipt['quote_fact'], receipt['company_fact']
        assert quote['volume_raw'] == '31419158' and quote['amount_raw'] == '1314805240'
        assert quote['display_volume_hands_exact'] == '314191.58' and quote['display_amount_10000_cny_exact'] == '131480.524'
        assert quote['trade_date'] == '2026-10-09' and quote['time_display'] == '16:29:05'
        assert quote['tradephase_original'] == 'E110    ' and quote['tradephase_compact'] == 'E110'
        assert quote['fp_volume_raw'] == '30600' and quote['fp_amount_raw'] == '1300806.000'
        assert quote['fp_phase_original'] == 'D0      ' and quote['fp_phase_semantics'] == 'UNKNOWN'
        assert state['company_state_reported'] == '上市' and state['listing_date_original'] == '20020111'
        assert state['listing_date_reported'] == '2002-01-11' and state['source_reported_date'] is None
        assert state['status_a_original'] == '   D  F  N          ' and state['risk_warning'] is None
        packet = client.post(base + '/post-close-packets', json={'basis': 'Friday snap is not Sunday full input'}).json()
        assert packet['company_contract_receipts'] == [receipt] and len(packet['source_contract_facts']) == 2
        assert 'SSE_CLIENT_QUOTE_NOT_CURRENT_HOST_DATE' in packet['gaps']
        assert not packet['forward_admissible'] and packet['forward_started_at'] is None
        assert client.get(base + '/source-gaps').json()['company_contract_receipts'] == [receipt]
        for saved in [old, packet]:
            assert client.post('/api/research/post-close-packets/' + saved['packet_id'] + '/replay').json()['matches_original']
        assert len(calls) == 2 and client.get('/api/account').json()['version'] == 0

def test_current_packet_fixed_empty_and_nonempty_contract_ids_survive_same_cutoff_append(tmp_path, monkeypatch):
    clock(monkeypatch)
    calls = []
    def supplier(request):
        calls.append(request)
        return httpx.Response(200, json=snap() if request.url.host == 'yunhq.sse.com.cn' else company())
    transport = httpx.MockTransport(supplier)
    with TestClient(create_app(tmp_path, market_transport=transport, runtime_role='API')) as client:
        base = start(client)
        before = client.post(base + '/post-close-packets', json={'basis': 'Old packet before contract'}).json()
        assert before['company_contract_receipts'] == []
        job = client.post(base + '/sse-company-contract/check', json={'basis': 'Once two-source job'}).json()
        assert job['state'] == 'RECORDED' and job['receipt_id']
        assert client.post(base + '/sse-company-contract/check', json={'basis': 'Cache no retry'}).json() == job
        packet = client.post(base + '/post-close-packets', json={'basis': 'Pin source documents and typed facts'}).json()
        assert [r['receipt_id'] for r in packet['company_contract_receipts']] == [job['receipt_id']]
        assert len(packet['source_contract_facts']) == 2
        assert packet['source_contract_facts'][0]['display_volume_hands_exact'] == '123.45'
        assert packet['status_facts'][0]['company_receipt_id'] == job['receipt_id']
        assert not packet['forward_admissible']
        gaps = client.get(base + '/source-gaps').json()
        assert gaps['company_contract_receipts'] == packet['company_contract_receipts']
        assert gaps['company_contract_jobs'] == [job]
        assert 'SSE_COMPANY_LISTING_RISK_ENUM_EFFECTIVE_AND_NEGATIVE_COVERAGE_UNPROVEN' in packet['gaps']
        assert client.post(base + '/sse-company-contract', json={'basis': 'Explicit later assessment same cutoff'}).status_code == 201
        for old in [before, packet]:
            replay = client.post('/api/research/post-close-packets/' + old['packet_id'] + '/replay')
            assert replay.status_code == 200 and replay.json()['matches_original'], replay.text
        assert len(calls) == 4
        pid = base.rsplit('/', 1)[1]
    with TestClient(create_app(tmp_path, market_transport=transport, runtime_role='API')) as restarted:
        assert restarted.post('/api/research/collections/' + pid + '/sse-company-contract/check', json={'basis': 'Restart retains original job'}).json() == job
        assert len(calls) == 4
        assert restarted.post('/api/research/post-close-packets/' + packet['packet_id'] + '/replay').json()['matches_original']

def test_raw_decimal_amount_is_not_rounded_through_binary_float_or_renderer(tmp_path, monkeypatch):
    clock(monkeypatch)
    raw = json.dumps(snap()).replace('1234567.89', '12345678901234567890.123456').encode()
    def supplier(request):
        return httpx.Response(200, content=raw) if request.url.host == 'yunhq.sse.com.cn' else httpx.Response(200, json=company())
    with TestClient(create_app(tmp_path, market_transport=httpx.MockTransport(supplier), runtime_role='API')) as client:
        base = start(client)
        receipt = client.post(base + '/sse-company-contract', json={'basis': 'METHOD exact raw decimal must survive'}).json()
        assert receipt['quote_fact']['amount_raw'] == '12345678901234567890.123456'
        assert receipt['quote_fact']['display_amount_10000_cny_exact'] == '1234567890123456.7890123456'

@pytest.mark.parametrize('fault,expected', [
    ('security', 'SNAP_SECURITY_UNPROVEN'), ('date', 'DATE_AFTER_HOST'),
    ('alignment', 'SELECT_ALIGNMENT_UNPROVEN'), ('negative', 'NUMERIC_VALUE_INVALID'),
    ('company_security', 'RESPONSE_SECURITY_UNPROVEN'), ('ambiguous', 'ROW_MISSING_OR_AMBIGUOUS'),
    ('sql', 'SQL_OR_ERRORS_UNPROVEN'), ('branch', 'A_BRANCH_UNPROVEN'),
])
def test_wrong_identity_date_numeric_and_company_branch_keep_both_originals_without_fallback(tmp_path, monkeypatch, fault, expected):
    clock(monkeypatch)
    quote, overview = snap(), company()
    if fault == 'security': quote['code'] = '600363'
    if fault == 'date': quote['date'] = 20261012
    if fault == 'alignment': quote['snap'].pop()
    if fault == 'negative': quote['snap'][4] = -1
    if fault == 'company_security': overview['result'][0]['COMPANY_CODE'] = '600363'
    if fault == 'ambiguous': overview['result'].append(dict(overview['result'][0]))
    if fault == 'sql': overview['sqlId'] = 'UNRELATED'
    if fault == 'branch': overview['result'][0]['SEC_TYPE'] = '主板B'
    raws = {'snap': json.dumps(quote).encode(), 'company': json.dumps(overview).encode()}
    calls = []
    def supplier(request):
        calls.append(request)
        return httpx.Response(200, content=raws['snap' if request.url.host == 'yunhq.sse.com.cn' else 'company'])
    with TestClient(create_app(tmp_path, market_transport=httpx.MockTransport(supplier), runtime_role='API')) as client:
        base = start(client)
        receipt = client.post(base + '/sse-company-contract', json={'basis': 'METHOD refuse actual malformed identity/source fields'}).json()
        assert len(calls) == receipt['network_calls'] == 2 and receipt['status'] == 'REFUSED_PARTIAL'
        assert any(expected in e for e in receipt['errors'].values())
        assert not receipt['system_usable'] and not receipt['no_event_authority']
        for role, raw in raws.items():
            assert client.get('/api/data/archives/' + receipt['responses'][role]['archive']['sha256']).content == raw
        assert client.get(base + '/sse-company-contract-receipts').json() == [receipt]

@pytest.mark.parametrize('dependency', ['snap', 'company', 'html', 'js', 'mapping', 'plan', 'receipt'])
def test_source_bound_receipt_and_packet_refuse_owned_archive_damage(tmp_path, monkeypatch, dependency):
    clock(monkeypatch)
    def supplier(request):
        return httpx.Response(200, json=snap() if request.url.host == 'yunhq.sse.com.cn' else company())
    app = create_app(tmp_path, market_transport=httpx.MockTransport(supplier), runtime_role='API')
    with TestClient(app) as client:
        base = start(client)
        receipt = client.post(base + '/sse-company-contract', json={'basis': 'METHOD source integrity'}).json()
        packet = client.post(base + '/post-close-packets', json={'basis': 'Freeze exact source dependencies'}).json()
        hashes = {role: receipt['responses'][role]['archive']['sha256'] for role in ['snap', 'company']}
        hashes.update(html=receipt['capture_plan']['html_hash'], js=receipt['capture_plan']['js_hash'],
                      mapping=receipt['mapping_hash'], plan=receipt['capture_plan_archive']['sha256'],
                      receipt=receipt['archive']['sha256'])
        app.state.evidence.raw(hashes[dependency]).write_bytes(b'owned METHOD archive corruption')
        assert client.get(base + '/sse-company-contract-receipts').status_code == 409
        assert client.post('/api/research/post-close-packets/' + packet['packet_id'] + '/replay').status_code == 409

def test_source_disable_client_flags_and_unknown_phase_or_listing_do_not_make_authority(tmp_path, monkeypatch):
    clock(monkeypatch)
    calls = []
    def supplier(request):
        calls.append(request)
        value = snap() if request.url.host == 'yunhq.sse.com.cn' else company()
        if 'snap' in value: value['snap'][12] = 'Z7'
        else: value['result'][0].update(STATE_CODE_A_DESC='', A_LIST_DATE='-')
        return httpx.Response(200, json=value)
    with TestClient(create_app(tmp_path, market_transport=httpx.MockTransport(supplier), runtime_role='API')) as client:
        base = start(client)
        for field in [{'complete_status_verified': True}, {'source_units': 'SHARE'}, {'evidence_kind': 'REAL'}, {'actual_forward_start': True}]:
            assert client.post(base + '/sse-company-contract', json={'basis': 'Caller cannot sign authority', **field}).status_code == 422
        receipt = client.post(base + '/sse-company-contract', json={'basis': 'Opaque stage/state are kept unknown'}).json()
        assert receipt['quote_fact']['tradephase_display'] == 'Z' and receipt['quote_fact']['tradephase_original'] == 'Z7'
        assert receipt['company_fact']['listing_date_reported'] is None and receipt['company_fact']['listing_date_precision'] == 'UNKNOWN'
        assert receipt['company_fact']['risk_warning'] is None and not receipt['system_usable']
        changed = client.post('/api/research/collection-sources/sse-company-client-contract/policy', json={
            'enabled': False, 'expected_revision': 1, 'basis': 'METHOD disable source'})
        assert changed.status_code == 200, changed.text
        refused = client.post(base + '/sse-company-contract/check', json={'basis': 'No network when source disabled'}).json()
        assert refused['state'] == 'RECORDED'
        latest = client.get(base + '/sse-company-contract-receipts').json()[-1]
        assert latest['network_calls'] == 0 and len(calls) == 2
        assert latest['errors'] and not latest['system_usable']

def test_timeout_and_stream_error_keep_independent_two_attempt_budget_and_prefix(tmp_path, monkeypatch):
    clock(monkeypatch)
    calls = []
    prefix = b'{"code":"600362","snap":['
    class Interrupted(httpx.SyncByteStream):
        def __iter__(self):
            yield prefix
            raise httpx.ReadTimeout('METHOD interrupted body')
    def supplier(request):
        calls.append(request)
        if request.url.host == 'yunhq.sse.com.cn': return httpx.Response(200, stream=Interrupted())
        return httpx.Response(200, json=company())
    with TestClient(create_app(tmp_path, market_transport=httpx.MockTransport(supplier), runtime_role='API')) as client:
        base = start(client)
        receipt = client.post(base + '/sse-company-contract', json={'basis': 'METHOD interruption must retain received original'}).json()
        assert receipt['network_calls'] == len(calls) == 2
        saved = receipt['responses']['snap']
        assert not saved['original_complete'] and saved['archive']['stream_error'] == 'ReadTimeout'
        assert client.get('/api/data/archives/' + saved['archive']['sha256']).content == prefix
        assert receipt['quote_fact'] is None and receipt['company_fact']['risk_warning'] is None
        assert receipt['errors'] == {'snap': 'ReadTimeout'}
        finite = receipt['capture_plan']
        assert finite['request_budget_calls'] == 2 and finite['retries'] == finite['fallbacks'] == 0
        assert finite['requests'][0]['parameters'] == {'select': SELECT}
        assert not finite['client_transport_equivalence_claim']
        assert json.loads(client.get('/api/data/archives/' + receipt['capture_plan_archive']['sha256']).content) == finite
        assert client.get(base + '/sse-company-contract-receipts').json() == [receipt]
