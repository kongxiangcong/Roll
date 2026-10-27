"""Append host08.5 without changing any four proposed model wire payloads. Offline only."""
import argparse,json
from pathlib import Path
from roll.accounts.ledger import Ledger
from roll.market.directory import MarketDirectory
from roll.market.evidence import EvidenceStore
from roll.research.company import CompanyResearch
from roll.research.company.report_revisions import RevisionCommand
from roll.research.company.service import fingerprint
p=argparse.ArgumentParser();p.add_argument('--data-directory',required=True);p.add_argument('--old-host-receipt',required=True);p.add_argument('--old-audit-directory',required=True);p.add_argument('--output',required=True);args=p.parse_args()
ledger=Ledger(Path(args.data_directory));research=CompanyResearch(EvidenceStore(ledger,MarketDirectory(ledger)))
prior=json.loads(Path(args.old_host_receipt).read_bytes());old_job=research.reports.get(prior['job_id']);old_revision=research.reports.revision(old_job['host_revision_id']);source=research.reports.get(old_revision['parent_job_id'])
def originals():
 items=dict(source_job=research.reports.get(source['job_id']),input=research.reports.input(source['input_id']),source_sections=research.reports.sections(source),old_host_revision=research.reports.revision(old_revision['revision_id']),old_host_sections=research.reports.sections(research.reports.get(old_job['job_id'])))
 items['source_runs']=[research.analysis.read('report_runs','run_id',s['run_id']) for s in items['source_sections']]
 return items
before=originals()
if old_job['status']!='CANCELLED':cancelled=research.reports.cancel(old_job['job_id'])
else:cancelled=old_job
fields=['section_id','output_sha256','location','index','fact_version_ids','reason','missing_basis']
findings=[{k:f[k] for k in fields} for f in old_revision['findings']]
job=research.reports.revise(RevisionCommand(parent_job_id=source['job_id'],command_plan_sha256=old_revision['original_plan_sha256'],previous_host_revision_id=old_revision['revision_id'],idempotency_key='rv08-host-revalidation05-substantive-summaries',findings=findings))
revision=research.reports.revision(job['host_revision_id']);audit=json.loads((Path(args.old_audit_directory)/'audit.json').read_bytes());compared=[]
for item in audit['commands']:
 preview=research.reports.chapter_preview(job['job_id'],item['section_id'])
 if preview['command_sha256']!=item['sha256']:raise RuntimeError('Proposed model payload changed: '+item['section_id'])
 compared.append(dict(section_id=item['section_id'],sha256=item['sha256'],will_execute=item['will_execute']))
if originals()!=before:raise RuntimeError('Append-only original records changed')
result=dict(job_id=job['job_id'],host_revision_id=revision['revision_id'],previous_host_job_id=old_job['job_id'],previous_host_revision_id=old_revision['revision_id'],old_job_cancelled=cancelled['status']=='CANCELLED',old_immutable_records_unchanged=True,old_immutable_records_sha256=fingerprint(before),data_directory=str(Path(args.data_directory).resolve()),snapshot_origin='TICKET05_SOURCE_DRIVEN_NOT_NEW_LLM_OPERATING_ANALYSIS',input_id=job['input_id'],input_sha256=revision['input_sha256'],core_sha256=revision['core_sha256'],host_version=revision['host_version'],execution_code_hashes=revision['execution_code_hashes'],model_commands_unchanged=compared,missing_model_calls=revision['missing_model_calls'],model_calls=0,network_calls=0,auth_read=False,worker_started=False)
Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:result[k] for k in ['job_id','host_revision_id','host_version','old_job_cancelled','old_immutable_records_unchanged','missing_model_calls','model_calls','network_calls']}))
