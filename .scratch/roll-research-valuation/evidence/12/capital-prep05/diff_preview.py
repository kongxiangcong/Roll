"""Review artefact only: compare exact old/new local compiler outputs."""
import json,hashlib
from pathlib import Path
H=Path(__file__).resolve().parent
load=lambda p:json.loads(p.read_text(encoding='utf-8'))
save=lambda n,v:(H/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
old=load(H.parent/'next-request-preview03/lulu-valuation-command.wire.json')
new=load(H/'candidate-command.json');a=json.loads(old['prompt']);b=json.loads(new['prompt'])
fa={f['version_id']:f for f in a['evidence']['facts']};fb={f['version_id']:f for f in b['evidence']['facts']}
ma={m['material_id']:m for m in a['evidence']['materials']};mb={m['material_id']:m for m in b['evidence']['materials']}
assert ma==mb and all(fa[k]==fb[k] for k in fa.keys()&fb.keys())
assert all(b['snapshot'].get(k) in (None,[]) for k in ('valuation_ids','economic_review_ids'))
omission_reason={
 'revenue_2024':'Historical revenue detail omitted for size; normalized FY2024 core-profit figure with saved derivation remains.',
 'cfo_2025':'Historical CFO is not FCFF or NWC stock; source-only capital components and capex/DA preserved instead.',
 'cfo_2024':'Historical CFO is not FCFF or NWC stock; no cashflow-to-stock substitution.',
 'cash_capex_2024':'Prior-year cash investment is not a maintenance/growth split; current capex remains.',
 'total_equity_2025':'Accounting equity is not economic operating capital; no shortcut from equity to invested capital.',
 'no_disclosed_material_commitment_2025':'Absence of material disclosure cannot prove no future payments; full workpaper preserves literal source.'}
def reason(f):
 if f['metric'] in omission_reason:return omission_reason[f['metric']]
 if f['metric'].startswith('cash_recon_'):return 'Cashflow reconciliation movement is not a working-capital stock; omitted, never relabelled.'
 return 'Repeated historic expense/depreciation detail omitted for existing size bound; selected core-profit/DA derived facts retain their original saved audit derivations; original records stay unchanged.'
diff=dict(old_command_sha256=hashlib.sha256((H.parent/'next-request-preview03/lulu-valuation-command.wire.json').read_bytes()).hexdigest(),
 new_command_sha256=hashlib.sha256((H/'candidate-command.json').read_bytes()).hexdigest(),
 nonprompt_fields_equal={k:old[k]==new[k] for k in old if k!='prompt'},
 same_contract=a['valuation_contract']==b['valuation_contract'],same_purpose=a['valuation_purpose']==b['valuation_purpose'],
 prompt_top_level_changes=[k for k in a if a[k]!=b[k]],request_cutoff={'old':a['request_cutoff'],'new':b['request_cutoff']},
 original_materials_identical=True,material_count=len(ma),new_materials=[],retained_original_fact_ids=sorted(fa.keys()&fb.keys()),
 omitted_original=[dict(version_id=k,metric=fa[k]['metric'],reason=reason(fa[k])) for k in fa.keys()-fb.keys()],
 added_facts=[dict(version_id=k,metric=fb[k]['metric'],material_id=fb[k]['material_id'],archive_sha256=fb[k]['archive_sha256'],kind=fb[k]['kind'],page=fb[k]['page'],value=fb[k]['value']) for k in fb.keys()-fa.keys()],
 omitted_new_workpaper='selection-plan.json / omitted_new and qualitative_stored_not_selected; subset/unknown-classification/detail not lost from the new store or workpaper.',
 authority='UNEXECUTED preview, source-only local publication, no approved economic classification or price',
 actual_budget={'used':2,'limit':16,'corrections_used':0},credentials_or_account_or_sealed=False)
save('command-diff.json',diff)
proof=load(H.parent/'next-request-preview03/actual-preview-receipt.json')['code_hashes']
root=H.parents[4]/'backend/src/roll'
current={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in proof}
assert current==proof
save('current-code-hashes.json',dict(code_hashes=current,all_25_equal_to_authorized04=True,model_calls=0))
print(json.dumps(dict(retained=len(diff['retained_original_fact_ids']),omitted=len(diff['omitted_original']),added=len(diff['added_facts']),sources=len(ma),source_code_files=len(current))))
