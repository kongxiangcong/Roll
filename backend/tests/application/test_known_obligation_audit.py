"""Known scheduled notices via public API; no account receipt or full coverage claims."""
import httpx
import json
import pytest
from datetime import datetime
from fastapi import HTTPException
from fastapi.testclient import TestClient
from roll.app import create_app
from test_post_close_packet import setup
from known_obligation_method_app import protocol


def test_known_notice_audit_binds_protocol_window_and_keeps_elapsed_schedule_unknown(tmp_path,monkeypatch):
    clock='2026-10-12T15:06:00+08:00'
    monkeypatch.setattr('roll.market.post_close_packet.now',lambda:clock)
    monkeypatch.setattr('roll.research.prospective.now',lambda:clock)
    def offline(request):raise AssertionError('Known-notice audit must stay offline')
    app=create_app(tmp_path,market_transport=httpx.MockTransport(offline))
    with TestClient(app) as client:
        pid=setup(client);registered=protocol(client,tmp_path)
        response=client.post(f'/api/research/collections/{pid}/known-obligation-audits',
            json={'protocol_id':registered['protocol_id'],'basis':'Known scheduled obligations at one protocol window'})
        assert response.status_code==201,response.text
        audit=response.json()
        assert len(audit['notices'])==14
        window=audit['protocol_effective_window']
        assert window['start_date']=='2026-10-12' and window['end_date']=='2026-11-09'
        assert window['horizon_sessions']==registered['design']['horizon_sessions']==20
        assert window['protocol_id']==registered['protocol_id'] and window['calendar_source_hashes']
        assert audit['protocol_context']['protocol_fingerprint']==registered['protocol_fingerprint']
        assert audit['knowledge_cutoff']==clock and audit['confirmatory_checkpoints_added']==0
        assert not audit['pending_older_obligations_complete'] and not audit['complete_action_coverage']
        first=next(n for n in audit['notices'] if n['announcement_id']=='62845175')
        assert first['record_date']=='2013-07-23' and first['ex_date']=='2013-07-24'
        assert first['scheduled_payment_date']=='2013-07-30' and first['date_precision']=='DATE'
        assert first['pdf_raw_hash']=='376fe3f19f2f1482101c75336b6f1ae0cc59896dbe36254a570b76d83d53865e'
        assert first['payment_schedule_relation_to_cutoff']=='BEFORE_CUTOFF_DATE'
        assert first['window_relation']=='OLDER_SCHEDULE_WITH_RESOLUTION_UNKNOWN'
        assert first['fulfillment_state']==first['cancellation_state']==first['deferral_state']=='UNKNOWN'
        assert first['owned_entitlement']=='UNKNOWN' and first['resolved_at'] is None
        assert first['resolution_evidence']==[] and first['actual_account_receipt'] is None
        assert first['first_available_at'] is None and not first['historical_pit_claim']
        assert client.get(f'/api/research/collections/{pid}/known-obligation-audits').json()==[audit]


def test_current_input_consumer_and_old_packet_pin_original_audit_ids(tmp_path,monkeypatch):
    clock='2026-10-12T15:06:00+08:00'
    for module in ['roll.market.post_close_packet','roll.research.prospective','roll.market.evidence']:
        monkeypatch.setattr(module+'.now',lambda:clock)
    raw=json.dumps({'date':20261012,'time':150005,'list':[['600362','江西铜业',100,101,99,100,1234,123400,100]]}).encode()
    app=create_app(tmp_path,market_transport=httpx.MockTransport(lambda request:httpx.Response(200,content=raw)))
    with TestClient(app) as client:
        pid=setup(client);registered=protocol(client,tmp_path)
        url=f'/api/research/collections/{pid}/known-obligation-audits'
        response=client.post(url,json={'protocol_id':registered['protocol_id'],'basis':'Original scoped audit'})
        assert response.status_code==201,response.text
        first=response.json()
        response=client.post(f'/api/research/collections/{pid}/post-close',json={'basis':'METHOD current source, no authority promotion'})
        assert response.status_code==201,response.text
        packet=response.json()
        assert packet['known_obligation_audits']==[first]
        assert packet['rows'][0]['known_obligation_audit_ids']==[first['audit_id']]
        assert 'KNOWN_OLDER_OBLIGATION_RESOLUTION_UNPROVEN:2026-10-12' in packet['gaps']
        assert 'CURRENT_ACTION_COVERAGE_UNPROVEN:2026-10-12' in packet['gaps']
        assert not packet['forward_admissible'] and packet['forward_started_at'] is None
        response=client.post(url,json={'protocol_id':registered['protocol_id'],'basis':'Later same-cutoff audit'})
        assert response.status_code==201,response.text
        second=response.json()
        assert second['audit_id']!=first['audit_id']
        replay=client.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay')
        assert replay.status_code==200 and replay.json()['matches_original'],replay.text
        gaps=client.get(f'/api/research/collections/{pid}/source-gaps').json()
        assert gaps['known_obligation_audits']==[first,second]
        assert 'ALL_OLDER_OBLIGATION_COVERAGE_UNPROVEN' in gaps['known_obligation_gaps']
        assert client.get(url).json()==[first,second]


def test_query_filters_protocol_and_does_not_reselect_empty_original_packet(tmp_path,monkeypatch):
    clock='2026-10-12T15:06:00+08:00'
    monkeypatch.setattr('roll.market.post_close_packet.now',lambda:clock)
    monkeypatch.setattr('roll.research.prospective.now',lambda:clock)
    def offline(request):raise AssertionError('Known-notice audit must stay offline')
    app=create_app(tmp_path,market_transport=httpx.MockTransport(offline))
    with TestClient(app) as client:
        pid=setup(client);first=protocol(client,tmp_path)
        response=client.post('/api/research/protocols',json={'dataset_id':first['dataset_id'],
            'predecessor_id':first['protocol_id'],'basis':'Linked METHOD successor; no real registry clock'})
        assert response.status_code==201,response.text
        second=response.json()
        packet=client.post(f'/api/research/collections/{pid}/post-close-packets',
            json={'basis':'Before any known-obligation audit'}).json()
        assert packet['known_obligation_audits']==[]
        url=f'/api/research/collections/{pid}/known-obligation-audits'
        audits=[]
        for registered in [first,second]:
            response=client.post(url,json={'protocol_id':registered['protocol_id'],'basis':'One protocol reference'})
            assert response.status_code==201,response.text
            audits.append(response.json())
        response=client.get(url,params={'protocol_id':first['protocol_id']})
        assert response.status_code==200,response.text
        assert response.json()==[audits[0]]
        assert client.get(url,params={'protocol_id':second['protocol_id']}).json()==[audits[1]]
        replay=client.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay')
        assert replay.status_code==200 and replay.json()['matches_original'],replay.text


@pytest.mark.parametrize('target',['notice','mapping','calendar','protocol_reference','audit'])
def test_damaged_own_archives_refuse_query_and_packet_replay(tmp_path,monkeypatch,target):
    clock='2026-10-12T15:06:00+08:00'
    monkeypatch.setattr('roll.market.post_close_packet.now',lambda:clock)
    monkeypatch.setattr('roll.research.prospective.now',lambda:clock)
    app=create_app(tmp_path)
    with TestClient(app) as client:
        pid=setup(client);registered=protocol(client,tmp_path)
        url=f'/api/research/collections/{pid}/known-obligation-audits'
        response=client.post(url,json={'protocol_id':registered['protocol_id'],'basis':'Source-bound known schedules'})
        assert response.status_code==201,response.text
        audit=response.json()
        packet=client.post(f'/api/research/collections/{pid}/post-close-packets',json={'basis':'Original bound audit'}).json()
        hashes={'notice':audit['notices'][0]['pdf_raw_hash'],'mapping':audit['cash_mapping_hash'],
            'calendar':audit['protocol_effective_window']['calendar_source_hashes'][0],
            'protocol_reference':audit['protocol_reference_hash'],'audit':audit['archive']['sha256']}
        # Approved original-supplier seam: corrupt only this fixture's copy.
        app.state.evidence.raw(hashes[target]).write_bytes(b'owned damaged fixture')
        assert client.get(url).status_code==409
        assert client.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay').status_code==409


def test_unknown_calendar_end_keeps_registered_horizon_without_inventing_sessions(tmp_path,monkeypatch):
    clock='2026-12-31T15:06:00+08:00'
    monkeypatch.setattr('roll.market.post_close_packet.now',lambda:clock)
    monkeypatch.setattr('roll.research.prospective.now',lambda:clock)
    app=create_app(tmp_path)
    with TestClient(app) as client:
        pid=setup(client);registered=protocol(client,tmp_path)
        response=client.post(f'/api/research/collections/{pid}/known-obligation-audits',
            json={'protocol_id':registered['protocol_id'],'basis':'Missing next-year official calendar remains unknown'})
        assert response.status_code==201,response.text
        audit=response.json();window=audit['protocol_effective_window']
        assert window['horizon_sessions']==20 and window['end_date'] is None
        assert window['covered_future_sessions']==0
        assert window['calendar_dates'][-1]['date']=='2027-01-01'
        assert window['calendar_dates'][-1]['is_trading_day'] is None
        assert 'PROTOCOL_REFERENCE_WINDOW_CALENDAR_UNKNOWN' in audit['gaps']
        assert audit['resolution_unknown_count']==14 and not audit['pending_older_obligations_complete']


def test_command_refuses_client_authority_and_unregistered_design(tmp_path,monkeypatch):
    clock='2026-10-12T15:06:00+08:00'
    monkeypatch.setattr('roll.market.post_close_packet.now',lambda:clock)
    monkeypatch.setattr('roll.research.prospective.now',lambda:clock)
    app=create_app(tmp_path)
    with TestClient(app) as client:
        pid=setup(client);registered=protocol(client,tmp_path)
        url=f'/api/research/collections/{pid}/known-obligation-audits'
        for field in ['complete_action_coverage','pending_older_obligations_complete','actual','current','resolved_at','cutoff']:
            response=client.post(url,json={'protocol_id':registered['protocol_id'],'basis':'Client assertion rejected',field:True})
            assert response.status_code==422,response.text
        draft=client.post('/api/research/protocols',json={'basis':'No registered dataset design'}).json()
        response=client.post(url,json={'protocol_id':draft['protocol_id'],'basis':'No source-bound design'})
        assert response.status_code==422,response.text
        assert 'REGISTERED_INSTRUMENT_AND_20_SESSION_DESIGN_REQUIRED' in response.text
        assert client.get(url).json()==[]


def test_read_only_forward_input_consumer_binds_protocol_without_registering_forward(tmp_path,monkeypatch):
    clock='2026-10-12T15:06:00+08:00'
    monkeypatch.setattr('roll.market.post_close_packet.now',lambda:clock)
    monkeypatch.setattr('roll.research.prospective.now',lambda:clock)
    app=create_app(tmp_path)
    with TestClient(app) as client:
        pid=setup(client);first=protocol(client,tmp_path)
        response=client.post('/api/research/protocols',json={'dataset_id':first['dataset_id'],
            'predecessor_id':first['protocol_id'],'basis':'METHOD successor consumer isolation'})
        assert response.status_code==201,response.text
        second=response.json();audits=[]
        for registered in [first,second]:
            response=client.post(f'/api/research/collections/{pid}/known-obligation-audits',
                json={'protocol_id':registered['protocol_id'],'basis':'Read-only input consumer METHOD fixture'})
            assert response.status_code==201,response.text
            audits.append(response.json())
        # Agreed consumer seam only: empty source input, no forward registration,
        # grant, model call, sample persistence or production clock.
        app.state.evidence.raw(audits[1]['archive']['sha256']).write_bytes(b'owned damaged successor')
        plan={'namespace':'FORWARD','protocol_id':first['protocol_id']}
        frozen={'scope':{'instruments':['SSE:600362']}}
        rows,gaps=app.state.forward.rows(plan,frozen,datetime.fromisoformat(clock))
        assert rows==[] and 'CURRENT_COMPLETE_DAILY_MISSING' in gaps
        app.state.evidence.raw(audits[0]['archive']['sha256']).write_bytes(b'owned damaged selected audit')
        with pytest.raises(HTTPException) as failure:
            app.state.forward.rows(plan,frozen,datetime.fromisoformat(clock))
        assert failure.value.status_code==409
        saved=client.get('/api/research/protocols/'+first['protocol_id']).json()
        assert saved['forward_started_at'] is None and saved['capability']=='NOT_GRANTED'
