"""Append an offline host revision; never starts workers, auth, network or model."""
import argparse,json,hashlib
from pathlib import Path
from roll.accounts.ledger import Ledger
from roll.market.directory import MarketDirectory
from roll.market.evidence import EvidenceStore
from roll.research.company import CompanyResearch
from roll.research.company.report_revisions import RevisionCommand
from roll.research.company.service import fingerprint

p=argparse.ArgumentParser();p.add_argument('--data-directory',required=True);p.add_argument('--original-plan',required=True);p.add_argument('--output',required=True);args=p.parse_args()
research=CompanyResearch(EvidenceStore(Ledger(Path(args.data_directory)),MarketDirectory(Ledger(Path(args.data_directory)))))
plan=json.loads(Path(args.original_plan).read_bytes());parent=research.reports.get(plan['plan']['parent_job_id']);packet=research.reports.input(parent['input_id'])
originals=dict(job=parent,input=packet,sections=research.reports.sections(parent));originals['runs']=[research.analysis.read('report_runs','run_id',s['run_id']) for s in originals['sections']]
by_id={s['section_id']:s for s in originals['sections']}
findings=[]
def finding(sid,location,index,reason,missing):
 section=by_id[sid];raw=json.loads(research.evidence.raw(section['output_archive']['sha256']).read_bytes());ids=raw['paragraphs'][index]['fact_version_ids'] if location=='PARAGRAPH' else []
 findings.append(dict(section_id=sid,output_sha256=section['output_archive']['sha256'],location=location,index=index,fact_version_ids=ids,reason=reason,missing_basis=missing))
finding('1','PARAGRAPH',3,'存货现金流调节额不能证明报表口径发生变化，原段对此的解释缺乏依据','仍缺会计政策或报表范围变动的原始披露；该金额也不能单独证明终端库存见底')
reason='该章节当时未取得模型参数，不能据此断定整份报告缺少预测假设和情景参数'
missing='固定假设和年度路径已列第九节；其合理性仍须原始经营证据核查，未形成新的共享经营假设集合'
finding('3','PARAGRAPH',0,reason,missing);finding('3','PARAGRAPH',6,reason,missing);finding('3','GAP',0,reason,missing)
job=research.reports.revise(RevisionCommand(parent_job_id=parent['job_id'],command_plan_sha256=plan['archive']['sha256'],idempotency_key='rv08-host-revalidation03-fixed-context',findings=findings))
revision=research.reports.revision(job['host_revision_id'])
current=dict(job=research.reports.get(parent['job_id']),input=research.reports.input(parent['input_id']),sections=research.reports.sections(parent));current['runs']=[research.analysis.read('report_runs','run_id',s['run_id']) for s in current['sections']]
if originals!=current:raise RuntimeError('Append-only boundary violated')
result=dict(job_id=job['job_id'],host_revision_id=revision['revision_id'],revision=revision,parent_job_id=parent['job_id'],input_id=packet['input_id'],input_sha256=packet['packet_sha256'],core_sha256=packet['payload']['core_sha256'],original_records_sha256=fingerprint(originals),old_records_unchanged=True,model_calls=0,network_calls=0,auth_read=False,worker_started=False)
Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:result[k] for k in ['job_id','host_revision_id','parent_job_id','input_sha256','old_records_unchanged','model_calls','network_calls']}))
