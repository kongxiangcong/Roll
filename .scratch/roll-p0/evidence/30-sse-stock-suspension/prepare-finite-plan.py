"""Prepare the one bounded actual plan with Host clock and pinned schema, no HTTP or DB."""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from roll.accounts.ledger import now
from roll.market.rules import SHANGHAI
from roll.market.sse_stock_suspension import schema,fingerprint,DAY_SQL,SQL

contract=schema();stamp=now();day=datetime.fromisoformat(stamp).astimezone(SHANGHAI).date().isoformat()
value={'prepared_at':stamp,'host_date':day,'source_url':contract['url'],'parser_fingerprint':fingerprint(),
 'query_js_hash':contract['js_source']['sha256'],'mapping_hash':contract['mapping_hash'],
 'reference_empty_hash':contract['empty_source']['sha256'],'trade_day_parameters':{'sqlId':DAY_SQL,'bizDate':day.replace('-','')},
 'interval_sql_id':SQL,'interval_security':'600362','interval_end_date':day,'interval_page_size':25,
 'interval_start_policy':'ONLY_ONE_REPORTED_BEFORE_TRADE_DAY_NO_DATE_FALLBACK',
 'request_budget_calls':3,'interval_page_budget':2,'timeout_seconds':15,'max_decoded_bytes_per_response':8*1024*1024,
 'no_retries':True,'no_redirects':True,'other_network_sources':False,'system_usable':False,'actual_forward_start':False}
target=Path(__file__).with_name('finite-execution-plan.json')
assert not target.exists(),'Do not silently replace the pre-capture plan'
target.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({'plan':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'parser_fingerprint':value['parser_fingerprint'],'host_date':day,'request_budget_calls':3}))
