"""Public offline action-window successor and deterministic consumer; no model fit."""
import httpx
import json
import pytest
from datetime import datetime
from fastapi import HTTPException
from fastapi.testclient import TestClient
from roll.app import create_app
from test_sse_company_actions import actual_bodies
from test_sse_company_contract import clock, start
from known_obligation_method_app import protocol
from test_post_close_packet import setup


def fixture(client, directory, capture=False):
    base = '/api/research/collections/'+setup(client) if capture else start(client)
    registered = protocol(client, directory)
    ordinary = client.post(base+('/post-close' if capture else '/post-close-packets'), json={'basis':'Original immutable daily packet'}).json()
    raw = client.post(base+'/sse-company-actions', json={'basis':'Offline saved public action originals'}).json()
    assessment = client.post(base+'/sse-action-assessments', json={'source_receipt_id':raw['receipt_id'], 'basis':'Explicit saved observed schema'}).json()
    action = client.post(base+'/sse-action-packets', json={'predecessor_packet_id':ordinary['packet_id'],
        'source_receipt_id':raw['receipt_id'], 'assessment_ids':[assessment['assessment_id']], 'basis':'Original action successor'}).json()
    obligation = client.post(base+'/known-obligation-audits', json={'protocol_id':registered['protocol_id'], 'basis':'Protocol known obligation reference'}).json()
    command = {'protocol_id':registered['protocol_id'], 'predecessor_packet_id':action['packet_id'],
        'known_obligation_audit_id':obligation['audit_id'], 'basis':'Consume explicit action and obligation references'}
    return base, registered, ordinary, action, obligation, command


def fixed_clock(monkeypatch, stamp='2026-10-12T15:06:00+08:00'):
    clock(monkeypatch, stamp)
    for module in ['roll.market.sse_company_actions', 'roll.market.sse_action_assessments', 'roll.market.action_window']:
        monkeypatch.setattr(module+'.now', lambda:stamp)


def test_protocol_window_successor_consumes_reported_rows_and_pins_original_ids(tmp_path, monkeypatch):
    fixed_clock(monkeypatch)
    bodies = actual_bodies()
    calls = []
    def supplier(request):
        calls.append(request)
        return httpx.Response(200, content=bodies[request.url.params['sqlId']])
    app = create_app(tmp_path, market_transport=httpx.MockTransport(supplier), runtime_role='API')
    with TestClient(app) as client:
        base, registered, ordinary, action, obligation, command = fixture(client, tmp_path)
        response = client.post(base+'/action-window-packets', json=command)
        assert response.status_code == 201, response.text
        packet = response.json()
        assert packet['packet_type'] == 'ACTION_WINDOW_SUCCESSOR'
        assert packet['predecessor'] == action
        assert packet['known_obligation_audit'] == obligation
        assert packet['protocol_effective_window']['end_date'] == '2026-11-09'
        assert len(packet['candidate_audits']) == 5
        first = packet['candidate_audits'][0]
        assert first['record_date_reported'] == '2026-07-16'
        assert first['dividend_date_reported'] == '2026-07-17'
        assert first['window_relation'] == 'OLDER_REPORTED_DATES_LIFECYCLE_UNKNOWN'
        assert first['date_precision'] == 'DATE' and first['lifecycle_state'] == 'UNKNOWN'
        assert first['notice_identity_link'] is None
        assert packet['missing_reported_rows'] == 1 and not packet['complete_action_coverage']
        inputs = client.get(base+'/action-window-inputs', params={'protocol_id':registered['protocol_id']})
        assert inputs.status_code == 200, inputs.text
        assert inputs.json()['packet_ids'] == [packet['packet_id']]
        assert len(inputs.json()['action_candidates']) == 5
        assert inputs.json()['missing_reported_rows'] == 1
        assert not inputs.json()['forward_admissible'] and inputs.json()['forward_started_at'] is None
        assert client.post('/api/research/post-close-packets/'+ordinary['packet_id']+'/replay').json()['matches_original']
        assert len(calls) == 2


def test_saved_window_replay_restart_future_cutoff_and_protocol_isolation(tmp_path, monkeypatch):
    fixed_clock(monkeypatch)
    bodies = actual_bodies()
    transport = httpx.MockTransport(lambda r:httpx.Response(200,content=bodies[r.url.params['sqlId']]))
    app = create_app(tmp_path, market_transport=transport, runtime_role='API')
    with TestClient(app) as client:
        base, registered, ordinary, action, obligation, command = fixture(client,tmp_path)
        packet = client.post(base+'/action-window-packets',json=command).json()
        # Repeated normalization does not change the saved predecessor or bind latest IDs.
        newer = client.post(base+'/sse-action-assessments',json={'source_receipt_id':action['source_receipt_ids'][0], 'basis':'Later same-cutoff assessment'}).json()
        assert newer['assessment_id'] not in packet['assessment_ids']
        replay = client.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay')
        assert replay.status_code==200 and replay.json()['matches_original'],replay.text
        second = client.post('/api/research/protocols',json={'dataset_id':registered['dataset_id'], 'predecessor_id':registered['protocol_id'], 'basis':'Separate METHOD protocol'}).json()
        assert client.get(base+'/action-window-inputs',params={'protocol_id':second['protocol_id']}).json()['packet_ids']==[]
        assert client.post(base+'/action-window-packets',json={**command,'protocol_id':second['protocol_id']}).status_code==409
        assert client.post(base+'/action-window-packets',json={**command,'forward_admissible':True}).status_code==422
        # Future-known originals are refused even though their reported event dates are older.
        fixed_clock(monkeypatch,'2026-10-12T15:05:59+08:00')
        assert client.get(base+'/action-window-inputs',params={'protocol_id':registered['protocol_id']}).json()['packet_ids']==[]
        # The predecessor owner already refuses replay beyond its Host clock with 422.
        assert client.post(base+'/action-window-packets',json=command).status_code in {409,422}
        fixed_clock(monkeypatch)
    def offline(request):raise AssertionError('Restart replay cannot request any source')
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(offline),runtime_role='API')) as client:
        assert client.get(base+'/action-window-packets/'+packet['packet_id']).json()==packet
        assert client.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay').json()['matches_original']


def test_read_only_forward_consumer_uses_window_and_refuses_damaged_selected_chain(tmp_path,monkeypatch):
    fixed_clock(monkeypatch)
    bodies=actual_bodies()
    app=create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,content=bodies[r.url.params['sqlId']])),runtime_role='API')
    with TestClient(app) as client:
        base,registered,ordinary,action,obligation,command=fixture(client,tmp_path)
        packet=client.post(base+'/action-window-packets',json=command).json()
        # Existing agreed read-only forward adapter seam. No forward registration or model call.
        rows,gaps=app.state.forward.rows({'namespace':'FORWARD','protocol_id':registered['protocol_id']},
            {'scope':{'instruments':['SSE:600362']}},datetime.fromisoformat('2026-10-12T15:06:00+08:00'))
        assert rows==[] and 'ACTION_SOURCE_REPORTED_ROWS_MISSING:1' in gaps
        assert 'ACTION_WINDOW_PACKET:'+packet['packet_id'] in gaps
        app.state.evidence.raw(packet['archive']['sha256']).write_bytes(b'owned damaged fixture')
        with pytest.raises(HTTPException) as failure:
            app.state.forward.rows({'namespace':'FORWARD','protocol_id':registered['protocol_id']},
                {'scope':{'instruments':['SSE:600362']}},datetime.fromisoformat('2026-10-12T15:06:00+08:00'))
        assert failure.value.status_code==409
        saved=client.get('/api/research/protocols/'+registered['protocol_id']).json()
        assert saved['forward_started_at'] is None and saved['capability']=='NOT_GRANTED'


def test_successor_attaches_actions_to_original_daily_rows_without_promoting_quote_or_completion(tmp_path,monkeypatch):
    fixed_clock(monkeypatch)
    bodies=actual_bodies()
    daily=json.dumps({'date':20261012,'time':150005,'list':[
        ['600362','江西铜业',100,101,99,100,1234,123400,100]]}).encode()
    def supplier(request):
        return httpx.Response(200,content=bodies[request.url.params['sqlId']] if 'sqlId' in request.url.params else daily)
    app=create_app(tmp_path,market_transport=httpx.MockTransport(supplier),runtime_role='API')
    with TestClient(app) as client:
        base,registered,ordinary,action,obligation,command=fixture(client,tmp_path,capture=True)
        response=client.post(base+'/action-window-packets',json=command)
        assert response.status_code==201,response.text
        packet=response.json()
        assert len(packet['reference_rows'])==1
        row=packet['reference_rows'][0]
        assert row['trade_date']=='2026-10-12' and row['close']=='100'
        assert row['action_assessment_ids']==action['assessment_ids']
        assert row['action_source_receipt_ids']==action['source_receipt_ids']
        assert len(row['reported_action_candidates'])==5 and row['action_missing_reported_rows']==1
        assert row['volume_unit']=='UNKNOWN' and not row['model_daily_input_allowed']
        assert packet['daily_reference_packet_id']==ordinary['packet_id']
        assert packet['daily_reference_knowledge_cutoff']==ordinary['knowledge_cutoff']
        assert not packet['forward_admissible'] and packet['account_events_added']==0
        inputs=client.get(base+'/action-window-inputs',params={'protocol_id':registered['protocol_id']}).json()
        assert inputs['reference_rows']==packet['reference_rows']
        assert client.get(base+'/sse-action-packets/'+action['packet_id']).json()==action


def test_explicit_empty_selection_and_unknown_calendar_do_not_manufacture_action_coverage(tmp_path,monkeypatch):
    fixed_clock(monkeypatch,'2026-12-31T15:06:00+08:00')
    def offline(request):raise AssertionError('Empty selection remains offline')
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(offline),runtime_role='API')) as client:
        base=start(client);registered=protocol(client,tmp_path)
        ordinary=client.post(base+'/post-close-packets',json={'basis':'Empty original daily reference'}).json()
        action=client.post(base+'/sse-action-packets',json={'source_receipt_id':None,'assessment_ids':[],
            'predecessor_packet_id':ordinary['packet_id'],'basis':'Explicit empty action selection'}).json()
        obligation=client.post(base+'/known-obligation-audits',json={'protocol_id':registered['protocol_id'],'basis':'Unknown future calendar kept unknown'}).json()
        response=client.post(base+'/action-window-packets',json={'protocol_id':registered['protocol_id'],
            'predecessor_packet_id':action['packet_id'],'known_obligation_audit_id':obligation['audit_id'],'basis':'Explicit empty reference successor'})
        assert response.status_code==201,response.text
        value=response.json()
        assert value['source_receipt_ids']==value['assessment_ids']==value['candidate_audits']==[]
        assert value['missing_reported_rows']==0 and value['protocol_effective_window']['end_date'] is None
        assert 'PROTOCOL_REFERENCE_WINDOW_CALENDAR_UNKNOWN' in value['gaps']
        assert 'EXPLICIT_ACTION_ASSESSMENT_MISSING' in value['gaps']
        assert not value['negative_coverage'] and not value['complete_action_coverage']
        fixed_clock(monkeypatch,'2027-01-01T15:06:00+08:00')
        assert client.get(base+'/action-window-inputs',params={'protocol_id':registered['protocol_id']}).json()['packet_ids']==[]
        assert client.post('/api/research/post-close-packets/'+value['packet_id']+'/replay').json()['matches_original']


@pytest.mark.parametrize('target',['source','assessment','obligation','predecessor','calendar'])
def test_consumer_and_replay_refuse_damaged_owned_dependency_chain(tmp_path,monkeypatch,target):
    fixed_clock(monkeypatch)
    bodies=actual_bodies()
    app=create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,content=bodies[r.url.params['sqlId']])),runtime_role='API')
    with TestClient(app) as client:
        base,registered,ordinary,action,obligation,command=fixture(client,tmp_path)
        packet=client.post(base+'/action-window-packets',json=command).json()
        sha={'source':action['source_receipts'][0]['responses']['dividend']['archive']['sha256'],
            'assessment':action['assessments'][0]['archive']['sha256'],
            'obligation':obligation['archive']['sha256'],'predecessor':action['archive']['sha256'],
            'calendar':obligation['protocol_effective_window']['calendar_source_hashes'][0]}[target]
        app.state.evidence.raw(sha).write_bytes(b'owned dependency corruption')
        assert client.get(base+'/action-window-inputs',params={'protocol_id':registered['protocol_id']}).status_code==409
        assert client.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay').status_code==409
