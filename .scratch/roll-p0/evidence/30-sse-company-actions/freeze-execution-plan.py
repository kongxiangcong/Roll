"""Freeze an execution successor; no HTTP, SQLite, registry or prior plan writes."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from roll.market.sse_company_actions import contract, fingerprint, PARAMS, URL, PREPARED_SHA
from roll.market.post_close_packet import code
from roll.market.sse_price_quotes import fingerprint as price_fingerprint

folder=Path(__file__).resolve().parent
repo=folder.parents[3]
proof=contract()
assert code()=='cae8f942a6f95b138743c54fb24348987bf288b8d960658120acf3a28083a0fc'
assert price_fingerprint()=='11a8063025fe548fb1c996923be6c9f818d5e1dd74f47382ed145ecf73019de1'
inventory={}
for relative in ['backend/src/roll/market/sse_company_actions.py','backend/src/roll/market/collection_sources.py',
                 'backend/src/roll/app.py','backend/tests/application/test_sse_company_actions.py']:
    body=(repo/relative).read_bytes().replace(b'\r\n',b'\n')
    inventory[relative]={'sha256_lf':hashlib.sha256(body).hexdigest(),'bytes_lf':len(body)}
plan={
    'execution_plan_id':str(uuid4()),'frozen_host_at':datetime.now(timezone.utc).isoformat(),
    'classification':'FINITE_ACTION_SOURCE_EXECUTION_SUCCESSOR_WAITING_EXPLICIT_RELEASE',
    'execution_allowed':False,'actual_network_calls':0,
    'accepted_base':'9b6e007','own_base':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    'prepared_plan_hash':PREPARED_SHA,'prepared_plan_rewritten':False,
    'implementation_fingerprint':fingerprint(),'source_inventory':inventory,
    'old_post_close_fingerprint':code(),'old_price_fingerprint':price_fingerprint(),
    'document_sources':proof['sources'],'mapping_hash':proof['mapping_hash'],
    'requests':proof['prepared']['requests'],
    'declared_client_variant':'POST_JSONP_CALLBACK','execution_variant':'GET_JSON_WITHOUT_CALLBACK',
    'transport_equivalence_claim':False,'root_path':'/commonQuery.do','historical_alternate_path_rewritten':False,
    'request_budget_total_attempts':2,'maximum_attempts_per_role':1,'page_per_role':1,'page_size':5,
    'attempt_deadline_seconds':15,'maximum_response_bytes_per_attempt':8388608,
    'redirects':False,'retries':0,'fallbacks':0,'further_pages':False,'alternate_host_or_path':False,
    'capture_public_endpoint':'POST /api/research/collections/{plan_id}/sse-company-actions',
    'request_command_fields':['basis'],'runtime_role':'API','runtime_namespace':'.scratch/t30a-actual',
    'host_clock_override':False,'external_transport_injection':False,
    'error_and_prefix_bytes_archived_before_interpretation':True,
    'cancelled_response_completeness':'UNKNOWN_AFTER_CANCELLATION',
    'response_schema_assessed':False,'response_parser_after_actual':'SEPARATE_EXPLICIT_ASSESSMENT_MODULE',
    'collector_will_not_be_modified_after_actual':True,
    'offline_public_api_validation':{
        'first_endpoint_red':'1 FAIL / 5.93s','first_endpoint_green':'1 PASS / 6.00s',
        'error_completeness_deadline_red':'2 FAIL / 30.54s','pre_cancellation_metadata_green':'3 PASS / 29.13s',
        'explicit_cancel_metadata_red':'1 FAIL / 21.70s','current_final':'3 PASS / 29.94s',
        'supplier_kind':'METHOD_CASE','actual_network_calls':0},
    'query_date_scope':'UNKNOWN','complete_action_coverage':False,'pending_older_obligations_complete':False,
    'system_usable':False,'model_daily_input_allowed':False,'forward_started_at':None,'capability':'NOT_GRANTED',
    'private_or_original_or_preserved_sqlite_opened':False,'provider_model_notification_requests':0,
    'stop_new_source_slices_after_two_sources':True,
}
target=folder/'finite-execution-plan.json'
assert not target.exists(),'Frozen plan immutable: a change requires a successor.'
body=(json.dumps(plan,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
target.write_bytes(body)
receipt={'execution_plan_sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body),
         'implementation_fingerprint':fingerprint(),'source_inventory':inventory,
         'actual_network_calls':0,'execution_allowed':False,'old_source_fingerprints_unchanged':True}
(folder/'execution-plan-freeze-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(receipt))
