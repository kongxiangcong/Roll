import json
import httpx
from datetime import datetime
from fastapi.testclient import TestClient
from fastapi import HTTPException
import pytest
from roll.app import create_app
from test_post_close_packet import setup
from known_obligation_method_app import protocol
from test_known_obligation_audit import test_read_only_forward_input_consumer_binds_protocol_without_registering_forward as forward_case

CLOCK='2026-10-12T15:06:00+08:00'
def fix(monkeypatch,clock=CLOCK):
    for module in ['roll.market.post_close_packet','roll.research.prospective','roll.market.evidence']:
        monkeypatch.setattr(module+'.now',lambda:clock)

def test_literals_binding_replay_and_owned_tamper(tmp_path,monkeypatch):
    fix(monkeypatch)
    calls=[]
    raw=json.dumps({'date':20261012,'time':150005,'list':[['600362','江西铜业',100,101,99,100,1234,123400,100]]}).encode()
    def supplier(request):
        calls.append(str(request.url));return httpx.Response(200,content=raw)
    app=create_app(tmp_path,market_transport=httpx.MockTransport(supplier))
    with TestClient(app) as c:
        pid=setup(c);p=protocol(c,tmp_path);account=c.get('/api/account').json()
        assert p['status']=='DESIGN_REGISTERED'
        url=f'/api/research/collections/{pid}/known-obligation-audits'
        first=c.post(url,json={'protocol_id':p['protocol_id'],'basis':'Independent METHOD known schedule'});assert first.status_code==201,first.text
        a=first.json();assert not calls
        assert a['known_notice_count']==a['resolution_unknown_count']==14 and a['confirmed_pending_count']==0
        assert a['protocol_effective_window']['start_date']=='2026-10-12'
        assert a['protocol_effective_window']['end_date']=='2026-11-09'
        assert a['protocol_effective_window']['horizon_sessions']==20
        assert a['protocol_effective_window']['calendar_source_hashes']==['7ea10c16202c4748f0ad5bcdfe6ee07b85b5462589504604b17c9d63865e7d8c']
        assert not a['pending_older_obligations_complete'] and not a['complete_action_coverage'] and not a['historical_pit_claim']
        assert a['account_events_added']==a['confirmatory_checkpoints_added']==0
        assert a['protocol_context']['protocol_fingerprint']==p['protocol_fingerprint']
        for n in a['notices']:
            assert n['window_relation']=='OLDER_SCHEDULE_WITH_RESOLUTION_UNKNOWN'
            assert n['fulfillment_state']==n['cancellation_state']==n['deferral_state']==n['owned_entitlement']=='UNKNOWN'
            assert n['first_available_at'] is None and n['resolved_at'] is None and n['actual_account_receipt'] is None
            assert n['date_precision']=='DATE' and n['resolution_evidence']==[] and n['pdf_bytes']>0
            assert len(n['pdf_raw_hash'])==64 and n['cash_mapping_hash']==a['cash_mapping_hash']
        old=c.post(f'/api/research/collections/{pid}/post-close',json={'basis':'Independent METHOD capture'});assert old.status_code==201,old.text
        packet=old.json();assert packet['rows'][0]['known_obligation_audit_ids']==[a['audit_id']]
        assert packet['known_obligation_audits']==[a] and not packet['forward_admissible'] and packet['forward_started_at'] is None
        assert c.post(url,json={'protocol_id':p['protocol_id'],'basis':'same cutoff append'}).status_code==201
        assert len(c.get(url,params={'protocol_id':p['protocol_id']}).json())==2
        replayurl='/api/research/post-close-packets/'+packet['packet_id']+'/replay'
        replay=c.post(replayurl);assert replay.status_code==200 and replay.json()['matches_original'],replay.text
        assert len(calls)==1
        inputs=c.get(f'/api/research/collections/{pid}/source-gaps').json()
        assert len(inputs['known_obligation_audits'])==2 and inputs['capability']=='NOT_GRANTED'
        assert c.get('/api/account').json()==account
        original=app.state.evidence.raw(a['archive']['sha256']);body=original.read_bytes();original.write_bytes(b'own corrupt audit')
        assert c.get(url).status_code==409 and c.post(replayurl).status_code==409
        original.write_bytes(body);assert c.post(replayurl).json()['matches_original']
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:(_ for _ in ()).throw(AssertionError('offline restart'))))) as c:
        assert c.post(replayurl).json()['matches_original']
        assert c.get('/api/research/protocols/'+p['protocol_id']).json()['forward_started_at'] is None

def test_empty_original_scope_flags_and_unknown_calendar(tmp_path,monkeypatch):
    fix(monkeypatch)
    app=create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:(_ for _ in ()).throw(AssertionError('offline'))))
    with TestClient(app) as c:
        pid=setup(c);p=protocol(c,tmp_path)
        packet=c.post(f'/api/research/collections/{pid}/post-close-packets',json={'basis':'before audit'}).json()
        assert packet['known_obligation_audits']==[]
        url=f'/api/research/collections/{pid}/known-obligation-audits'
        for flag in ['cutoff','actual','current','complete_action_coverage','pending_older_obligations_complete','resolved_at']:
            assert c.post(url,json={'protocol_id':p['protocol_id'],'basis':'reject authority',flag:True}).status_code==422
        draft=c.post('/api/research/protocols',json={'basis':'own draft'}).json()
        assert c.post(url,json={'protocol_id':draft['protocol_id'],'basis':'no design'}).status_code==422
        successor=c.post('/api/research/protocols',json={'dataset_id':p['dataset_id'],'predecessor_id':p['protocol_id'],'basis':'own successor'}).json()
        for reg in [p,successor]:
            assert c.post(url,json={'protocol_id':reg['protocol_id'],'basis':'scoped known'}).status_code==201
        assert len(c.get(url,params={'protocol_id':p['protocol_id']}).json())==1
        assert len(c.get(url,params={'protocol_id':successor['protocol_id']}).json())==1
        assert c.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay').json()['matches_original']
        fix(monkeypatch,'2026-12-31T15:06:00+08:00')
        unknown=c.post(url,json={'protocol_id':p['protocol_id'],'basis':'missing 2027 calendar'}).json()
        assert unknown['protocol_effective_window']['end_date'] is None and unknown['protocol_effective_window']['covered_future_sessions']==0
        assert 'PROTOCOL_REFERENCE_WINDOW_CALENDAR_UNKNOWN' in unknown['gaps']
        assert unknown['resolution_unknown_count']==14 and not unknown['pending_older_obligations_complete']

def test_selected_forward_read_only_protocol_isolation(tmp_path,monkeypatch):
    forward_case(tmp_path,monkeypatch)
