"""Freeze documentary request plan only. No HTTP/SQLite/source parser or release."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import httpx
folder=Path(__file__).resolve().parent
repo=folder.parents[3]
reference=repo/'backend/src/roll/market/reference/sse-company-contract'
mapping=json.loads((reference/'sources.json').read_bytes())
expected={'company_html':('72bdf9f924465e3c848577fa4ec5285c163474a79be9bee4a0500a2ecb53f55b',39826),
          'company_js':('478fb2a72fc5a3725088adb208756e88171f79628956a9f5ca67c900d37def2f',277193)}
documents={};texts={}
for item in mapping['sources']:
 sha,size=expected[item['role']];body=(reference/(sha+'.raw')).read_bytes()
 assert item['sha256']==sha and item['bytes']==size and len(body)==size and hashlib.sha256(body).hexdigest()==sha
 documents[item['role']]=item;texts[item['role']]=body.decode('utf-8')
assert 'var sseQueryURL = "//query.sse.com.cn/";' in texts['company_html']
assert 'commonQueryUrl: sseQueryURL + "commonQuery.do?jsonCallBack=?"' in texts['company_js']
url='https://query.sse.com.cn/commonQuery.do'
shared={'isPagination':'true','pageHelp.pageSize':'5','pageHelp.pageNo':'1','pageHelp.beginPage':'1',
        'pageHelp.cacheSize':'1','pageHelp.endPage':'1','COMPANY_CODE':'600362','IS_STAR':'0'}
requests=[]
for role,key,sql,conditions in [
 ('dividend','abprofitParams','COMMON_SSE_CP_GPJCTPZ_GPLB_LRFP_FH_L',{'CONDITION_ZBA':'1','CONDITION_ZBB':''}),
 ('send_share','agprofitParams','COMMON_SSE_CP_GPJCTPZ_GPLB_LRFP_SG_L',{})]:
 block=texts['company_js'].split('  '+key+': {',1)[1].split('\n  },',1)[0]
 assert sql in block and 'isPagination: true' in block and '"pageHelp.pageSize": 5' in block
 assert '_this.'+key+'.COMPANY_CODE = _this.stockCode;' in texts['company_js']
 for key_name,value in conditions.items():assert key_name+': "'+value+'"' in block
 if not conditions:assert 'CONDITION_ZBA' not in block and 'CONDITION_ZBB' not in block
 params={**shared,'sqlId':sql,**conditions}
 requests.append({'role':role,'method':'GET','url':url,'parameters':params,
                  'canonical_request_url':str(httpx.URL(url,params=params)),
                  'request_date_scope':'UNKNOWN_NOT_DECLARED_BY_FIXED_CLIENT',
                  'max_attempts':1,'page':1,'page_size':5,'further_pages_allowed':False})
plan={'preparation_id':str(uuid4()),'prepared_host_at':datetime.now(timezone.utc).isoformat(),
      'classification':'DOCUMENTARY_PLAN_NOT_RESPONSE_OR_EXECUTION_PROOF',
      'prepared_from_eighth_stable':'3d541869989d446150b0c25b2dd8370a55f088ab',
      'state':'PREPARED_WAITING_ACCEPTED8_AND_EXPLICIT_PARENT_RELEASE',
      'execution_allowed':False,'offline_public_api_tdd_complete':False,
      'implementation_fingerprint':None,'implementation_fingerprint_required_before_http':True,
      'documents':documents,'client_variant':{'method':'POST','format':'JSONP','callback':'jsonCallBack=?'},
      'planned_variant':{'method':'GET','format':'JSON','callback':None,'client_path_retained':True},
      'older_proposal_path':'/sseQuery/commonQuery.do','older_proposal_rewritten':False,
      'requests':requests,'request_budget_calls':2,'actual_network_calls':0,
      'timeout_seconds':15,'maximum_response_bytes_per_attempt':8388608,
      'redirects':False,'retry':False,'fallback':False,'alternate_host_or_path':False,
      'raw_first_including_http_error_and_interruption_prefix':True,
      'query_date_scope':'UNKNOWN','current_or_negative_coverage':False,'lifecycle_or_payment_proof':False,
      'system_usable':False,'model_daily_input_allowed':False,'forward_started_at':None,'capability':'NOT_GRANTED',
      'account_or_original_or_preserved_sqlite_opened':False,'followup_source_slices_after_two_sources':False}
target=folder/'prepared-finite-plan.json'
assert not target.exists(),'Preparation immutable: create a successor instead of overwrite.'
body=(json.dumps(plan,ensure_ascii=False,indent=2)+'\n').encode('utf-8');target.write_bytes(body)
receipt={'plan_sha256':hashlib.sha256(body).hexdigest(),'plan_bytes':len(body),
         'fixed_document_count':2,'fixed_document_bytes':317019,'exact_sha_length_mismatches':0,
         'actual_network_calls':0,'sqlite_opened':False,'eighth_frozen_sources_modified':False,
         'execution_allowed':False,'requests':[r['canonical_request_url'] for r in requests]}
(folder/'preparation-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(receipt))
