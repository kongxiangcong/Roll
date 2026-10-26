"""Deterministic financial metrics from immutable observations at a knowledge cutoff."""
from datetime import date
from decimal import Decimal,InvalidOperation,localcontext
from roll.market.financial_statements import joined

VERSION='financial-metrics-v1'
FLOW={'revenue':'INCOME','parent_net_profit':'INCOME','net_profit':'INCOME','operating_cash_flow':'CASH_FLOW'}


def comparable(facts):
    if not facts or any(f is None for f in facts):return False
    keys=('instrument','statement_scope','currency','unit','source_id','evidence_kind')
    first=facts[0]
    return all(all(f.get(k) not in (None,'UNKNOWN') and f[k]==first[k] for k in keys) and
        f['period_basis']==('POINT_IN_TIME' if f['statement']=='BALANCE' else 'YEAR_TO_DATE') and
        f['original_fields'].get('ORG_CODE')==first['original_fields'].get('ORG_CODE') for f in facts)


def amount(fact,key):
    if fact is None:return None
    source_field={'operating_cost':'OPERATE_COST','operating_revenue':'OPERATE_INCOME'}.get(key)
    raw=fact['original_fields'].get(source_field) if source_field else fact['values'].get(key)
    try:
        value=Decimal(str(raw));return value if value.is_finite() else None
    except (InvalidOperation,ValueError,TypeError):return None


def result(value,formula,facts,reason=None,unit='YUAN',**extra):
    return {'status':'UNKNOWN' if value is None else 'KNOWN','value':None if value is None else str(value),
        'formula':formula,'reason':reason,'unit':unit,'source_fact_ids':list(dict.fromkeys(f['fact_id'] for f in facts if f)),**extra}


def previous_quarter(period):
    year,month=period.year,period.month
    return date(year-1,12,31) if month==3 else date(year,month-3,31 if month==6 else 30)


def metrics(income,supplement,instrument,cutoff=None):
    view=joined(income,supplement,instrument,cutoff);current={}
    for fact in view['facts']:
        key=(fact['statement'],fact['report_period'])
        if key not in current or fact['version']>current[key]['version']:current[key]=fact
    def get(statement,period):return current.get((statement,period.isoformat()))
    def quarter(key,period):
        fact=get(FLOW[key],period);sources=[fact]
        if period.month not in (3,6,9,12) or period.day!=(31 if period.month in (3,12) else 30):return result(None,'quarter(YTD)',sources,'NON_QUARTER_PERIOD')
        if period.month==3:
            value=amount(fact,key) if comparable(sources) else None
            return result(value,'Q1 = YTD(Q1)',sources,None if value is not None else 'CURRENT_FACT_UNKNOWN')
        prior=get(FLOW[key],previous_quarter(period));sources.append(prior)
        a,b=amount(fact,key),amount(prior,key)
        valid=comparable(sources) and a is not None and b is not None
        return result(a-b if valid else None,'YTD(current) - YTD(previous_quarter)',sources,None if valid else 'PRIOR_YTD_MISSING_OR_INCOMPARABLE')
    def ratio(numerator,denominator,formula,facts,percent=True,applicable=True):
        if not applicable:return result(None,formula,facts,'FINANCIAL_OR_UNKNOWN_INDUSTRY_NOT_APPLICABLE',unit='PERCENT' if percent else 'RATIO')
        same_period=len({f['report_period'] for f in facts if f})<=1
        same_update=len({f['reported_update_date'] for f in facts if f})<=1
        if not comparable(facts) or not same_period or not same_update or numerator is None or denominator is None:
            return result(None,formula,facts,'MISSING_OR_INCOMPARABLE_INPUT',unit='PERCENT' if percent else 'RATIO')
        if denominator<=0:return result(None,formula,facts,'NON_POSITIVE_DENOMINATOR',unit='PERCENT' if percent else 'RATIO')
        with localcontext() as context:
            context.prec=40;value=(numerator/denominator*(100 if percent else 1)).quantize(Decimal('.000001'))
        return result(value,formula,facts,unit='PERCENT' if percent else 'RATIO')
    periods=[]
    for stamp in sorted({p for _,p in current},reverse=True):
        period=date.fromisoformat(stamp);inc=get('INCOME',period);balance=get('BALANCE',period);cash=get('CASH_FLOW',period);output={}
        for key,statement in FLOW.items():
            fact=get(statement,period);value=amount(fact,key) if comparable([fact]) else None
            output[key]=result(value,'reported YTD '+key,[fact],None if value is not None else 'CURRENT_FACT_UNKNOWN')
            output['quarter_'+key]=quarter(key,period)
            quarters=[];cursor=period
            is_quarter=period.month in (3,6,9,12) and period.day==(31 if period.month in (3,12) else 30)
            if is_quarter:
                for _ in range(4):quarters.append(quarter(key,cursor));cursor=previous_quarter(cursor)
            sources=[current_fact for q in quarters for identifier in q['source_fact_ids'] for current_fact in current.values() if current_fact['fact_id']==identifier]
            valid=len(quarters)==4 and all(q['status']=='KNOWN' for q in quarters) and comparable(sources)
            output['ttm_'+key]=result(sum(Decimal(q['value']) for q in quarters) if valid else None,'sum(four consecutive comparable quarters)',sources,None if valid else 'FOUR_COMPARABLE_QUARTERS_REQUIRED')
        for key in ('revenue','parent_net_profit'):
            try:prior=get('INCOME',date(period.year-1,period.month,period.day))
            except ValueError:prior=None
            a,b=amount(inc,key),amount(prior,key);sources=[inc,prior]
            valid=comparable(sources) and a is not None and b is not None
            delta=a-b if valid else None
            yoy=ratio(delta,b,'(current_YTD - prior_year_YTD) / prior_year_YTD * 100',sources) if valid and b>0 else result(None,'(current_YTD - prior_year_YTD) / prior_year_YTD * 100',sources,'NON_POSITIVE_BASE' if valid else 'PRIOR_YEAR_MISSING_OR_INCOMPARABLE',unit='PERCENT')
            # A year-on-year comparison intentionally spans report dates/updates.
            if valid and b>0:
                with localcontext() as context:context.prec=40;yoy=result((delta/b*100).quantize(Decimal('.000001')),yoy['formula'],sources,unit='PERCENT')
            yoy['absolute_change']=None if delta is None else str(delta);output[key+'_yoy']=yoy
        total_revenue=amount(inc,'revenue');revenue=amount(inc,'operating_revenue');cost=amount(inc,'operating_cost');profit=amount(inc,'net_profit')
        # Existing semantic reference verifies the issuer's operating-income line.
        # A contradictory supplier subfield cannot inherit that proof silently.
        conflict=revenue is not None and total_revenue is not None and revenue!=total_revenue
        if conflict:revenue=None
        output['operating_revenue']=result(revenue if comparable([inc]) else None,'reported OPERATE_INCOME',[inc],'OPERATING_REVENUE_CONFLICT' if conflict else (None if revenue is not None and comparable([inc]) else 'MISSING_OR_INCOMPARABLE_INPUT'))
        output['gross_margin']=ratio(None if revenue is None or cost is None else revenue-cost,revenue,'(operating_revenue - operating_cost) / operating_revenue * 100',[inc],applicable=bool(inc and inc['original_fields'].get('ORG_TYPE')=='通用'))
        output['net_margin']=ratio(profit,revenue,'consolidated_net_profit / operating_revenue * 100',[inc])
        output['cash_profit_ratio']=ratio(amount(cash,'operating_cash_flow'),profit,'operating_cash_flow / consolidated_net_profit',[cash,inc],percent=False)
        output['debt_ratio']=ratio(amount(balance,'liabilities'),amount(balance,'assets'),'liabilities / assets * 100',[balance])
        periods.append({'report_period':stamp,'metrics':output})
    return {'instrument':instrument,'known_by':view['known_by'],'calculation_version':VERSION,'periods':periods,
        'source_versions':{f['fact_id']:{k:f.get(k) for k in ('statement','report_period','version','statement_scope','currency','unit','period_basis','raw_sha256','semantic_document','available_at')} for f in current.values()},
        'network_calls':0,'historical_pit_eligible':False,'system_usable':False,'capability':'NOT_GRANTED',
        'limitations':['CURRENT_OBSERVED_REVISIONS_ONLY','RATIOS_ARE_DESCRIPTIVE_NOT_TRADING_SIGNALS','UNKNOWN_PREDECESSORS_ARE_NOT_IMPUTED']}
