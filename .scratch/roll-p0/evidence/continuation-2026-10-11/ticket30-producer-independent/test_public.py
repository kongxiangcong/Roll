"""Fixed source bodies; public producer/replay with actual isolated SQLite/raw/Parquet."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
from io import BytesIO

ROOT=Path(__file__).resolve().parents[5]
SCOPE=Path(__file__).resolve().parent
CHILD=ROOT/'.scratch/worktrees/ticket30-producer'
for key in ['ROLL_ENV_FILE','ROLL_CODEX_AUTH_FILE','ROLL_DEEPSEEK_API_KEY_FILE','DEEPSEEK_API_KEY',
            'ROLL_TEST_CRASH_POINT','ROLL_TEST_BOOTSTRAP_FAULT']:
    os.environ.pop(key,None)
os.environ['ROLL_ENV']='test'
sys.path.insert(0,str(CHILD/'backend/src'))
sys.path.insert(0,str(CHILD/'backend/tests/application'))
from roll.app import create_app
from test_market_directory import establish
from fastapi.testclient import TestClient
from roll.accounts.ledger import encode
import httpx
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

SHA='100af352fe6f66c87b18310e26f01b5eb41d932a68e27a094f87a906f78ec5ab'
RAW=(CHILD/'.scratch/roll-p0/evidence/30-producer/originals'/(SHA+'.raw')).read_bytes()
assert len(RAW)==193804 and hashlib.sha256(RAW).hexdigest()==SHA
def write(name,value):
    (SCOPE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def clock(monkeypatch,instant):
    for name in ['roll.market.evidence','roll.market.post_close_packet','roll.research.prospective']:
        monkeypatch.setattr(name+'.now',lambda:instant[0])
def setup(c):
    establish(c,['SSE:600362'])
    response=c.post('/api/market/identities',json={'instrument':'SSE:600362','exchange':'SSE','board':'MAIN',
        'instrument_type':'STOCK','name':'METHOD fixed official raw','basis':'Independent METHOD identity',
        'effective_at':'2026-07-06T00:00:00+08:00'})
    assert response.status_code==200,response.text
    response=c.post('/api/research/collections',json={'instrument':'SSE:600362','basis':'Independent METHOD only'})
    assert response.status_code==201,response.text
    return response.json()['plan_id']
def response_packet(c,path):
    r=c.post(path,json={'basis':'Independent fixed raw METHOD producer'})
    assert r.status_code==201,r.text
    return r.json()
def replay(c,packet):
    r=c.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay')
    assert r.status_code==200,r.text
    assert r.json()['matches_original'] and r.json()['network_calls']==0 and not r.json()['forward_admissible']
    return r.json()
def supplier(bodies,calls):
    def fixed(request):
        # MockTransport dispatch is a local fixture read, never an external HTTP request.
        calls.append(request.url.host)
        assert request.url.host=='yunhq.sse.com.cn'
        return httpx.Response(200,content=bodies.pop(0))
    return httpx.MockTransport(fixed)
def derived(*,close=None,time=None):
    raw=json.loads(RAW)
    if time is not None:raw['time']=time
    if close is not None:
        row=next(row for row in raw['list'] if row[0]=='600362');row[5]=close
    return json.dumps(raw,ensure_ascii=False,separators=(',',':')).encode()

def test_official_fixed_raw_partial_same_cutoff_correction_and_exact_membership(tmp_path,monkeypatch):
    instant=['2026-10-09T08:35:00+00:00'];clock(monkeypatch,instant)
    calls=[];bodies=[RAW,derived(close=42.52)]
    directory=tmp_path/'data'
    with TestClient(create_app(directory,market_transport=supplier(bodies,calls))) as c:
        pid=setup(c);account=c.get('/api/account').json()
        path='/api/research/collections/'+pid+'/post-close'
        old=response_packet(c,path)
        assert old['evidence_kind']=='METHOD_CASE' and not old['forward_admissible']
        bar=old['rows'][0]
        assert bar['raw_hash']==SHA and bar['close']=='42.5100'
        assert bar['volume_shares'] is None and bar['amount_yuan'] is None and bar['volume_unit']=='UNKNOWN'
        assert bar['source_close_time']=='16:29:05' and not bar['model_daily_input_allowed']
        assert bar['historical_pit_claim'] is False
        assert c.get('/api/data/archives/'+SHA).content==RAW
        assert 'CURRENT_LISTING_STAGE_UNPROVEN:2026-10-09' in old['gaps']
        assert 'CURRENT_ACTION_COVERAGE_UNPROVEN:2026-10-09' in old['gaps']
        corrected=response_packet(c,path)
        assert corrected['knowledge_cutoff']==old['knowledge_cutoff'] and corrected['rows'][0]['close']=='42.52'
        assert {v['ordinal'] for v in old['versions']}.isdisjoint({v['ordinal'] for v in corrected['versions']})
        assert {v['batch_id'] for v in old['versions']}.isdisjoint({v['batch_id'] for v in corrected['versions']})
        assert len(corrected['acquisition_attempts'])==2
        before=len(calls);replay(c,old);replay(c,corrected)
        assert len(calls)==before==2 and c.get('/api/account').json()==account
        assert c.post(path,json={'basis':'cannot assert completeness','complete_status_verified':True}).status_code==422
    # Negative corruption affects only our closed, isolated fixture. Its source archive stays exact.
    with sqlite3.connect(directory/'roll.sqlite3') as db:
        ordinal=old['versions'][0]['ordinal']
        saved=db.execute('SELECT batch_id FROM pit_fact_versions WHERE ordinal=?',(ordinal,)).fetchone()[0]
        db.execute('UPDATE pit_fact_versions SET batch_id=? WHERE ordinal=?',('wrong-original-batch',ordinal))
    with TestClient(create_app(directory,market_transport=supplier([],calls))) as c:
        refused=c.post('/api/research/post-close-packets/'+old['packet_id']+'/replay')
        assert refused.status_code==409 and refused.json()['detail']=='PIT_PACKET_ORIGINAL_VERSION_BINDING_MISMATCH',refused.text
    with sqlite3.connect(directory/'roll.sqlite3') as db:
        db.execute('UPDATE pit_fact_versions SET batch_id=? WHERE ordinal=?',(saved,ordinal))
    with TestClient(create_app(directory,market_transport=supplier([],calls))) as c:
        replay(c,old);replay(c,corrected)
        assert c.get('/api/account').json()==account
    write('ordinal-correction-results.json',{'status':'PASS','original_raw_sha256':SHA,'original_raw_bytes':len(RAW),
        'fixed_original_method_only':True,'same_cutoff':old['knowledge_cutoff'],'old_ordinals':[v['ordinal'] for v in old['versions']],
        'new_ordinals':[v['ordinal'] for v in corrected['versions']],'original_batch_corruption_status':409,
        'restart_original_replay':True,'mock_supplier_reads':len(calls),'external_HTTP_calls':0,
        'units_unknown':True,'forward_admissible':False,'account_unchanged':True})

def test_raw_and_agreeing_sql_parquet_tamper_cannot_replace_official_original(tmp_path,monkeypatch):
    instant=['2026-10-09T08:35:00+00:00'];clock(monkeypatch,instant)
    calls=[];directory=tmp_path/'data'
    with TestClient(create_app(directory,market_transport=supplier([RAW],calls))) as c:
        pid=setup(c)
        packet=response_packet(c,'/api/research/collections/'+pid+'/post-close')
        batch=c.get('/api/research/collections/'+pid+'/batches').json()[0]
        replay(c,packet)
    raw_path=directory/'raw'/(SHA+'.raw');assert raw_path.read_bytes()==RAW
    raw_path.write_bytes(b'OWNED_METHOD_CORRUPTION')
    with TestClient(create_app(directory,market_transport=supplier([],calls))) as c:
        refused=c.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay')
        assert refused.status_code==409 and refused.json()['detail']['code']=='ARCHIVE_MISSING_OR_CORRUPT',refused.text
    raw_path.write_bytes(RAW);assert hashlib.sha256(raw_path.read_bytes()).hexdigest()==SHA
    with sqlite3.connect(directory/'roll.sqlite3') as db:
        saved=db.execute('SELECT value FROM market_evidence_snapshots WHERE id=?',(batch['snapshot_id'],)).fetchone()[0]
        snapshot=json.loads(saved);snapshot['facts'][0]['close']='42.52'
        buffer=BytesIO();pq.write_table(pa.Table.from_pylist([{'payload':encode(f)} for f in snapshot['facts']]),buffer)
        body=buffer.getvalue();digest=hashlib.sha256(body).hexdigest()
        relative='parquet/'+digest+'.parquet';(directory/relative).write_bytes(body)
        metadata={'sha256':digest,'path':relative,'bytes':len(body),'kind':'NORMALIZED_PARQUET'}
        db.execute('INSERT OR IGNORE INTO evidence_archives VALUES(?,?)',(digest,encode(metadata)))
        snapshot['parquet']=metadata
        db.execute('UPDATE market_evidence_snapshots SET value=? WHERE id=?',(encode(snapshot),batch['snapshot_id']))
    with TestClient(create_app(directory,market_transport=supplier([],calls))) as c:
        for path in ['/api/data/runs/'+batch['run_id']+'/replay',
            '/api/research/post-close-packets/'+packet['packet_id']+'/replay']:
            refused=c.post(path)
            assert refused.status_code==409 and refused.json()['detail']=='POST_CLOSE_NORMALIZED_ORIGINAL_MISMATCH',refused.text
    with sqlite3.connect(directory/'roll.sqlite3') as db:
        db.execute('UPDATE market_evidence_snapshots SET value=? WHERE id=?',(saved,batch['snapshot_id']))
    with TestClient(create_app(directory,market_transport=supplier([],calls))) as c:replay(c,packet)
    assert len(calls)==1 and hashlib.sha256(raw_path.read_bytes()).hexdigest()==SHA
    write('tamper-results.json',{'status':'PASS','raw_corruption_status':409,'normalized_SQL_Parquet_agree':True,
        'run_and_packet_original_binding_status':409,'reason':'POST_CLOSE_NORMALIZED_ORIGINAL_MISMATCH',
        'fixture_restored_and_replayed':True,'original_raw_sha256':SHA,'mock_supplier_reads':1,'external_HTTP_calls':0})

def test_shanghai_date_failure_history_does_not_permanently_block_current(tmp_path,monkeypatch):
    instant=['2026-10-09T08:35:00+00:00'];clock(monkeypatch,instant)
    calls=[];directory=tmp_path/'data'
    with TestClient(create_app(directory,market_transport=supplier([derived(time=145959)],calls))) as c:
        pid=setup(c);account=c.get('/api/account').json()
        path='/api/research/collections/'+pid
        failure=response_packet(c,path+'/post-close')
        gap='SOURCE_ACQUISITION_FAILURE:sse-closing-board:SSE_SESSION_NOT_CLOSED'
        assert gap in failure['gaps'] and failure['acquisition_attempts'][0]['status']=='FAILED'
        current_failure=response_packet(c,path+'/post-close-packets')
        assert gap in current_failure['gaps'] and current_failure['acquisition_attempts']==failure['acquisition_attempts']
        # UTC date is still Friday; Shanghai is already Saturday. No new acquisition takes place.
        instant[0]='2026-10-09T16:10:00+00:00'
        following=response_packet(c,path+'/post-close-packets')
        assert following['acquisition_attempts']==failure['acquisition_attempts'] and gap not in following['gaps']
        assert 'CURRENT_COMPLETE_DAILY_MISSING' in following['gaps'] and not following['forward_admissible']
        replay(c,failure);replay(c,following);assert len(calls)==1
        assert c.get('/api/account').json()==account
    with TestClient(create_app(directory,market_transport=supplier([],calls))) as c:
        replay(c,failure);replay(c,following)
        assert c.get('/api/account').json()==account
    write('failure-current-day-results.json',{'status':'PASS','same_current_Shanghai_day_failure_active':True,
        'UTC_date_unchanged_but_Shanghai_next_day_failure_inactive':True,'old_failure_receipt_unchanged':True,
        'mock_supplier_reads':1,'external_HTTP_calls':0,'forward_admissible':False,'actual_forward_start':False,
        'account_unchanged':True})

def test_explicit_success_preserves_failed_receipt_and_bounded_job_restart(tmp_path,monkeypatch):
    instant=['2026-10-09T08:35:00+00:00'];clock(monkeypatch,instant)
    calls=[];directory=tmp_path/'data'
    with TestClient(create_app(directory,market_transport=supplier([derived(time=145959),RAW],calls))) as c:
        pid=setup(c);account=c.get('/api/account').json()
        path='/api/research/collections/'+pid
        failure=response_packet(c,path+'/post-close')
        gap='SOURCE_ACQUISITION_FAILURE:sse-closing-board:SSE_SESSION_NOT_CLOSED'
        assert gap in failure['gaps'] and failure['acquisition_attempts'][0]['status']=='FAILED'
        old_attempt=failure['acquisition_attempts'][0]
        # A second explicit same-day command reads the fixed original; no implicit retry occurred.
        first_job=response_packet(c,path+'/post-close/check')
        assert first_job['state']=='RECORDED' and first_job['actual_forward_start'] is False
        duplicate=response_packet(c,path+'/post-close/check')
        assert first_job==duplicate and len(calls)==2
        successful=response_packet(c,path+'/post-close-packets')
        assert successful['acquisition_attempts'][0]==old_attempt and len(successful['acquisition_attempts'])==2
        assert gap not in successful['gaps'] and not successful['forward_admissible']
        replay(c,failure);replay(c,successful)
        assert c.get('/api/account').json()==account
    with TestClient(create_app(directory,market_transport=supplier([],calls))) as c:
        duplicate=response_packet(c,path+'/post-close/check')
        assert duplicate==first_job and len(calls)==2
        replay(c,failure);replay(c,successful)
        assert c.get('/api/research/collections/'+pid+'/readiness').json()['real_recorded_sessions']==0
        assert c.get('/api/account').json()==account
    write('explicit-success-results.json',{'status':'PASS','same_current_Shanghai_day_failure_active':True,
        'old_failure_receipt_unchanged':True,
        'explicit_success_clears_only_active_failure':True,'duplicate_and_restart_job_identical':True,
        'mock_supplier_reads':2,'external_HTTP_calls':0,'forward_admissible':False,'actual_forward_start':False,
        'account_unchanged':True,'real_recorded_sessions':0})
