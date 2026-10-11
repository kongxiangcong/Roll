"""Independent eighth-slice public API checks; fresh METHOD databases only."""
import hashlib
import json
from pathlib import Path
import httpx
from fastapi.testclient import TestClient
from roll.app import create_app
from test_sse_company_contract import clock, start, company, snap, SELECT

OWNER=Path('D:/dsh-proj/Roll/.scratch/worktrees/ticket30-producer')
RAW_SHA='bc0971238819277c2b9d6773e341c6d12496adb7991fc897000974cbb2942403'
PROOF=OWNER/'.scratch/roll-p0/evidence/30-sse-company-contract/runtime/source-assessment'

def fixed_clock(monkeypatch,stamp='2026-10-11T19:00:00+08:00'):
    clock(monkeypatch,stamp)
    monkeypatch.setattr('roll.market.sse_price_quotes.now',lambda:stamp)

def transport(raw,calls):
    def supplier(request):
        calls.append(str(request.url))
        assert request.url.host in ['yunhq.sse.com.cn','query.sse.com.cn']
        if request.url.host=='yunhq.sse.com.cn':
            assert request.url.path=='/v1/sh1/snap/600362' and dict(request.url.params)=={'select':SELECT}
            return httpx.Response(200,content=raw)
        assert request.url.path=='/sseQuery/commonQuery.do'
        return httpx.Response(200,json=company())
    return httpx.MockTransport(supplier)

def capture(client):
    base=start(client)
    response=client.post(base+'/sse-company-contract',json={'basis':'Independent offline source assessment'})
    assert response.status_code==201,response.text
    return base,response.json()

def assess(client,base,source):
    response=client.post(base+'/sse-price-quotes',json={'source_receipt_id':source['receipt_id'],'basis':'Independent explicit price receipt'})
    assert response.status_code==201,response.text
    return response.json()

def test_exact_actual_bytes_fixed_successor_ids_restart_and_typed_gaps(tmp_path,monkeypatch):
    fixed_clock(monkeypatch)
    raw=(PROOF/(RAW_SHA+'.raw')).read_bytes()
    assert len(raw)==409 and hashlib.sha256(raw).hexdigest()==RAW_SHA
    calls=[];fixture=transport(raw,calls)
    with TestClient(create_app(tmp_path,market_transport=fixture,runtime_role='API')) as client:
        base,source=capture(client)
        old=client.post(base+'/post-close-packets',json={'basis':'Independent fixed old packet'}).json()
        first=assess(client,base,source);q=first['quote_fact']
        assert [q[k] for k in ['last','open','prev_close','high','low']]==['42.5100','41.4500','41.8900','42.6600','41.0600']
        assert q['turnover_ratio_raw']=='151' and q['turnover_percent_document_exact']=='1.51'
        assert q['volume_raw']=='31419158' and q['amount_raw']=='1314805240'
        assert q['tradephase_original']=='E110    ' and q['fp_volume_raw']=='30600'
        assert q['kind']=='QUOTE' and q['session_scope']==q['completion_state']=='UNKNOWN'
        command={'predecessor_packet_id':old['packet_id'],'source_receipt_id':source['receipt_id'],'assessment_ids':[first['assessment_id']],'basis':'Independent explicit pinned IDs'}
        response=client.post(base+'/sse-price-packets',json=command);assert response.status_code==201,response.text
        saved=response.json();later=assess(client,base,source)
        assert later['assessment_id']!=first['assessment_id']
        assert saved['predecessor']==old and saved['assessment_ids']==[first['assessment_id']]
        assert not saved['system_usable'] and not saved['model_daily_input_allowed'] and not saved['forward_admissible']
        assert saved['forward_started_at'] is None and saved['capability']=='NOT_GRANTED'
        assert not saved['quote_states'][0]['current_quote_available']
        for ids in [['not-saved'],[first['assessment_id'],first['assessment_id']]]:
            assert client.post(base+'/sse-price-packets',json={**command,'assessment_ids':ids}).status_code==409
        for flag in ['complete','current','actual','system_usable','knowledge_cutoff']:
            assert client.post(base+'/sse-price-quotes',json={'source_receipt_id':source['receipt_id'],'basis':'Independent no authority flags',flag:True}).status_code==422
        for packet in [old,saved]:
            replay=client.post('/api/research/post-close-packets/'+packet['packet_id']+'/replay')
            assert replay.status_code==200 and replay.json()['matches_original'] and replay.json()['network_calls']==0
        gaps=client.get(base+'/source-gaps').json()
        assert len(gaps['price_quote_assessments'])==2 and 'QUOTE_NOT_CURRENT_HOST_DATE' in gaps['price_quote_current']['gaps']
        assert client.get(base+'/sse-company-contract-receipts').json()==[source]
        assert 'last' not in old['source_contract_facts'][0]
        assert client.get('/api/account').json()['version']==0 and len(calls)==2
        (tmp_path/'independent-receipts.json').write_text(json.dumps({'source':source,'old':old,'assessment':first,'successor':saved,'gaps':gaps},ensure_ascii=False,indent=2),encoding='utf-8')
    with TestClient(create_app(tmp_path,market_transport=fixture,runtime_role='API')) as client:
        assert client.get(base+'/sse-price-packets/'+saved['packet_id']).json()==saved
        assert client.post('/api/research/post-close-packets/'+saved['packet_id']+'/replay').json()['matches_original']
        assert len(calls)==2

def test_precision_current_p1_and_previous_close_are_separate_scopes(tmp_path,monkeypatch):
    fixed_clock(monkeypatch,'2026-10-12T19:00:00+08:00')
    q=snap();q['date']=20261012;q['snap'][7]=100;q['snap'][12]=' P1 '
    raw=json.dumps(q).replace('44.01','44.010000000000000000000000000001').replace('125,','12345678901234567890.123456,').encode()
    calls=[]
    with TestClient(create_app(tmp_path,market_transport=transport(raw,calls),runtime_role='API')) as client:
        base,source=capture(client);a=assess(client,base,source)
        assert a['quote_fact']['last']=='44.010000000000000000000000000001'
        assert a['quote_fact']['turnover_percent_document_exact']=='123456789012345678.90123456'
        current=client.get(base+'/sse-price-quotes/current').json()
        assert current['quote_fact']['prev_close']=='100' and not current['current_quote_available']
        assert 'OFFICIAL_CLIENT_P1_PRICE_DISPLAY_WITHHELD' in current['gaps']
        assert not current['model_daily_input_allowed'] and not current['system_usable'] and len(calls)==2

def test_refused_source_and_nonpositive_price_have_typed409(tmp_path,monkeypatch):
    fixed_clock(monkeypatch)
    q=snap();q['snap'][1]=0
    for name,raw in [('nonobject',b'[]'),('zero',json.dumps(q).encode())]:
        calls=[]
        with TestClient(create_app(tmp_path/name,market_transport=transport(raw,calls),runtime_role='API'),raise_server_exceptions=False) as client:
            base,source=capture(client)
            r=client.post(base+'/sse-price-quotes',json={'source_receipt_id':source['receipt_id'],'basis':'Independent typed source refusal'})
            assert r.status_code==409,r.text
            assert client.get(base+'/sse-price-quotes').json()==[]
            assert client.get(base+'/sse-company-contract-receipts').json()==[source]
            assert len(calls)==2

def test_each_fixed_dependency_damage_refuses_query_replay(tmp_path,monkeypatch):
    fixed_clock(monkeypatch)
    for role in ['snap','js','source','assessment','packet']:
        calls=[];app=create_app(tmp_path/role,market_transport=transport(json.dumps(snap()).encode(),calls),runtime_role='API')
        with TestClient(app) as client:
            base,source=capture(client);old=client.post(base+'/post-close-packets',json={'basis':'Independent damage predecessor'}).json();a=assess(client,base,source)
            p=client.post(base+'/sse-price-packets',json={'predecessor_packet_id':old['packet_id'],'source_receipt_id':source['receipt_id'],'assessment_ids':[a['assessment_id']],'basis':'Independent fixed damage consumer'}).json()
            hashes={'snap':source['responses']['snap']['archive']['sha256'],'js':a['quote_fact']['document_js_hash'],'source':source['archive']['sha256'],'assessment':a['archive']['sha256'],'packet':p['archive']['sha256']}
            # Deliberate corruption only in this fresh scenario's own raw archive.
            app.state.evidence.raw(hashes[role]).write_bytes(b'independent owned corruption')
            assert client.get(base+'/sse-price-packets/'+p['packet_id']).status_code==409
            assert client.post('/api/research/post-close-packets/'+p['packet_id']+'/replay').status_code==409
            assert len(calls)==2
