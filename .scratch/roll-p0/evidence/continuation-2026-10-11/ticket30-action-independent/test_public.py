"""Three independent finite offline public action assessment checks."""
import json,hashlib
from pathlib import Path
import httpx
from fastapi.testclient import TestClient
from roll.app import create_app
from test_sse_company_actions import method_clock,actual_bodies,FH,SG
from test_sse_company_contract import start

HERE=Path(__file__).resolve().parent
OWNER=Path('D:/dsh-proj/Roll/.scratch/worktrees/ticket30-producer')
EVIDENCE=OWNER/'.scratch/roll-p0/evidence/30-sse-company-actions'

def post(client,path,body):
    r=client.post(path,json=body);assert r.status_code==201,r.text;return r.json()

def test_saved_actual_fresh_copy_has_fixed_replay_current_refusal_and_no_new_capture(monkeypatch):
    method_clock(monkeypatch);setup=json.loads((HERE/'integrity-copy.json').read_bytes());profile=Path(setup['fresh_copy'])
    summary=json.loads((EVIDENCE/'actual-assessment-summary.json').read_bytes());calls=[]
    def forbidden(request):calls.append(str(request.url));raise AssertionError('Independent actual-copy consumer cannot send HTTP')
    fixture=httpx.MockTransport(forbidden)
    with TestClient(create_app(profile,market_transport=fixture,runtime_role='API')) as client:
        base='/api/research/collections/'+summary['collection_plan_id']
        raw=client.get(base+'/sse-company-action-receipts').json()[0]
        assert raw['receipt_id']==summary['receipt_id'] and raw['evidence_kind']=='REAL_SOURCE_ASSESSMENT'
        assert raw['implementation_fingerprint']==setup['source_guard']['collector_fingerprint']
        old=post(client,base+'/post-close-packets',{'basis':'Independent fixed predecessor before derived assessment'})
        command={'predecessor_packet_id':old['packet_id'],'source_receipt_id':None,'assessment_ids':[],'basis':'Independent explicit empty action selection'}
        empty=post(client,base+'/sse-action-packets',command)
        a=post(client,base+'/sse-action-assessments',{'source_receipt_id':raw['receipt_id'],'basis':'Independent offline saved public first page'})
        assert a['role_audits']['dividend']['returned_count']==5 and a['role_audits']['dividend']['total_reported']==6
        assert a['role_audits']['dividend']['page_count_reported']==2 and a['role_audits']['dividend']['missing_reported_rows']==1
        assert a['role_audits']['send_share']['returned_count']==0 and a['role_audits']['send_share']['negative_coverage'] is False
        row=a['candidates'][0]
        assert row['record_date_reported']=='2026-07-16' and row['dividend_date_reported']=='2026-07-17' and row['cash_before_tax_exact']=='0.6'
        assert row['authoritative_event_id'] is None and row['authoritative_version_id'] is None and row['payment_fulfilled'] is None
        assert row['cash_per_share_unit']==row['lifecycle_state']=='UNKNOWN' and row['source_row_pointer']=='/result/0'
        command.update(source_receipt_id=raw['receipt_id'],assessment_ids=[a['assessment_id']])
        packet=post(client,base+'/sse-action-packets',command)
        later=post(client,base+'/sse-action-assessments',{'source_receipt_id':raw['receipt_id'],'basis':'Independent same-cutoff later assessment'})
        assert later['assessment_id']!=a['assessment_id'] and packet['assessment_ids']==[a['assessment_id']]
        assert packet['predecessor']==old and empty['assessment_ids']==[] and empty['source_receipt_ids']==[]
        for saved in [old,empty,packet]:
            r=client.post('/api/research/post-close-packets/'+saved['packet_id']+'/replay');assert r.status_code==200 and r.json()['matches_original'] and r.json()['network_calls']==0
        for ids in [['missing'],[a['assessment_id'],a['assessment_id']]]:assert client.post(base+'/sse-action-packets',json={**command,'assessment_ids':ids}).status_code==409
        assert client.post(base+'/sse-action-packets',json={**command,'complete_action_coverage':True}).status_code==422
        current=client.get(base+'/sse-action-assessments/current').json()
        assert not current['current_complete_action_coverage'] and not current['system_usable'] and current['forward_started_at'] is None
        assert not packet['forward_admissible'] and not packet['system_usable'] and packet['capability']=='NOT_GRANTED'
        assert client.get('/api/actions/current?instrument=SSE:600362').json()['decisions']==[]
        assert client.get(base+'/source-gaps').json()['action_assessments']==[a,later]
        assert client.post(base+'/sse-company-actions',json={'basis':'Independent cached repeat cannot restart closed source budget'}).json()==raw
        assert client.get('/api/account').json()['version']==0 and not calls
        (profile/'independent-public-receipts.json').write_text(json.dumps({'raw':raw,'assessment':a,'old':old,'empty':empty,'packet':packet,'current':current},ensure_ascii=False,indent=2),encoding='utf-8')
    with TestClient(create_app(profile,market_transport=fixture,runtime_role='API')) as client:
        assert client.get(base+'/sse-action-packets/'+packet['packet_id']).json()==packet
        assert client.get(base+'/sse-action-packets/'+empty['packet_id']).json()==empty
        assert client.post(base+'/sse-company-actions',json={'basis':'Independent restart cached source receipt'}).json()==raw
        assert not calls
    for record in setup['copied_registered_files']:
        body=Path(record['source']).read_bytes();assert hashlib.sha256(body).hexdigest()==record['sha256'] and len(body)==record['bytes']
    assert hashlib.sha256((EVIDENCE/'actual-budget-closure.json').read_bytes()).hexdigest()==setup['closure_sha256']

def test_unproved_page_and_nonempty_send_share_refuse_with_raw_retained(tmp_path,monkeypatch):
    method_clock(monkeypatch)
    for defect in ['page','share']:
        bodies=actual_bodies();role=FH if defect=='page' else SG;value=json.loads(bodies[role])
        if defect=='page':value['pageHelp']['pageNo']=2
        else:value['result']=[{'SECURITY_CODE_A':'600362'}];value['pageHelp'].update(total=1,pageCount=1,data=value['result'])
        bodies[role]=json.dumps(value).encode();calls=[]
        def supplier(request):
            calls.append(str(request.url));assert request.url.host=='query.sse.com.cn' and request.url.path=='/commonQuery.do'
            return httpx.Response(200,content=bodies[request.url.params['sqlId']])
        with TestClient(create_app(tmp_path/defect,market_transport=httpx.MockTransport(supplier),runtime_role='API')) as client:
            base=start(client);raw=post(client,base+'/sse-company-actions',{'basis':'Independent finite malformed source raw retained'})
            r=client.post(base+'/sse-action-assessments',json={'source_receipt_id':raw['receipt_id'],'basis':'Independent unsupported schema refusal'});assert r.status_code==409,r.text
            assert client.get(base+'/sse-company-action-receipts').json()==[raw] and client.get(base+'/sse-action-assessments').json()==[]
            assert len(calls)==2

def test_archive_damage_refuses_new_current_and_replay_without_changing_old_packet(tmp_path,monkeypatch):
    method_clock(monkeypatch)
    for role in ['raw','mapping','plan','assessment']:
        bodies=actual_bodies();calls=[]
        def supplier(request):calls.append(str(request.url));return httpx.Response(200,content=bodies[request.url.params['sqlId']])
        app=create_app(tmp_path/role,market_transport=httpx.MockTransport(supplier),runtime_role='API')
        with TestClient(app) as client:
            base=start(client);old=post(client,base+'/post-close-packets',{'basis':'Independent unchanged old packet before action capture'})
            raw=post(client,base+'/sse-company-actions',{'basis':'Independent fixed source dependency'})
            a=post(client,base+'/sse-action-assessments',{'source_receipt_id':raw['receipt_id'],'basis':'Independent explicit assessment dependency'})
            packet=post(client,base+'/sse-action-packets',{'source_receipt_id':raw['receipt_id'],'assessment_ids':[a['assessment_id']],'predecessor_packet_id':old['packet_id'],'basis':'Independent fixed action packet dependency'})
            sha={'raw':raw['responses']['dividend']['archive']['sha256'],'mapping':a['schema_mapping_hash'],'plan':raw['capture_plan_archive']['sha256'],'assessment':a['archive']['sha256']}[role]
            app.state.evidence.raw(sha).write_bytes(b'independent own scenario corruption')
            assert client.get(base+'/sse-action-assessments/current').status_code==409
            assert client.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay').status_code==409
            oldreplay=client.post('/api/research/post-close-packets/'+old['packet_id']+'/replay');assert oldreplay.status_code==200 and oldreplay.json()['matches_original']
            assert len(calls)==2 and client.get('/api/account').json()['version']==0
