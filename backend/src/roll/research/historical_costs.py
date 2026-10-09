"""Evidence-bound SSE A-share statutory costs; broker commission is a scenario."""
import hashlib
import json
from datetime import date
from pathlib import Path

from roll.accounts.ledger import encode


REFERENCE=Path(__file__).parent/'reference'
MANIFEST=REFERENCE/'historical-cost-sources.json'


def sources():
    items=json.loads(MANIFEST.read_text(encoding='utf-8'))
    for item in items:
        raw=(REFERENCE/item['file']).read_bytes()
        if len(raw)!=item['bytes'] or hashlib.sha256(raw).hexdigest()!=item['sha256']:
            raise ValueError('HISTORICAL_COST_SOURCE_CORRUPT:'+item['id'])
    return {item['id']:item for item in items}


def schedule_fingerprint():
    # Both the effective-date logic and the original authority bytes are dependencies.
    originals={key:value['sha256'] for key,value in sources().items()}
    return hashlib.sha256(encode({'code':hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
        'manifest':hashlib.sha256(MANIFEST.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),'originals':originals}).encode()).hexdigest()


def resolve(trade_date,side,identity):
    result={'trade_date':trade_date,'side':side,'status':'UNKNOWN','reasons':[],
        'stamp_sell_rate':None,'stamp_applied_rate':None,'transfer_each_side_rate':None,
        'transfer_basis':None,'stamp_source_ids':[],'transfer_source_ids':[]}
    if not trade_date:
        result['reasons']=['HISTORICAL_COST_TRADE_DATE_UNKNOWN'];return result
    day=date.fromisoformat(trade_date)
    if (identity.get('exchange'),identity.get('board'),identity.get('instrument_type'))!=('SSE','MAIN','STOCK'):
        result['reasons']=['HISTORICAL_COST_SCOPE_UNSUPPORTED'];return result
    if day<date(2008,9,19):result['reasons'].append('HISTORICAL_STAMP_TAX_PERIOD_UNPROVEN')
    else:
        rate='0.001' if day<date(2023,8,28) else '0.0005'
        result.update(stamp_sell_rate=rate,stamp_applied_rate=rate if side=='SELL' else '0',
            stamp_source_ids=['stamp-2008']+(['stamp-2023'] if day>=date(2023,8,28) else []))
    if day<date(2015,8,1):
        result['reasons'].append('HISTORICAL_TRANSFER_FACE_VALUE_START_AND_MINIMUM_UNPROVEN')
        result.update(transfer_basis='UNKNOWN_PRE_2015_FACE_VALUE_PERIOD',
            prior_reported_transfer={'basis':'SHARE_FACE_VALUE','rate':'0.0003','minimum_yuan':None,
                'period_start':None,'source_id':'2015-fee-change'})
    elif date(2026,7,6)<=day<=date(2026,12,31):
        result.update(transfer_each_side_rate='0.00001',transfer_basis='TRADED_CONSIDERATION',
            transfer_source_ids=['transfer-2022','current-sse-charge-2026'],status='CURRENT_DISPLAY_SCENARIO',
            current_tariff_basis='SSE2026 current display; no exact effective day or intervening historical stability claim',
            rule_compatibility_range=['2026-07-06','2026-12-31'])
    elif day>=date(2022,4,29):
        result.update(transfer_each_side_rate='0.00001',transfer_basis='TRADED_CONSIDERATION',
            transfer_source_ids=['transfer-2022'])
    else:
        result.update(transfer_each_side_rate='0.00002',transfer_basis='TRADED_CONSIDERATION',
            transfer_source_ids=['2015-fee-change'])
    if not result['reasons'] and result['status']!='CURRENT_DISPLAY_SCENARIO':result['status']='VERIFIED_STATUTORY_SCHEDULE'
    return result


def freeze(evidence,identity,entry_date,exit_date,costs):
    verified=sources()
    buy=resolve(entry_date,'BUY',identity);sell=resolve(exit_date,'SELL',identity)
    used={key for item in [buy,sell] for field in ['stamp_source_ids','transfer_source_ids'] for key in item[field]}
    if any(item.get('prior_reported_transfer') for item in [buy,sell]):used.add('2015-fee-change')
    archives=[]
    for key in sorted(used):
        item=verified[key]
        archive=evidence.archive((REFERENCE/item['file']).read_bytes(),'HISTORICAL_STATUTORY_COST_SOURCE',extension='html',
            research_namespace='HISTORICAL',source_id=key,source_url=item['url'],published_date=item['publication_date'],
            publication_precision=item['publication_precision'],original_received_at=item['received_at'])
        archives.append({**item,'archive':archive})
    allowed={'VERIFIED_STATUTORY_SCHEDULE','CURRENT_DISPLAY_SCENARIO'}
    state='UNKNOWN' if any(item['status'] not in allowed for item in [buy,sell]) else ('CURRENT_DISPLAY_SCENARIO' if any(item['status']=='CURRENT_DISPLAY_SCENARIO' for item in [buy,sell]) else 'VERIFIED_STATUTORY_SCHEDULE')
    return {'version':'19-historical-costs-v1','BUY':buy,'SELL':sell,'sources':archives,
        'schedule_sha256':schedule_fingerprint(),'status':state,
        'commission_basis':'PREREGISTERED_SCENARIO_INCLUDES_REGULATORY_FEES',
        'commission_scenario_rate':costs['commission_scenario_rate'],'minimum_commission_yuan':costs['minimum_commission_yuan'],
        'broker_actual_commission':'UNKNOWN','extra_regulatory_charge':'0',
        'rounding':'PREREGISTERED_DECIMAL_YUAN_CENTS; not an observed broker charge',
        'historical_data_eligibility':'NOT_GRANTED; statutory rates do not prove PIT/status/actions or actual fills'}
