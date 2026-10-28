"""Compile local correction preview and prove the only05 delta is contract1.1."""
import json,urllib.request,hashlib
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent
P=H.parent/'capital-prep05'
load=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
save=lambda n,v:(H/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
old=load(P/'preview.json')
with urllib.request.urlopen('http://127.0.0.1:8034/api/company-research/jobs/ecf287d8-cfe4-4c18-8388-c95d59ac44e6/valuation/preview',timeout=30) as r:new=json.load(r)
oldp=json.loads(old['command']['prompt']);newp=json.loads(new['command']['prompt'])
assert {k:v for k,v in old['command'].items() if k!='prompt'}=={k:v for k,v in new['command'].items() if k!='prompt'}
assert [k for k in oldp if oldp[k]!=newp[k]]==['valuation_contract']
assert newp['evidence']==oldp['evidence'] and newp['snapshot']==oldp['snapshot']
root=H.parents[4]/'backend/src/roll'
prior=load(P/'current-code-hashes.json')['code_hashes']
current={k:hashlib.sha256((root/k).read_bytes()).hexdigest() for k in prior}
assert [k for k in prior if prior[k]!=current[k]]==['research/company/valuation_candidate_contract.md']
assert current['research/company/valuation_candidate_contract.md']=='1e9cf88f78a3d5c03cc78eb02a0b2f02c89db8b8424bff11bb38331a3823c318'
wire=json.dumps(new['command'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
assert hashlib.sha256(wire).hexdigest()==new['command_sha256']
(H/'candidate-command.json').write_bytes(wire);save('preview.json',new)
save('receipt.json',dict(prepared_at=datetime.now(timezone.utc).isoformat(),job_id=new['job_id'],snapshot_id=new['snapshot_id'],
 command_sha256=new['command_sha256'],command_bytes=len(wire),prior05_command_sha256=old['command_sha256'],
 changed_prompt_fields=['valuation_contract'],all49facts_input_snapshot_cutoff_unchanged=True,all_other24runtime_source_hashes_unchanged=True,
 code_hashes=current,api_restart_required=False,reason='Only external Markdown contract read afresh by ReportValuationRuntime.command; Python/runtime unchanged',
 model_calls=0,source_network_calls=0,auth_read=False,budget_used_before=2,corrections_used_before=0))
print(json.dumps(dict(command_sha256=new['command_sha256'],command_bytes=len(wire),only_delta='valuation_contract1.1',budget=2,corrections=0)))
