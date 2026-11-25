"""Decimal valuations of confirmed account holdings and fees."""
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from roll.accounts.fills import money

SHANGHAI = timezone(timedelta(hours=8))


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
