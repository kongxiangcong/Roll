"""Reconcile archived public annual facts with implementation notices, without labels."""
import hashlib,json,re
from pathlib import Path
from pypdf import PdfReader
BASE=Path(__file__).resolve().parent
OLD=BASE.parent/'continuation-2026-10-09'
OUT=BASE/'.roll-data'/'rights-public'
def ref(d,parent):
 p=Path(d['path']);p=p if p.is_absolute() else parent/p
 assert hashlib.sha256(p.read_bytes()).hexdigest()==d['sha256']
 return {'url':d['url'],'publication_date':d.get('publication_date') or (re.search(r'finalpage/(\d{4}-\d{2}-\d{2})/',d['url']).group(1) if 'finalpage/' in d['url'] else d.get('source_index_display_date')),'publication_precision':'DATE','received_at':d['received_at'],'sha256':d['sha256'],'bytes':p.stat().st_size,'path':str(p.resolve())}
annual={}
gb=OLD/'.roll-data'/'gap-research-v1'
for name in ['manifest.json','annual-additional-manifest.json']:
 for d in json.loads((gb/name).read_text('utf8'))['records']:
  match=re.search(r'(20\d\d).*年度报告',d.get('title',''))
  if not match or '修订' in d['title'] or not d.get('sha256'):continue
  y=int(match.group(1))
  for q in d.get('selected_status_action_pages',[]):
   if '股份变动情况表' in q['text']:
    annual[y]={'year':y,'source':ref(d,gb),'pdf_page':q['pdf_page'],'annual_declaration':'Share count and structure unchanged' if y>=2014 else 'Share movement table has no additions/transfers/new ordinary shares','page_text':q['text'],'retrospective_reconciliation_only':True,'split_bonus_rights_new_issuance_observed':False,'does_not_certify_every_day_state':True};break
for year,sub,page in [(2022,'gap-research-v2-2022',81),(2025,'gap-research-v3-2025',94)]:
 b=OLD/'.roll-data'/sub;d=json.loads((b/'manifest.json').read_text('utf8'));tp=b/(f'page-{page}.txt' if year==2022 else f'plumber-page-{page}.txt')
 annual[year]={'year':year,'source':ref(d,b),'pdf_page':page,'annual_declaration':'Share count and structure unchanged','page_text':tp.read_text('utf8'),'retrospective_reconciliation_only':True,'split_bonus_rights_new_issuance_observed':False,'does_not_certify_every_day_state':True}
docs=json.loads((OLD/'.roll-data/official-disclosures-v6/manifest.json').read_text('utf8'))['documents'];byurl={d['url']:d for d in docs};parent=OLD/'.roll-data/official-disclosures-v6'
cash=json.loads((OLD/'corporate-action-reconstruction.json').read_text('utf8'))['cash_distributions']
for d in cash:
 src=byurl[d['source']['url']];d['source']=ref(src,parent);pages=[]
 for i,p in enumerate(PdfReader(d['source']['path']).pages):
  txt=p.extract_text() or '';compact=re.sub(r'\s+','',txt)
  if any(w in compact for w in ['股权登记日','除息日','现金红利发放日','差异化分红','差异化权益分派']):pages.append({'pdf_page':i+1,'text':txt})
 d['source']['fact_pdf_pages']=[p['pdf_page'] for p in pages];tp=OUT/f"{d['source']['sha256']}.pages.json";tp.write_text(json.dumps(pages,ensure_ascii=False,indent=2)+'\n','utf8');d['source']['extracted_pages_path']=str(tp.resolve());d['tax_withholding_at_payment_pct']='5' if d['ex_date']<'2015-09-08' else '0';d['tax_withholding_explanation']='A-share domestic individual cash lot; later sale can trigger differential withholding; actual account receipts not asserted'
selected=[]
for d in docs:
 if ('回购' in d['title'] and not '前十名' in d['title']) or d['url'].endswith('/1203689481.PDF') or '停牌' in d['title'] or '复牌' in d['title']:
  src=ref(d,parent);pages=[{'pdf_page':i+1,'text':p.extract_text() or ''} for i,p in enumerate(PdfReader(src['path']).pages)];selected.append({'title':d['title'],'source':src,'pages':pages})
yearly=[]
for year in range(2013,2026):
 yearly.append({'year':year,'annual_audit':annual.get(year),'cash_implementation_events':[x for x in cash if x['ex_date'].startswith(str(year))],'repurchase_audit_required':year>=2024,'all_daily_trade_statuses_certified':False,'new_share_rights_policy':'No split/bonus/rights issue observed in direct annual share movement declarations; reconciliation is retrospective, not predictor input before publication'})
result={'instrument':'SSE:600362','yearly':yearly,'action_documents':selected,'known_suspension_interval':{'start_date_inclusive':'2016-02-16','resumption_date_exclusive':'2016-02-26','precision':'DATE','intraday_halt_clock':None},'2015_full_day_suspension_proof':None,'negative_keyword_search_not_normal_state_proof':True,'annual_years_reconciled':len(annual),'cash_events':len(cash),'sha_mismatches':0,'account_authority':'NONE','labels_computed':False,'sealed_read':False,'models_fitted':False}
(OUT/'yearly-event-inventory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf8')
print(json.dumps({'annual_years':len(annual),'cash_events':len(cash),'action_docs':len(selected),'sha_mismatches':0}))
if len(annual)<14:print('ANNUAL_MISSING',sorted(set(range(2012,2026))-set(annual)))
