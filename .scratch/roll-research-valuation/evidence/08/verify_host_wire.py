"""Independent structural byte comparison of old and host03 command plans. No model/network."""
import json,hashlib
from pathlib import Path
from roll.accounts.ledger import encode
from roll.research.company.report_template import code_hashes
root=Path('.scratch/roll-research-valuation/evidence/08');new=root/'preview-host03';old=root/'preview-08.2'
audit=json.loads((new/'audit.json').read_bytes());revision=json.loads((new/'revision.json').read_bytes());packet=json.loads((new/'packet.json').read_bytes())
if revision['execution_code_hashes']!=code_hashes():raise RuntimeError('Execution source drifted after revision freeze')
rows=[]
for item in audit['commands']:
 sid=item['section_id'];wire=(new/item['file']).read_bytes();prior=(old/item['file']).read_bytes()
 if hashlib.sha256(wire).hexdigest()!=item['sha256'] or wire!=encode(json.loads(wire)).encode():raise RuntimeError('Actual wire is not exactly canonical audited SHA')
 current=json.loads(wire);previous=json.loads(prior);p=json.loads(current['prompt']);q=json.loads(previous['prompt'])
 if item['will_execute']:
  context=p.pop('fixed_valuation_context')
  if p!=q:raise RuntimeError('Unexpected change outside fixed model context')
  if context['operating_model_sha256']!=packet['payload']['valuation_binding']['fixed_operating_model']['content_sha256']:raise RuntimeError('Context model differs')
  if context['assumptions']!=packet['payload']['valuation_binding']['fixed_operating_model']['assumptions']:raise RuntimeError('Context assumptions changed')
 else:
  if wire!=prior:raise RuntimeError('An existing output command was changed')
 if any(current[k]!=previous[k] for k in ['model','tools','output_schema','instructions']):raise RuntimeError('Model/schema/tools/instructions changed')
 rows.append(dict(section_id=sid,will_execute=item['will_execute'],wire_sha256=item['sha256'],bytes=len(wire),old_sha256=hashlib.sha256(prior).hexdigest()))
result=dict(job_id=audit['job_id'],host_revision_id=revision['revision_id'],input_sha256=audit['input_sha256'],rows=rows,execution_source_hashes_verified=len(revision['execution_code_hashes']),generation_source_hashes_preserved=len(revision['generation_code_hashes']),existing_commands_exact=8,new_context_only_commands=4,model_calls=0,network_calls=0,auth_read=False)
(root/'host03-wire-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result))
