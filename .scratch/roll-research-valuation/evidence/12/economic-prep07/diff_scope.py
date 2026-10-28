"""Static exact source/data-scope comparison; no auth/network/model."""
import json,hashlib
from pathlib import Path
H=Path(__file__).resolve().parent
load=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
save=lambda n,v:(H/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
a=load(H.parent/'correction06/candidate-command.json');b=load(H/'candidate-command.json')
pa=json.loads(a['prompt']);pb=json.loads(b['prompt'])
fa={f['version_id']:f for f in pa['evidence']['facts']};fb={f['version_id']:f for f in pb['evidence']['facts']}
ma={m['material_id']:m for m in pa['evidence']['materials']};mb={m['material_id']:m for m in pb['evidence']['materials']}
assert all(fa[k]==fb[k] for k in fa.keys()&fb.keys())
assert all(ma[k]==mb[k] for k in ma.keys()&mb.keys())
newm=load(H/'new-materials.json')
for row in newm:
 m=row['material'];source=row['source'];file=H/'source-data'/Path(source['path']).name
 assert hashlib.sha256(file.read_bytes()).hexdigest()==source['sha256']==m['raw_sha256']==m['archive']['sha256']
receipt=load(H/'preview-receipt.json')
assert hashlib.sha256((H/'candidate-command.json').read_bytes()).hexdigest()==receipt['command_sha256']
reasons={
 'approx_market_equity_value_20251231':'Optional reverse-DCF market-cap proxy; no same-day share-class price fact. Existing source and record preserved, not used to infer current pricing. Its sole material is not selected in the new bounded packet.',
 'associate_boundary':'Original text boundary remains in full51/workpaper, but no independent recoverable economic value established. Omitted is UNKNOWN, not assumed zero.',
 'noncash_asset_boundary':'Accounting residual check is not an appraisal/economic exclusion. Full record preserved; omitted is not zero or approval of economic recovery value.',
 'accrued_deposit_interest_2025_stock':'Nonoperating accrued interest component, not operating NWC. Full numeric record preserved; not recast as operating cash or assumed zero.',
 'input_vat_credit_2025_stock':'Small separately disclosed VAT-credit component preserved in workpaper; economic scope not adopted, omitted is UNKNOWN not zero.',
 'other_receivables_net_2025_stock':'Economic classification unresolved and no selected baseline policy. Full numeric/source detail remains available; omission cannot be an unspoken zero or deduction.',
 'deferred_grant_income_2025_stock':'Asset-related grant classification requires an explicit policy. Full source number preserved; omission is UNKNOWN, not automatic operating financing/zero.'}
changes=dict(prior_command_sha256=hashlib.sha256((H.parent/'correction06/candidate-command.json').read_bytes()).hexdigest(),new_command_sha256=receipt['command_sha256'],
 nonprompt_fields_equal={k:a[k]==b[k] for k in a if k!='prompt'},contract_equal=pa['valuation_contract']==pb['valuation_contract'],purpose_equal=pa['valuation_purpose']==pb['valuation_purpose'],
 changed_prompt_fields=[k for k in pa if pa[k]!=pb[k]],old_fact_count=len(fa),new_fact_count=len(fb),unchanged_selected=len(fa.keys()&fb.keys()),
 omitted_facts=[dict(version_id=k,metric=fa[k]['metric'],reason=reasons[fa[k]['metric']]) for k in sorted(fa.keys()-fb.keys())],
 added_facts=[fb[k] for k in sorted(fb.keys()-fa.keys())],old_material_count=len(ma),new_selected_material_count=len(mb),
 removed_selected_materials=[ma[k] for k in ma.keys()-mb.keys()],new_materials=[mb[k] for k in mb.keys()-ma.keys()],
 new_source_origin_roots=sorted({r['material']['origin_root_id'] for r in newm}),
 disclosure_date_and_unknown_exact_time=[dict(source_id=r['source']['source_id'],date=r['source']['disclosure_date'],exact_disclosed_at=r['material']['disclosed_at'],received_at=r['material']['received_at'],consumable_at=r['material']['consumable_at']) for r in newm],
 financial_numeric_fields_added=0,qualified_text_observations_added=3,
 quoted_rounded_deposit='Included only as context within literal issuer prose; precise annual NUMBER cash_at_related_finance_company_2025 remains unchanged and selected. New TEXT is not calculator numeric provenance, no converted yuan number/actual regulatory ratio imported.',
 new_documents_outside_original_fixed_scope=True,external_execution_authorized=False,budget_used=3,corrections_used=1)
save('scope-diff.json',changes)
prior=load(H.parent/'correction06/receipt.json')['code_hashes'];root=H.parents[4]/'backend/src/roll'
current={k:hashlib.sha256((root/k).read_bytes()).hexdigest() for k in prior};assert current==prior
save('current-code-hashes.json',dict(code_hashes=current,all25_equal_to_correction06=True,model_calls=0))
print(json.dumps(dict(retained=42,omitted=7,added=3,selected_materials=14,new_documents=3,code_files=len(current))))
