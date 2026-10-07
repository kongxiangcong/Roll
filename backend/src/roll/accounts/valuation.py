"""Versioned account marks and fee-before period facts from immutable inputs."""
import hashlib
import json
from datetime import datetime, timezone, timedelta
from decimal import Decimal, localcontext, ROUND_HALF_UP
from uuid import uuid4
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from roll.accounts.ledger import encode, now, timestamp
from roll.accounts.fills import money
from roll.decisions.funding import LossFacts,Funding

METHOD='account-raw-nav-dietz-v1'
SHANGHAI=timezone(timedelta(hours=8))


class ValuationRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    baseline_account_version:int=Field(ge=1)
    origin_at:str
    as_of:str
    known_by:str|None=None
    scope_kind:Literal['ACCOUNT','TRIAL_ACTUAL']='ACCOUNT'
    scope_id:str='account'


def at(value):
    return datetime.fromisoformat(value)


def fees(account):
    if account.get('fees_pending') or account.get('rights_fee_breakdown_pending'):return None
    total=Decimal(account.get('investment_expenses','0.00'))
    for item in account.get('fills',[]):
        total+=Decimal(account.get('fee_resolutions',{}).get(item['record_id'],{}).get('actual_fee_amount',item['charged_fee']))
    for item in account.get('share_records',[]):
        if item['kind']=='RIGHTS_SUBSCRIPTION':
            total+=Decimal(account.get('fee_resolutions',{}).get(item['record_id'],{}).get('actual_fee_amount',item['fee_amount']))
    return total


def marks(account,quotes,as_of):
    rows=[]
    for position in account['positions']:
        quote=quotes.get(position['instrument'])
        price=quote['last'] if quote else None
        status='MISSING' if price is None or position['quantity'] is None else 'STALE' if quote.get('method_status')=='SUSPENDED' or at(quote['upstream_at']).astimezone(SHANGHAI).date()!=at(as_of).astimezone(SHANGHAI).date() else 'SAME_DAY_INDICATIVE'
        rows.append({'instrument':position['instrument'],'quantity':position['quantity'],
            'price':price,'market_value':None if price is None or position['quantity'] is None else money(Decimal(position['quantity'])*Decimal(price)),
            'acquisition_cost_including_fees':position.get('acquisition_cost'),
            'broker_reference_cost':position.get('reference_cost'),'quote_status':status,'quote':quote})
    unknown=account['cash_balance'] is None or any(r['market_value'] is None for r in rows)
    assets=None if unknown else Decimal(account['cash_balance'])+sum((Decimal(r['market_value']) for r in rows),Decimal(0))
    net=None if assets is None else assets+Decimal(account.get('pending_income','0.00'))-Decimal(account.get('pending_expenses','0.00'))
    times={r['quote']['upstream_at'] for r in rows if r['quote']}
    status='MISSING' if unknown else 'STALE' if any(r['quote_status']=='STALE' for r in rows) or len(times)>1 else 'COMPLETE'
    return rows,assets,net,status,len(times)>1


def calculate(ledger,inputs,valuation_id,created_at):
    command=inputs['command']; baseline,current=inputs['baseline'],inputs['account']
    with localcontext() as context:
        context.prec=80
        rows,assets,net,status,async_quotes=marks(current,inputs['quotes'],command['as_of'])
        _,_,base_net,base_status,_=marks(baseline,inputs['baseline_quotes'],command['origin_at'])
        opening={k:q['last'] for k,q in inputs['baseline_quotes'].items()}
        right_fees={r['record_id']:current.get('fee_resolutions',{}).get(r['record_id'],{}).get('actual_fee_amount',r['fee_amount']) for r in current.get('share_records',[]) if r['kind']=='RIGHTS_SUBSCRIPTION'}
        gross=ledger.price_period(baseline,command['origin_at'],command['as_of'],inputs['events'],opening,right_fees)
        realized=None if gross is None or gross.get('realized_gain') is None else Decimal(gross.get('realized_gain','0.00'))
        remaining=None if gross is None or any(p.get('acquisition_cost') is None for p in gross['positions']) else sum((Decimal(p['acquisition_cost']) for p in gross['positions']),Decimal(0))
        holdings=None if any(r['market_value'] is None for r in rows) else sum((Decimal(r['market_value']) for r in rows),Decimal(0))
        unrealized=None if remaining is None or holdings is None else holdings-remaining
        amounts={'baseline_assets':base_net,'net_assets':net,'realized_pnl':realized,'unrealized_pnl':unrealized}
        for field,account_field in [('external_in','external_cash_in'),('external_out','external_cash_out'),('income','investment_income'),('pending_income_delta','pending_income'),('pending_expense_delta','pending_expenses')]:
            amounts[field]=Decimal(current.get(account_field,'0.00'))-Decimal(baseline.get(account_field,'0.00'))
        for field in ['external_in','external_out']:
            if amounts[field]<0:amounts[field]=None
        f,bf=fees(current),fees(baseline)
        amounts['fees']=None if f is None or bf is None else f-bf
        if current.get('fees_pending'):amounts['net_assets']=None
        facts=LossFacts(scope_kind=command['scope_kind'],scope_id=command['scope_id'],baseline_account_version=command['baseline_account_version'],
            origin_at=command['origin_at'],as_of=command['as_of'],facts_version=valuation_id,
            valuation_status='MISSING' if base_status=='MISSING' else 'STALE' if base_status=='STALE' or status=='STALE' else status,
            **{k:None if v is None else money(v) for k,v in amounts.items()}).model_dump()
        pnl=None if None in amounts.values() else realized+unrealized+amounts['income']-amounts['fees']+amounts['pending_income_delta']-amounts['pending_expense_delta']
        nav_pnl=None if any(amounts[k] is None for k in ['net_assets','baseline_assets','external_in','external_out']) else net-base_net-amounts['external_in']+amounts['external_out']
        conservation='UNKNOWN' if pnl is None or nav_pnl is None else 'MATCH' if money(pnl)==money(nav_pnl) else 'RECONCILE_REQUIRED'
        if conservation=='RECONCILE_REQUIRED':facts['valuation_status']='MISSING'
        duration=(at(command['as_of'])-at(command['origin_at'])).total_seconds()
        weighted=Decimal(0)
        for record in current.get('cash_records',[]):
            if record['kind'] not in {'CASH_IN','CASH_OUT'} or not at(command['origin_at'])<at(record['effective_at'])<=at(command['as_of']):continue
            amount=current.get('cash_resolutions',{}).get(record['record_id'],{}).get('amount',record['amount'])
            weight=Decimal(str((at(command['as_of'])-at(record['effective_at'])).total_seconds()))/Decimal(str(duration)) if duration else Decimal(0)
            weighted+=Decimal(amount)*weight*(1 if record['kind']=='CASH_IN' else -1)
        denominator=None if base_net is None else base_net+weighted
        percent=None if conservation!='MATCH' or denominator is None or denominator<=0 or duration<=0 else format((pnl/denominator*100).quantize(Decimal('0.00000001'),rounding=ROUND_HALF_UP),'f')
        return {'valuation_id':valuation_id,'created_at':created_at,'method_version':METHOD,'namespace':'ACTUAL',
            'input_authority':'ACTUAL_ACCOUNT_WITH_METHOD_MARKS' if any(q['evidence_kind']=='METHOD_CASE' for q in list(inputs['quotes'].values())+list(inputs['baseline_quotes'].values())) else 'CONFIRMED_ACCOUNT_AND_ARCHIVED_SOURCE',
            'scope_kind':command['scope_kind'],'scope_id':command['scope_id'],'account_version':current['version'],
            'known_by':command['known_by'],'origin_at':command['origin_at'],'as_of':command['as_of'],
            'baseline_before_history':'INCOMPLETE','historical_return_before_baseline':None,
            'account':{k:current.get(k) for k in ['confirmed_at','effective_at','cash_balance','cash_balance_basis','fees_pending','rights_fee_breakdown_pending','broker_available','broker_available_as_of','broker_frozen','broker_frozen_as_of','withdrawable','withdrawable_as_of']},
            'baseline_quote_status':base_status,'baseline_quotes':inputs['baseline_quotes'],
            'positions':rows,'cash_plus_holdings':None if assets is None else money(assets),
            'cash_estimated':bool(current.get('fees_pending')),
            'pending_items':current.get('pending_items',[]),'pending_income':current.get('pending_income','0.00'),'pending_expenses':current.get('pending_expenses','0.00'),
            'pending_policy':'CONFIRMED_OUTSTANDING_RECEIVABLES_MINUS_PAYABLES_INCLUDED_IN_NET_ASSETS; NOT_CASH_OR_BROKER_AVAILABLE',
            'asynchronous_quotes':async_quotes,'freshness_policy':'SAME_SHANGHAI_DATE_INDICATIVE; DIFFERENT_DATES_OR_SUSPENDED_OR_ASYNCHRONOUS_STALE; NOT_TRADING_QUALIFICATION',
            'facts':facts,'performance':{'total_pnl':None if conservation!='MATCH' else money(pnl),'nav_adjusted_pnl':None if nav_pnl is None else money(nav_pnl),
                'conservation':conservation,'return_method':'MODIFIED_DIETZ_ACTUAL_EFFECTIVE_TIME_V1','weighted_capital':None if denominator is None else money(denominator),
                'return_percent':percent,'estimated':status=='STALE' or base_status=='STALE'},
            'authority':{'technical_capability':'UNGRANTED','remaining_loss_allowance':None},'input_fingerprint':hashlib.sha256(encode(inputs).encode()).hexdigest()}


class Valuations:
    def __init__(self,ledger,evidence):
        self.ledger,self.evidence=ledger,evidence
        with ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS valuation_versions(id TEXT PRIMARY KEY, inputs TEXT NOT NULL, result TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS valuation_baselines(id TEXT PRIMARY KEY, quotes TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS schema_migrations(name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO schema_migrations VALUES(?,?)',('09-valuation-v1',now()))

    def basis(self):
        funding=Funding(self.ledger).current()
        versions=self.ledger.versions()
        if not versions:raise HTTPException(409,'请先确认账户基线')
        return {'baseline_account_version':funding.get('baseline_account_version',versions[0]['version']),
            'origin_at':funding.get('loss_origin_at',versions[0]['effective_at']),
            'scope_kind':funding.get('scope_kind','ACCOUNT'),'scope_id':funding.get('scope_id','account'),
            'funding_version':funding['version'],'as_of':now()}

    def quotes(self,account,as_of,known_by):
        result={}
        for position in account['positions']:
            candidates=[{**f,'snapshot_id':s['snapshot_id'],'run_id':s['run_id']} for s in self.evidence.snapshots(position['instrument'],'QUOTE',at(known_by)) for f in s['facts'] if at(f['upstream_at'])<=at(as_of)]
            if candidates:
                result[position['instrument']]=max(candidates,key=lambda f:(at(f['upstream_at']),at(f['available_at'])))
        return result

    def publish(self,command):
        command=command.model_dump()
        basis=self.basis()
        if command['scope_kind']!='ACCOUNT' or command['scope_id']!=basis['scope_id'] or basis['scope_kind']!='ACCOUNT':raise HTTPException(422,{'code':'UNSUPPORTED_ACTUAL_SCOPE','reason':'真实试用逐事件归属尚未确认，不能用全账户代替；账户范围需匹配现有事实链'})
        for field in ['origin_at','as_of']:
            command[field]=timestamp(command[field],field)
        command['known_by']=timestamp(command['known_by'] or now(),'known_by')
        if basis['funding_version'] and (command['baseline_account_version']!=basis['baseline_account_version'] or at(command['origin_at'])!=at(basis['origin_at'])):
            raise HTTPException(409,'不能更换已确认资金授权链的基线或损失起点')
        baseline=self.ledger.account(command['baseline_account_version'])
        if at(command['origin_at'])<at(baseline['effective_at']) or at(command['as_of'])<at(command['origin_at']):raise HTTPException(422,'基线版本不能含起点后的事实，截止不能早于起点')
        if at(command['known_by'])<at(baseline['confirmed_at']):raise HTTPException(422,'当时尚未知所请求基线版本')
        current=self.ledger.replay(known_by=command['known_by'],effective_at=command['as_of'])
        events=[e for e in self.ledger.events() if at(e['recorded_at'])<=at(command['known_by'])]
        inputs={'command':command,'baseline':baseline,'account':current,'events':events,
            'quotes':self.quotes(current,command['as_of'],command['known_by']),
            'baseline_quotes':self.quotes(baseline,command['origin_at'],min(at(command['origin_at']),at(command['known_by'])).isoformat())}
        for q in list(inputs['quotes'].values())+list(inputs['baseline_quotes'].values()):self.evidence.replay(q['run_id'])
        identifier,created=str(uuid4()),now()
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                if at(command['known_by'])>=at(command['origin_at']):
                    anchor=encode({key:command[key] for key in ['baseline_account_version','scope_kind','scope_id']}|{'origin_at':at(command['origin_at']).astimezone(timezone.utc).isoformat()})
                    db.execute('INSERT OR IGNORE INTO valuation_baselines VALUES(?,?)',(anchor,encode(inputs['baseline_quotes'])))
                    inputs['baseline_quotes']=json.loads(db.execute('SELECT quotes FROM valuation_baselines WHERE id=?',(anchor,)).fetchone()[0])
                result=calculate(self.ledger,inputs,identifier,created)
                db.execute('INSERT INTO valuation_versions VALUES(?,?,?)',(identifier,encode(inputs),encode(result)))
                self.ledger.crash_point('valuation_before_commit')
                db.commit()
                self.ledger.crash_point('valuation_after_commit')
            except BaseException:
                db.rollback()
                raise
        return result

    def get(self,identifier=None,replay=False):
        with self.ledger.connection() as db:
            row=db.execute('SELECT inputs,result FROM valuation_versions ORDER BY rowid DESC LIMIT 1' if identifier is None else 'SELECT inputs,result FROM valuation_versions WHERE id=?',() if identifier is None else (identifier,)).fetchone()
        if row is None:raise HTTPException(404,'估值版本尚未发布')
        inputs,result=json.loads(row[0]),json.loads(row[1])
        if replay:
            for q in list(inputs['quotes'].values())+list(inputs['baseline_quotes'].values()):self.evidence.replay(q['run_id'])
            actual=calculate(self.ledger,inputs,result['valuation_id'],result['created_at'])
            if actual!=result:raise HTTPException(409,'估值结构化重放不一致')
        return result

    def history(self):
        with self.ledger.connection() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT result FROM valuation_versions ORDER BY rowid DESC LIMIT 100')]
