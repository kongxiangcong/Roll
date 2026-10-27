"""Advance only previously generated raw outputs offline. Refuse any model-bearing stage."""
import json
from pathlib import Path
from roll.accounts.ledger import Ledger
from roll.market.directory import MarketDirectory
from roll.market.evidence import EvidenceStore
from roll.research.company import CompanyResearch
from roll.research.company.report_template import SECTIONS
from roll.research.company.service import fingerprint
root=Path('.scratch/roll-research-valuation/evidence/08');prepared=json.loads((root/'host-revision05.json').read_bytes());ledger=Ledger(Path('D:/dsh-proj/Roll/.scratch/rv08-real02'));research=CompanyResearch(EvidenceStore(ledger,MarketDirectory(ledger)))
job=research.reports.get(prepared['job_id']);revision=research.reports.revision(job['host_revision_id']);parent=research.reports.get(job['parent_job_id'])
old=dict(job=parent,input=research.reports.input(parent['input_id']),sections=research.reports.sections(parent));old['runs']=[research.analysis.read('report_runs','run_id',s['run_id']) for s in old['sections']]
def count():
 with ledger.connection() as db:return db.execute('SELECT count(*) FROM company_research_report_runs').fetchone()[0]
before=count()
for _ in range(8):
 done={s['section_id'] for s in research.reports.sections(job)};sid=next(sid for sid in SECTIONS if sid not in done)
 if sid not in revision['reusable']:break
 if job['stage']!='CHAPTERS' or job['status']!='QUEUED':raise RuntimeError('Not a queued offline revalidation checkpoint')
 job=research.reports.advance(job['job_id'])
 if job['status']!='QUEUED':raise RuntimeError(str(job))
sections=research.reports.sections(job);current=dict(job=research.reports.get(parent['job_id']),input=research.reports.input(parent['input_id']),sections=research.reports.sections(parent));current['runs']=[research.analysis.read('report_runs','run_id',s['run_id']) for s in current['sections']]
if old!=current or before!=count():raise RuntimeError('Offline append changed originals or created model attempts')
result=dict(job_id=job['job_id'],host_revision_id=revision['revision_id'],stage=job['stage'],status=job['status'],chapter_statuses={s['section_id']:s['status'] for s in sections},new_model_runs=0,new_model_calls=0,network_calls=0,auth_read=False,original_records_equal=True,original_records_sha256=fingerprint(old),remaining=['9','10','REVIEW','CHALLENGE'],section_ids=job['section_ids'])
(root/'offline-revalidation05.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result))
