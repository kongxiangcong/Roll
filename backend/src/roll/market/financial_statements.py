from roll.market.observation_symbols import symbols
"""Three-statement observations sharing the income acquisition and immutable versions."""
from datetime import date,datetime
from decimal import Decimal
import hashlib,json
from roll.accounts.ledger import now
from roll.market.financial_income import REFERENCE,SOURCE,decimal_text
from roll.market.akshare_financial_process import SDK_VERSION

FIELDS={'BALANCE':{'assets':'TOTAL_ASSETS','liabilities':'TOTAL_LIABILITIES','equity':'TOTAL_EQUITY'},
        'CASH_FLOW':{'operating_cash_flow':'NETCASH_OPERATE','investing_cash_flow':'NETCASH_INVEST','financing_cash_flow':'NETCASH_FINANCE','net_cash_change':'CCE_ADD'}}
ROLES={'BALANCE':'zcfzbAjaxNew','CASH_FLOW':'xjllbAjaxNew'}


def unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('FINANCIAL_DUPLICATED_COLUMN:'+key)
        result[key]=value
    return result


def normalize(service,instrument,run,manifest,captures):
    proofs=json.loads((REFERENCE/'statements-manifest.json').read_text(encoding='utf-8'))['periods'];facts=[]
    for statement,fields in FIELDS.items():
        entities=[i for i,c in enumerate(captures) if c.get('role')==ROLES[statement]]
        if len(entities)!=1:raise ValueError('FINANCIAL_SINGLE_STATEMENT_ENTITY_REQUIRED:'+statement)
        original=run['originals'][entities[0]]
        rows=json.loads(service.evidence.raw(original['sha256']).read_bytes(),parse_float=Decimal,object_pairs_hook=unique_object).get('data')
        if not isinstance(rows,list) or not 1<=len(rows)<=5:raise ValueError('FINANCIAL_ROW_BUDGET_OR_SCHEMA')
        selected=manifest.get('date_selections',{}).get(statement,[])
        if not selected or len(set(selected))!=len(rows):raise ValueError('FINANCIAL_PERIOD_SELECTION_MISMATCH')
        seen=set()
        for row in rows:
            if row.get('SECUCODE')!=symbols(instrument)[2]:raise ValueError('FINANCIAL_ROW_INSTRUMENT_MISMATCH')
            period=str(row.get('REPORT_DATE',''))[:10];date.fromisoformat(period)
            if period not in selected or period in seen:raise ValueError('FINANCIAL_PERIOD_DUPLICATED_OR_UNREQUESTED')
            seen.add(period);values={name:decimal_text(row.get(field)) for name,field in fields.items()}
            proof=next((p for p in proofs if instrument=='SSE:600362' and p['statement']==statement and p['report_period']==period and
                p['reported_update_date']==str(row.get('UPDATE_DATE',''))[:10] and (p['values']['assets']==values['assets'] if statement=='BALANCE' else p['values']==values) and row.get('CURRENCY')=='CNY'),None)
            document=None;available=now()
            if proof:
                body=(REFERENCE/proof['filename']).read_bytes()
                if hashlib.sha256(body).hexdigest()!=proof['sha256']:raise ValueError('FINANCIAL_SEMANTIC_DOCUMENT_CORRUPT')
                document=service.evidence.archive(body,'FINANCIAL_STATEMENT_SEMANTICS',extension='pdf',source_url=proof['url'],received_at=proof['received_at'],page=proof['page'],reference_basis=proof['basis'])
                available=max(available,proof['received_at'],key=datetime.fromisoformat)
            facts.append({'instrument':instrument,'statement':statement,'report_period':period,
                'reported_publication_date':row.get('NOTICE_DATE'),'reported_update_date':row.get('UPDATE_DATE'),
                'publication_precision':'DATE' if row.get('NOTICE_DATE') else 'UNKNOWN',
                'first_received_at':original['received_at'],'available_at':max(available,original['received_at'],key=datetime.fromisoformat),
                'currency':row.get('CURRENCY') if row.get('CURRENCY')=='CNY' else None,
                'unit':'YUAN' if proof else 'UNKNOWN','statement_scope':'CONSOLIDATED' if proof else 'UNKNOWN',
                'period_basis':('POINT_IN_TIME' if statement=='BALANCE' else 'YEAR_TO_DATE') if proof else 'UNKNOWN',
                'rounding_quantum':proof['rounding_quantum'] if proof else None,'semantic_document':document,
                'values':values,'original_fields':json.loads(json.dumps(row,default=str)),
                'raw_sha256':original['sha256'],'source_id':SOURCE,'sdk_version':SDK_VERSION,'evidence_kind':run['evidence_kind'],
                'historical_pit_eligible':False,'system_usable':False,
                'gaps':['HISTORICAL_REVISION_AVAILABILITY_UNPROVEN']+([] if proof else ['STATEMENT_SCOPE_AND_UNIT_UNVERIFIED'])})
    return facts


def joined(income,supplement,instrument,cutoff=None):
    primary=income.listing(instrument,cutoff)
    extra=supplement.listing(instrument,datetime.fromisoformat(primary['known_by']),active_current=cutoff is None)
    all_facts=primary['facts']+extra['facts'];latest={}
    for f in all_facts:
        stream=(f['statement'],f['report_period'],f['source_id'])
        if stream not in latest or f['version']>latest[stream]['version']:latest[stream]=f
    groups={}
    for f in latest.values():
        valid=all(f.get(k) not in (None,'UNKNOWN') for k in ('statement_scope','currency','unit','period_basis'))
        valid=valid and f['period_basis']==('POINT_IN_TIME' if f['statement']=='BALANCE' else 'YEAR_TO_DATE')
        key=(f['instrument'],f['report_period'],f['statement_scope'],f['currency'],f['unit'],f['source_id'],str(f['reported_update_date'])[:10],f['evidence_kind'],None if valid else f['fact_id'])
        if key not in groups:groups[key]={'report_period':f['report_period'],'statement_scope':f['statement_scope'],'currency':f['currency'],'unit':f['unit'],'reported_update_date':f['reported_update_date'],'facts':{},'versions':{},'comparable':valid}
        group=groups[key];group['facts'][f['statement']]=f;group['versions'][f['statement']]=f['fact_id']
    for group in groups.values():
        group['missing']=[s for s in ('INCOME','BALANCE','CASH_FLOW') if s not in group['facts']]
        group['status']='UNVERIFIED_SCOPE' if not group['comparable'] else ('MISSING_STATEMENTS' if group['missing'] else 'MATCHED')
        balance=group['facts'].get('BALANCE');check={'status':'UNKNOWN','difference':None,'tolerance':None}
        if balance and balance.get('rounding_quantum') and all(v is not None for v in balance['values'].values()):
            values=balance['values'];difference=Decimal(values['assets'])-Decimal(values['liabilities'])-Decimal(values['equity']);tolerance=Decimal(balance['rounding_quantum'])*Decimal('1.5')
            check={'status':'WITHIN_ROUNDING' if abs(difference)<=tolerance else 'REQUIRES_REVIEW','difference':str(difference),'tolerance':str(tolerance)}
        if group['status']=='MATCHED' and any(v is None for f in group['facts'].values() for v in f['values'].values()):group['status']='INCOMPLETE_VALUES'
        group['balance_check']=check
    return {'instrument':instrument,'known_by':primary['known_by'],'groups':sorted(groups.values(),key=lambda g:g['report_period'],reverse=True),
        'facts':all_facts,'runs':primary['runs']+extra['runs'],'active_run_ids':primary['active_run_ids']+extra['active_run_ids'],
        'system_usable':False,'historical_pit_eligible':False,'network_calls':0,'capability':'NOT_GRANTED'}
