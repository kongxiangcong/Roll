"""Fixed official public originals at the HTTP/SQLite/archive boundary, offline only."""
import httpx
import pytest
import json
from fastapi.testclient import TestClient
from roll.app import create_app
from test_post_close_packet import setup


def test_official_historical_daily_keeps_its_own_units_and_receipt_without_current_admission(tmp_path, monkeypatch):
    clock='2026-10-12T15:06:00+08:00'
    monkeypatch.setattr('roll.market.post_close_packet.now',lambda:clock)
    monkeypatch.setattr('roll.research.prospective.now',lambda:clock)
    def offline(request):
        raise AssertionError('Historical originals must not cause a live request')
    app=create_app(tmp_path,market_transport=httpx.MockTransport(offline))
    with TestClient(app) as client:
        pid=setup(client)
        response=client.post(f'/api/research/collections/{pid}/sse-history-assessments',
            json={'basis':'Inspect fixed official archived originals, no current coverage claim'})
        assert response.status_code==201,response.text
        assessment=response.json()
        assert assessment['evidence_kind']=='REAL_ARCHIVED_SOURCE_ASSESSMENT'
        bar=assessment['daily_facts'][0]
        assert bar['trade_date']=='2025-12-31'
        assert [bar[k] for k in ('open','high','low','close')]==['50.25','55.28','50.24','54.92']
        assert bar['volume_shares']=='128845200.00' and bar['amount_yuan']=='7005041400.00'
        assert bar['amount_precision_yuan']=='100' and bar['source_volume_unit']=='10000_SHARES'
        assert bar['received_at']=='2026-10-09T02:54:16.837153+00:00'
        assert bar['available_at']==clock and not bar['historical_pit_claim']
        assert not bar['model_daily_input_allowed'] and not assessment['current_coverage_verified']
        assert bar['unit_source_hash']=='478fb2a72fc5a3725088adb208756e88171f79628956a9f5ca67c900d37def2f'
        packet=client.post(f'/api/research/collections/{pid}/post-close-packets',json={'basis':'Review history separately'}).json()
        assert packet['rows']==[] and not packet['forward_admissible']
        assert packet['historical_source_assessments']==[assessment]
        replay=client.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay')
        assert replay.status_code==200,replay.text
        assert replay.json()['matches_original'] and replay.json()['network_calls']==0
        gaps=client.get(f'/api/research/collections/{pid}/source-gaps').json()
        assert gaps['historical_source_assessments']==[assessment]
        assert 'CURRENT_COMPLETE_DAILY_MISSING' in gaps['gaps']
        assert 'CURRENT_BOARD_UNIT_SOURCE_UNVERIFIED' in gaps['source_gaps']
        assert gaps['forward_started_at'] is None and gaps['capability']=='NOT_GRANTED'


def test_official_suspension_proves_returned_event_and_one_date_query_only(tmp_path,monkeypatch):
    clock='2026-10-12T15:06:00+08:00'
    monkeypatch.setattr('roll.market.post_close_packet.now',lambda:clock)
    app=create_app(tmp_path,market_transport=httpx.MockTransport(lambda request: (_ for _ in ()).throw(AssertionError('offline'))))
    with TestClient(app) as client:
        pid=setup(client)
        value=client.post(f'/api/research/collections/{pid}/sse-history-assessments',json={'basis':'Inspect returned halt event'}).json()
        assert len(value['suspension_facts'])==1
        event=value['suspension_facts'][0]
        assert event['instrument']=='SSE:600362' and event['reason']=='重要事项未公告'
        assert event['reported_start_date']=='2016-02-16' and event['reported_end_date']=='2016-02-26'
        assert event['stop_time_reported']=='自2016-02-16起连续停牌' and event['stop_date_reported']=='-'
        assert event['resume_date'] is None and event['published_at'] is None
        assert not event['complete_status_verified'] and not event['current_status_authority']
        audit=next(a for a in value['query_audits'] if a['source_role']=='suspension')
        assert audit['returned_count']==78 and audit['declared_total']==78
        assert audit['query_date']=='2016-02-16' and audit['finite_query_completed']
        assert not audit['complete_current_status'] and not audit['no_event_authority']
        assert event['query_raw_hash']==audit['raw_hash']


def test_zero_rows_with_nonzero_total_and_old_empty_daily_stay_named_gaps(tmp_path,monkeypatch):
    clock='2026-10-12T15:06:00+08:00'
    monkeypatch.setattr('roll.market.post_close_packet.now',lambda:clock)
    monkeypatch.setattr('roll.research.prospective.now',lambda:clock)
    app=create_app(tmp_path)
    with TestClient(app) as client:
        pid=setup(client)
        value=client.post(f'/api/research/collections/{pid}/sse-history-assessments',json={'basis':'Preserve failed finite query evidence'}).json()
        audit=next(a for a in value['query_audits'] if a['source_role']=='suspension_inconsistent')
        assert audit['returned_count']==0 and audit['declared_total']==10
        assert audit['requested_start_date']=='2013-01-01' and audit['requested_end_date']=='2025-12-31'
        assert not audit['finite_query_completed'] and not audit['no_event_authority']
        assert 'SSE_HISTORY_SUSPENSION_TOTAL_RETURNED_MISMATCH' in audit['gaps']
        empty=next(a for a in value['query_audits'] if a['source_role']=='daily_empty')
        assert empty['returned_count']==0 and empty['query_date']=='2013-01-04'
        assert not empty['no_event_authority'] and not empty['complete_current_status']
        gap_response=client.get(f'/api/research/collections/{pid}/source-gaps')
        assert gap_response.status_code==200,gap_response.text
        gaps=gap_response.json()
        assert 'SSE_HISTORY_SUSPENSION_TOTAL_RETURNED_MISMATCH' in gaps['historical_source_gaps']
        assert 'SSE_HISTORY_DAILY_NO_ROWS_NOT_NO_TRADE_EVIDENCE' in gaps['historical_source_gaps']
        assert not gaps['forward_admissible']


@pytest.mark.parametrize('role',['daily_units','suspension_query_js','suspension'])
def test_archived_history_dependency_damage_refuses_packet_replay(tmp_path,monkeypatch,role):
    clock='2026-10-12T15:06:00+08:00'
    monkeypatch.setattr('roll.market.post_close_packet.now',lambda:clock)
    monkeypatch.setattr('roll.research.prospective.now',lambda:clock)
    app=create_app(tmp_path)
    with TestClient(app) as client:
        pid=setup(client)
        assessment=client.post(f'/api/research/collections/{pid}/sse-history-assessments',json={'basis':'Original binding'}).json()
        packet=client.post(f'/api/research/collections/{pid}/post-close-packets',json={'basis':'Original packet'}).json()
        mapping=json.loads(client.get('/api/data/archives/'+assessment['mapping_hash']).content)
        source=next(s for s in mapping['sources'] if s['role']==role)
        app.state.evidence.raw(source['sha256']).write_bytes(b'METHOD test damage, not original public source')
        replay=client.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay')
        assert replay.status_code==409,replay.text


def test_old_packet_keeps_original_assessment_ids_after_same_cutoff_append(tmp_path,monkeypatch):
    clock='2026-10-12T15:06:00+08:00'
    monkeypatch.setattr('roll.market.post_close_packet.now',lambda:clock)
    monkeypatch.setattr('roll.research.prospective.now',lambda:clock)
    app=create_app(tmp_path)
    with TestClient(app) as client:
        pid=setup(client)
        first=client.post(f'/api/research/collections/{pid}/sse-history-assessments',json={'basis':'Original finite assessment'}).json()
        packet=client.post(f'/api/research/collections/{pid}/post-close-packets',json={'basis':'Immutable selection'}).json()
        second=client.post(f'/api/research/collections/{pid}/sse-history-assessments',json={'basis':'Later same-clock inspection'}).json()
        assert first['assessment_id']!=second['assessment_id']
        replay=client.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay')
        assert replay.status_code==200,replay.text
        assert replay.json()['matches_original']
        assert packet['historical_source_assessments']==[first]
        assert len(client.get(f'/api/research/collections/{pid}/source-gaps').json()['historical_source_assessments'])==2


def test_historical_statistic_units_never_complete_current_board_input(tmp_path,monkeypatch):
    clock='2026-10-12T15:06:00+08:00'
    for module in ['roll.market.post_close_packet','roll.research.prospective','roll.market.evidence']:
        monkeypatch.setattr(module+'.now',lambda:clock)
    raw=json.dumps({'date':20261012,'time':150005,'list':[['600362','江西铜业',100,101,99,100,1234,123400,100]]}).encode()
    app=create_app(tmp_path,market_transport=httpx.MockTransport(lambda request:httpx.Response(200,content=raw)))
    with TestClient(app) as client:
        pid=setup(client)
        client.post(f'/api/research/collections/{pid}/sse-history-assessments',json={'basis':'Different historical endpoint units'})
        response=client.post(f'/api/research/collections/{pid}/post-close',json={'basis':'METHOD current board source'})
        assert response.status_code==201,response.text
        packet=response.json()
        assert len(packet['historical_source_assessments'])==1
        assert packet['rows'][0]['volume_unit']=='UNKNOWN' and packet['rows'][0]['amount_yuan'] is None
        assert 'CLOSING_VOLUME_AMOUNT_UNIT_AND_TURNOVER_SCOPE_UNVERIFIED:2026-10-12' in packet['gaps']
        assert not packet['forward_admissible'] and packet['forward_started_at'] is None
