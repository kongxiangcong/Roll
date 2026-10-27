"""Unpublished offline draft for review only; never advances missing chapters or inserts a report."""
import json,hashlib
from pathlib import Path
from roll.accounts.ledger import Ledger
from roll.market.directory import MarketDirectory
from roll.market.evidence import EvidenceStore
from roll.research.company import CompanyResearch
from roll.research.company.report_revisions import ReportRevisions
from roll.research.company.report_template import assemble
from roll.research.company.report_quality import check_quality
root=Path('.scratch/roll-research-valuation/evidence/08');ledger=Ledger(Path('D:/dsh-proj/Roll/.scratch/rv08-real02'));research=CompanyResearch(EvidenceStore(ledger,MarketDirectory(ledger)))
prepared=json.loads((root/'host-revision03.json').read_bytes());job=research.reports.get(prepared['job_id']);packet=research.reports.input(job['input_id']);sections=research.reports.sections(job)
if job['report_id'] or {s['section_id'] for s in sections}!={str(i) for i in range(1,9)}:raise RuntimeError('Expected eight offline revalidated chapters and no publication')
view=ReportRevisions(research.reports).presentation_packet(job,packet);markdown=assemble(view,sections,job['job_id'])
quality=check_quality(view,sections,markdown,research.evidence.directory)
if quality['completeness']!='PARTIAL':raise RuntimeError('Unfinished report cannot be full')
text='> 未发布离线预览。仅复用八份已有原输出；四个缺章尚未生成，当前任务待明确授权，不是报告验收。\n\n'+markdown
(root/'offline-preview03.md').write_text(text,encoding='utf-8');(root/'offline-preview03-quality.json').write_text(json.dumps(quality,ensure_ascii=False,indent=2),encoding='utf-8');(root/'offline-sections03.json').write_text(json.dumps(sections,ensure_ascii=False,indent=2),encoding='utf-8')
result=dict(job_id=job['job_id'],published=False,report_id=None,chapter_count=len(sections),core_sha256=packet['payload']['core_sha256'],input_sha256=packet['packet_sha256'],markdown_sha256=hashlib.sha256(text.encode()).hexdigest(),quality='PARTIAL',reference_rule_count=len(quality['reference_rules']),model_calls=0,network_calls=0,auth_read=False)
(root/'offline-preview03.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result))
