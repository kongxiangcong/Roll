from fastapi.testclient import TestClient
from roll.app import create_app
from test_fills import establish, fill
from test_account import submit
import httpx
import json
from datetime import datetime,timedelta
from datetime import timezone
from test_fills import fee_adjustment


def save_case(name,value,expected):
    import os
    from pathlib import Path
    directory=os.environ.get('ROLL_VALUATION_EVIDENCE_DIR')
    if directory:
        target=Path(directory)
        target.mkdir(parents=True,exist_ok=True)
        (target/(name+'.json')).write_text(json.dumps({'evidence_kind':'METHOD_CASE_PUBLIC_API_REAL_SQLITE',
            'expected':expected,'actual':value},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def quote_transport(price='12.00', upstream='2026-10-07T15:00:00+08:00', status='NORMAL'):
    return httpx.MockTransport(lambda request: httpx.Response(200, json={
        'instrument':'SSE:600000','last':price,'upstream_at':upstream,
        'method_case_status':status,'basis':'仅用于估值算术方法样例，不声明实际市场状态'}))


def acquire(client):
    response=client.post('/api/data/requests',json={'instruments':['SSE:600000'],'groups':['QUOTE'],
        'purpose':'OBSERVATION','start_date':'2026-10-07','end_date':'2026-10-07'})
    assert response.status_code==201,response.text
    run=client.post('/api/data/requests/'+response.json()['request_id']+'/retrieve')
    assert run.status_code==200 and run.json()['status']=='COMPLETE',run.text
    return run.json()


def cash(client, kind, record, amount, time='15:00:00', **values):
    version=client.get('/api/account').json()['version']
    fields={'effective_at':'2026-10-07T'+time+'+08:00','source':'方法案例已确认账户原件',
            'record_id':record,'amount':amount,'basis':'逐项核对到账/待结算金额',**values}
    if kind in {'CASH_IN','CASH_OUT','DIVIDEND','INTEREST','TAX','FEE'}:
        fields.update(instrument=values.get('instrument'),broker_available_after=None)
    if kind=='SETTLEMENT':fields['broker_available_after']=None
    response=submit(client,{'kind':kind,'expected_account_version':version,'payload':fields},record)
    assert response.status_code==200,response.text


def test_partial_sale_gross_before_fees_flows_pending_tax_and_correction_conserve(tmp_path):
    with TestClient(create_app(tmp_path,market_transport=quote_transport())) as client:
        establish(client)
        assert submit(client,fill(),'buy').status_code==200
        sell=fill(2,'sell','SELL')
        sell['payload'].update(quantity='100',price='12',effective_at='2026-10-07T13:00:00+08:00')
        assert submit(client,sell,'sell').status_code==200
        acquire(client)
        simple=publish(client)
        assert simple['facts']['realized_pnl']=='200.00'
        assert simple['facts']['unrealized_pnl']=='400.00'
        assert simple['facts']['fees']=='10.00'
        assert simple['facts']['net_assets']=='100590.00'
        cash(client,'CASH_IN','deposit','10000','12:00:00')
        cash(client,'CASH_OUT','withdraw','4000','14:00:00')
        cash(client,'DIVIDEND','div','20','14:30:00')
        cash(client,'INTEREST','interest','10')
        cash(client,'PENDING_ITEM','claim','100','15:05:00',item_type='DIVIDEND',instrument='SSE:600000')
        cash(client,'SETTLEMENT','settle','60','15:10:00',target_record_id='claim')
        cash(client,'PENDING_ITEM','tax','10','15:20:00',item_type='TAX',instrument='SSE:600000')
        value=publish(client)
        assert value['cash_plus_holdings']=='106680.00'
        assert value['facts']['net_assets']=='106710.00'
        assert value['facts']['external_in']=='10000.00' and value['facts']['external_out']=='4000.00'
        assert value['facts']['income']=='90.00'
        assert value['facts']['pending_income_delta']=='40.00' and value['facts']['pending_expense_delta']=='10.00'
        assert value['performance']['total_pnl']=='710.00'
        assert value['performance']['return_percent']=='0.67405063'
        fields={'effective_at':'2026-10-07T15:30:00+08:00','source':'原件到账更正','record_id':'settle-correction',
            'target_record_id':'settle','corrected_amount':'50','basis':'原确认多记10元','broker_available_after':None}
        response=submit(client,{'kind':'CASH_CORRECTION','expected_account_version':client.get('/api/account').json()['version'],'payload':fields},'correct')
        assert response.status_code==200,response.text
        corrected=publish(client)
        assert corrected['facts']['income']=='80.00' and corrected['facts']['pending_income_delta']=='50.00'
        assert corrected['facts']['net_assets']=='106710.00'
        assert corrected['performance']['total_pnl']=='710.00'
        cash(client,'SETTLEMENT','tax-paid','10','15:40:00',target_record_id='tax')
        stale=publish(client,as_of='2026-10-08T00:00:00+08:00')
        assert stale['positions'][0]['quote_status']=='STALE'
        assert stale['facts']['net_assets']=='106710.00'
        assert stale['facts']['fees']=='20.00' and stale['facts']['pending_expense_delta']=='0.00'
        assert stale['performance']['total_pnl']=='710.00'
        for target,record in [('tax-paid','tax-paid-correction'),('tax','tax-liability-correction')]:
            payload={**fields,'record_id':record,'target_record_id':target,'corrected_amount':'8',
                'effective_at':'2026-10-07T15:50:00+08:00','basis':'税费原件更正，保留到账和应付关系'}
            response=submit(client,{'kind':'CASH_CORRECTION','expected_account_version':client.get('/api/account').json()['version'],'payload':payload},record)
            assert response.status_code==200,response.text
        final=publish(client,as_of='2026-10-08T00:00:00+08:00')
        assert final['facts']['net_assets']=='106712.00'
        assert final['facts']['fees']=='18.00' and final['facts']['pending_expense_delta']=='0.00'
        assert final['performance']['total_pnl']=='712.00'
        save_case('cash-flows-and-tax-corrections',final,{'net_assets':'106712.00','fees':'18.00','pnl':'712.00','quote_status':'STALE'})
        assert client.post('/api/account/valuations/'+value['valuation_id']+'/replay').json()==value


def test_late_fee_and_free_share_children_are_not_double_deducted(tmp_path):
    with TestClient(create_app(tmp_path,market_transport=quote_transport('6'))) as client:
        establish(client)
        assert submit(client,fill(fee_status='PROVISIONAL'),'buy').status_code==200
        cmd={'kind':'SHARE_CHANGE','expected_account_version':2,'payload':{'effective_at':'2026-10-07T12:00:00+08:00',
             'source':'免费送转原件','record_id':'double','instrument':'SSE:600000','new_quantity':'600','basis':'份额加倍，总成本不变'}}
        assert submit(client,cmd,'double').status_code==200
        sell=fill(3,'sell','SELL')
        sell['payload'].update(quantity='200',price='6',effective_at='2026-10-07T13:00:00+08:00')
        assert submit(client,sell,'sell').status_code==200
        acquire(client)
        pending=publish(client)
        assert pending['facts']['fees'] is None and pending['performance']['total_pnl'] is None
        assert submit(client,fee_adjustment(4,'3.00'),'fee').status_code==200
        value=publish(client)
        assert value['facts']['realized_pnl']=='200.00'
        assert value['facts']['unrealized_pnl']=='400.00'
        assert value['facts']['fees']=='8.00'
        assert value['facts']['net_assets']=='100592.00'
        assert value['performance']['total_pnl']=='592.00'
        save_case('free-share-late-fee',value,{'gross_realized':'200.00','gross_unrealized':'400.00','fees':'8.00','pnl':'592.00'})
        assert client.post('/api/account/valuations/'+value['valuation_id']+'/replay').json()==value


def test_paid_rights_known_total_unknown_split_and_later_fee_do_not_pay_twice(tmp_path):
    with TestClient(create_app(tmp_path,market_transport=quote_transport('6'))) as client:
        establish(client)
        command={'kind':'RIGHTS_SUBSCRIPTION','expected_account_version':1,'payload':{
            'effective_at':'2026-10-07T11:00:00+08:00','source':'配股缴款原件','record_id':' paid-rights ',
            'instrument':'SSE:600000','quantity':'100','amount':'501','fee_amount':None,
            'basis':'实际支付总额已知，本金与费用分拆待核','broker_available_after':None}}
        assert submit(client,command,'rights').status_code==200
        acquire(client)
        unknown=publish(client)
        assert unknown['facts']['net_assets']=='100099.00'
        assert unknown['facts']['fees'] is None and unknown['performance']['total_pnl'] is None
        assert submit(client,fee_adjustment(2,'1.00','paid-rights'),'split').status_code==200
        known=publish(client)
        assert known['account']['cash_balance']=='99499.00'
        assert known['facts']['unrealized_pnl']=='100.00' and known['facts']['fees']=='1.00'
        assert known['performance']['total_pnl']=='99.00'
        sell=fill(3,'sell-rights','SELL')
        sell['payload'].update(quantity='50',price='6',effective_at='2026-10-07T13:00:00+08:00')
        assert submit(client,sell,'sell-rights').status_code==200
        partial=publish(client)
        assert partial['facts']['realized_pnl']=='50.00' and partial['facts']['unrealized_pnl']=='50.00'
        assert partial['facts']['fees']=='6.00' and partial['performance']['total_pnl']=='94.00'
        save_case('paid-rights-partial',partial,{'gross_realized':'50.00','gross_unrealized':'50.00','fees':'6.00','pnl':'94.00'})


def test_stale_suspended_and_unknown_baseline_are_explicit_not_adjusted_prices(tmp_path):
    with TestClient(create_app(tmp_path,market_transport=quote_transport('12',status='SUSPENDED'))) as client:
        establish(client)
        submit(client,fill(),'buy')
        acquire(client)
        stale=publish(client,as_of='2026-10-08T00:00:00+08:00')
        assert stale['facts']['valuation_status']=='STALE'
        assert stale['positions'][0]['quote_status']=='STALE'
        assert stale['positions'][0]['quote']['upstream_at']=='2026-10-07T15:00:00+08:00'
        assert stale['facts']['unrealized_pnl']=='600.00' and stale['performance']['total_pnl']=='595.00'
        assert stale['performance']['estimated'] is True
        cutoff=stale['positions'][0]['quote']['available_at']
        unavailable=publish(client,known_by=(datetime.fromisoformat(cutoff)-timedelta(microseconds=1)).isoformat())
        # The 8th's actual acquisition was not available at this knowledge cutoff.
        assert unavailable['facts']['net_assets'] is None
        assert client.post('/api/account/valuations',json={'scope_kind':'TRIAL_ACTUAL','scope_id':'trial',
            'baseline_account_version':1,'origin_at':'2026-10-07T10:00:00+08:00','as_of':'2026-10-07T16:00:00+08:00'}).status_code==422


def test_imported_baseline_without_mark_never_becomes_whole_history_profit(tmp_path):
    from test_account import baseline
    with TestClient(create_app(tmp_path,market_transport=quote_transport())) as client:
        command=baseline()
        command['payload']['positions'][0]['reference_cost']=None
        submit(client,command,'baseline')
        acquire(client)
        value=publish(client)
        assert value['facts']['net_assets']=='103600.10'
        assert value['facts']['baseline_assets'] is None
        assert value['facts']['unrealized_pnl'] is None
        assert value['performance']['total_pnl'] is None
        assert value['historical_return_before_baseline'] is None
        assert value['account']['broker_frozen']=='10000.00'
        assert value['cash_plus_holdings']=='103600.10'
        save_case('unknown-opening-history',value,{'net_assets':'103600.10','baseline_assets':None,'pnl':None})


def test_funding_origin_baseline_scope_are_retained_and_loss_contract_consumes_gross_facts(tmp_path):
    from test_funding import funding
    from roll.decisions.funding import LossFacts,evaluate_loss
    with TestClient(create_app(tmp_path,market_transport=quote_transport('8'))) as client:
        establish(client)
        authorization=client.post('/api/funding/confirm',json=funding()).json()
        submit(client,fill(),'buy')
        acquire(client)
        value=publish(client,scope_id='account-1')
        result=evaluate_loss(authorization,LossFacts(**value['facts']))
        assert result['pnl']=='-605.00' and result['loss']=='605.00'
        assert result['remaining_loss_allowance']=='4395.00'
        # 09 only provides facts. This arithmetic call does not mutate funding/actions.
        assert client.get('/api/funding').json()['loss_status']=='PENDING_FACTS'
        assert client.get('/api/capabilities').json()['state']=='UNGRANTED'
        expanded=client.post('/api/funding/confirm',json=funding(1,capital_amount='200000.00',loss_threshold='10000.00')).json()
        assert expanded['loss_origin_at']==authorization['loss_origin_at']
        assert publish(client,scope_id='account-1')['facts']['baseline_account_version']==1
        bad={'baseline_account_version':2,'origin_at':'2026-10-07T11:00:00+08:00',
            'as_of':'2026-10-07T16:00:00+08:00','scope_id':'account-1'}
        assert client.post('/api/account/valuations',json=bad).status_code==409


def test_asynchronous_marks_missing_placeholder_and_raw_hash_tamper(tmp_path):
    def provider(request):
        symbol=str(request.url).rsplit('=',1)[1]
        second=symbol.endswith('600001')
        return httpx.Response(200,json={'instrument':'SSE:'+symbol[2:],'last':'8' if second else '12',
            'upstream_at':'2026-10-07T14:00:00+08:00' if second else '2026-10-07T15:00:00+08:00',
            'method_case_status':'NORMAL','basis':'异步报价方法案例'})
    app=create_app(tmp_path,market_transport=httpx.MockTransport(provider))
    with TestClient(app) as client:
        establish(client)
        submit(client,fill(),'buy')
        second=fill(2,'buy2')
        second['payload'].update(instrument='SSE:600001',quantity='100',price='8',effective_at='2026-10-07T12:00:00+08:00')
        submit(client,second,'buy2')
        for instrument in ['SSE:600000','SSE:600001']:
            req=client.post('/api/data/requests',json={'instruments':[instrument],'groups':['QUOTE'],'purpose':'OBSERVATION',
                'start_date':'2026-10-07','end_date':'2026-10-07'}).json()
            run=client.post('/api/data/requests/'+req['request_id']+'/retrieve').json()
            assert run['status']=='COMPLETE',run
        value=publish(client)
        assert value['asynchronous_quotes'] is True and value['facts']['valuation_status']=='STALE'
        assert value['facts']['net_assets']=='100590.00'
        assert value['facts']['fees']=='10.00'
        raw=app.state.evidence.raw(value['positions'][0]['quote']['raw_hash'])
        raw.write_bytes(b'corrupt-method-case')
        assert client.post('/api/account/valuations/'+value['valuation_id']+'/replay').status_code==409


def test_reconciliation_alignment_is_not_invented_profit_and_actual_correction_replays(tmp_path):
    from test_reconcile import reconcile
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        cash(client,'CASH_IN','deposit','1000','12:00:00')
        command=reconcile(2,'cash-align',{'cash_balance':'101500.00','broker_available':'101500.00',
            'broker_frozen':'0.00','withdrawable':None,'positions':[],'pending_items':[],
            'investment_income':'0.00','investment_expenses':'0.00'})
        response=submit(client,command,'align')
        assert response.status_code==200,response.text
        value=publish(client)
        assert value['facts']['net_assets']=='101500.00'
        assert value['performance']['nav_adjusted_pnl']=='500.00'
        assert value['performance']['total_pnl'] is None
        assert value['performance']['conservation']=='RECONCILE_REQUIRED'
        assert value['facts']['valuation_status']=='MISSING'


def test_append_sell_replacement_and_late_fifo_do_not_mutate_old_values(tmp_path):
    with TestClient(create_app(tmp_path,market_transport=quote_transport())) as client:
        establish(client)
        submit(client,fill(),'buy')
        sell=fill(2,'sell','SELL')
        sell['payload'].update(quantity='100',price='12',effective_at='2026-10-07T13:00:00+08:00')
        submit(client,sell,'sell')
        acquire(client)
        original=publish(client)
        event=next(e for e in client.get('/api/account/events').json() if e['event_type']=='SELL_FILL')
        replacement={**sell['payload'],'price':'11'}
        command={'kind':'CORRECTION','expected_account_version':3,'payload':{'effective_at':'2026-10-07T15:30:00+08:00',
            'source':'更正实际成交回报','record_id':'correct-sell','target_event_id':event['event_id'],
            'reason':'原件卖价为11非12','replacement':{'kind':'FILL','payload':replacement}}}
        assert submit(client,command,'correct-sell').status_code==200
        corrected=publish(client)
        assert corrected['facts']['realized_pnl']=='100.00' and corrected['performance']['total_pnl']=='490.00'
        late=fill(4,'late-buy')
        late['payload'].update(quantity='100',price='8',effective_at='2026-10-07T10:30:00+08:00',
            fee={'status':'KNOWN','amount':'1','reserve_amount':None,'basis':'迟补原件费用'})
        assert submit(client,late,'late-buy').status_code==200
        latest=publish(client)
        assert latest['facts']['realized_pnl']=='300.00' and latest['facts']['unrealized_pnl']=='600.00'
        assert latest['facts']['fees']=='11.00' and latest['performance']['total_pnl']=='889.00'
        assert client.post('/api/account/valuations/'+original['valuation_id']+'/replay').json()==original
        assert publish(client,known_by=original['known_by'])['performance']==original['performance']


def test_opening_quote_knowledge_is_origin_time_not_account_confirmation_time(tmp_path):
    from test_account import baseline
    from test_funding import funding
    upstream=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()
    with TestClient(create_app(tmp_path,market_transport=quote_transport('12',upstream))) as client:
        command=baseline()
        command['payload']['positions'][0]['reference_cost']=None
        submit(client,command,'baseline')
        acquire(client)
        origin=datetime.now(timezone.utc).isoformat()
        authorization=client.post('/api/funding/confirm',json=funding(effective_at=origin)).json()
        value=publish(client,origin_at=origin,as_of=datetime.now(timezone.utc).isoformat(),scope_id='account-1')
        assert value['facts']['baseline_assets']=='103600.10'
        assert value['facts']['net_assets']=='103600.10'
        assert value['facts']['unrealized_pnl']=='0.00'
        assert value['performance']['total_pnl']=='0.00'
        assert value['facts']['valuation_status']=='COMPLETE'
        quote=value['baseline_quotes']['SSE:600000']
        assert datetime.fromisoformat(value['account']['confirmed_at']) < datetime.fromisoformat(quote['available_at']) <= datetime.fromisoformat(origin)
        assert authorization['baseline_account_version']==1
        assert client.post('/api/account/valuations/'+value['valuation_id']+'/replay').json()==value



def test_trial_authorization_does_not_block_whole_account_valuation_or_relabel_it_as_trial(tmp_path):
    from test_funding import funding
    from roll.decisions.funding import LossFacts,evaluate_loss
    import pytest
    from fastapi import HTTPException
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        authorization=client.post('/api/funding/confirm',json=funding(scope_kind='TRIAL_ACTUAL',scope_id='trial-1')).json()
        basis=client.get('/api/account/valuation-basis').json()
        assert basis['scope_kind']=='ACCOUNT' and basis['scope_id']=='account'
        assert basis['loss_binding'] is False
        value=publish(client)
        assert value['facts']['net_assets']=='100000.00'
        assert value['facts']['scope_kind']=='ACCOUNT'
        with pytest.raises(HTTPException):evaluate_loss(authorization,LossFacts(**value['facts']))
        rejected=client.post('/api/account/valuations',json={'scope_kind':'TRIAL_ACTUAL','scope_id':'trial-1',
            'baseline_account_version':1,'origin_at':authorization['loss_origin_at'],'as_of':'2026-10-07T16:00:00+08:00'})
        assert rejected.status_code==422
        assert client.get('/api/funding').json()==authorization


def test_tax_payment_and_claim_restatement_preserves_old_knowledge_and_overshoot_guard(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        cash(client,'PENDING_ITEM','tax','10','12:00:00',item_type='TAX',instrument=None)
        cash(client,'SETTLEMENT','paid','10','13:00:00',target_record_id='tax')
        original=client.get('/api/account').json()
        events=client.get('/api/account/events').json()
        for target,record in [('paid','paid-fixed'),('tax','tax-fixed')]:
            fields={'effective_at':'2026-10-07T15:00:00+08:00','source':'实际税款原件更正','record_id':record,
                'target_record_id':target,'corrected_amount':'8','basis':'到账与应付皆为8元','broker_available_after':None}
            response=submit(client,{'kind':'CASH_CORRECTION','expected_account_version':client.get('/api/account').json()['version'],'payload':fields},record)
            assert response.status_code==200,response.text
        current=client.get('/api/account').json()
        assert current['cash_balance']=='99992.00' and current['investment_expenses']=='8.00'
        assert current['pending_items'][0]['outstanding_amount']=='0.00'
        assert current['pending_items'][0]['settled_amount']=='8.00'
        assert client.get('/api/account/versions/3').json()==original
        assert client.get('/api/account/events').json()[:len(events)]==events
        before=client.get('/api/account/as-of',params={'known_by':original['confirmed_at'],'effective_at':'2026-10-07T16:00:00+08:00'}).json()['account']
        assert before['cash_balance']=='99990.00' and before['investment_expenses']=='10.00'
        assert client.get('/api/account/replay').json()['cash_balance']=='99992.00'
        value=publish(client)
        assert value['facts']['fees']=='8.00' and value['performance']['total_pnl']=='-8.00'
        save_case('tax-double-restatement',value,{'cash':'99992.00','pending':'0.00','fees':'8.00','pnl':'-8.00'})
    with TestClient(create_app(tmp_path/'illegal')) as client:
        establish(client)
        cash(client,'PENDING_ITEM','tax','8','12:00:00',item_type='TAX',instrument=None)
        fields={'effective_at':'2026-10-07T13:00:00+08:00','source':'错误超额原件','record_id':'paid',
            'target_record_id':'tax','amount':'10','basis':'不可无更正超额结算','broker_available_after':None}
        draft=client.post('/api/account/drafts',json={'kind':'SETTLEMENT','expected_account_version':2,'payload':fields}).json()
        assert draft['status']=='QUARANTINED'
        assert client.post('/api/account/confirm',json={'draft_id':draft['draft_id'],'idempotency_key':'overshoot'}).status_code==422
        assert client.get('/api/account').json()['cash_balance']=='100000.00'


def test_csv_three_preserves_raw_claim_payment_and_two_corrections_in_one_version(tmp_path):
    from test_csv_import import upload,confirm
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        rows=[{'kind':'PENDING_ITEM','record_id':'tax','item_type':'TAX','amount':'10','basis':'已核对税款'},
              {'kind':'SETTLEMENT','record_id':'paid','target_record_id':'tax','amount':'10','basis':'原缴税凭证'},
              {'kind':'CASH_CORRECTION','record_id':'paid-fixed','target_record_id':'paid','corrected_amount':'8','basis':'已付原件更正'},
              {'kind':'CASH_CORRECTION','record_id':'tax-fixed','target_record_id':'tax','corrected_amount':'8','basis':'应付原件更正'}]
        for row,time in zip(rows,['12:00:00','13:00:00','14:00:00','15:00:00']):row['effective_at']='2026-10-07T'+time+'+08:00'
        draft=upload(client,rows,1,template_version='ROLL-CSV-3').json()
        assert draft['status']=='READY',draft
        response=confirm(client,draft,'all-four')
        assert response.status_code==200,response.text
        assert response.json()['account_version']==2 and len(response.json()['event_ids'])==4
        account=client.get('/api/account').json()
        assert account['cash_balance']=='99992.00' and account['pending_expenses']=='0.00'
        assert client.get('/api/account/replay').json()['cash_balance']=='99992.00'
        file=client.get('/api/account/csv/files/'+draft['file']['sha256']).content
        import hashlib
        assert hashlib.sha256(file).hexdigest()==draft['file']['sha256']
        rows_saved=client.get('/api/account/csv/drafts/'+draft['draft_id']).json()['rows']
        assert rows_saved[0]['fields']['amount']=='10' and rows_saved[1]['fields']['amount']=='10'


def publish(client, **values):
    command = {'baseline_account_version': 1, 'origin_at': '2026-10-07T10:00:00+08:00',
               'as_of': '2026-10-07T16:00:00+08:00', **values}
    response = client.post('/api/account/valuations', json=command)
    assert response.status_code == 201, response.text
    return response.json()


def test_cash_only_nav_freezing_and_immutable_replay(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app) as client:
        establish(client)
        value = publish(client)
        assert value['facts']['baseline_assets'] == '100000.00'
        assert value['facts']['net_assets'] == '100000.00'
        assert value['facts']['realized_pnl'] == '0.00'
        assert value['facts']['fees'] == '0.00'
        assert value['performance']['total_pnl'] == '0.00'
        assert value['performance']['return_percent'] == '0.00000000'
        assert value['account']['broker_frozen'] == '0.00'
        assert client.get('/api/account/valuations/' + value['valuation_id']).json() == value
        assert client.post('/api/account/valuations/' + value['valuation_id'] + '/replay').json() == value
        assert client.get('/api/account').json()['version'] == 1
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/account/valuations/' + value['valuation_id']).json() == value


def test_missing_quote_does_not_hide_position_or_invent_zero_nav(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        assert submit(client, fill(), 'buy').status_code == 200
        value = publish(client)
        assert value['facts']['net_assets'] is None
        assert value['facts']['valuation_status'] == 'MISSING'
        assert value['facts']['fees'] == '5.00'
        assert value['positions'][0]['quantity'] == '300'
        assert value['positions'][0]['market_value'] is None
        assert value['facts']['realized_pnl'] == '0.00'
