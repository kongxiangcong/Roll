"""Append three genuinely new source documents in a fresh clone; no model."""
import json,base64,hashlib,shutil,urllib.request,urllib.error
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent
BASE='http://127.0.0.1:8035/api/company-research'
C='54abcc3d-67c2-453e-83b4-8fdc92b7a292'
def save(n,v):(H/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def call(p,b=None):
 req=urllib.request.Request(BASE+p,data=None if b is None else json.dumps(b).encode(),headers={'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=60) as r:return json.load(r)
 except urllib.error.HTTPError as e:raise RuntimeError((p,e.code,e.read().decode())) from e
assert not (H/'new-input.json').exists(),'Never mutate the completed preparation evidence'
notes=json.loads((H/'rv12-lulu-economic-source-supplement.json').read_text(encoding='utf-8-sig'))
sources=[notes['two_query_followup']['source']]+[s for s in notes['sources'] if s['source_id'] in ['supply-credit-2025-021','supply-framework-2025-020-mirror']]
company=call('/companies/'+C)
original={
 'input49':call('/analysis/inputs/8877427a-9073-47fc-954c-267023e5b028'),
 'snapshot49':call('/snapshots/50604854-d481-4f98-bc0c-33def10cfe4a'),
 'job_correction':call('/jobs/ecf287d8-cfe4-4c18-8388-c95d59ac44e6'),
 'run_correction':call('/analysis/runs/bf290081-a8b0-4441-82e4-21c7bf3aa3dc'),
 'run_first':call('/analysis/runs/fff7d56d-2f44-4d46-9877-a56ab31c4489')}
save('original-before.json',original)
materials=[];facts=[]
values={
 'finance-risk-2025fy':('3-5','2025-12-31','2025-12-31','ISSUER_ASSESSMENT_RELATED_FINANCE_COMPANY',
  '以上数据已经审计。\n截至2025年12月31日，财务公司的各项监管指标均符合规定要求。\n截至2025年12月31日，本公司在财务公司存款余额为312,391.83万元。本公司在财务公司的存款安全性和流动性良好，未发生财务公司现金头寸不足而延迟付款的情况。\n本公司与财务公司发生的关联存款等金融业务风险可控。',
  'Issuer board self-assessment; audit statement concerns finance-company financial data, not an independent deposit guarantee. Regulatory table reports compliance, not measured ratios; do not substitute25% threshold or interim45.55%. Rounded balance does not replace precise annual CNY value. Historical assertions are not future full recovery, current availability, free withdrawal or excess cash.'),
 'supply-credit-2025-021':('2-3','2025-04-24','2025-04-24','ISSUER_PROPOSED_SUPPLIER_CREDIT_TERMS',
  '本次关联交易事项尚需提交公司股东大会审议。\n公司在采购端根据采购业务执行情况向供应商开具区块链债权凭证——“万纳信”，确认应付账款。供应商可凭“万纳信”向合作金融机构申请应付账款额度内的融资，融资资金由金融机构支付给供应商，“万纳信”到期时，公司需向金融机构兑付。\n各方（包括银行）尚未签署最终协议，实际情况以最终签署的协议为准，有效期自协议签订之日起至2026年5月31日。',
  'Official-hosted issuer proposal/business-flow disclosure. Supports AP recognition and supplier-finance mechanism, not proof of final approval/signing, financed fraction, year-end payable subledger allocation or no implicit financing. Avoid adding the same certificate to both AP and debt without reconciliation.'),
 'supply-framework-2025-020-mirror':('2-5','2025-04-24','2025-04-24','ISSUER_PROPOSED_SUPPLIER_FRAMEWORK_MIRROR',
  '本次关联交易事项尚需提交公司股东大会审议。\n也可持有“万纳信”到期，直接获得公司支付的应付款；也可将“万纳信”拆分、流转，用于供应商的上游货款结算。\n万向区块链不向公司收取费用，公司与万向区块链之间不存在实质的资金往来。供应商获取“万纳信”后，如果在持有到期前进行融资，万向区块链及合作金融机构将以市场价格为定价依据，经协商确定，向融资的供应商收取相关费用。\n协议有效期为壹年。有效期自2025年6月1日至2026年5月31日。',
  'Issuer-authored original announcement PDF on third-party Sina mirror; no official-hosted byte match obtained. Framework proposal still pending shareholder approval at disclosure, not final signed-year evidence or proof of zero full-year corporate financing costs. Same issuer/mechanism as official021, not independent corroboration.')}
for s in sources:
 sid=s['source_id'];path=Path(s['path']);data=path.read_bytes();assert hashlib.sha256(data).hexdigest()==s['sha256']
 shutil.copyfile(path,H/'source-data'/path.name)
 for suffix in ['-pages.json','-receipt.json']:
  other=path.with_name(path.stem+suffix)
  if other.exists():shutil.copyfile(other,H/'source-data'/other.name)
 page,start,end,scope,value,boundary=values[sid]
 m=call('/materials',dict(company_id=C,source_id='rv12-economic07-'+sid,origin_root_id='ISSUER:SZSE:000848:ECONOMIC_DISCLOSURES',
  source_url=s['requested_url'],subject_name=company['legal_name'],media_type='application/pdf',disclosed_at=None,
  period_start='2025-01-01' if sid=='finance-risk-2025fy' else '2025-04-24',period_end='2025-12-31' if sid=='finance-risk-2025fy' else '2026-05-31',
  unit=None,currency=None,scope=scope,page=page,table=s['title'][:160],limitations=[
   'Issuer disclosure date '+s['disclosure_date']+'; exact disclosure timestamp unknown. Acquired now, non-PIT.',boundary],
  idempotency_key='rv12-economic07-'+sid,content_base64=base64.b64encode(data).decode()))
 materials.append(dict(source=s,material=m))
 f=call('/facts',dict(company_id=C,material_id=m['material_id'],metric=sid+'_qualified_source_statement',business='FINANCING_RISK',value=value,value_type='TEXT',unit=None,currency=None,
  scope=scope,period_start=start,period_end=end,page=page,table=s['title'][:160],kind='DISCLOSED',
  change_reason='Qualified literal source excerpts; '+boundary,idempotency_key='rv12-economic07-fact-'+sid))
 facts.append(f)
save('new-materials.json',materials);save('new-qualified-facts.json',facts)
old=original['input49']['payload'];rows=old['facts']
omit={'approx_market_equity_value_20251231','associate_boundary','noncash_asset_boundary','accrued_deposit_interest_2025_stock','input_vat_credit_2025_stock','other_receivables_net_2025_stock','deferred_grant_income_2025_stock'}
selected=[f for f in rows if f['metric'] not in omit]+facts
gap=('Unexecuted new-source preparation only.3 new issuer PDFs,1 mirror. Historical assessment and proposed terms are not guarantees or signed contracts. Omissions stay unknown; no economic policy approved.')
allm={m['material_id']:m for m in old['materials']};allm.update({x['material']['material_id']:x['material'] for x in materials})
payload=dict(old,as_of=datetime.now(timezone.utc).isoformat(),facts=selected,materials=[allm[i] for i in dict.fromkeys(f['material_id'] for f in selected)],evidence_gap_reason=gap)
raw=lambda o:json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
save('selection-plan.json',dict(selected=selected,selected_count=len(selected),estimated_bytes=len(raw(payload)),all_registered_materials=allm,
 selected_material_ids=[m['material_id'] for m in payload['materials']],omitted_from49=[f for f in rows if f['metric'] in omit],
 parent_snapshot_id=original['snapshot49']['snapshot_id'],evidence_gap_reason=gap,model_calls=0,budget_used=3,corrections_used=1))
print(json.dumps(dict(new_documents=len(materials),new_qualified_text_facts=len(facts),selected=len(selected),bytes=len(raw(payload)),selected_materials=len(payload['materials']))))
