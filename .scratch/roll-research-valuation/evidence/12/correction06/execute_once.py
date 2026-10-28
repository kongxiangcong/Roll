"""Exactly one same-original correction, shared original16-call durable budget.

New49-fact source-only child and contract1.1 are explicitly different from the
original4d5 wire. No chapters, other companies, generic worker or second retry.
"""
import os,json,hashlib,inspect
from pathlib import Path
from datetime import datetime,timezone
from roll.accounts.ledger import Ledger,encode
from roll.market.directory import MarketDirectory
from roll.market.evidence import EvidenceStore
from roll.research.company import CompanyResearch
from roll.research.company.report_valuation import ReportValuationRuntime
H=Path(__file__).resolve().parent
RUNROOT=Path('D:/dsh-proj/Roll/.scratch/rv12-execution04')
BUDGET=RUNROOT/'budget.json'
STORE=Path('D:/dsh-proj/Roll/.scratch/rv12-capital-prep01')
JOB='ecf287d8-cfe4-4c18-8388-c95d59ac44e6'
SNAPSHOT='50604854-d481-4f98-bc0c-33def10cfe4a'
SHA='692adaf2b2d7b89d98cea163827e2c752c5b29eaef4ad84ee80226386900f983'
AUTH=Path('C:/Users/72449/.codex/auth.json')
for key in list(os.environ):
 if key.startswith(('ROLL_CODEX_','ROLL_DEEPSEEK_')):os.environ.pop(key,None)
def now():return datetime.now(timezone.utc).isoformat()
def save(n,v):(H/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def budget_change(change):
 lock=RUNROOT/'budget.lock';fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
 try:
  budget=json.loads(BUDGET.read_text());change(budget)
  temp=RUNROOT/'correction06-budget.tmp'
  with temp.open('w',encoding='utf-8') as stream:
   json.dump(budget,stream,indent=2);stream.flush();os.fsync(stream.fileno())
  os.replace(temp,BUDGET)
  return budget
 finally:os.close(fd);lock.unlink()
def reserve(b):
 assert b['limit']==16 and b['normal_limit']==14 and b['correction_limit']==2
 assert len(b['attempts'])==2 and all(a['number']==i+1 for i,a in enumerate(b['attempts']))
 assert [a['kind'] for a in b['attempts']]==['LULU_VALUATION_FIRST','JCC_OPERATING_FIRST']
 b['attempts'].append(dict(number=3,kind='LULU_VALUATION_CORRECTION_1',is_correction=True,correction_number=1,command_sha256=SHA,
  job_id=JOB,store=str(STORE),reserved_at=now(),status='RESERVED_COUNTS_EVEN_IF_FAILURE',
  scope='Same12originals/FY25literalcapitalchild49facts+existingcontract1.1clarification; original4d5input/run unchanged'))
def main():
 proof=json.loads((H/'receipt.json').read_text(encoding='utf-8'));root=H.parents[4]/'backend/src/roll'
 for path,sha in proof['code_hashes'].items():assert hashlib.sha256((root/path).read_bytes()).hexdigest()==sha,path
 assert hashlib.sha256((H/'candidate-command.json').read_bytes()).hexdigest()==SHA
 assert Path(inspect.getfile(ReportValuationRuntime)).resolve()==(root/'research/company/report_valuation.py').resolve()
 ledger=Ledger(STORE);research=CompanyResearch(EvidenceStore(ledger,MarketDirectory(ledger)));reports=research.reports
 oldinput=research.analysis_input('4b3229a6-8db4-4b13-b5cd-c7696a3c002a');oldsource=research.analysis_snapshot('c54935d7-760e-4dbd-9156-2f0b4a686a26')
 oldjob=reports.get('9797a495-41a9-4a53-9781-70cc61428841');oldrun=research.analysis_run('fff7d56d-2f44-4d46-9877-a56ab31c4489')
 job=reports.get(JOB)
 assert job['status']=='QUEUED' and job['snapshot_id']==SNAPSHOT and not job['section_ids']
 assert job['valuation_purpose']=='BASELINE_RESEARCH' and job['source_mode']=='REUSE' and job['model']=='gpt-6.1-sol'
 for _ in range(4):
  if job['stage']=='VALUATION':break
  assert job['stage'] in {'ACQUISITION','SHARED_FACTS','ANALYSIS'}
  job=reports.advance(JOB)
 assert job['stage']=='VALUATION' and not job.get('analysis_input_id')
 assert hashlib.sha256(encode(ReportValuationRuntime(reports).command(job)).encode()).hexdigest()==SHA
 assert AUTH.is_file() # File existence only; standard runtime reads ephemeral auth internally.
 b=budget_change(reserve);save('before.json',dict(job=job,budget=b,module_path=inspect.getfile(ReportValuationRuntime),source_hashes=proof['code_hashes'],auth_global=False))
 os.environ['ROLL_CODEX_AUTH_FILE']=str(AUTH);os.environ['ROLL_CODEX_MODEL']='gpt-6.1-sol'
 try:after=reports.advance(JOB)
 finally:os.environ.pop('ROLL_CODEX_AUTH_FILE',None);os.environ.pop('ROLL_CODEX_MODEL',None)
 build=after.get('valuation_build',{});run=research.analysis_run(build['run_id']) if build.get('run_id') else None
 assert run and run['command_sha256']==SHA
 assert research.analysis_input(oldinput['input_id'])==oldinput and research.analysis_snapshot(oldsource['snapshot_id'])==oldsource
 assert reports.get(oldjob['job_id'])==oldjob and research.analysis_run(oldrun['run_id'])==oldrun
 assert not after['section_ids']
 presentations={}
 if build.get('snapshot_id'):
  accepted=research.analysis_snapshot(build['snapshot_id']);save('accepted-child.json',accepted)
  for review in accepted.get('economic_review_ids',[]):
   presentations[review]={p:research.valuation_presentation(review,p) for p in ['CURRENT_PRICING','BASELINE_RESEARCH']}
 save('result.json',dict(job_after=after,build=build,run=run,presentations=presentations,original_input_source_job_run_unchanged=True,
  source_network_calls=0,global_worker_auth_changed=False,chapters_executed=0,account_version=ledger.account()['version'],finished_at=now()))
 for name in ['raw_output_archive','candidate_output_archive','command_archive']:
  if run.get(name):(H/(name+'.raw')).write_bytes(research.evidence.raw(run[name]['sha256']).read_bytes())
 def finish(b):
  entry=b['attempts'][2];assert entry['command_sha256']==SHA and entry['number']==3
  entry.update(status=run['status'],run_id=run['run_id'],model_executed=run.get('model_executed'),finished_at=now())
 save('budget-after.json',budget_change(finish))
 print(json.dumps(dict(run_id=run['run_id'],status=run['status'],build=build,resolved_model=run.get('resolved_model'),provider=run.get('model_provider'),
  model_executed=run.get('model_executed'),error=run.get('error'),command_sha256=run['command_sha256'],budget_used=3,corrections_used=1)),flush=True)
if __name__=='__main__':main()
