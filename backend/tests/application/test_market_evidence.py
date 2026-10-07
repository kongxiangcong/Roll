import hashlib
import json
from datetime import datetime,timezone,timedelta
import httpx
import pytest
from fastapi.testclient import TestClient
from roll.app import create_app
from test_market_directory import establish


def test_finite_request_run_archives_raw_before_persisted_daily_snapshot_and_replays_offline(tmp_path):
    raw=b'{"rc":0,"data":{"code":"600519","market":1,"dktotal":1000,"klines":["2026-09-30,1239.53,1258.62,1268.00,1236.05,38331,4797246636.00"]}}'
    calls=[]
    def provider(request):
        calls.append(str(request.url))
        return httpx.Response(200,content=raw)
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        establish(client,['SSE:600519'])
        client.post('/api/market/identities',json={'instrument':'SSE:600519','exchange':'SSE','board':'MAIN',
            'instrument_type':'STOCK','name':'贵州茅台','basis':'合成身份核对：主板A股','effective_at':'2026-10-07T00:00:00+08:00'})
        request=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['DAILY'],
            'purpose':'OBSERVATION','start_date':'2026-09-21','end_date':'2026-09-30'})
        assert request.status_code==201,request.text
        rejected=client.post('/api/data/requests',json={'instruments':['SSE:600000'],'groups':['DAILY'],
            'purpose':'OBSERVATION','start_date':'2026-09-21','end_date':'2026-09-30'})
        assert rejected.status_code==403 and calls==[]
        run=client.post('/api/data/requests/'+request.json()['request_id']+'/retrieve').json()
        assert run['status']=='COMPLETE',run
        assert run['backend']=='DIRECT_HTTP' and run['evidence_kind']=='METHOD_CASE'
        snapshot=client.get('/api/data/snapshots/'+run['snapshot_id']).json()
        bar=next(f for f in snapshot['facts'] if f['group']=='DAILY' and f['adjustment']=='RAW')
        assert bar['close']=='1258.62' and bar['volume_shares']=='3833100'
        assert bar['amount_yuan']=='4797246636.00'
        assert bar['completion_state']=='COMPLETE_REPORTED_HISTORICAL'
        source=next(a for a in snapshot['archives'] if a['kind']=='RAW_RESPONSE')
        saved=client.get('/api/data/archives/'+source['sha256'])
        assert saved.content==raw and hashlib.sha256(saved.content).hexdigest()==source['sha256']
        assert saved.headers['x-content-type-options']=='nosniff' and saved.headers['content-disposition'].startswith('attachment;')
        parquet=client.get('/api/data/archives/'+snapshot['parquet']['sha256'])
        assert parquet.content[:4]==b'PAR1'
        before=len(calls)
        assert client.post('/api/data/runs/'+run['run_id']+'/replay').json()['facts']==snapshot['facts']
        assert len(calls)==before


def test_bad_units_placeholders_and_today_bar_restrict_only_dependent_model_inputs(tmp_path):
    today=datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    rows=['2026-09-30,10,10,10,10,10000,100000', # 10000 shares mislabelled as hands: vwap .1 !=10
          '2026-09-29,10,10,10,10,0,0', # an explicit true zero report, not missing
          '2026-09-28,0,10,10,10,-,-', # zero price placeholder / missing volume
          today+',10,10,10,10,100,100000']
    raw=json.dumps({'rc':0,'data':{'code':'600519','klines':rows}}).encode()
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,content=raw)))) as client:
        establish(client,['SSE:600519'])
        client.post('/api/market/identities',json={'instrument':'SSE:600519','exchange':'SSE','board':'MAIN',
            'instrument_type':'STOCK','name':'合成证券','basis':'合成主板A股身份','effective_at':'2026-10-07T00:00:00+08:00'})
        request=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['DAILY'],
            'purpose':'OBSERVATION','start_date':'2026-09-21','end_date':today}).json()
        run=client.post('/api/data/requests/'+request['request_id']+'/retrieve').json()
        facts=client.get('/api/data/snapshots/'+run['snapshot_id']).json()['facts']
        bars={f['trade_date']:f for f in facts if f['adjustment']=='RAW'}
        assert 'UNIT_AMOUNT_OHLC_MISMATCH' in bars['2026-09-30']['errors']
        assert bars['2026-09-30']['model_daily_input_allowed'] is False
        assert bars['2026-09-29']['volume_state']=='ZERO_REPORTED'
        assert bars['2026-09-29']['volume_shares']=='0'
        assert bars['2026-09-28']['open'] is None and bars['2026-09-28']['volume_state']=='MISSING'
        assert bars[today]['completion_state']=='UNCONFIRMED_CURRENT_DAY'
        assert bars[today]['model_daily_input_allowed'] is False


def test_twenty_one_real_holdings_are_requested_and_budget_gaps_are_each_visible(tmp_path):
    instruments=['SSE:'+str(600519+i) for i in range(21)]
    raw=b'{"rc":0,"data":{"code":"600519","klines":["2026-09-30,10,10,10,10,100,100000"]}}'
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,content=raw)))) as client:
        establish(client,instruments)
        response=client.post('/api/data/requests',json={'instruments':instruments,'groups':['DAILY'],'purpose':'OBSERVATION',
            'start_date':'2026-09-30','end_date':'2026-09-30','max_calls':1})
        assert response.status_code==201,response.text
        assert response.json()['instruments']==instruments
        run=client.post('/api/data/requests/'+response.json()['request_id']+'/retrieve').json()
        assert run['status']=='PARTIAL' and len(run['tools'])==1
        assert {g['instrument'] for g in run['gaps']}==set(instruments)
        assert all(g['code']=='TECHNICAL_LIMIT' for g in run['gaps'])


def test_all_company_groups_keep_disclosure_precision_original_documents_and_no_account_write(tmp_path):
    quote=['']*60
    for i,v in {2:'600519',3:'1258.62',4:'1235.58',5:'1239.53',6:'38331',30:'20260930161458',33:'1268',34:'1236.05',
                35:'1258.62/38331/4797246636',47:'1359.14',48:'1112.02'}.items():quote[i]=v
    announcements={'success':1,'data':{'total_hits':100,'list':[
        {'art_code':'AN_METHOD_NOTICE','title':'业绩说明会公告','notice_date':'2026-08-15 00:00:00','display_time':'2026-08-14 20:41:29:275',
         'eiTime':'2026-08-14 20:42:30:000','codes':[{'stock_code':'600519'}],'columns':[{'column_code':'001002008'}]},
        {'art_code':'AN_METHOD_REPORT','title':'2026年半年度报告','notice_date':'2026-08-15 00:00:00',
         'codes':[{'stock_code':'600519'}],'columns':[{'column_code':'001001001002001'}]},
        {'art_code':'AN_METHOD_MAJOR','title':'重大事项公告','notice_date':'2026-07-18 00:00:00',
         'codes':[{'stock_code':'600519'}],'columns':[{'column_code':'001002008'}]}]}}
    def provider(request):
        host=request.url.host
        if host=='qt.gtimg.cn':return httpx.Response(200,content=('v_sh600519="'+'~'.join(quote)+'";').encode('gbk'))
        if host=='np-anotice-stock.eastmoney.com':return httpx.Response(200,json=announcements)
        if host=='np-cnotice-stock.eastmoney.com':
            art=request.url.params['art_code']
            return httpx.Response(200,json={'success':1,'data':{'art_code':art,'notice_title':'合成公开事项',
                'notice_date':'2026-08-15 00:00:00','notice_content':'合成原文；外部权益分派只待核对。',
                'attach_list':[{'attach_url':'https://pdf.dfcfw.com/pdf/'+art+'.pdf'}]}})
        if host=='pdf.dfcfw.com':
            from pypdf import PdfWriter
            from io import BytesIO
            stream=BytesIO();writer=PdfWriter();writer.add_blank_page(width=200,height=200);writer.write(stream)
            return httpx.Response(200,content=stream.getvalue(),headers={'content-type':'application/pdf'})
        report=request.url.params['reportName']
        if report=='RPT_LICO_FN_CPD':
            return httpx.Response(200,content=b'{"success":true,"code":0,"result":{"pages":35,"count":105,"data":[{"SECURITY_CODE":"600519","REPORTDATE":"2026-06-30 00:00:00","NOTICE_DATE":"2026-08-15 00:00:00","TOTAL_OPERATE_INCOME":92278072083.21,"PARENT_NETPROFIT":44516880421.86,"EPS":35.57}]}}')
        return httpx.Response(200,json={'success':True,'code':0,'result':{'pages':6,'count':28,'data':[
            {'SECURITY_CODE':'600519','REPORT_DATE':'2025-12-31 00:00:00','NOTICE_DATE':'2026-06-22 00:00:00',
             'EX_DIVIDEND_DATE':'2026-06-26 00:00:00','EQUITY_RECORD_DATE':'2026-06-25 00:00:00',
             'PRETAX_BONUS_RMB':280.2423,'PLAN_PROGRESS':'实施方案','ASSIGNDSCRPT':'10派280.2423元(含税)'}]}})
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        establish(client,['SSE:600519'])
        before=client.get('/api/account').json()
        request=client.post('/api/data/requests',json={'instruments':['SSE:600519'],
            'groups':['QUOTE','ADJUSTMENTS','ANNOUNCEMENTS','PERFORMANCE','MAJOR_EVENTS','STATUS'],
            'purpose':'OBSERVATION','start_date':'2026-01-01','end_date':'2026-09-30','max_calls':20}).json()
        run=client.post('/api/data/requests/'+request['request_id']+'/retrieve').json()
        snapshot=client.get('/api/data/snapshots/'+run['snapshot_id']).json()
        assert {f['group'] for f in snapshot['facts']}==set(request['groups'])
        performance=next(f for f in snapshot['facts'] if f['group']=='PERFORMANCE' and f.get('total_operating_income_yuan'))
        assert performance['total_operating_income_yuan']=='92278072083.21'
        assert performance['report_period']=='2026-06-30' and performance['disclosure_date']=='2026-08-15'
        assert performance['published_at'] is None and performance['time_precision']=='DATE'
        quote_fact=next(f for f in snapshot['facts'] if f['group']=='QUOTE')
        assert quote_fact['upstream_at']=='2026-09-30T16:14:58+08:00'
        assert quote_fact['available_at']==quote_fact['received_at']
        documents=[f for f in snapshot['facts'] if f.get('document_hash')]
        assert {f['group'] for f in documents}=={'ANNOUNCEMENTS','PERFORMANCE','MAJOR_EVENTS'}
        assert all(client.get('/api/data/archives/'+f['document_hash']).content.startswith(b'%PDF') for f in documents)
        assert any(o['kind']=='PENDING_ACCOUNT_RECONCILIATION' for o in snapshot['observations'])
        assert any(g['code']=='CURRENT_STATUS_UNKNOWN' for g in run['gaps'])
        assert client.get('/api/account').json()==before


def test_fixed_background_index_retains_unknown_aggregate_units_and_missing_historical_amount(tmp_path):
    raw={'code':0,'data':{'sh000001':{'day':[['2026-09-29','3800','3830','3840','3790','400000000'],
        ['2026-09-30','3839.25','3842.19','3850','3820','414560247']]}}}
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,json=raw)))) as client:
        request=client.post('/api/data/requests',json={'instruments':['SSE:000001'],'groups':['DAILY'],'purpose':'BACKGROUND',
            'start_date':'2026-09-21','end_date':'2026-09-30'}).json()
        run=client.post('/api/data/requests/'+request['request_id']+'/retrieve').json()
        snapshot=client.get('/api/data/snapshots/'+run['snapshot_id']).json()
        assert len(snapshot['facts'])==2,run
        assert {tool['source_id'] for tool in run['tools']}=={'tencent-index-daily'}
        assert all(f['volume_reported'] and f['volume_shares'] is None and f['amount_yuan'] is None for f in snapshot['facts'])
        assert all(f['volume_unit']=='UNKNOWN' and f['model_daily_input_allowed'] is False for f in snapshot['facts'])
        assert all(f['group']=='DAILY' and f['adjustment']=='RAW' for f in snapshot['facts'])
        assert client.post('/api/data/requests',json={'instruments':['SSE:000001'],'groups':['PERFORMANCE'],
            'purpose':'RESEARCH','start_date':'2026-09-21','end_date':'2026-09-30'}).status_code==403


def test_source_revisions_preserve_old_snapshots_and_later_fetch_is_not_past_knowledge(tmp_path):
    revision=['10']
    def provider(request):
        return httpx.Response(200,json={'rc':0,'data':{'code':'600519','klines':[
            '2026-09-30,'+','.join([revision[0]]*4)+',0,0',
            '2026-10-09,20,20,20,20,0,0']}})
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        establish(client,['SSE:600519'])
        q=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['DAILY'],'purpose':'RESEARCH',
            'start_date':'2026-09-30','end_date':'2026-09-30','cutoff':'2026-09-30T23:59:59+08:00'}).json()
        old_run=client.post('/api/data/requests/'+q['request_id']+'/retrieve').json()
        old=client.get('/api/data/snapshots/'+old_run['snapshot_id']).json()
        revision[0]='11'
        new_run=client.post('/api/data/requests/'+q['request_id']+'/retrieve').json()
        new=client.get('/api/data/snapshots/'+new_run['snapshot_id']).json()
        assert len(old['facts'])==2 and all(f['trade_date']=='2026-09-30' for f in old['facts'])
        assert new['facts'][0]['revision_id']!=old['facts'][0]['revision_id']
        assert client.get('/api/data/snapshots/'+old_run['snapshot_id']).json()==old
        assert all(f['point_in_time_input_allowed'] is False for f in old['facts'])
        assert client.get('/api/data/snapshots',params={'instrument':'SSE:600519','available_before':'2026-09-30T23:59:59+08:00'}).json()==[]
        coverage=client.get('/api/data/coverage',params={'instrument':'SSE:600519','group':'DAILY'}).json()
        assert len(coverage['coverage'])==4
        assert all(c['evidence_kind']=='METHOD_CASE' and c['historical_revision_proof']=='NOT_AVAILABLE' for c in coverage['coverage'])


def test_dividend_ex_date_explains_raw_price_jump_without_cash_ledger_mutation(tmp_path):
    def provider(request):
        if request.url.host=='push2his.eastmoney.com':
            return httpx.Response(200,json={'rc':0,'data':{'code':'600519','klines':[
                '2026-06-25,100,100,100,100,0,0','2026-06-26,72,72,72,72,0,0']}})
        return httpx.Response(200,json={'success':True,'code':0,'result':{'data':[{'SECURITY_CODE':'600519',
            'REPORT_DATE':'2025-12-31 00:00:00','NOTICE_DATE':'2026-06-22 00:00:00','EX_DIVIDEND_DATE':'2026-06-26 00:00:00',
            'PRETAX_BONUS_RMB':280,'ASSIGN_PROGRESS':'实施分配'}]}})
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        establish(client,['SSE:600519']);before=client.get('/api/account').json()
        q=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['DAILY','ADJUSTMENTS'],
            'purpose':'OBSERVATION','start_date':'2026-06-22','end_date':'2026-06-30'}).json()
        run=client.post('/api/data/requests/'+q['request_id']+'/retrieve').json()
        observations=client.get('/api/data/snapshots/'+run['snapshot_id']).json()['observations']
        context=next(o for o in observations if o['kind']=='EX_RIGHTS_PRICE_CONTEXT')
        assert context['classification']=='DETERMINISTIC_INFERENCE' and context['cash_dividend_adjusted_return']=='0'
        assert len(context['basis_raw_hashes'])==2 and context['formal_judgment']=='DISABLED'
        assert not any(o['kind']=='PRICE_MOVE_OBSERVATION' for o in observations)
        assert client.get('/api/account').json()==before


@pytest.mark.parametrize('state',['NORMAL','SUSPENDED','RISK_WARNING','EX_RIGHTS','UNKNOWN'])
def test_explicit_current_status_method_cases_never_grant_real_model_or_trade_capability(tmp_path,state):
    sample={'method_case_status':state,'instrument':'SSE:600519','upstream_at':'2026-09-30T16:14:58+08:00',
        'last':'10','volume_reported':'0','amount_yuan':'0','reported_limit_up':'11','reported_limit_down':'9',
        'basis':'明确的固定异常状态样本；模拟状态时点，不是实际当前状态'}
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(lambda r:httpx.Response(200,json=sample)))) as client:
        establish(client,['SSE:600519'])
        q=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['STATUS'],'purpose':'OBSERVATION',
            'start_date':'2026-09-30','end_date':'2026-09-30'}).json()
        run=client.post('/api/data/requests/'+q['request_id']+'/retrieve').json()
        snapshot=client.get('/api/data/snapshots/'+run['snapshot_id']).json()
        fact=next(f for f in snapshot['facts'] if f['group']=='STATUS')
        assert fact['state']==state and fact['evidence_kind']=='METHOD_CASE' and fact['model_input_allowed'] is False
        assert fact['status_basis']==sample['basis']
        assert snapshot['formal_judgment']=='DISABLED'
        assert client.get('/api/market/list').json()['members'][0]['current_status']['state']=='UNKNOWN'
        if state in {'SUSPENDED','RISK_WARNING'}:
            assert any(o['kind']=='STATUS_RISK_ALERT' and o['severity']=='ATTENTION' for o in snapshot['observations'])
