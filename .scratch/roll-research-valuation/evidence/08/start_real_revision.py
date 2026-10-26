"""Create an explicit new report revision after a cancelled host-validation failure."""
import argparse
import json
from pathlib import Path
from roll.accounts.ledger import Ledger,now
from roll.market.directory import MarketDirectory
from roll.market.evidence import EvidenceStore
from roll.research.company import CompanyResearch
from roll.research.company.reports import ReportCommand

parser=argparse.ArgumentParser();parser.add_argument('--data-directory',required=True);parser.add_argument('--parent-job',required=True);parser.add_argument('--output',required=True)
args=parser.parse_args();directory=Path(args.data_directory);ledger=Ledger(directory)
research=CompanyResearch(EvidenceStore(ledger,MarketDirectory(ledger)));parent=research.reports.get(args.parent_job)
if parent['status']!='CANCELLED':raise RuntimeError('Parent cancellation must be durable before a new version')
materials=[r['material_id'] for r in parent['acquisition']['receipts'] if r.get('material_id')]
job=research.reports.start(ReportCommand(company_id=parent['company_id'],snapshot_id=parent['snapshot_id'],as_of=now(),
    source_mode='REUSE',parent_job_id=parent['job_id'],additional_material_ids=materials,idempotency_key='rv08-real-report02-subheads'))
snapshot=research.analysis_snapshot(job['snapshot_id'])
receipt=dict(data_directory=str(directory.resolve()),job_id=job['job_id'],parent_job_id=parent['job_id'],parent_status=parent['status'],
    company_id=job['company_id'],snapshot_id=job['snapshot_id'],core_sha256=snapshot['core_sha256'],
    snapshot_origin='TICKET05_SOURCE_DRIVEN_NOT_NEW_LLM_OPERATING_ANALYSIS',template_binding=job['template_binding'],
    parent_source_check_ids=[r['check_id'] for r in parent['acquisition']['receipts']],additional_material_ids=materials,
    parent_section_count=len(parent['section_ids']),network_calls=0,model_calls=0,original_store_modified=False,
    current_status=research.daily_view(job['company_id'],job['snapshot_id'])['valuation']['status'],
    baseline_status=research.valuation_presentation(snapshot['economic_review_ids'][0],'BASELINE_RESEARCH')['status'])
Path(args.output).write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(receipt,ensure_ascii=False))
