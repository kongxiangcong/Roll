"""Host producer through HTTP, genuine SQLite/archive; injected suppliers stay METHOD."""
import json
import httpx
import pytest
import hashlib
from pathlib import Path
from roll.market.post_close_packet import closing_facts
from io import BytesIO
import pyarrow as pa
import pyarrow.parquet as pq
from roll.accounts.ledger import encode
from fastapi.testclient import TestClient
from roll.app import create_app
from test_market_directory import establish


def setup(client):
    establish(client, ['SSE:600362'])
    assert client.post('/api/market/identities', json={'instrument':'SSE:600362','exchange':'SSE',
        'board':'MAIN','instrument_type':'STOCK','name':'江西铜业','basis':'METHOD identity',
        'effective_at':'2026-07-06T00:00:00+08:00'}).status_code == 200
    return client.post('/api/research/collections', json={'instrument':'SSE:600362','basis':'METHOD collector'}).json()['plan_id']


def test_closing_capture_keeps_exact_original_partial_facts_and_offline_packet(tmp_path, monkeypatch):
    clock = '2026-10-12T15:06:00+08:00'
    monkeypatch.setattr('roll.research.prospective.now', lambda: clock)
    monkeypatch.setattr('roll.market.post_close_packet.now', lambda: clock)
    monkeypatch.setattr('roll.market.evidence.now', lambda: clock)
    raw = json.dumps({'date':20261012,'time':150005,'list':[
        ['600362','江西铜业',100,101,99,100,1234,123400,100]]}, ensure_ascii=False).encode()
    calls=[]
    def supplier(request):
        calls.append(str(request.url))
        return httpx.Response(200, content=raw)
    app=create_app(tmp_path, market_transport=httpx.MockTransport(supplier))
    with TestClient(app) as client:
        pid=setup(client)
        response=client.post('/api/research/collections/'+pid+'/post-close',json={'basis':'METHOD closing capture'})
        assert response.status_code==201,response.text
        packet=response.json()
        assert len(calls)==1 and calls[0].startswith('http://yunhq.sse.com.cn:32041/')
        assert packet['evidence_kind']=='METHOD_CASE' and not packet['forward_admissible']
        bar=packet['rows'][0]
        assert bar['close']=='100' and bar['volume_reported']=='1234'
        assert bar['volume_unit']=='UNKNOWN' and bar['source_close_time']=='15:00:05'
        assert not bar['model_daily_input_allowed']
        assert 'CLOSING_VOLUME_AMOUNT_UNIT_AND_TURNOVER_SCOPE_UNVERIFIED:2026-10-12' in packet['gaps']
        assert 'CURRENT_LISTING_STAGE_UNPROVEN:2026-10-12' in packet['gaps']
        assert 'CURRENT_ACTION_COVERAGE_UNPROVEN:2026-10-12' in packet['gaps']
        assert packet['status_facts'][0]['suspension'] is False
        assert packet['execution_context'][0]['rule']['buy_minimum']=='100'
        assert packet['execution_context'][0]['company_action_treatment']=='UNPROVEN_CURRENT_COVERAGE'
        assert client.get('/api/data/archives/'+bar['raw_hash']).content==raw
        account=client.get('/api/account').json()
        before=len(calls)
        replay=client.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay')
        assert replay.status_code==200,replay.text
        assert replay.json()['matches_original'] and replay.json()['network_calls']==0
        assert len(calls)==before and client.get('/api/account').json()==account
        assert client.post('/api/research/collections/'+pid+'/post-close',json={
            'basis':'cannot assert complete','complete_status_verified':True}).status_code==422
        app.state.evidence.raw(bar['raw_hash']).write_bytes(b'corrupt')
        assert client.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay').status_code==409


def archived_batch(app,pid,facts,clock):
    """Explicit METHOD supplier at the accepted archive/SQLite seam."""
    evidence=app.state.evidence
    raw=evidence.archive(encode({'method_facts':facts}).encode(),'METHOD_SUPPLIER',received_at=clock)
    facts=[{**f,'raw_hash':raw['sha256'],'received_at':clock,'available_at':clock} for f in facts]
    buffer=BytesIO()
    pq.write_table(pa.Table.from_pylist([{'payload':encode(f)} for f in facts]),buffer)
    parquet=evidence.archive(buffer.getvalue(),'NORMALIZED_PARQUET','parquet')
    rid=raw['sha256']; sid='snap-'+rid;qid='req-'+rid
    snapshot={'snapshot_id':sid,'run_id':rid,'request_id':qid,'created_at':clock,
        'facts':facts,'archives':[raw],'parquet':parquet,'evidence_kind':'METHOD_CASE',
        'adapter_version':'explicit-method-supplier','observations':[]}
    with app.state.ledger.connection() as db:
        db.execute('INSERT INTO data_requests VALUES(?,?)',(qid,encode({'request_id':qid,'purpose':'RESEARCH','instruments':['SSE:600362']})))
        db.execute('INSERT INTO retrieval_runs VALUES(?,?,?)',(rid,qid,encode({'run_id':rid,'request_id':qid,
            'started_at':clock,'finished_at':clock,'status':'COMPLETE','snapshot_id':sid,'gaps':[]})))
        db.execute('INSERT INTO market_evidence_snapshots VALUES(?,?,?)',(sid,rid,encode(snapshot)))
    app.state.prospective.record(pid,rid)


def test_client_shaped_status_certificate_has_no_source_authority(tmp_path,monkeypatch):
    clock='2026-10-12T15:06:00+08:00'
    monkeypatch.setattr('roll.research.prospective.now',lambda:clock)
    monkeypatch.setattr('roll.market.post_close_packet.now',lambda:clock)
    app=create_app(tmp_path)
    with TestClient(app) as client:
        pid=setup(client)
        common={'instrument':'SSE:600362','trade_date':'2026-10-12','errors':[]}
        archived_batch(app,pid,[{**common,'group':'DAILY','source_id':'method-daily','close':'100','open':'100',
            'high':'101','low':'99','volume_shares':'1234','amount_yuan':'123400','volume_unit':'SHARE',
            'adjustment':'RAW','completion_state':'COMPLETE_REPORTED_HISTORICAL','model_daily_input_allowed':True},
            {**common,'group':'STATUS','source_id':'method-claims','complete_status_verified':True,
            'state':'CONFIRMED_NORMAL','suspension':False,'risk_warning':False,'listing_stage':'ORDINARY','ex_rights':False}],clock)
        packet=client.post('/api/research/collections/'+pid+'/post-close-packets',json={'basis':'check actual sources'}).json()
        assert 'CURRENT_STATUS_FIELD_SOURCE_UNPROVEN:2026-10-12' in packet['gaps']
        assert not packet['forward_admissible']


def test_known_cash_implementation_original_does_not_certify_current_no_events(tmp_path,monkeypatch):
    clock='2026-10-12T15:06:00+08:00'
    monkeypatch.setattr('roll.research.prospective.now',lambda:clock)
    monkeypatch.setattr('roll.market.post_close_packet.now',lambda:clock)
    app=create_app(tmp_path)
    with TestClient(app) as client:
        pid=setup(client)
        packet=client.post('/api/research/collections/'+pid+'/post-close-packets',json={'basis':'known source inventory, no current coverage claim'}).json()
        inventory=packet['known_cash_inventory']
        event=next(e for e in inventory['events'] if e['ex_date']=='2025-11-28')
        assert event['gross_cash_yuan_per_eligible_share']=='0.40'
        assert event['differentiated_ex_reference_deduction_yuan_per_listed_share']=='0.3980'
        assert event['record_date']=='2025-11-27' and event['cash_payment_date']=='2025-11-28'
        assert event['lifecycle_stage']=='IMPLEMENTATION_NOTICE' and event['actual_account_receipt'] is None
        assert event['source']['sha256']=='e486d0e9a99e5aa0dc77a4aa2037963022a44a1d3f6cd3315290b8e6afe2a28c'
        assert client.get('/api/data/archives/'+event['source']['sha256']).content[:4]==b'%PDF'
        assert inventory['complete_action_coverage'] is False
        assert inventory['covered_effective_interval'] is None and not packet['forward_admissible']
        assert client.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay').json()['matches_original']


def test_conflict_checks_compare_decimal_amount_and_retain_all_status_sources(tmp_path,monkeypatch):
    clock='2026-10-12T15:06:00+08:00'
    monkeypatch.setattr('roll.research.prospective.now',lambda:clock)
    monkeypatch.setattr('roll.market.post_close_packet.now',lambda:clock)
    app=create_app(tmp_path)
    with TestClient(app) as client:
        pid=setup(client)
        common={'instrument':'SSE:600362','trade_date':'2026-10-12','errors':[]}
        daily={**common,'group':'DAILY','close':'100','open':'100','high':'101','low':'99',
            'volume_shares':'10','amount_yuan':'1000','volume_unit':'SHARE','adjustment':'RAW',
            'completion_state':'COMPLETE_REPORTED_HISTORICAL','model_daily_input_allowed':True}
        status={**common,'group':'STATUS','complete_status_verified':False,'listing_stage':None,'ex_rights':None}
        archived_batch(app,pid,[{**daily,'source_id':'method-a'},{**daily,'source_id':'method-b','amount_yuan':'1000.00'},
            {**status,'source_id':'method-status-a','state':'NORMAL','suspension':False},
            {**status,'source_id':'method-status-b','state':'SUSPENDED','suspension':True}],clock)
        path='/api/research/collections/'+pid+'/post-close-packets'
        packet=client.post(path,json={'basis':'compare exact decimal source quantities'}).json()
        assert 'UNRESOLVED_CURRENT_DAILY_CONFLICT:2026-10-12' not in packet['gaps']
        assert 'UNRESOLVED_CURRENT_STATUS_CONFLICT:2026-10-12' in packet['gaps']
        assert len(packet['status_facts'])==2
        archived_batch(app,pid,[{**daily,'source_id':'method-c','amount_yuan':'1001'}],clock)
        changed=client.post(path,json={'basis':'retain genuinely different turnover'}).json()
        assert 'UNRESOLVED_CURRENT_DAILY_CONFLICT:2026-10-12' in changed['gaps']
        assert len([v for v in changed['versions'] if v['fact']['group']=='DAILY'])==3


@pytest.mark.parametrize('change,reason',[
    ({'date':20261009},'SSE_CLOSING_DATE_MISMATCH'),
    ({'time':145959},'SSE_SESSION_NOT_CLOSED'),
    ({'time':True},'SSE_SOURCE_TIME_MISSING'),
    ({'time':156099},'SSE_SOURCE_TIME_INVALID'),
    ({'list':[]},'SSE_SECURITY_ROW_MISSING_OR_DUPLICATED'),
    ({'list':[['600362','江西铜业',100,101,99,'NaN',1234,123400,100]]},'SSE_NUMERIC_FIELD_INVALID'),
])
def test_source_failure_is_retained_without_current_complete_bar(tmp_path,monkeypatch,change,reason):
    clock='2026-10-12T15:06:00+08:00'
    for module in ['roll.research.prospective','roll.market.post_close_packet','roll.market.evidence']:
        monkeypatch.setattr(module+'.now',lambda:clock)
    payload={'date':20261012,'time':150005,'list':[['600362','江西铜业',100,101,99,100,1234,123400,100]],**change}
    raw=json.dumps(payload,ensure_ascii=False).encode()
    app=create_app(tmp_path,market_transport=httpx.MockTransport(lambda _:httpx.Response(200,content=raw)))
    with TestClient(app) as client:
        pid=setup(client)
        packet=client.post('/api/research/collections/'+pid+'/post-close',json={'basis':'METHOD bad supplier'}).json()
        assert packet['rows']==[] and not packet['forward_admissible']
        batches=client.get('/api/research/collections/'+pid+'/batches').json()
        assert len(batches)==1 and batches[0]['status']=='FAILED'
        assert reason in [g['code'] for g in batches[0]['gaps']]
        attempts=packet['acquisition_attempts']
        assert attempts[0]['batch_id']==batches[0]['batch_id']
        assert attempts[0]['run_id']==batches[0]['run_id']
        assert reason in [g['code'] for g in attempts[0]['gaps']]
        assert 'SOURCE_ACQUISITION_FAILURE:sse-closing-board:'+reason in packet['gaps']
        assert client.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay').json()['matches_original']
        run=client.get('/api/data/runs/'+batches[0]['run_id']).json()
        assert len(run['tools'])==1
        assert client.get('/api/data/archives/'+run['tools'][0]['raw_hash']).content==raw


def test_genuine_sunday_capture_of_friday_board_is_not_sunday_daily_or_unit_proof():
    sha='100af352fe6f66c87b18310e26f01b5eb41d932a68e27a094f87a906f78ec5ab'
    root=Path(__file__).resolve().parents[3]
    raw=(root/'.scratch/roll-p0/evidence/30-producer/originals'/str(sha+'.raw')).read_bytes()
    assert len(raw)==193804 and hashlib.sha256(raw).hexdigest()==sha
    archive={'sha256':sha,'received_at':'2026-10-11T02:45:17.568187+00:00',
        'source_url':'http://yunhq.sse.com.cn:32041/v1/sh1/list/exchange/equity'}
    daily,status=closing_facts(raw,archive,'SSE:600362','2026-10-09')
    assert [daily[k] for k in ['open','high','low','close']]==['41.4500','42.6600','41.0600','42.5100']
    assert daily['volume_reported']=='31419158' and daily['amount_reported']=='1314805240'
    assert daily['trade_date']=='2026-10-09' and daily['received_at']==archive['received_at']
    assert daily['volume_shares'] is None and daily['volume_unit']=='UNKNOWN'
    assert not daily['model_daily_input_allowed'] and status['listing_stage'] is None
    with pytest.raises(ValueError,match='SSE_CLOSING_DATE_MISMATCH'):
        closing_facts(raw,archive,'SSE:600362','2026-10-11')


def test_normalized_sqlite_and_parquet_agreement_cannot_override_closing_original(tmp_path,monkeypatch):
    clock='2026-10-12T15:06:00+08:00'
    for module in ['roll.research.prospective','roll.market.post_close_packet','roll.market.evidence']:
        monkeypatch.setattr(module+'.now',lambda:clock)
    raw=json.dumps({'date':20261012,'time':150005,'list':[['600362','江西铜业',100,101,99,100,1234,123400,100]]},ensure_ascii=False).encode()
    app=create_app(tmp_path,market_transport=httpx.MockTransport(lambda _:httpx.Response(200,content=raw)))
    with TestClient(app) as client:
        pid=setup(client)
        packet=client.post('/api/research/collections/'+pid+'/post-close',json={'basis':'METHOD original binding'}).json()
        batch=client.get('/api/research/collections/'+pid+'/batches').json()[0]
        snap=app.state.evidence.get('market_evidence_snapshots',batch['snapshot_id'])
        snap['facts'][0]['close']='101'
        buffer=BytesIO();pq.write_table(pa.Table.from_pylist([{'payload':encode(f)} for f in snap['facts']]),buffer)
        snap['parquet']=app.state.evidence.archive(buffer.getvalue(),'NORMALIZED_PARQUET','parquet')
        with app.state.ledger.connection() as db:
            db.execute('UPDATE market_evidence_snapshots SET value=? WHERE id=?',(encode(snap),snap['snapshot_id']))
        rejected=client.post('/api/data/runs/'+batch['run_id']+'/replay')
        assert rejected.status_code==409 and rejected.json()['detail']=='POST_CLOSE_NORMALIZED_ORIGINAL_MISMATCH'
        assert client.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay').status_code==409


def test_persisted_post_close_job_is_bounded_and_not_retried_by_repeated_trigger(tmp_path,monkeypatch):
    clock='2026-10-12T15:06:00+08:00'
    for module in ['roll.research.prospective','roll.market.post_close_packet','roll.market.evidence','roll.market.sse_stock_suspension','roll.market.sse_company_contract']:
        monkeypatch.setattr(module+'.now',lambda:clock)
    calls=[]
    raw=json.dumps({'date':20261012,'time':150005,'list':[['600362','江西铜业',100,101,99,100,1234,123400,100]]},ensure_ascii=False).encode()
    def transport(request):
        calls.append(request.url.host)
        if request.url.path=='/v1/sh1/snap/600362':
            from test_sse_company_contract import snap
            return httpx.Response(200,json=snap())
        if request.url.params.get('sqlId')=='COMMON_SSE_CP_GPJCTPZ_GPLB_GPGK_GSGK_C':
            from test_sse_company_contract import company
            return httpx.Response(200,json=company())
        if request.url.host=='query.sse.com.cn' and request.url.params.get('sqlId','').startswith('GW_PL_JYTS_TFPXX'):
            from test_sse_stock_suspension import interval
            return httpx.Response(200,json={'sqlId':'GW_PL_JYTS_TFPXX_TRADEDAY','result':[{'beforeTradeDay':'20261009'}]}
                if request.url.params['sqlId'].endswith('TRADEDAY') else interval(rows=[],total=0,pages=0))
        if request.url.host=='query.sse.com.cn':
            from test_sse_current_suspension import page
            return httpx.Response(200,json=page(rows=[],total=0,page_count=0))
        return httpx.Response(200,content=raw)
    app=create_app(tmp_path,market_transport=httpx.MockTransport(transport))
    with TestClient(app) as client:
        pid=setup(client)
        path='/api/research/collections/'+pid+'/post-close/check'
        account=client.get('/api/account').json()
        response=client.post(path,json={'basis':'METHOD single worker job'})
        assert response.status_code==201,response.text
        job=response.json()
        assert job['state']=='RECORDED' and job['actual_forward_start'] is False
        assert client.post(path,json={'basis':'repeat same bounded job'}).json()==job
        assert sorted(calls)==['query.sse.com.cn']*4+['yunhq.sse.com.cn']*2
        assert job['company_contract_receipt_id'] and job['company_contract_job_state']=='RECORDED'
        assert len(client.get('/api/research/collections/'+pid+'/sse-company-contract-receipts').json())==1
        assert len(client.get('/api/research/collections/'+pid+'/batches').json())==1
        assert len(client.get('/api/research/collections/'+pid+'/sse-suspension-receipts').json())==1
        assert client.get('/api/account').json()==account


def test_packet_replay_keeps_exact_old_versions_when_same_cutoff_receives_correction(tmp_path,monkeypatch):
    clock='2026-10-12T15:06:00+08:00'
    for module in ['roll.research.prospective','roll.market.post_close_packet']:
        monkeypatch.setattr(module+'.now',lambda:clock)
    app=create_app(tmp_path)
    with TestClient(app) as client:
        pid=setup(client)
        fact={'instrument':'SSE:600362','group':'DAILY','trade_date':'2026-10-12','source_id':'method-a',
            'open':'100','close':'100','high':'101','low':'99','volume_shares':'10','amount_yuan':'1000',
            'volume_unit':'SHARE','adjustment':'RAW','errors':[],'model_daily_input_allowed':True,
            'completion_state':'COMPLETE_REPORTED_HISTORICAL'}
        archived_batch(app,pid,[fact],clock)
        path='/api/research/collections/'+pid+'/post-close-packets'
        old=client.post(path,json={'basis':'immutable first input packet'}).json()
        archived_batch(app,pid,[{**fact,'close':'101','amount_yuan':'1010'}],clock)
        new=client.post(path,json={'basis':'new correction retains prior input packet'}).json()
        assert old['rows'][0]['close']=='100' and new['rows'][0]['close']=='101'
        assert old['versions'][0]['ordinal']!=new['versions'][0]['ordinal']
        assert old['versions'][0]['batch_id']!=new['versions'][0]['batch_id']
        replay=client.post('/api/research/post-close-packets/'+old['packet_id']+'/replay')
        assert replay.status_code==200,replay.text
        assert replay.json()['matches_original'] and replay.json()['network_calls']==0


def test_failed_source_receipt_stays_in_old_packet_after_explicit_successful_capture(tmp_path,monkeypatch):
    clock='2026-10-12T15:06:00+08:00'
    for module in ['roll.research.prospective','roll.market.post_close_packet','roll.market.evidence']:
        monkeypatch.setattr(module+'.now',lambda:clock)
    times=iter([145959,150005]);calls=[]
    def supplier(_):
        calls.append(1)
        return httpx.Response(200,json={'date':20261012,'time':next(times),
            'list':[['600362','江西铜业',100,101,99,100,1234,123400,100]]})
    app=create_app(tmp_path,market_transport=httpx.MockTransport(supplier))
    with TestClient(app) as client:
        pid=setup(client);path='/api/research/collections/'+pid+'/post-close'
        old=client.post(path,json={'basis':'METHOD failed explicit capture'}).json()
        new=client.post(path,json={'basis':'METHOD separately authorized successful capture'}).json()
        gap='SOURCE_ACQUISITION_FAILURE:sse-closing-board:SSE_SESSION_NOT_CLOSED'
        assert gap in old['gaps'] and gap not in new['gaps']
        assert len(old['acquisition_attempts'])==1 and len(new['acquisition_attempts'])==2
        assert new['acquisition_attempts'][0]==old['acquisition_attempts'][0]
        assert new['acquisition_attempts'][0]['status']=='FAILED'
        assert len(calls)==2
        for packet in [old,new]:
            replay=client.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay')
            assert replay.status_code==200,replay.text
            assert replay.json()['matches_original'] and replay.json()['network_calls']==0
        assert len(calls)==2 and not new['forward_admissible']


def test_historical_failure_remains_a_receipt_without_becoming_current_checkpoint_failure(tmp_path,monkeypatch):
    clock=['2026-10-12T15:06:00+08:00']
    for module in ['roll.research.prospective','roll.market.post_close_packet','roll.market.evidence']:
        monkeypatch.setattr(module+'.now',lambda:clock[0])
    calls=[]
    def supplier(_):
        calls.append(1)
        return httpx.Response(200,json={'date':20261012,'time':145959,
            'list':[['600362','江西铜业',100,101,99,100,1234,123400,100]]})
    app=create_app(tmp_path,market_transport=httpx.MockTransport(supplier))
    with TestClient(app) as client:
        pid=setup(client)
        old=client.post('/api/research/collections/'+pid+'/post-close',json={'basis':'METHOD prior checkpoint failure'}).json()
        clock[0]='2026-10-13T15:06:00+08:00'
        current=client.post('/api/research/collections/'+pid+'/post-close-packets',json={'basis':'METHOD current packet, no collection'}).json()
        gap='SOURCE_ACQUISITION_FAILURE:sse-closing-board:SSE_SESSION_NOT_CLOSED'
        assert gap in old['gaps'] and gap not in current['gaps']
        assert current['acquisition_attempts']==old['acquisition_attempts']
        assert 'CURRENT_COMPLETE_DAILY_MISSING' in current['gaps'] and not current['forward_admissible']
        assert len(calls)==1
        assert client.post('/api/research/post-close-packets/'+old['packet_id']+'/replay').json()['matches_original']
