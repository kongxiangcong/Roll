"""Reproduce09 local file acceptance; no model, credentials or source requests."""
import json
from pathlib import Path
import hashlib
from roll.accounts.ledger import Ledger
from roll.market.directory import MarketDirectory
from roll.market.evidence import EvidenceStore
from roll.research.company import CompanyResearch
from roll.research.company.report_deliveries import DeliveryCommand
from roll.runtime.backups import Backups, restore_at_start

ROOT=Path('D:/dsh-proj/Roll/.scratch')
OUT=Path(__file__).parent
REPORT='b9cfb2a0-8f93-516a-a4cd-7b7801fd7911'

def research(path):
    ledger=Ledger(path)
    return CompanyResearch(EvidenceStore(ledger,MarketDirectory(ledger)))

def main():
    target=ROOT/'rv09-real01'
    if target.exists():
        raise RuntimeError('Target already exists: do not overwrite a prior acceptance store')
    source=ROOT/'rv08-real02'
    backup=Backups(source)
    saved=backup.create()
    bundle=backup.export(saved['backup_id'])
    restored=Backups(target);restored.stage_restore(bundle);restore_at_start(restored)
    service=research(target)
    original=service.reports.read(REPORT)
    delivery=service.report_deliveries.create(DeliveryCommand(report_id=REPORT,idempotency_key='actual09-01'))
    (OUT/'real-delivery01.json').write_text(json.dumps(delivery,ensure_ascii=False,indent=2),encoding='utf-8')
    if delivery['status']!='COMPLETE':
        raise RuntimeError(delivery['render_error'])
    output=OUT/'output';output.mkdir(exist_ok=True)
    artifacts={}
    for name in ['markdown','pdf','manifest','references','valuation','input']:
        raw,media,filename=service.report_deliveries.download(delivery['delivery_id'],name)
        path=output/filename;path.write_bytes(raw)
        artifacts[name]=dict(path=str(path.resolve()),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),media_type=media)
    assert service.reports.read(REPORT)==original
    (OUT/'real01-receipt.json').write_text(json.dumps(dict(source=str(source),target=str(target),
        source_backup_id=saved['backup_id'],delivery_id=delivery['delivery_id'],report_id=REPORT,
        report_unchanged=True,core_sha256=original['core_sha256'],completeness=original['completeness'],
        artifacts=artifacts,account_version=service.ledger.account()['version'],model_calls=0,source_network_calls=0,auth_read=False),ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(status=delivery['status'],delivery_id=delivery['delivery_id'],pages=delivery['renderer']['pages'],artifacts=artifacts)))

if __name__=='__main__':main()
