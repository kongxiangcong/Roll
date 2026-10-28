"""Copy an already saved recovery bundle read-only to a NEW ticket08 store."""
import argparse
import io
import json
from pathlib import Path
import zipfile
from roll.runtime.backups import Backups,restore_at_start
from roll.accounts.ledger import Ledger,now
from roll.market.directory import MarketDirectory
from roll.market.evidence import EvidenceStore
from roll.research.company import CompanyResearch
from roll.research.company.reports import ReportCommand


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source-backup',required=True)
    parser.add_argument('--data-directory',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--source-plan')
    args=parser.parse_args()
    source=Path(args.source_backup).resolve();target=Path(args.data_directory).resolve()
    if target.exists():raise RuntimeError('Fresh store required; existing research is never reset')
    manifest=json.loads((source/'manifest.json').read_bytes())
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED) as bundle:
        for name in ['manifest.json','roll.sqlite3']+[item['path'] for item in manifest['attachments']]:
            path=(source/name).resolve()
            if not path.is_relative_to(source):raise RuntimeError('Unsafe backup attachment')
            bundle.writestr(name,path.read_bytes())
    restored=Backups(target);restored.stage_restore(buffer.getvalue());restore_at_start(restored)
    ledger=Ledger(target);research=CompanyResearch(EvidenceStore(ledger,MarketDirectory(ledger)))
    company=research.resolve('SZSE:000848')['company']
    with ledger.connection() as db:snapshot=research.analysis.latest(company['company_id'],db)
    plans=json.loads(Path(args.source_plan).read_bytes()) if args.source_plan else []
    for plan in plans:plan['material']['company_id']=company['company_id']
    job=research.reports.start(ReportCommand(company_id=company['company_id'],snapshot_id=snapshot['snapshot_id'],
        as_of=now(),source_mode='REFRESH' if plans else 'REUSE',sources=plans,idempotency_key='rv08-real-report01'))
    receipt=dict(data_directory=str(target),source_backup_id=manifest['backup_id'],original_store_modified=False,
        company_id=company['company_id'],snapshot_id=snapshot['snapshot_id'],core_sha256=snapshot['core_sha256'],
        job_id=job['job_id'],request_cutoff=job['request_cutoff'],snapshot_origin='TICKET05_SOURCE_DRIVEN_NOT_NEW_LLM_OPERATING_ANALYSIS',
        current_status=research.daily_view(company['company_id'],snapshot['snapshot_id'])['valuation']['status'],
        baseline_status=research.valuation_presentation(snapshot['economic_review_ids'][0],'BASELINE_RESEARCH')['status'],
        account_version=ledger.account()['version'],network_calls=0,model_calls=0)
    Path(args.output).write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False))


if __name__=='__main__':main()
