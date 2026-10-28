"""Read-only PDF anchor/index and literal number recheck; not economic approval."""
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from pypdf import PdfReader

out=Path(__file__).parent
source=out.parent/'05'/'source-data'
q3=source/'lulu-2026-q3-issuer-mirror.pdf'
saved=json.loads((source/'lulu-q3-update-facts.json').read_text(encoding='utf-8'))
sha=hashlib.sha256(q3.read_bytes()).hexdigest()
assert sha==saved['source']['sha256']
pages=[p.extract_text() for p in PdfReader(q3).pages]
literal=[]
for fact in saved['facts']:
    text=''.join(pages[fact['pdf_page_1based']-1].split()).replace(',','')
    value=fact['value']
    found=value.replace(',','') in text
    literal.append(dict(fact_key=fact['fact_key'],page=fact['pdf_page_1based'],value=value,literal_found=found,
                        source_sha256=sha,value_basis=fact['value_basis']))
half=Path('D:/dsh-proj/Roll/.scratch/rv12-real01/acceptance-source/halfyear2026.pdf')
half_pages=[p.extract_text() for p in PdfReader(half).pages]
terms=['货币资金','受限制的货币资金','财务有限公司','交易性金融资产','其他权益工具投资','应付账款','资本承诺','股本','折旧','承诺事项']
anchors={term:[i+1 for i,t in enumerate(half_pages) if term in ''.join(t.split())] for term in terms}
# Independent cash identity from the actual Q3 disclosed statement rows.
facts={f['fact_key']:f for f in saved['facts']}
amount=lambda key: Decimal(facts[key]['value'])
change=amount('cfo_ytd')+amount('cash_flow_investing_ytd')+amount('cash_flow_financing_ytd')
assert change==amount('cash_change_ytd')
opening_cash=Decimal(facts['cash']['comparative_value'])
assert opening_cash+change==amount('cash')
cash_identity=dict(opening_cash=str(opening_cash),cfo=str(amount('cfo_ytd')),
    investing=str(amount('cash_flow_investing_ytd')),financing=str(amount('cash_flow_financing_ytd')),
    change=str(change),closing_cash=str(amount('cash')),cash_identity_pass=True,
    source_pages=[4,8,9],scope='CONSOLIDATED/CNY/YTD9MONTH',not_fcff=True)
receipt=dict(q3_sha256=sha,q3_pages=len(pages),literal_checks=literal,
             literal_passed=sum(v['literal_found'] for v in literal),literal_total=len(literal),
             halfyear_sha256=hashlib.sha256(half.read_bytes()).hexdigest(),halfyear_pages=len(half_pages),halfyear_page_index=anchors,
             current_unknowns=saved['unknowns'],cash_identity=cash_identity,existing_reconciliation_keys=list(saved['deterministic_reconciliations']),
             new_facts_written=0,economic_status_changed=False,model_calls=0,
             limitations=['Literal numeric presence is not proof of chosen economic scope or current usability',
              'June30 notes cannot prove September30 restricted cash, deposits, commitments or current debt split',
              'Nine-month CFO must not be annualised4/3 into FCFF; published old models remain immutable'])
(out/'source-readiness.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(q3_literal_passed=receipt['literal_passed'],q3_literal_total=len(literal),halfyear_pages=len(half_pages),
    halfyear_page_index=anchors,model_calls=0)))
