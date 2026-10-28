"""Public local API only. Publish a labelled source-only core and preview, never execute."""
import json,hashlib,urllib.request,urllib.error
from pathlib import Path
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent
BASE='http://127.0.0.1:8034/api/company-research'
def save(name,obj): (HERE/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def raw(obj):return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def call(path,body=None):
 req=urllib.request.Request(BASE+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=90) as r:return json.load(r)
 except urllib.error.HTTPError as e:raise RuntimeError((path,e.code,e.read().decode())) from e
assert not (HERE/'preview.json').exists(),'Do not duplicate frozen preview'
plan=json.loads((HERE/'selection-plan.json').read_text(encoding='utf-8'))
old=json.loads((HERE.parent/'next-request-preview/lulu-unvalued-static.json').read_text(encoding='utf-8'))
C=old['company']['company_id']
stamp=datetime.now(timezone.utc).isoformat()
packet=call('/analysis/inputs',dict(company_id=C,as_of=stamp,fact_version_ids=[f['version_id'] for f in plan['selected']],parent_snapshot_id=plan['parent_snapshot_id'],purpose='SHARED',evidence_gap_reason=plan['gap_reason']))
save('new-input.json',packet)
assert len(raw(packet['payload']))<=98304 and len(packet['payload']['facts'])<=80
limitations=[plan['gap_reason'],
 'LOCAL SOURCE-ONLY WORKPAPER PUBLICATION: not a new model success, no approved economic capital or valuation; original approved packet and BLOCKED run unchanged.',
 'Existing contract clarification: sourced RF may have period_end <= WACC as_of; WACC as_of must equal calculation metadata date. Explicit stale-date proxy, ERP/beta/target weights remain assumptions with rationale; this does not supply new current market facts.',
 'Existing contract clarification: EPV/reverse DCF without inputs is N/A, not an independent mandatory BASELINE DCF gate. All mandatory economic source/scale/capital/bridge gates remain.',
 'Source only FY2025 annual current-year columns; FY2024 independent PDF excluded. No newly obtained half-year report, previous valuation output, account, SEALED or credentials in selected evidence.',
 'No issuer-defined economic NWC; other payables and electronic debt certificates may be operating or financing and overlap. No blank financial field imputed zero; idle PPE is a fixed-assets subset.',
 'No verified maintenance/growth capex split, necessary operating cash, finance deposit recoverability/haircut/withdrawal terms, or actual current project commissioning. Conditional explicit assumptions may be proposed and audited; unknowns must remain visible.']
candidate=dict(company_id=C,input_sha256=packet['packet_sha256'],business_structure=[dict(text='The issuer manufactures plant protein beverages. Capital components are source observations awaiting economic classification.',fact_version_ids=['741985a1-01b6-4cf5-ac1d-1f29dad6e0e4'],gap_reason=None)],attention_reasons=[],counterevidence=[],hypotheses=[],insufficient_hypotheses_reason='Local literal-source supplementation only; no new model-generated hypotheses.',limitations=limitations,valuation_unavailable_reason='No valuation executed; source-only preparation with unresolved economic classifications.')
snapshot=call('/analysis/inputs/'+packet['input_id']+'/candidates',{'candidate':candidate})
save('source-only-candidate.json',candidate);save('source-only-snapshot.json',snapshot)
assert snapshot['valuation_ids']==[] and not snapshot.get('economic_review_ids') and snapshot['model_id']=='EXTERNAL_CANDIDATE'
job=call('/reports',dict(company_id=C,snapshot_id=snapshot['snapshot_id'],as_of=datetime.now(timezone.utc).isoformat(),source_mode='REUSE',valuation_purpose='BASELINE_RESEARCH',idempotency_key='rv12-capital05-local-preview-only',parent_job_id='9797a495-41a9-4a53-9781-70cc61428841'))
save('new-job.json',job)
preview=call('/jobs/'+job['job_id']+'/valuation/preview')
save('preview.json',preview)
command=raw(preview['command']);(HERE/'candidate-command.json').write_bytes(command)
assert hashlib.sha256(command).hexdigest()==preview['command_sha256']
prompt=json.loads(preview['command']['prompt'])
assert preview['command']['tools']==[] and snapshot['snapshot_id']==prompt['snapshot']['snapshot_id']
oldbefore=json.loads((HERE/'original-before.json').read_text(encoding='utf-8'))
oldafter={'input':call('/analysis/inputs/'+old['analysis_input']['input_id']),'snapshot':call('/snapshots/'+old['snapshot']['snapshot_id']),'job':call('/jobs/9797a495-41a9-4a53-9781-70cc61428841')}
assert oldbefore==oldafter
save('original-after.json',oldafter)
facts_equal=all(call('/facts/'+f['version_id'])==f for f in old['facts'])
manifest=[]
for m in old['materials']:
 live=call('/materials/'+m['material_id']);assert live==m
 manifest.append(dict(material_id=m['material_id'],raw_sha256=m['archive']['sha256'],content_sha256=m['content_sha256'],unchanged=True,selected=m['material_id'] in packet['material_ids']))
save('same-source-manifest.json',manifest)
orig_preview=json.loads((HERE.parent/'next-request-preview03/lulu-first-preview.json').read_text(encoding='utf-8')) if (HERE.parent/'next-request-preview03/lulu-first-preview.json').exists() else None
receipt=dict(kind='LOCAL_ONLY_UNEXECUTED_CORRECTION_CANDIDATE_PREVIEW',prepared_at=stamp,store='D:/dsh-proj/Roll/.scratch/rv12-capital-prep01',api=8034,job_id=job['job_id'],job_status=job['status'],snapshot_id=snapshot['snapshot_id'],parent_snapshot_id=snapshot['parent_snapshot_id'],model_id=snapshot['model_id'],input_id=packet['input_id'],packet_sha256=packet['packet_sha256'],packet_bytes=len(raw(packet['payload'])),fact_count=len(packet['fact_version_ids']),original_fact_count=51,original_51_unchanged=facts_equal,original_objects_unchanged=True,all_original_12_materials_unchanged=len(manifest)==12,selected_material_count=len(packet['material_ids']),added_source_materials=[],command_bytes=len(command),command_sha256=preview['command_sha256'],old_command_sha256='4d5ae801204adb12cc09f2c2f2b391bb99d58f639ef34b3db8dff019f67f48fe',model=preview['command']['model'],tools=preview['command']['tools'],model_calls=0,public_source_network_calls=0,auth_read=False,worker_started=False,batch_used=2,batch_limit=16,corrections_used=0,execution_authorized_here=False)
save('preview-receipt.json',receipt)
print(json.dumps(receipt))
