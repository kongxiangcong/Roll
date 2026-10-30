"""Deterministic transport checks: these are not supplier live qualification."""
import json
import threading
from datetime import datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from roll.app import create_app
from roll.market import miaoxiang
from test_market_directory import establish


DAY='2026-09-30'
MS=int(datetime.fromisoformat(DAY+'T00:00:00+08:00').timestamp()*1000)


def fuyao_daily(request, close='11'):
    return httpx.Response(200,json={'code':0,'data':{'thscode':'600519.SH','interval':'1d',
        'adjust':request.url.params['adjust'],'item':[{'date_ms':MS,'open_price':'10','high_price':'12',
        'low_price':'9','close_price':close,'volume':1000,'turnover':11000}]}})


def eastmoney():
    return httpx.Response(200,json={'rc':0,'data':{'code':'600519','market':1,
        'klines':[DAY+',10,11,12,9,10,11000']}})


def command(**overrides):
    return dict(instruments=['SSE:600519'],groups=['DAILY'],purpose='OBSERVATION',start_date=DAY,end_date=DAY,
                daily_source='AUTO',max_calls=8,**overrides)


def fetch(client, value):
    result=client.post('/api/data/requests',json=value)
    assert result.status_code==201,result.text
    run=client.post('/api/data/requests/'+result.json()['request_id']+'/retrieve')
    assert run.status_code==200,run.text
    run=run.json()
    return run,client.get('/api/data/snapshots/'+run['snapshot_id']).json()


@pytest.fixture
def credential(monkeypatch):
    monkeypatch.setenv('FUYAO_API_KEY','METHOD_FUYAO_SECRET')
    monkeypatch.setenv('EM_API_KEY','METHOD_MX_SECRET')
    monkeypatch.delenv('ROLL_DATA_SOURCE_POLICY',raising=False)


def test_business_rate_limit_falls_back_cools_down_and_replays(tmp_path,credential):
    calls=[]
    def provider(request):
        calls.append(request.url.host)
        return httpx.Response(200,json={'code':4001,'message':'rate limit'}) if request.url.host=='fuyao.aicubes.cn' else eastmoney()
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        establish(client,['SSE:600519'])
        run,snapshot=fetch(client,command())
        assert calls.count('fuyao.aicubes.cn')==1
        assert {f['source_id'] for f in snapshot['facts']}=={'eastmoney-daily'}
        assert snapshot['source_attempts'][0]['resolved_primary_gaps']
        assert snapshot['source_attempts'][0]['role']=='FALLBACK'
        before=len(calls)
        assert client.post('/api/data/runs/'+run['run_id']+'/replay').json()['network_calls']==0
        assert len(calls)==before
        fetch(client,command())
        assert calls.count('fuyao.aicubes.cn')==1
        assert 'METHOD_FUYAO_SECRET' not in json.dumps(snapshot)


def test_explicit_source_is_not_silently_replaced(tmp_path,credential):
    calls=[]
    def provider(request):
        calls.append(request.url.host)
        return httpx.Response(200,json={'code':2003})
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        establish(client,['SSE:600519'])
        value=command();value['daily_source']='FUYAO'
        run,snapshot=fetch(client,value)
        assert run['status']=='FAILED'
        assert set(calls)=={'fuyao.aicubes.cn'} and snapshot['source_attempts']==[]


def test_comparison_retains_primary_and_records_differences(tmp_path,credential):
    def provider(request):
        return fuyao_daily(request,close='10.5') if request.url.host=='fuyao.aicubes.cn' else eastmoney()
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        establish(client,['SSE:600519'])
        client.post('/api/market/identities',json={'instrument':'SSE:600519','exchange':'SSE','board':'MAIN',
            'instrument_type':'STOCK','name':'合成证券','basis':'合成主板A股身份','effective_at':'2026-09-01T00:00:00+08:00'})
        _,snapshot=fetch(client,command(compare_sources=True))
        assert {f['source_id'] for f in snapshot['facts']}=={'fuyao-daily'}
        assert snapshot['source_comparisons'][0]['result']=='DIFFERENT'
        assert snapshot['source_comparisons'][0]['independence']=='UNPROVEN'


def test_no_fallback_calls_past_budget_or_after_cancel(tmp_path,credential):
    calls=[]
    def provider(request):
        calls.append(str(request.url));return httpx.Response(503)
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        establish(client,['SSE:600519'])
        value=command();value['max_calls']=1
        run,_=fetch(client,value)
        assert len(calls)==1 and not run['source_attempts']
        cancelled=threading.Event();cancelled.set()
        request=client.post('/api/data/requests',json=command()).json()
        client.app.state.evidence.retrieve(request['request_id'],cancel_event=cancelled)
        assert len(calls)==1


def test_mx_quota_preserves_receipt_and_uses_fuyao_reference_not_fact(tmp_path,credential):
    methods=[]
    def provider(request):
        if request.url.host=='mxapi.eastmoney.com':
            method=json.loads(request.content)['method'];methods.append(method)
            if method=='initialize':return httpx.Response(200,json={'result':{'protocolVersion':'2024-11-05'}})
            if method=='notifications/initialized':return httpx.Response(202)
            return httpx.Response(200,json={'result':{'isError':True,'content':[{'type':'text','text':'积分不足'}]}})
        if request.url.host=='fuyao.aicubes.cn':
            return httpx.Response(200,json={'code':0,'data':{'item':[{'thscode':'600519.SH','operating_income':123}]}})
        return httpx.Response(503)
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        establish(client,['SSE:600519'])
        value=command();value.update(groups=['PERFORMANCE'],research_source='AUTO')
        run,snapshot=fetch(client,value)
        assert snapshot['research_context'][0]['error']=='MX_QUOTA_EXHAUSTED'
        assert snapshot['research_context'][1]['provider']=='FUYAO'
        assert snapshot['research_context'][1]['status']=='ACQUIRED_REFERENCE'
        assert snapshot['facts']==[]
        assert len(methods)==3
        assert client.post('/api/data/runs/'+run['run_id']+'/replay').json()['network_calls']==0


def test_mx_rejects_reflected_secret_before_archiving(credential):
    archived=[]
    transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'result':{'echo':'METHOD_MX_SECRET'}}))
    with pytest.raises(ValueError,match='MX_SECRET_REFLECTED_RESPONSE_REJECTED'):
        miaoxiang.query('mx_ashare_finance_data','test',transport=transport,on_response=lambda *args:archived.append(args))
    assert archived==[]


def test_supplier_material_is_reference_only_and_idempotent(tmp_path,credential):
    from types import SimpleNamespace
    from roll.accounts.ledger import Ledger
    from roll.market.directory import MarketDirectory,WatchCommand
    from roll.market.evidence import EvidenceStore
    from roll.research.company import CompanyResearch,CompanyCommand
    from roll.research.company.supplier_references import SupplierReferences
    def provider(request):
        if request.url.host!='mxapi.eastmoney.com':return httpx.Response(503)
        method=json.loads(request.content)['method']
        if method=='initialize':return httpx.Response(200,json={'result':{'protocolVersion':'2024-11-05'}})
        if method=='notifications/initialized':return httpx.Response(202)
        return httpx.Response(200,json={'result':{'content':[{'type':'text','text':json.dumps({'data':[{'metric':'reference','value':123}]})}]}})
    ledger=Ledger(tmp_path);market=MarketDirectory(ledger)
    market.watch(WatchCommand(operation='ADD',instrument='SSE:600519',expected_list_version=market.listing()['version']))
    research=CompanyResearch(EvidenceStore(ledger,market,httpx.MockTransport(provider)))
    issuer=research.register(CompanyCommand(legal_name='METHOD company',jurisdiction='CN',industry='METHOD',
        identity_basis='METHOD company reference',listings=[dict(exchange='SSE',code='600519',share_class='A',currency='CNY')]))
    collector=SupplierReferences(research)
    args=SimpleNamespace(idempotency_key='once')
    run=collector.acquire('SSE:600519',args,threading.Event())
    assert run['status']=='COMPLETE' and len(run['material_ids'])==1
    assert collector.acquire('SSE:600519',args,threading.Event())==run
    material=research.materials(issuer['company_id'])['materials'][0]
    assert 'NO_AUTOMATIC_FINANCIAL_FACT_ADMISSION' in material['limitations']
    assert ledger.account()['version']==0


def test_assistance_uses_real_supplement_and_blocks_conflicting_execution_fields(tmp_path,credential,monkeypatch):
    from types import SimpleNamespace
    from roll.accounts.ledger import Ledger
    from roll.market.directory import MarketDirectory
    from roll.market.evidence import EvidenceStore
    from roll.runtime.assistance import Assistance
    monkeypatch.setenv('ROLL_DATA_SOURCE_POLICY','OFFICIAL_FIRST')
    ledger=Ledger(tmp_path)
    store=EvidenceStore(ledger,MarketDirectory(ledger),httpx.MockTransport(fuyao_daily))
    service=Assistance(ledger,research=SimpleNamespace(evidence=store))
    def supplement(*args,**kwargs):
        return dict(provider='METHOD_BAO',rows=[dict(date=DAY,open='10',high='12',low='9',close='9.5',
            preclose='10',isST='0',tradestatus='1')],sha256='method-supplement')
    monkeypatch.setattr(service,'_baostock_source',supplement)
    run=dict(instrument='SSE:600519',start_date=DAY,as_of=DAY)
    result=service.source(run,'sh.600519',threading.Event())
    assert result['provider']=='FUYAO' and result['rows'][0]['close']=='11'
    assert result['rows'][0]['isST']=='UNKNOWN'
    assert result['comparison']['different_or_missing_days']==[DAY]
    assert result['execution_supplement']['sha256']=='method-supplement'


def test_fuyao_news_fallback_uses_documented_items_not_financial_item_shape(tmp_path,credential):
    import time
    from roll.accounts.ledger import Ledger
    from roll.market.directory import MarketDirectory
    from roll.market.evidence import EvidenceStore
    from roll.market.research_context import fuyao_reference
    ledger=Ledger(tmp_path)
    transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'code':0,'data':{'items':[{'title':'METHOD news'}],'has_more':True,'offset':'next'}}))
    store=EvidenceStore(ledger,MarketDirectory(ledger),transport)
    run={'tools':[]};archives=[]
    item,size=fuyao_reference(store,dict(groups=['ANNOUNCEMENTS'],start_date=DAY,end_date=DAY),
        'SSE:600519',run,archives,time.monotonic()+5,threading.Event(),4096)
    assert item['status']=='ACQUIRED_REFERENCE' and item['reference_kind']=='NEWS_REFERENCE'
    assert 'NOT_NOTICE' in item['scope'] and not item['admitted_as_fact']
    assert size>0 and len(archives)==1


def test_capability_denial_does_not_disable_other_fuyao_products(tmp_path,credential):
    import time
    from roll.accounts.ledger import Ledger
    from roll.market.directory import MarketDirectory
    from roll.market.evidence import EvidenceStore
    from roll.market.research_context import fuyao_reference
    from roll.market.source_policy import health
    ledger=Ledger(tmp_path)
    store=EvidenceStore(ledger,MarketDirectory(ledger),httpx.MockTransport(lambda request:httpx.Response(200,json={'code':2003})))
    item,_=fuyao_reference(store,dict(groups=['PERFORMANCE'],start_date=DAY,end_date=DAY),
        'SSE:600519',{'tools':[]},[],time.monotonic()+5,threading.Event(),4096)
    assert item['error']=='FUYAO_BUSINESS_ERROR'
    assert health(store,'FUYAO_RESEARCH_FINANCIAL')['reason']=='BUSINESS_2003'
    assert health(store,'FUYAO') is None and health(store,'fuyao-daily') is None


@pytest.mark.parametrize('body',[[],{'result':[]},{'result':{'content':None}}])
def test_malformed_mcp_envelope_has_safe_stable_error(credential,body):
    with pytest.raises(ValueError,match='MX_'):
        miaoxiang.query('mx_ashare_finance_data','METHOD',transport=httpx.MockTransport(lambda request:httpx.Response(200,json=body)))


def test_missing_credential_does_not_consume_network_fallback_budget(tmp_path,credential,monkeypatch):
    monkeypatch.delenv('FUYAO_API_KEY')
    calls=[]
    def provider(request):
        calls.append(request.url.host);return eastmoney()
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        establish(client,['SSE:600519'])
        value=command();value['max_calls']=2
        run,snapshot=fetch(client,value)
        assert calls==['push2his.eastmoney.com']*2
        assert sum(tool['network_calls'] for tool in run['tools'])==2
        assert {fact['source_id'] for fact in snapshot['facts']}=={'eastmoney-daily'}
