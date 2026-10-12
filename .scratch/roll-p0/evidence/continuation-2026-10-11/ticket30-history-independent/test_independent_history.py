import pytest,httpx
from fastapi.testclient import TestClient
from roll.app import create_app
from test_post_close_packet import setup

def test_independent_exact_historical_values_unknowns_and_frozen_selection(tmp_path,monkeypatch):
    clock='2026-10-12T15:06:00+08:00'
    for module in ['roll.market.post_close_packet','roll.research.prospective']:
        monkeypatch.setattr(module+'.now',lambda:clock)
    def offline(request):raise AssertionError('Independent historical verification must stay offline')
    app=create_app(tmp_path,market_transport=httpx.MockTransport(offline),runtime_role='API')
    with TestClient(app) as client:
        plan=setup(client)
        base='/api/research/collections/'+plan
        before=client.get('/api/account').json()
        response=client.post(base+'/sse-history-assessments',json={'basis':'Independent exact public archived facts'})
        assert response.status_code==201,response.text
        first=response.json()
        assert first['evidence_kind']=='REAL_ARCHIVED_SOURCE_ASSESSMENT'
        assert first['network_calls']==0 and first['historical_pit_claim'] is False
        assert first['current_coverage_verified'] is False
        daily=first['daily_facts'][0]
        assert daily['close']=='54.92'
        assert daily['volume_shares']=='128845200.00' and daily['amount_yuan']=='7005041400.00'
        assert daily['amount_precision_yuan']=='100'
        assert daily['trade_date']=='2025-12-31' and daily['published_at'] is None and daily['revision_chain'] is None
        assert daily['received_at']=='2026-10-09T02:54:16.837153+00:00' and daily['available_at']==clock
        assert daily['model_daily_input_allowed'] is False and daily['current_board_unit_authority'] is False
        halt=first['suspension_facts'][0]
        assert halt['reported_start_date']=='2016-02-16' and halt['reported_end_date']=='2016-02-26'
        assert halt['stop_date_reported']=='-' and halt['resume_date'] is None and halt['published_at'] is None
        assert halt['reason']=='重要事项未公告' and halt['current_status_authority'] is False
        audit=next(a for a in first['query_audits'] if a['source_role']=='suspension')
        assert audit['returned_count']==78 and audit['declared_total']==78
        assert audit['finite_query_completed'] is True and audit['query_date']=='2016-02-16'
        inconsistent=next(a for a in first['query_audits'] if a['source_role']=='suspension_inconsistent')
        assert inconsistent['returned_count']==0 and inconsistent['declared_total']==10
        assert inconsistent['requested_page_size']==100 and inconsistent['page_size']==1000
        assert inconsistent['finite_query_completed'] is False and inconsistent['no_event_authority'] is False
        assert inconsistent['gaps']==['SSE_HISTORY_SUSPENSION_TOTAL_RETURNED_MISMATCH','SSE_HISTORY_SUSPENSION_REQUEST_RESPONSE_PAGE_SIZE_MISMATCH']
        empty=next(a for a in first['query_audits'] if a['source_role']=='daily_empty')
        assert empty['returned_count']==0 and empty['query_date']=='2013-01-04'
        assert empty['no_event_authority'] is False and empty['gaps']==['SSE_HISTORY_DAILY_NO_ROWS_NOT_NO_TRADE_EVIDENCE']
        packet_response=client.post(base+'/post-close-packets',json={'basis':'Independent frozen original assessment IDs'})
        assert packet_response.status_code==201,packet_response.text
        packet=packet_response.json()
        assert packet['rows']==[] and packet['historical_source_assessments']==[first]
        assert packet['forward_admissible'] is False and packet['forward_started_at'] is None
        second=client.post(base+'/sse-history-assessments',json={'basis':'Same-cutoff later finite assessment'}).json()
        assert second['assessment_id']!=first['assessment_id']
        one=client.get(base+'/source-gaps').json();two=client.get(base+'/source-gaps').json()
        assert one==two and len(one['historical_source_assessments'])==2
        assert one['capability']=='NOT_GRANTED' and one['forward_started_at'] is None
        assert 'CURRENT_COMPLETE_DAILY_MISSING' in one['gaps']
        assert 'CURRENT_BOARD_UNIT_SOURCE_UNVERIFIED' in one['source_gaps']
        replay=client.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay')
        assert replay.status_code==200,replay.text
        assert replay.json()['matches_original'] and replay.json()['network_calls']==0
        assert client.post(base+'/sse-history-assessments',json={'basis':'Cannot certify completeness','complete_current_status':True}).status_code==422
        assert client.get('/api/account').json()==before
        assert client.get('/api/reviews/health').json()['worker_state']=='STOPPED'
