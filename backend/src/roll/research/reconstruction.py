"""Finite host admission for current-version 600362 price/volume reconstruction.

No client trust flags, no source-clock rewriting and no strict-PIT upgrade.
"""
import hashlib,json
from collections import Counter
from datetime import date,datetime,timedelta
from decimal import Decimal,ROUND_HALF_UP
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field
from typing import Literal

from roll.accounts.ledger import encode,now
from roll.market.baostock import rows as baostock_rows
from roll.research.corporate_actions import cash_rights_manifest,_holding_tax

REFERENCE=Path(__file__).parent/'reference/reconstruction'
VERSION='19-reconstructed-price-volume-v4'
CANDIDATE='PRICE_VOLUME_LOGIT_RECONSTRUCTED_V2'
FEATURES=['economic_return_5','economic_return_20','economic_return_volatility_20','log_volume_to_trailing20_mean']

class ReconstructionCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    status_run_id:str
    data_use:Literal['RECONSTRUCTED_RESEARCH','STRICT_HISTORICAL_AS_OF']='RECONSTRUCTED_RESEARCH'
    basis:str=Field(min_length=1,max_length=2000)

def fingerprint():
    return hashlib.sha256(encode({'code':hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
        'references':hashlib.sha256((REFERENCE/'sources.json').read_bytes()).hexdigest()}).encode()).hexdigest()

def dates_between(rules,first,last):
    current=date.fromisoformat(first);end=date.fromisoformat(last);result=[]
    while current<=end:
        state=rules.calendar('SSE',current)['is_trading_day']
        if state is None:raise HTTPException(409,'RECONSTRUCTION_CALENDAR_NOT_SUPPORTED')
        if state:result.append(current.isoformat())
        current+=timedelta(days=1)
    return result

def rule(evidence,identity,day):
    if (identity.get('exchange'),identity.get('board'),identity.get('instrument_type'))!=('SSE','MAIN','STOCK') or not '2016-12-01'<=day<='2023-12-31':
        raise ValueError('RECONSTRUCTION_RULE_SCOPE_UNSUPPORTED')
    manifest=json.loads((REFERENCE/'sources.json').read_text(encoding='utf-8'))
    content=(REFERENCE/manifest['rule_file']).read_bytes()
    if hashlib.sha256(content).hexdigest()!=manifest['rule_source']['sha256']:raise ValueError('RECONSTRUCTION_RULE_SOURCE_CORRUPT')
    archive=evidence.archive(content,'RECONSTRUCTED_DAILY_RULE_SOURCE',**manifest['rule_source'])
    return {'rule_id':'SSE-MAIN-RECONSTRUCTED-DAILY-2017-2023','implementation_status':'ADAPTED',
        'buy_minimum':'100','buy_increment':'100','price_tick_yuan':'0.01','normal_price_limit_percent':'10',
        'resale':'NEXT_TRADING_DAY','source':archive,'provisions':['3.1.4','3.3.8','3.3.11','3.4.13'],
        'rule_scope':'RECONSTRUCTED_RESEARCH_NORMAL_SSE_MAIN_DAILY_ONLY','close_time':'15:00:00',
        'limitations':['Daily open/close scenario, not observed fills or auction path','No newly listed, relisted, ST, suspended or unknown-special-state execution'],
        'closing_price_formation':'CALL_AUCTION' if day>='2018-08-20' else 'CONTINUOUS_CLOSE'}

def verify_sources(evidence,dataset):
    if dataset['source_evidence_kind']!='REAL_ACQUISITION' or dataset['scope']['instruments']!=['SSE:600362']:
        raise HTTPException(409,'REAL_SINGLE_NAME_RECONSTRUCTION_SOURCE_REQUIRED')
    if dataset['coverage']['first_date']<'2015-01-01' or dataset['coverage']['last_date']>'2023-12-31':
        raise HTTPException(409,'SOURCE_CONTAINER_OUTSIDE_FINITE_RECONSTRUCTION_SCOPE')
    snap=evidence.get('market_evidence_snapshots',dataset['source_snapshot_id'])
    if snap.get('external_source_view')!='SRC-WIND':raise HTTPException(409,'FIXED_WIND_PRIMARY_REQUIRED_NO_OUTCOME_SOURCE_SELECTION')
    for archive in snap['archives']+[snap['parquet']]:evidence.raw(archive['sha256'])
    facts=[json.loads(r['payload']) for r in pq.read_table(evidence.raw(snap['parquet']['sha256'])).to_pylist()]
    if facts!=snap['facts']:raise HTTPException(409,'SOURCE_PARQUET_SNAPSHOT_MISMATCH')
    daily=[f for f in facts if f['group']=='DAILY']
    if len({f['trade_date'] for f in daily})!=len(daily):raise HTTPException(409,'CONFLICTING_DUPLICATE_SOURCE_DATE')
    originals={}
    for f in daily:
        if f.get('instrument')!='SSE:600362' or f.get('adjustment')!='RAW' or f.get('volume_unit')!='SHARE' or f.get('currency')!='CNY' or f.get('price_unit')!='CNY_PER_SHARE':
            raise HTTPException(409,'SOURCE_IDENTITY_OR_UNITS_INVALID')
        sha=f['original_evidence_hashes'][0]
        if sha not in originals:
            raw=json.loads(evidence.raw(sha).read_text(encoding='utf-8'))['data']
            if raw['unit'].get('VOLUME 单位：')!='股' or raw['unit'].get('TURNOVER 单位：')!='元':raise HTTPException(409,'RAW_UNIT_EVIDENCE_INVALID')
            originals[sha]={r[0][:10]:r for r in raw['rows']}
        source=originals[sha][f['trade_date']]
        for field,index in [('open',1),('close',2),('high',3),('low',4),('amount_yuan',5),('volume_shares',6)]:
            if f[field] is None or source[index] is None:
                if f[field]!=source[index]:raise HTTPException(409,'NORMALIZED_RAW_VALUE_MISMATCH')
            elif Decimal(str(f[field]))!=Decimal(str(source[index])):raise HTTPException(409,'NORMALIZED_RAW_VALUE_MISMATCH')
    return snap,facts

def reconstruct(registry,source_id,command):
    if command.data_use=='STRICT_HISTORICAL_AS_OF':raise HTTPException(409,'STRICT_HISTORICAL_AS_OF_EVIDENCE_NOT_PROVEN')
    evidence=registry.evidence;source=registry.dataset(source_id)
    run=evidence.get('retrieval_runs',command.status_run_id)
    request=evidence.get('data_requests',run['request_id'])
    if request['instruments']!=['SSE:600362'] or not '2016-12-01'<=request['start_date']<=request['end_date']<='2023-12-31':
        raise HTTPException(409,'STATUS_CONTAINER_OUTSIDE_FINITE_RECONSTRUCTION_SCOPE')
    # Check protected ranges from metadata before opening any source container.
    for p in registry.protocols():
        if not p.get('dataset_id'):continue
        d=registry.dataset(p['dataset_id']);sealed=d['partitions'].get('SEALED',{})
        if 'SSE:600362' in d['scope']['instruments'] and sealed.get('first_date') and any(sealed['first_date']<=last and sealed['last_date']>=first for first,last in [(source['coverage']['first_date'],source['coverage']['last_date']),(request['start_date'],request['end_date'])]):
            raise HTTPException(403,'PROTECTED_SEALED_RANGE_CANNOT_BE_REDOWNLOADED_OR_RECONSTRUCTED')
    snap,facts=verify_sources(evidence,source)
    status_snap=evidence.get('market_evidence_snapshots',run['snapshot_id'])
    if status_snap['evidence_kind']!='REAL_ACQUISITION':raise HTTPException(409,'REAL_STATUS_SOURCE_REQUIRED')
    captured=next((a for a in status_snap['archives'] if a.get('source_id')=='baostock-daily' and a.get('decoded_hash')),None)
    if not captured:raise HTTPException(409,'BAOSTOCK_RAW_STATUS_CAPTURE_REQUIRED')
    evidence.raw(captured['sha256'])
    decoded=json.loads(evidence.raw(captured['decoded_hash']).read_text(encoding='utf-8'))
    status_rows=baostock_rows(decoded)
    if any(r['code']!='sh.600362' or r['adjustflag']!='3' for r in status_rows):raise HTTPException(409,'WRONG_STATUS_SECURITY_OR_ADJUSTMENT')
    if len({r['date'] for r in status_rows})!=len(status_rows):raise HTTPException(409,'CONFLICTING_STATUS_DUPLICATES')
    statuses={r['date']:r for r in status_rows}
    manifest=json.loads((REFERENCE/'sources.json').read_text(encoding='utf-8'))
    rights=cash_rights_manifest();audits=[]
    for item in manifest['share_structure_audits']:
        path=evidence.raw(item['sha256'])
        if path.stat().st_size!=item['bytes']:raise HTTPException(409,'EQUITY_AUDIT_SOURCE_CORRUPT')
        audits.append(item)
    events=[{k:e[k] for k in ['record_date','ex_date','cash_payment_date','gross_cash_yuan_per_eligible_share','source']} for e in rights['events'] if '2016-12-01'<=e['ex_date']<='2023-12-31']
    vendor={f['ex_date']:f for f in facts if f['group']=='ADJUSTMENTS'}
    if set(vendor)!=set(e['ex_date'] for e in events):raise HTTPException(409,'UNRESOLVED_CASH_EVENT_INVENTORY_CONFLICT')
    for event in events:
        if Decimal(vendor[event['ex_date']]['gross_cash_per_eligible_share'])!=Decimal(event['gross_cash_yuan_per_eligible_share']):raise HTTPException(409,'UNRESOLVED_CASH_AMOUNT_CONFLICT')
    bars={f['trade_date']:f for f in facts if f['group'] in {'DAILY','SUSPENSION_PLACEHOLDER'}}
    alternate={f['trade_date']:f for f in facts if f['group']=='ALTERNATE_SOURCE_DAILY'}
    calendar=dates_between(evidence.market.rules,'2016-12-01','2023-12-29');clean=[];quality=[]
    for day in calendar:
        original=bars.get(day);state=statuses.get(day);reasons=[];uncertainty=[]
        if original is None:reasons.append('MISSING_BAR')
        if state is None or state.get('tradestatus') not in {'0','1'} or state.get('isST') not in {'0','1'}:reasons.append('STATUS_UNKNOWN')
        elif state['isST']=='1':reasons.append('SPECIAL_RISK_WARNING_NOT_SUPPORTED')
        if original:
            row={**original,'original_values':{k:original.get(k) for k in ['open','high','low','close','volume_shares','amount_yuan']},'original_errors':original.get('errors',[])}
            try:
                if state and state['tradestatus']=='0':raise StopIteration
                o,h,l,c=[Decimal(row[k]) for k in ['open','high','low','close']]
                if not 0<l<=min(o,c)<=max(o,c)<=h:reasons.append('INCONSISTENT_OHLC')
                if state and state['tradestatus']=='1':
                    if row['volume_shares'] is None or Decimal(row['volume_shares'])<=0:reasons.append('NONPOSITIVE_OR_UNKNOWN_VOLUME')
                    if any(abs(Decimal(row[k])-Decimal(state[k]))>Decimal('.01') for k in ['open','high','low','close']):reasons.append('UNRESOLVED_BAOSTOCK_PRICE_CONFLICT')
                if state and state['tradestatus']=='0':uncertainty.append('REPORTED_SUSPENSION_NOT_TRADED')
            except StopIteration:uncertainty.append('REPORTED_SUSPENSION_NOT_TRADED')
            except (KeyError,TypeError,ArithmeticError):reasons.append('INVALID_REQUIRED_FIELDS')
            other=alternate.get(day)
            if other:
                if any(Decimal(other[k])!=Decimal(row[k]) for k in ['open','high','low','close']):reasons.append('UNRESOLVED_SOHU_PRICE_CONFLICT')
                if other.get('volume_shares') and row.get('volume_shares') and abs(Decimal(other['volume_shares'])-Decimal(row['volume_shares']))>100:reasons.append('UNRESOLVED_VOLUME_CONFLICT')
                if other.get('amount_yuan') and row.get('amount_yuan') and abs(Decimal(other['amount_yuan'])-Decimal(row['amount_yuan']))>100:uncertainty.append('OPTIONAL_AMOUNT_SOURCE_DIFFERENCE_NOT_USED')
            if row.get('amount_yuan') is None:uncertainty.append('OPTIONAL_AMOUNT_MISSING_NOT_USED')
        else:
            row={'instrument':'SSE:600362','trade_date':day,'adjustment':'RAW','volume_unit':'SHARE','raw_hash':captured['sha256'],
                'available_at':captured['received_at'],'received_at':captured['received_at'],'completion_state':'MISSING','open':None,'high':None,'low':None,'close':None,'volume_shares':None,'amount_yuan':None}
        row.update(data_use='RECONSTRUCTED_RESEARCH',research_completion_available_at=day+'T15:05:00+08:00',
            research_availability_basis='ASSUMED_HISTORICAL_DAILY_COMPLETE_1505_NEXT_OPEN_CONSUMPTION; NOT_ACTUAL_SOURCE_PUBLICATION',
            errors=sorted(set(reasons)),uncertainty=uncertainty,cash_events_effective=[e for e in events if e['ex_date']==day],
            execution_evidence={'state':'REPORTED_NORMAL_RECONSTRUCTED' if state and state['tradestatus']=='1' and state['isST']=='0' else 'REPORTED_SUSPENDED_RECONSTRUCTED' if state and state['tradestatus']=='0' else 'UNKNOWN',
                'company_actions':'SOURCE_BOUND_CASH_AND_ANNUAL_SHARE_AUDIT','status_raw_hash':captured['sha256'],'reported_is_st':state.get('isST') if state else None})
        clean.append(row);quality.append({'instrument':'SSE:600362','date':day,'fields':row['original_values'] if original else {},'basic_pass':not reasons,'exclusions':row['errors'],'uncertainty':uncertainty})
    cal_dates=[d for d in calendar if d>='2022-01-01'];first_cal=cal_dates[20]
    intervals={'DEVELOPMENT':('2017-01-03','2021-12-31'),'CALIBRATION':(first_cal,'2023-12-29')}
    parts={}
    for name,(first,last) in intervals.items():
        start=calendar.index(first);end=calendar.index(last)+1;context=start-20
        payload=clean[context:end];buffer=BytesIO();pq.write_table(pa.Table.from_pylist([{'payload':encode(f)} for f in payload]),buffer)
        artifact=evidence.archive(buffer.getvalue(),'RESEARCH_PARTITION',extension='parquet',partition=name,research_namespace='HISTORICAL')
        parts[name]={'state':'HOST_FILTERED','rows':end-start,'context_rows':20,'first_date':first,'last_date':last,'context_first_date':calendar[context],'artifact':artifact,'access':'DEVELOPMENT_OR_CALIBRATION_ONLY'}
    parts['SEALED']={'state':'NOT_ALLOCATED','rows':0,'reason':'No claim of unused final evidence; prior exposure retained'}
    clean_archive=evidence.archive(encode(clean).encode(),'RECONSTRUCTED_CLEAN_VERSION',research_namespace='HISTORICAL')
    assumptions={'version':VERSION,'data_use':'RECONSTRUCTED_RESEARCH','daily_clock':'15:05 Asia/Shanghai each historical session, assumed complete for NEXT_OPEN research',
        'actual_receipt_rewritten':False,'historical_source_publication':'UNKNOWN_RETAINED','status':'BaoStock actual reported trading/ST flags, limited annual equity and cash audit; not complete intraday state',
        'action_coverage':'SOURCE_BOUND_CASH_PLUS_ANNUAL_UNCHANGED_SHARE_AUDIT_WITH_RESIDUAL_REVISION_RISK','equity_sources':audits,'cash_events':events,
        'feature_definition':'Gross cash economic return chain on/before observation; no future effective adjustment or current qfq',
        'commission':'UNKNOWN_ACTUAL; frozen3bp research scenario/min5CNY','slippage':'frozen5bp per-side scenario; not observed',
        'scope':['SSE:600362','2016-12-01','2023-12-29'],'no_financial_news_or_sentiment_inputs':True}
    report={'version':VERSION,'instrument':'SSE:600362','primary_source':'SRC-WIND','cross_checks':['SRC-SOHU','baostock-daily'],
        'source_raw_rows':len([f for f in facts if f['group'] in {'DAILY','SUSPENSION_PLACEHOLDER'}]),'deduplicated_dates':len(bars),
        'study_context_rows':len(clean),'basic_quality_pass':sum(not r['errors'] for r in clean),'suspended_dates':[r['trade_date'] for r in clean if 'SUSPENDED' in r['execution_evidence']['state']],
        'exclusion_counts':dict(Counter(e for r in quality for e in r['exclusions'])),'uncertainty_counts':dict(Counter(e for r in quality for e in r['uncertainty'])),
        'per_date_fields':quality,'windows':parts,'window_selection':'fixed annual2017-2021 DEV /20-session embargo /remaining2022-2023 CAL; selected from coverage/rules before labels or candidate performance',
        'missing_status_dates':[d for d in calendar if d not in statuses],'source_versions_are_not_independent_upstreams':True}
    report_archive=evidence.archive(encode(report).encode(),'RECONSTRUCTED_QUALITY_REPORT',research_namespace='HISTORICAL')
    assumptions_archive=evidence.archive(encode(assumptions).encode(),'RECONSTRUCTED_RESEARCH_ASSUMPTIONS',research_namespace='HISTORICAL')
    value={**source,'dataset_id':str(uuid4()),'registered_at':now(),'basis':command.basis,'parent_dataset_id':source_id,
        'source_origin':'HOST_RECONSTRUCTED_RESEARCH','data_use':'RECONSTRUCTED_RESEARCH','reconstruction_version':VERSION,
        'status_run_id':command.status_run_id,'partitions':parts,'clean_archive':clean_archive,'quality_report_archive':report_archive,
        'research_assumptions':assumptions,'assumptions_archive':assumptions_archive,'reconstruction_code_fingerprint':fingerprint(),
        'scope':{**source['scope'],'data_use':'RECONSTRUCTED_RESEARCH'},'coverage':{**source['coverage'],'first_date':calendar[0],'last_date':calendar[-1],'session_count':len(clean)},
        'training_readiness':{'state':'INPUTS_ADMITTED_SUPPORT_PENDING','blockers':[],'basis':'Host raw/identity/unit/calendar/local-conflict checks plus explicit reconstructed-purpose assumptions; labels/support not yet computed'},
        'partition_basis':report['window_selection'],'limitations':sorted(set(source['limitations']+manifest['limitations']+['RECONSTRUCTED_NOT_STRICT_PIT','CALIBRATION_EFFECTIVENESS_UNVALIDATED'])),
        'original_archives':source['original_archives']+status_snap['archives']+[status_snap['parquet']],
        'prior_exposure':source['prior_exposure']+'; RECONSTRUCTION_IS_NOT_NEW_UNSEEN_EVIDENCE'}
    value['data_fingerprint']=hashlib.sha256(encode({'source':source['data_fingerprint'],'status':captured,'clean':clean_archive['sha256'],'assumptions':assumptions_archive['sha256'],'parts':parts,'code':fingerprint()}).encode()).hexdigest()
    with registry.ledger.connection() as db:db.execute('INSERT INTO research_datasets VALUES(?,?)',(value['dataset_id'],encode(value)))
    return value

def cash_economics(events,entry,exit,quantity,cutoff):
    """Horizon CLOSE disposal owns record-day shares; preserve paid/receivable distinction."""
    results=[];net=Decimal(0)
    for event in events:
        if not entry<=event['record_date']<=exit:continue
        if datetime.fromisoformat(event['source']['received_at'])>datetime.fromisoformat(cutoff):raise ValueError('CASH_SOURCE_NOT_AVAILABLE_TO_RECONSTRUCTION_CONSUMER')
        rate=_holding_tax(date.fromisoformat(entry),date.fromisoformat(exit),True)
        if rate is None:raise ValueError('TAX_CALENDAR_ANNIVERSARY_UNDEFINED')
        gross=Decimal(event['gross_cash_yuan_per_eligible_share'])*quantity;tax=(gross*rate).quantize(Decimal('.01'),rounding=ROUND_HALF_UP);amount=gross-tax;net+=amount
        results.append({**event,'gross_entitlement_yuan':str(gross),'final_tax_rate':str(rate),'final_tax_yuan':str(tax),'net_entitlement_yuan':str(amount),
            'payment_basis':'RECEIVABLE_AT_EXIT' if event['cash_payment_date']>exit else 'PAYMENT_DATE_REPORTED_NOT_OBSERVED_ACCOUNT_RECEIPT'})
    return {'net_economic_entitlement_yuan':str(net),'events':results,'account_authority':'NONE','coverage':'LIMITED_RECONSTRUCTED_SOURCE_AUDIT_NOT_STRICT_PIT'}
