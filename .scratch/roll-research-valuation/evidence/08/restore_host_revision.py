"""Public backup/recovery proof, independent target directory, no auth/model/network."""
import argparse,json,hashlib
from pathlib import Path
from roll.runtime.backups import Backups,restore_at_start
from roll.accounts.ledger import Ledger
from roll.market.evidence import EvidenceStore
from roll.market.directory import MarketDirectory
from roll.research.company import CompanyResearch
from roll.research.company.service import fingerprint
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--target',required=True);p.add_argument('--job-id',required=True);p.add_argument('--output',required=True);args=p.parse_args()
source=Path(args.source).resolve();target=Path(args.target).resolve()
if target.exists():raise RuntimeError('Recovery proof requires a fresh target; never replaces data')
def service(path):
 ledger=Ledger(path);return CompanyResearch(EvidenceStore(ledger,MarketDirectory(ledger)))
research=service(source);job=research.reports.get(args.job_id);revision=research.reports.revision(job['host_revision_id']);packet=research.reports.input(job['input_id'])
def evidence(research):
 j=research.reports.get(args.job_id);r=research.reports.revision(j['host_revision_id']);sections=research.reports.sections(j);runs=[research.analysis.read('report_runs','run_id',s['run_id']) for s in sections]
 result=dict(job=j,revision=r,input=research.reports.input(j['input_id']),sections=sections,runs=runs)
 if j['report_id']:result.update(report=research.reports.read(j['report_id']),markdown=research.reports.markdown(j['report_id']))
 return result
before=evidence(research);backups=Backups(source);backup=backups.create();bundle=backups.export(backup['backup_id'])
restore=Backups(target);restore.stage_restore(bundle);restore_at_start(restore);recovered=service(target);after=evidence(recovered)
if before!=after:raise RuntimeError('Recovery changed bound report/revision/input/raw references')
archives=[r['execution_algorithm_archives'] for r in [revision]]+[packet['algorithm_archives']]
count=0
for values in archives:
 for metadata in values.values():
  raw=recovered.evidence.raw(metadata['sha256']).read_bytes()
  if hashlib.sha256(raw).hexdigest()!=metadata['sha256']:raise RuntimeError('Recovered algorithm bytes differ')
  count+=1
for item in revision['commands'].values():
 if recovered.evidence.raw(item['sha256']).read_bytes()!=research.evidence.raw(item['sha256']).read_bytes():raise RuntimeError('Recovered command bytes differ')
result=dict(backup_id=backup['backup_id'],target=str(target),job_id=job['job_id'],host_revision_id=revision['revision_id'],status=job['status'],stage=job['stage'],records_equal=True,record_sha256=fingerprint(before),algorithm_archives_verified=count,commands_verified=len(revision['commands']),bundle_bytes=len(bundle),model_calls=0,network_calls=0,auth_read=False,source_account_version=research.ledger.account()['version'],restored_account_version=recovered.ledger.account()['version'])
Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result))
