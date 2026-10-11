"""Offline inspection of exactly the pinned JS, historical response and this one real response."""
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs,urlparse

repo=Path(__file__).resolve().parents[4];reference=repo/'backend/src/roll/market/reference/sse-history'
sources={s['role']:s for s in json.loads((reference/'sources.json').read_bytes())['sources']}
js=(reference/sources['suspension_query_js']['path']).read_bytes()
assert hashlib.sha256(js).hexdigest()==sources['suspension_query_js']['sha256']
block=js.decode('utf-8').split('var suspension_stock',1)[0]
checks={term:term in block for term in ["'sseQuery/commonQuery.do'","'COMMON_SSE_XXPL_JYTS_TFPXX_L'",
 '"SEARCH_DATE": get_systemDate_global()',"format: 'yyyy-MM-dd'",
 '_this.suspensionParams.SEARCH_DATE = $(".js_date input").val()',
 '"pageHelp.pageSize": 25','"pageHelp.pageNo": 1','"pageHelp.beginPage": 1',
 '"pageHelp.cacheSize": 1','"pageHelp.endPage": 1',"type: 'post'","dataType: 'jsonp'"]}
assert all(checks.values())
receipt=json.loads(Path(__file__).with_name('runtime').joinpath('source-assessment/receipt.json').read_bytes())
saved=receipt['pages'][0]
actual=Path(__file__).with_name('runtime').joinpath('source-assessment',saved['archive']['sha256']+'.raw').read_bytes()
assert hashlib.sha256(actual).hexdigest()==saved['archive']['sha256']
value=json.loads(actual);rows=value['result'];historical=json.loads((reference/sources['suspension']['path']).read_bytes())
query={k:v[0] for k,v in parse_qs(urlparse(saved['archive']['source_url']).query).items()}
assert query==saved['parameters'] and query['SEARCH_DATE']==receipt['query_date']=='2026-10-11'
assert query['pageHelp.pageSize']=='100' and value['pageHelp']['pageSize']==100
audit={'query_js_sha256':sources['suspension_query_js']['sha256'],'client_first_block_checks':checks,
 'client_line_locators':{'url':7,'sql_id':10,'date_default':11,'page_fields':'12-16',
  'calendar_date_format':26,'date_value_assignment':44,'transport':'62-65','returned_fields':'70-83'},
 'request_parameters':query,'date_case_and_format_matches_pinned_client':True,
 'request_page_size':100,'pinned_client_default_page_size':25,
 'page_size_basis':'EXACT_FIXED_2016_MANIFEST_GET_REQUEST_AND_RESPONSE_PAGE_SIZE100; NOT_CLIENT_DEFAULT25',
 'transport_basis':'ANONYMOUS_JSON_GET_VARIANT_PROVEN_BY_FIXED_GET_MANIFEST; CLIENT_DECLARED_POST_JSONP_NOT_REPLICATED',
 'raw_response_date_echo':value['queryDate'],'raw_page_search_date':value['pageHelp']['searchDate'],
 'returned_rows':len(rows),'reported_total':value['pageHelp']['total'],
 'returned_product_codes':[r['PRODUCT_CODE'] for r in rows],
 'target600362_returned':any(r['PRODUCT_CODE']=='600362' for r in rows),
 'reported_show_start_dates':sorted(set(r['SHOW_START_DATE'] for r in rows)),
 'reported_show_end_dates':sorted(set(r['SHOW_END_DATE'] for r in rows)),
 'old_historical_response_query_date_echo':historical['queryDate'],
 'old_historical_response_page_search_date':historical['pageHelp']['searchDate'],
 'parameter_case_or_date_format_error_observed':False,
 'date_selection_or_current_authority_proven':False,
 'conclusion':'Returned starts 2024/2025 and dash ends are schedules, not publication/expiry or confirmed current applicability. Date echoes absent and target absent; cannot prove exact date filtering, current normality or complete coverage. One observed supplier response, not permanent endpoint absence.',
 'new_http_calls':0,'system_usable':False,'actual_forward_start':False}
Path(__file__).with_name('request-contract-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({k:audit[k] for k in ['date_case_and_format_matches_pinned_client','reported_show_start_dates','reported_show_end_dates','target600362_returned','new_http_calls']}))
