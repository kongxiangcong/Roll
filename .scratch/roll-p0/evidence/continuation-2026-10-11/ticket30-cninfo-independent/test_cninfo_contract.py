import httpx
from fastapi.testclient import TestClient
from roll.app import create_app
from test_post_close_packet import setup

def prepare(tmp_path, monkeypatch):
    clock = '2026-10-12T15:06:00+08:00'
    monkeypatch.setattr('roll.market.post_close_packet.now', lambda: clock)
    monkeypatch.setattr('roll.research.prospective.now', lambda: clock)
    def offline(request):
        raise AssertionError('Independent CNINFO check must not request data')
    return create_app(tmp_path, market_transport=httpx.MockTransport(offline), runtime_role='API'), clock


def test_literal_finite_index_exact_cash_and_fixed_mixed_family_ids(tmp_path, monkeypatch):
    app, clock = prepare(tmp_path, monkeypatch)
    with TestClient(app) as client:
        pid = setup(client)
        before = client.get('/api/account').json()
        sse = client.post(f'/api/research/collections/{pid}/sse-history-assessments', json={'basis': 'Independent fixed SSE'}).json()
        response = client.post(f'/api/research/collections/{pid}/cninfo-history-assessments', json={'basis': 'Independent finite candidate audit'})
        assert response.status_code == 201, response.text
        value = response.json()
        assert value['source_family'] == 'CNINFO_HISTORY'
        assert len(value['source_hashes']) == 6 and len(value['query_audits']) == 8
        assert len(value['candidates']) == len({c['announcement_id'] for c in value['candidates']}) == 24
        assert value['network_calls'] == 0
        assert [a['search_key'] for a in value['query_audits']] == ['停牌', '复牌', '回购', '注销', '权益分派', '利润分配方案实施', '送股', '配股']
        assert [a['returned_count'] for a in value['query_audits']] == [2, 1, 7, 0, 10, 4, 0, 0]
        assert [a['declared_total'] for a in value['query_audits']] == [2, 1, 7, 0, 10, 4, 0, 0]
        assert [a['declared_record_total'] for a in value['query_audits']] == [2, 1, 7, 0, 10, 4, 0, 0]
        assert [a['reported_total_pages'] for a in value['query_audits']] == [0] * 8
        for audit in value['query_audits']:
            assert (audit['requested_start_date'], audit['requested_end_date'], audit['requested_page'], audit['requested_page_size']) == ('2013-01-01', '2025-12-31', 1, 30)
            assert audit['request_form']['stock'] == '600362,gssh0600362'
            assert audit['request_date_filter_semantics'] == 'UNPROVEN'
            assert audit['finite_query_completed'] is False and audit['no_event_authority'] is False
            assert audit['received_at'].startswith('2026-10-09') and audit['available_at'] == clock
        halt = value['query_audits'][0]
        assert (halt['returned_count'], halt['declared_total'], halt['declared_record_total'], halt['reported_total_pages'], halt['has_more_reported']) == (2, 2, 2, 0, False)
        assert halt['returned_count_matches_total'] is True
        candidate = next(c for c in value['candidates'] if c['announcement_id'] == '1224816852')
        assert candidate['announcement_time_reported'] == 1763654400000
        assert candidate['index_time_precision'] == candidate['lifecycle_state'] == 'UNKNOWN'
        assert candidate['published_at'] is None and candidate['historical_pit_claim'] is False
        assert candidate['source_path_date'] == '2025-11-21'
        assert len(value['known_cash_links']) == 13
        assert value['known_cash_unreturned_ids'] == ['1202538463']
        link = next(l for l in value['known_cash_links'] if l['announcement_id'] == '1224816852')
        assert link['pdf_raw_hash'] == 'e486d0e9a99e5aa0dc77a4aa2037963022a44a1d3f6cd3315290b8e6afe2a28c'
        assert link['pdf_bytes'] == 145503
        assert link['link_basis'] == 'EXACT_ANNOUNCEMENT_ID_AND_PDF_LOCATOR'
        assert link['pdf_field_source_locator'] and link['cash_mapping_hash']
        assert link['revision_coverage_verified'] is False and link['actual_account_receipt'] is None
        clue = next(c for c in value['revision_cancellation_audit']['clues'] if c['announcement_id'] == '1201981143')
        assert clue['associate_announcement_reported'] == '1201981166' and clue['associated_candidate_returned'] is False
        assert clue['lifecycle_interpretation'] == 'UNKNOWN'
        packet = client.post(f'/api/research/collections/{pid}/post-close-packets', json={'basis': 'Pinned mixed family'}).json()
        assert packet['historical_source_assessments'] == [sse, value]
        assert len(packet['known_cash_inventory']['events']) == 14
        events = {e['event_identity']: e for e in packet['known_cash_inventory']['events']}
        for known in value['known_cash_links']:
            assert known['pdf_source_url'] == events[known['announcement_id']]['source']['url']
            assert known['pdf_raw_hash'] == events[known['announcement_id']]['source']['sha256']
            assert known['link_basis'] == 'EXACT_ANNOUNCEMENT_ID_AND_PDF_LOCATOR'
        assert '1202538463' in [e['event_identity'] for e in packet['known_cash_inventory']['events']]
        assert packet['rows'] == [] and packet['forward_admissible'] is False
        second = client.post(f'/api/research/collections/{pid}/cninfo-history-assessments', json={'basis': 'Later same-cutoff audit'}).json()
        assert second['assessment_id'] != value['assessment_id']
        replay = client.post('/api/research/post-close-packets/' + packet['packet_id'] + '/replay')
        assert replay.status_code == 200 and replay.json()['matches_original'] is True, replay.text
        assert replay.json()['network_calls'] == 0
        gaps = client.get(f'/api/research/collections/{pid}/source-gaps').json()
        assert gaps['historical_source_assessments'] == [sse, value, second]
        assert gaps['forward_started_at'] is None and gaps['capability'] == 'NOT_GRANTED'
        assert client.get('/api/account').json() == before
        forbidden = client.post(f'/api/research/collections/{pid}/cninfo-history-assessments', json={'basis': 'Caller cannot assert completeness', 'complete': True})
        assert forbidden.status_code == 422


def test_each_own_archived_index_mapping_pdf_damage_refuses_replay(tmp_path, monkeypatch):
    app, clock = prepare(tmp_path, monkeypatch)
    with TestClient(app) as client:
        pid = setup(client)
        value = client.post(f'/api/research/collections/{pid}/cninfo-history-assessments', json={'basis': 'Own dependency audit'}).json()
        packet = client.post(f'/api/research/collections/{pid}/post-close-packets', json={'basis': 'Own immutable packet'}).json()
        for sha in [value['query_audits'][0]['raw_hash'], value['mapping_hash'], value['known_cash_links'][0]['pdf_raw_hash']]:
            own = app.state.evidence.raw(sha)
            original = own.read_bytes()
            own.write_bytes(b'METHOD independent own archive damage')
            replay = client.post('/api/research/post-close-packets/' + packet['packet_id'] + '/replay')
            assert replay.status_code == 409, replay.text
            own.write_bytes(original)
            restored = client.post('/api/research/post-close-packets/' + packet['packet_id'] + '/replay')
            assert restored.status_code == 200 and restored.json()['matches_original'] is True, restored.text
