"""Local-only append and bounded packet preparation; no model/runtime execution."""
import json, urllib.request, urllib.error, hashlib
from pathlib import Path
from datetime import datetime, timezone

HERE=Path(__file__).resolve().parent
assert not (HERE/'new-input.json').exists(), 'Preparation complete; preserve the frozen evidence rather than rerunning'
BASE='http://127.0.0.1:8034/api/company-research'
C='54abcc3d-67c2-453e-83b4-8fdc92b7a292'
def save(name,obj):
    (HERE/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def call(path,body=None):
    req=urllib.request.Request(BASE+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=90) as r:return json.load(r)
    except urllib.error.HTTPError as e:raise RuntimeError((path,e.code,e.read().decode())) from e
def wire(obj):return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def sha(obj):return hashlib.sha256(wire(obj)).hexdigest()

old=json.loads((HERE.parent/'next-request-preview/lulu-unvalued-static.json').read_text(encoding='utf-8'))
notes=json.loads((HERE/'rv12-lulu-capital-source-notes.json').read_text(encoding='utf-8'))
before={'input':call('/analysis/inputs/'+old['analysis_input']['input_id']),
        'snapshot':call('/snapshots/'+old['snapshot']['snapshot_id']),
        'job':call('/jobs/9797a495-41a9-4a53-9781-70cc61428841')}
save('original-before.json',before)
new=[]; mapping=[]
for f in notes['facts']:
    assert f['source_id']=='FY2025' and f['raw_sha256']==notes['source_files'][0]['sha256']
    known=f.get('known_frozen51_fact')
    if known:
        row=next(x for x in old['facts'] if x['version_id']==known)
        assert row['value']==f['value']
    else:
        row=call('/facts',dict(company_id=C,material_id='600f0c90-3e6e-40d3-8a2a-140c0cb8853f',
          metric=f['metric_suggestion']+'_2025_stock',business='FINANCIAL_STATEMENT',value=f['value'],value_type='NUMBER',unit='unit',currency='CNY',scope='CONSOLIDATED',
          period_start='2025-12-31',period_end='2025-12-31',page=str(f['physical_page']),table=f['source_section'][:160],kind='DISCLOSED',
          change_reason='Same approved FY2025 annual PDF; current-year consolidated stock, CNY yuan. Literal: '+f['literal_excerpt']+' Boundary: '+f['classification_boundary']+' Comparison not imported; blank is UNKNOWN.',
          idempotency_key='rv12-capital05-'+f['metric_suggestion']))
        new.append(row)
    mapping.append({'source':f,'fact':row,'reused_original':bool(known)})
save('numeric-facts.json',mapping)
quotes=[]
for i,q in enumerate(notes['qualitative_source_excerpts']):
    assert q['source_id']=='FY2025'
    row=call('/facts',dict(company_id=C,material_id='2d4f1b11-f0e2-49d8-84f2-4f30b5aa5303',metric='capital_source_boundary_'+str(i+1),business='FINANCIAL_STATEMENT',
      value=q['literal'],value_type='TEXT',unit=None,currency=None,scope='CONSOLIDATED',period_start='2025-01-01',period_end='2025-12-31',
      page=str(q['physical_page']),table='FY2025 annual source excerpt',kind='DISCLOSED',change_reason='Literal same-original excerpt. Interpretation boundary: '+q['support_boundary'],idempotency_key='rv12-capital05-quote-'+str(i+1)))
    quotes.append(row)
save('qualitative-facts.json',quotes)
# Prefer derived historic normalization with its disclosed audit trail over repeating
# every expense component; all omitted originals remain publicly readable unchanged.
keep_old=[0,9,14,15,16,17,18,19,20,24,25,34,35,36,37,38,39,40,41,42,43,44,45,48,49,50]
keep_new=['trade_receivables_net','prepayments','other_receivables_net','inventory_net','accrued_deposit_interest','input_vat_credit',
 'fixed_assets_net','idle_fixed_assets_net','cip_net','rou_assets_net','intangible_assets_net','capital_prepayments',
 'accounts_payable_other','other_payables_deposits','other_payables_current_accounts','contract_liabilities','payroll_payables',
 'tax_payables_total','corporate_income_tax_payable','pending_output_vat','deferred_grant_income']
selected=[old['facts'][i] for i in keep_old]+[x['fact'] for x in mapping if x['source']['metric_suggestion'] in keep_new]+[quotes[4],quotes[9]]
gap=('Local source-only revision, no model or economic approval. Only FY2025 approved annual original added; its FY2024 comparisons are not another vintage. '
     'No issuer-defined economic NWC; other AP/current accounts/electronic debt certificates, operating cash and finance deposit recovery, maintenance-growth capex remain uncertain. '
     'Idle PPE is a subset; interest is nonoperating. Historical WC cashflow changes are not stocks. Full literal workpaper is archived separately; selection omissions are explicit.')
parent=call('/companies/'+C+'/snapshots')['snapshots'][-1]['snapshot_id']
materials={m['material_id']:m for m in old['materials']}
asof=datetime.now(timezone.utc).isoformat()
def payload(rows):
 return dict(company=old['company'],as_of=asof,facts=rows,materials=[materials[i] for i in dict.fromkeys(f['material_id'] for f in rows)],conflicts=[],conflict_resolutions=[],prior_hypotheses=[],evidence_gap_reason=gap,historical_pit_eligible=False,authority='RESEARCH_ONLY_NO_TOOLS_NO_ACCOUNT_WRITES')
# Packet must respect the actual existing 96KiB guard; produce a reviewable plan first.
plan={'selected':selected,'selected_fact_count':len(selected),'estimated_payload_bytes':len(wire(payload(selected))),
 'all_original_material_hashes':[{ 'material_id':m['material_id'],'raw_sha256':m['raw_sha256']} for m in old['materials']],
 'omitted_original':[f for f in old['facts'] if f['version_id'] not in {r['version_id'] for r in selected}],
 'omitted_new':[x for x in mapping if x['fact']['version_id'] not in {r['version_id'] for r in selected}],
 'qualitative_stored_not_selected':quotes,'parent_snapshot_id':parent,'gap_reason':gap,'model_calls':0,'source_network_calls':0}
save('selection-plan.json',plan)
print(json.dumps({'facts':len(selected),'bytes':plan['estimated_payload_bytes'],'parent':parent,'new_numeric':len(new),'new_qualitative':len(quotes)}))
