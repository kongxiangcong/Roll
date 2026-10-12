"""Pinned public index bytes through real HTTP/SQLite/archive, always offline."""
import httpx
import pytest
from fastapi.testclient import TestClient
from roll.app import create_app
from test_post_close_packet import setup


def test_finite_cninfo_index_keeps_counts_opaque_dates_and_current_gaps(tmp_path,monkeypatch):
    clock='2026-10-12T15:06:00+08:00'
    monkeypatch.setattr('roll.market.post_close_packet.now',lambda:clock)
    monkeypatch.setattr('roll.research.prospective.now',lambda:clock)
    def offline(request):raise AssertionError('Fixed public originals must not request live data')
    app=create_app(tmp_path,market_transport=httpx.MockTransport(offline))
    with TestClient(app) as client:
        pid=setup(client)
        response=client.post(f'/api/research/collections/{pid}/cninfo-history-assessments',json={'basis':'Finite historical candidate audit'})
        assert response.status_code==201,response.text
        assessment=response.json()
        assert assessment['source_family']=='CNINFO_HISTORY'
        assert len(assessment['query_audits'])==8 and len(assessment['candidates'])==24
        assert len(assessment['source_hashes'])==6 and assessment['network_calls']==0
        halt=assessment['query_audits'][0]
        assert halt['search_key']=='停牌' and halt['returned_count']==halt['declared_total']==2
        assert halt['reported_total_pages']==0 and halt['returned_count_matches_total']
        assert not halt['finite_query_completed'] and not halt['no_event_authority']
        assert halt['requested_start_date']=='2013-01-01' and halt['requested_end_date']=='2025-12-31'
        assert 'CNINFO_PAGE_COUNT_SEMANTICS_UNPROVEN' in halt['gaps']
        empty=assessment['query_audits'][3]
        assert empty['returned_count']==0 and not empty['no_event_authority']
        candidate=next(c for c in assessment['candidates'] if c['announcement_id']=='1224816852')
        assert candidate['announcement_time_reported']==1763654400000
        assert candidate['index_time_precision']=='UNKNOWN' and candidate['published_at'] is None
        assert candidate['available_at']==clock and not candidate['historical_pit_claim']
        assert candidate['source_path_date']=='2025-11-21' and candidate['lifecycle_state']=='UNKNOWN'
        assert not assessment['current_coverage_verified'] and not assessment['older_pending_obligations_complete']
        packet=client.post(f'/api/research/collections/{pid}/post-close-packets',json={'basis':'Candidate isolation'}).json()
        assert packet['historical_source_assessments']==[assessment] and packet['rows']==[]
        assert not packet['forward_admissible']
        replay=client.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay')
        assert replay.status_code==200,replay.text
        assert replay.json()['matches_original'] and replay.json()['network_calls']==0
        gaps=client.get(f'/api/research/collections/{pid}/source-gaps').json()
        assert gaps['historical_source_assessments']==[assessment]
        assert 'CNINFO_PAGE_COUNT_SEMANTICS_UNPROVEN' in gaps['historical_source_gaps']
        assert gaps['forward_started_at'] is None and gaps['capability']=='NOT_GRANTED'


def test_cash_links_require_exact_announcement_locator_and_keep_unreturned_known_notice(tmp_path,monkeypatch):
    clock='2026-10-12T15:06:00+08:00'
    monkeypatch.setattr('roll.market.post_close_packet.now',lambda:clock)
    monkeypatch.setattr('roll.research.prospective.now',lambda:clock)
    app=create_app(tmp_path)
    with TestClient(app) as client:
        pid=setup(client)
        response=client.post(f'/api/research/collections/{pid}/cninfo-history-assessments',json={'basis':'Exact cash index/PDF link audit'})
        assert response.status_code==201,response.text
        value=response.json()
        assert len(value['known_cash_links'])==13
        assert value['known_cash_unreturned_ids']==['1202538463']
        link=next(l for l in value['known_cash_links'] if l['announcement_id']=='1224816852')
        assert link['pdf_raw_hash']=='e486d0e9a99e5aa0dc77a4aa2037963022a44a1d3f6cd3315290b8e6afe2a28c'
        assert link['pdf_bytes']==145503 and link['link_basis']=='EXACT_ANNOUNCEMENT_ID_AND_PDF_LOCATOR'
        assert link['pdf_field_source_locator'] and link['cash_mapping_hash']
        assert link['candidate_raw_locators'][0]['raw_hash'] in value['source_hashes']
        assert link['lifecycle_stage']=='IMPLEMENTATION_NOTICE' and not link['revision_coverage_verified']
        assert 'CNINFO_KNOWN_CASH_NOTICE_NOT_RETURNED_BY_KEYWORD_INDEX' in value['gaps']
        assert value['revision_cancellation_audit']['coverage']=='UNKNOWN'
        assert not value['revision_cancellation_audit']['title_or_association_confirms_lifecycle']
        clue=next(c for c in value['revision_cancellation_audit']['clues'] if c['announcement_id']=='1201981143')
        assert clue['associate_announcement_reported']=='1201981166'
        assert not clue['associated_candidate_returned'] and clue['lifecycle_interpretation']=='UNKNOWN'
        assert 'ALLOTMENT_LIFECYCLE' in value['unknown_action_categories']
        packet=client.post(f'/api/research/collections/{pid}/post-close-packets',json={'basis':'Keep 14 independent mapped cash notices'}).json()
        assert len(packet['known_cash_inventory']['events'])==14
        assert not packet['known_cash_inventory']['pending_older_obligations_complete']
        replay=client.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay')
        assert replay.status_code==200 and replay.json()['matches_original'],replay.text


@pytest.mark.parametrize('dependency',['index','mapping','cash_pdf'])
def test_original_index_mapping_and_exact_pdf_damage_refuse_replay(tmp_path,monkeypatch,dependency):
    clock='2026-10-12T15:06:00+08:00'
    monkeypatch.setattr('roll.market.post_close_packet.now',lambda:clock)
    monkeypatch.setattr('roll.research.prospective.now',lambda:clock)
    app=create_app(tmp_path)
    with TestClient(app) as client:
        pid=setup(client)
        value=client.post(f'/api/research/collections/{pid}/cninfo-history-assessments',json={'basis':'Dependency binding'}).json()
        packet=client.post(f'/api/research/collections/{pid}/post-close-packets',json={'basis':'Immutable raw dependency'}).json()
        sha={'index':value['query_audits'][0]['raw_hash'],'mapping':value['mapping_hash'],
            'cash_pdf':value['known_cash_links'][0]['pdf_raw_hash']}[dependency]
        app.state.evidence.raw(sha).write_bytes(b'METHOD damage of own archive only')
        replay=client.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay')
        assert replay.status_code==409,replay.text


def test_mixed_history_packet_pins_original_ids_after_same_cutoff_append(tmp_path,monkeypatch):
    clock='2026-10-12T15:06:00+08:00'
    monkeypatch.setattr('roll.market.post_close_packet.now',lambda:clock)
    monkeypatch.setattr('roll.research.prospective.now',lambda:clock)
    app=create_app(tmp_path)
    with TestClient(app) as client:
        pid=setup(client)
        sse=client.post(f'/api/research/collections/{pid}/sse-history-assessments',json={'basis':'Independent SSE source'}).json()
        first=client.post(f'/api/research/collections/{pid}/cninfo-history-assessments',json={'basis':'Original candidate set'}).json()
        packet=client.post(f'/api/research/collections/{pid}/post-close-packets',json={'basis':'Fixed historical selection'}).json()
        second=client.post(f'/api/research/collections/{pid}/cninfo-history-assessments',json={'basis':'Later same-cutoff inspection'}).json()
        assert first['assessment_id']!=second['assessment_id']
        assert packet['historical_source_assessments']==[sse,first]
        replay=client.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay')
        assert replay.status_code==200 and replay.json()['matches_original'],replay.text
        gaps=client.get(f'/api/research/collections/{pid}/source-gaps').json()
        assert gaps['historical_source_assessments']==[sse,first,second]
        assert not gaps['forward_admissible']


def test_caller_cannot_promote_historical_index_to_complete_authority(tmp_path):
    app=create_app(tmp_path)
    with TestClient(app) as client:
        pid=setup(client)
        response=client.post(f'/api/research/collections/{pid}/cninfo-history-assessments',
            json={'basis':'METHOD caller claim','complete':True,'current_coverage_verified':True})
        assert response.status_code==422,response.text
        gaps=client.get(f'/api/research/collections/{pid}/source-gaps').json()
        assert gaps['historical_source_assessments']==[] and gaps['forward_started_at'] is None
