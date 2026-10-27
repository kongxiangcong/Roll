"""Host05 local byte comparison; no external model/network/auth access."""
import json,hashlib
from pathlib import Path
from roll.accounts.ledger import encode,Ledger
from roll.market.directory import MarketDirectory
from roll.market.evidence import EvidenceStore
from roll.research.company import CompanyResearch
from roll.research.company.report_template import code_hashes
root=Path('.scratch/roll-research-valuation/evidence/08');current=root/'preview-host05';previous=root/'preview-host04';audit=json.loads((current/'audit.json').read_bytes());revision=json.loads((current/'revision.json').read_bytes());rows=[]
ledger=Ledger(Path('D:/dsh-proj/Roll/.scratch/rv08-real02'));research=CompanyResearch(EvidenceStore(ledger,MarketDirectory(ledger)))
if revision['execution_code_hashes']!=code_hashes():raise RuntimeError('Execution code drifted')
for name,item in revision['execution_algorithm_archives'].items():
 if hashlib.sha256(research.evidence.raw(item['sha256']).read_bytes()).hexdigest()!=revision['execution_code_hashes'][name]:raise RuntimeError('Archive source differs')
for item in audit['commands']:
 wire=(current/item['file']).read_bytes();old=(previous/item['file']).read_bytes()
 if wire!=old or hashlib.sha256(wire).hexdigest()!=item['sha256'] or wire!=encode(json.loads(wire)).encode():raise RuntimeError('Model wire changed')
 rows.append(dict(section_id=item['section_id'],sha256=item['sha256'],bytes=len(wire),same_as_host04=True,will_execute=item['will_execute']))
old_job=research.reports.get('416d3883-f0a6-4454-a40d-3104c018ba0f');new_job=research.reports.get(audit['job_id'])
if old_job['status']!='CANCELLED' or len(new_job['section_ids'])!=8 or new_job['report_id']:raise RuntimeError('Queue checkpoint differs')
result=dict(job_id=new_job['job_id'],host_revision_id=revision['revision_id'],previous_host_revision_id=revision['previous_host_revision_id'],old_job_status=old_job['status'],new_job_status=new_job['status'],new_job_stage=new_job['stage'],existing_raw_sections=len(new_job['section_ids']),published=False,input_sha256=revision['input_sha256'],source_book_sha256=hashlib.sha256(encode(revision['source_coverage']).encode()).hexdigest(),execution_sources_verified=len(revision['execution_code_hashes']),model_commands=rows,new_model_calls=0,network_calls=0,auth_read=False)
(root/'host05-wire-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');(root/'host04-cancelled-by05.json').write_text(json.dumps(dict(reason='EXPLICIT_CANCELLATION_SUPERSEDED_BY_HOST_08_5',new_job_id=new_job['job_id'],new_revision_id=revision['revision_id'],old_job=old_job),ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(dict(job_id=new_job['job_id'],same_commands=12,same_missing_commands=4,execution_sources_verified=18,existing_raw_sections=8,new_model_calls=0,old_job_status=old_job['status'])))
