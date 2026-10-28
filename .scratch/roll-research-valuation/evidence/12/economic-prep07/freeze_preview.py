"""Freeze a new-source local packet and exact preview. No execution/reservation."""
import json,hashlib,urllib.request,urllib.error
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent
BASE='http://127.0.0.1:8035/api/company-research'
def save(n,v):(H/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
load=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
raw=lambda v:json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def call(p,b=None):
 req=urllib.request.Request(BASE+p,data=None if b is None else json.dumps(b).encode(),headers={'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=60) as r:return json.load(r)
 except urllib.error.HTTPError as e:raise RuntimeError((p,e.code,e.read().decode())) from e
assert not (H/'preview.json').exists(),'Preserve exact preview; do not duplicate'
plan=load(H/'selection-plan.json');before=load(H/'original-before.json');newfacts=load(H/'new-qualified-facts.json');C=before['input49']['company_id']
packet=call('/analysis/inputs',dict(company_id=C,as_of=datetime.now(timezone.utc).isoformat(),fact_version_ids=[f['version_id'] for f in plan['selected']],parent_snapshot_id=plan['parent_snapshot_id'],purpose='SHARED',evidence_gap_reason=plan['evidence_gap_reason']))
save('new-input.json',packet);assert len(raw(packet['payload']))<=98304
limits=[
 'LOCAL SOURCE-ONLY NEW-DOCUMENT PREPARATION; not a successful model or economic approval. No execution or budget reservation authorized by this preview.',
 'Three new issuer documents beyond prior approved original12/49packet, including one third-party Sina mirror. Official021 and mirror020 concern the same issuer/mechanism, not independent corroboration. Disclosure dates known, exact times unknown; obtained now/nonPIT.',
 'Issuer year-end risk assessment supplies historical deposit safety/liquidity and no delayed-payment statements. Audit language concerns finance-company financial data; no independent deposit guarantee or future full recovery/withdrawal proof. Regulatory compliance is not an actual measured ratio.',
 'Supplier-credit proposals disclose procurement AP recognition, financing supplier fee burden and maturity payment. At disclosure still pending shareholder approval/final signing. Year-end financed fraction, AP subledger allocation, extensions and implicit purchase costs remain unknown; do not double count certificates and AP.',
 'Material omissions are listed explicitly. Unselected accrued interest/VAT/other receivables/grants/associate and other noncash assets are UNKNOWN, not zero or an approved exclusion. Complete prior capital workpaper and all original facts remain immutable/readable in the clone.',
 'No adopted economic NWC, necessary operating cash, deposit haircut, maintenance/growth investment, commissioning/utilization or capital roll-forward policy has been selected. Idle PPE remains a fixed-asset subset and indefinite-life trademark remains within intangible assets.',
 'Existing contract supports source-anchored limited proxies and explicit conditional assumptions with limitations and sensitivity; future assumptions do not have to be disguised as observed facts. No numeric proxy or economic classification is chosen by this local preparation, and source/scale/bridge gates remain unchanged.',
 'BASELINE_RESEARCH may use the disclosed year-end anchor with dated WACC proxy assumptions; current pricing and strict historical PIT are separately unavailable. Latest interim disclosure existence is preserved; no synthetic stub or rolled-forward disclosed balance. Optional missing EPV/reverse DCF is N/A, not an independent mandatory DCF gate.'
]
candidate=dict(company_id=C,input_sha256=packet['packet_sha256'],business_structure=[dict(text='The issuer manufactures plant protein beverages.',fact_version_ids=['741985a1-01b6-4cf5-ac1d-1f29dad6e0e4'],gap_reason=None)],
 attention_reasons=[dict(text='Issuer historical deposit assessment and proposed supplier-credit terms add qualified source evidence; their limitations remain explicit.',fact_version_ids=[f['version_id'] for f in newfacts],gap_reason=None)],
 counterevidence=[],hypotheses=[],insufficient_hypotheses_reason='Literal source-only new-document preparation, no new model hypotheses.',limitations=limits,valuation_unavailable_reason='No economic policy or valuation executed; new-source scope is not approved for external sending.')
snapshot=call('/analysis/inputs/'+packet['input_id']+'/candidates',{'candidate':candidate});save('source-only-candidate.json',candidate);save('source-only-snapshot.json',snapshot)
assert snapshot['model_id']=='EXTERNAL_CANDIDATE' and not snapshot['valuation_ids'] and not snapshot.get('economic_review_ids')
job=call('/reports',dict(company_id=C,snapshot_id=snapshot['snapshot_id'],as_of=datetime.now(timezone.utc).isoformat(),source_mode='REUSE',valuation_purpose='BASELINE_RESEARCH',idempotency_key='rv12-economic07-new-sources-preview-only',parent_job_id='ecf287d8-cfe4-4c18-8388-c95d59ac44e6'));save('new-job.json',job)
preview=call('/jobs/'+job['job_id']+'/valuation/preview');save('preview.json',preview);wire=raw(preview['command']);(H/'candidate-command.json').write_bytes(wire)
assert hashlib.sha256(wire).hexdigest()==preview['command_sha256']
after={
 'input49':call('/analysis/inputs/'+before['input49']['input_id']),
 'snapshot49':call('/snapshots/'+before['snapshot49']['snapshot_id']),
 'job_correction':call('/jobs/'+before['job_correction']['job_id']),
 'run_correction':call('/analysis/runs/'+before['run_correction']['run_id']),
 'run_first':call('/analysis/runs/'+before['run_first']['run_id'])}
assert before==after;save('original-after.json',after)
old=load(H.parent/'next-request-preview/lulu-unvalued-static.json');manifest=[]
for m in old['materials']:
 assert call('/materials/'+m['material_id'])==m
 manifest.append(dict(material_id=m['material_id'],raw_sha256=m['archive']['sha256'],record_unchanged=True,selected=m['material_id'] in packet['material_ids']))
assert all(call('/facts/'+f['version_id'])==f for f in old['facts'])
capital=load(H.parent/'capital-prep05/numeric-facts.json')
assert all(call('/facts/'+f['fact']['version_id'])==f['fact'] for f in capital)
save('original-source-manifest.json',manifest)
budget=load(Path('D:/dsh-proj/Roll/.scratch/rv12-execution04/budget.json'));assert len(budget['attempts'])==3
receipt=dict(kind='UNEXECUTED_NEW_DOCUMENT_SCOPE_PREVIEW',job_id=job['job_id'],snapshot_id=snapshot['snapshot_id'],parent_snapshot_id=snapshot['parent_snapshot_id'],input_id=packet['input_id'],packet_sha256=packet['packet_sha256'],
 packet_bytes=len(raw(packet['payload'])),fact_count=len(packet['fact_version_ids']),old49_retained=42,old49_omitted=7,new_qualified_text_facts=3,
 original_12_material_records_preserved=True,new_materials=3,original_materials_selected=11,total_selected_materials=len(packet['material_ids']),
 original51_and38capital_rows_unchanged=True,old_lulu_runs_jobs_inputs_unchanged=True,
 command_sha256=preview['command_sha256'],command_bytes=len(wire),model=preview['command']['model'],tools=preview['command']['tools'],
 model_calls=0,public_source_network_calls=0,auth_read=False,worker_started=False,budget_used=3,corrections_used=1,new_slot_reserved=False,
 new_source_payload_authorized=False,scope='3 new documents beyond original fixed sources; root must review exact added data scope before any execution')
save('preview-receipt.json',receipt);save('budget-unchanged.json',budget);print(json.dumps(receipt))
