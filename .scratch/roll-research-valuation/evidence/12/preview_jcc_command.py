"""Compile one exact possible future command locally. This never executes it."""
import hashlib
import json
from pathlib import Path
import httpx
from roll.accounts.ledger import encode
from roll.agents.company_analysis_runtime import command

out=Path(__file__).parent/'next-request-preview'
out.mkdir(exist_ok=True)
run_id='df662b1b-8fda-469c-9751-7caabccda0c4'
input_id='4b2f8962-30d7-447e-a9db-ae2f077b783f'
with httpx.Client(base_url='http://127.0.0.1:8033',trust_env=False,timeout=90) as c:
    def get(path):
        r=c.get(path);r.raise_for_status();return r.json()
    run=get('/api/company-research/analysis/runs/'+run_id)
    packet=get('/api/company-research/analysis/inputs/'+input_id)
assert run['status']=='UNAVAILABLE' and not run['model_executed']
assert run['input_id']==input_id and packet['company_id']=='469c1865-a145-4a47-a8ec-3056eeff81a2'
compiled=command(run,packet)
assert compiled['tools']==[] and compiled['model']=='gpt-6.1-sol'
wire=encode(compiled).encode('utf-8')
(out/'jcc-operating-analysis.wire.json').write_bytes(wire)
(out/'jcc-operating-analysis.pretty.json').write_text(json.dumps(compiled,ensure_ascii=False,indent=2),encoding='utf-8')
(out/'jcc-frozen-input.json').write_text(json.dumps(packet,ensure_ascii=False,indent=2),encoding='utf-8')
payload=packet['payload']
facts=payload['facts']
receipt=dict(kind='LOCAL_PREVIEW_ONLY_NOT_SEND_AUTHORIZATION',company_id=packet['company_id'],
    company_name=payload['company']['legal_name'],input_id=input_id,input_sha256=packet['packet_sha256'],
    previous_unavailable_run_id=run_id,model=compiled['model'],provider_destination='OpenAI through existing ChatGPT subscription CODEX',
    wire_bytes=len(wire),wire_sha256=hashlib.sha256(wire).hexdigest(),tools=[],maximum_model_turns=1,
    timeout_seconds=90,runtime_operations=8,source_tool_calls=0,fact_count=len(facts),
    fact_kinds={kind:sum(f['kind']==kind for f in facts) for kind in sorted({f['kind'] for f in facts})},
    payload_keys=list(payload),source_urls=sorted({m['source_url'] for m in payload['materials']}),
    exposure=['Public issuer/AKShare-derived financial facts and original source references',
              'Saved research hypotheses/derived facts where present, limitations and evidence conflicts',
              'Internal company/input/fact/material/version IDs and hashes'],
    excluded=['Account holdings/events/credentials','SEALED data','Old experiment budget/training writes',
              'Source tools/browser/files/MCP/skills/subagents/other external destinations'],
    model_calls=0,source_network_calls=0,auth_read=False,
    execution_constraint='If later specifically approved, execute only this frozen wire/input once with retained failures; do not enable model auth on the ongoing daily worker')
(out/'jcc-preview-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:receipt[k] for k in ['kind','input_id','input_sha256','wire_bytes','wire_sha256','fact_count','fact_kinds','maximum_model_turns','model_calls']}))
