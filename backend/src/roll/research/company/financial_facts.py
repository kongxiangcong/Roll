"""Exact mappings of already normalized financial fields; no inferred economics."""
import json
from uuid import uuid4
from decimal import Decimal, InvalidOperation

from roll.accounts.ledger import encode
from .models import FactCommand
from .service import fingerprint, record, verified

FIELDS = {
    'INCOME': {'revenue':'TOTAL_OPERATE_INCOME','net_profit':'NETPROFIT','parent_net_profit':'PARENT_NETPROFIT'},
    'BALANCE': {'assets':'TOTAL_ASSETS','liabilities':'TOTAL_LIABILITIES','equity':'TOTAL_EQUITY'},
    'CASH_FLOW': {'operating_cash_flow':'NETCASH_OPERATE','investing_cash_flow':'NETCASH_INVEST',
                  'financing_cash_flow':'NETCASH_FINANCE','net_cash_change':'CCE_ADD'},
}


def initialize(research):
    with research.transaction() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS company_research_financial_adaptations(
            adaptation_id TEXT PRIMARY KEY,company_id TEXT NOT NULL,material_id TEXT NOT NULL,
            attempt_key TEXT NOT NULL,value TEXT NOT NULL,UNIQUE(company_id,material_id,attempt_key))''')


def pending_materials(research, company_id, retry_rejected=False):
    with research.ledger.connection() as db:
        query='''SELECT material_id FROM company_research_materials m WHERE company_id=?
            AND json_extract(value,'$.upstream.source_type')='FINANCIAL_FACT'
            AND (NOT EXISTS(SELECT 1 FROM company_research_financial_adaptations a WHERE a.material_id=m.material_id)
                OR (? AND json_array_length((SELECT json_extract(a.value,'$.gaps') FROM company_research_financial_adaptations a
                    WHERE a.material_id=m.material_id ORDER BY rowid DESC LIMIT 1))>0))'''
        count=db.execute('SELECT count(*) FROM ('+query+')',(company_id,retry_rejected)).fetchone()[0]
        ids=[r[0] for r in db.execute(query+' ORDER BY rowid LIMIT 20',(company_id,retry_rejected))]
    return ids,count


def adaptation_state(research, company_id):
    _,remaining=pending_materials(research,company_id)
    with research.ledger.connection() as db:
        selection='''SELECT value FROM company_research_financial_adaptations a WHERE company_id=?
            AND rowid=(SELECT max(b.rowid) FROM company_research_financial_adaptations b WHERE b.material_id=a.material_id)
            AND json_array_length(json_extract(value,'$.gaps'))>0'''
        unresolved=db.execute('SELECT count(*) FROM ('+selection+')',(company_id,)).fetchone()[0]
        examples=[dict(material_id=saved['material_id'],gaps=saved['gaps']) for (raw,) in db.execute(selection+' LIMIT 20',(company_id,)) for saved in [verified(json.loads(raw))]]
    return dict(remaining_material_count=remaining,unresolved_material_count=unresolved,examples=examples,
        meaning='规范字段适配独立于材料导入；旧材料可回填。原口径/缺值问题保留，明确修正后可显式重查，不以采集日补期间。')


def adapt_financial_fields(research, company_id, material_ids, attempt_key):
    facts, gaps = [], []
    for material_id in dict.fromkeys(material_ids):
        material = research.material(material_id, company_id)
        upstream = material.get('upstream') or {}
        if upstream.get('source_type') != 'FINANCIAL_FACT':
            continue
        with research.ledger.connection() as db:
            prior=db.execute('SELECT value FROM company_research_financial_adaptations WHERE company_id=? AND material_id=? AND attempt_key=?',
                (company_id,material_id,attempt_key)).fetchone()
        if prior:
            saved=verified(json.loads(prior[0]));facts.extend(saved['fact_version_ids']);gaps.extend(saved['gaps'])
            continue
        first_fact,first_gap=len(facts),len(gaps)
        try:
            with research.ledger.connection() as db:
                row = db.execute('SELECT value FROM financial_income_facts WHERE id=?', (upstream['record_id'],)).fetchone()
            source = json.loads(row[0]) if row else None
            if not source or fingerprint(source) != upstream['source_record_sha256']:
                raise ValueError('FINANCIAL_SOURCE_VERSION_UNAVAILABLE')
            statement = source.get('statement')
            required_period = 'POINT_IN_TIME' if statement=='BALANCE' else 'YEAR_TO_DATE'
            if statement not in FIELDS or source.get('unit')!='YUAN' or source.get('currency')!='CNY' or source.get('statement_scope')!='CONSOLIDATED' or source.get('period_basis')!=required_period or not material['period_start'] or not material['period_end']:
                raise ValueError('FINANCIAL_BASIS_UNVERIFIED_NO_FACT_INFERENCE')
            proof = source.get('semantic_document')
            if not proof or not proof.get('sha256'):
                raise ValueError('FINANCIAL_SEMANTIC_PROOF_MISSING')
            research.evidence.raw(proof['sha256'])
            raw = json.loads(research.material_bytes(material_id),parse_float=Decimal)
            exchange,code = source['instrument'].split(':')
            qualified = code + {'SSE':'.SH','SZSE':'.SZ'}[exchange]
            matching = [(index,row) for index,row in enumerate(raw.get('data',[]))
                if row.get('SECUCODE')==qualified and str(row.get('REPORT_DATE',''))[:10]==source['report_period']]
            if len(matching)!=1:
                raise ValueError('FINANCIAL_ORIGINAL_ROW_NOT_UNIQUE')
            index, original = matching[0]
            for metric, field in FIELDS[statement].items():
                value = source.get('values',{}).get(metric)
                if value is None or original.get(field) is None:
                    gaps.append(dict(material_id=material_id,metric=metric,code='FINANCIAL_VALUE_MISSING'))
                    continue
                try:
                    expected, observed = Decimal(str(value)), Decimal(str(original[field]))
                    if not expected.is_finite() or not observed.is_finite() or expected!=observed:
                        raise InvalidOperation()
                except (InvalidOperation,ValueError):
                    gaps.append(dict(material_id=material_id,metric=metric,code='FINANCIAL_NATIVE_VALUE_MISMATCH'))
                    continue
                reason = f"Exact original data[{index}].{field}; no unit/currency/period conversion; semantic basis proof {proof['sha256']} page {proof.get('page','UNKNOWN')} (not an independent per-field PDF numeric audit); normalized source {upstream['record_id']}; inherited gaps: {encode(source.get('gaps',[]))}"
                fact = research.add_fact(FactCommand(company_id=company_id,material_id=material_id,
                    metric=metric,business='FINANCIAL_STATEMENT',value=str(value),value_type='NUMBER',kind='DISCLOSED',
                    unit=material['unit'],currency=material['currency'],scope=material['scope'],
                    period_start=material['period_start'],period_end=material['period_end'],
                    page=f'data[{index}]',table=statement+':'+field,change_reason=reason,
                    idempotency_key='daily-native:'+material_id+':'+metric))
                facts.append(fact['version_id'])
        except Exception as error:
            code = str(error) if isinstance(error,ValueError) and str(error).replace('_','').isalnum() else 'FINANCIAL_ADAPTATION_UNAVAILABLE'
            gaps.append(dict(material_id=material_id,code=code))
        saved=record(dict(adaptation_id=str(uuid4()),company_id=company_id,material_id=material_id,
            source_record_id=upstream.get('record_id'),adapter_version='native-financial-1',attempt_key=attempt_key,
            fact_version_ids=facts[first_fact:],gaps=gaps[first_gap:]))
        with research.transaction() as db:
            db.execute('INSERT OR IGNORE INTO company_research_financial_adaptations VALUES(?,?,?,?,?)',
                (saved['adaptation_id'],company_id,material_id,attempt_key,encode(saved)))
    state=adaptation_state(research,company_id)
    return dict(fact_version_ids=list(dict.fromkeys(facts)),gaps=gaps,
        **state,
        adapter_scope='仅适配已确认原件/期间/单位/币种/范围的规范财务字段；不推断UNKNOWN口径或新闻经营期间')
