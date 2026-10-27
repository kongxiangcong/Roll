"""Clone the accepted09 public store through Backups; no model/source/auth calls."""
import hashlib,json
from pathlib import Path
from roll.runtime.backups import Backups,restore_at_start
from roll.accounts.ledger import Ledger
from roll.market.directory import MarketDirectory
from roll.market.evidence import EvidenceStore
from roll.research.company import CompanyResearch

root=Path('D:/dsh-proj/Roll/.scratch')
target=root/'rv10-real01'
if target.exists():raise RuntimeError('Target exists; never overwrite prior acceptance evidence')
source=Backups(root/'rv09-real01')
saved=source.create();bundle=source.export(saved['backup_id'])
restored=Backups(target);restored.stage_restore(bundle);restore_at_start(restored)
ledger=Ledger(target);research=CompanyResearch(EvidenceStore(ledger,MarketDirectory(ledger)))
report=research.reports.read('b9cfb2a0-8f93-516a-a4cd-7b7801fd7911')
delivery=research.report_deliveries.read('e3e6e93c-0a17-4bfc-92af-82b86aa86487')
receipt=dict(source='rv09-real01',target=str(target),backup_id=saved['backup_id'],bundle_bytes=len(bundle),report_id=report['report_id'],core_sha256=report['core_sha256'],completeness=report['completeness'],delivery_id=delivery['delivery_id'],account_version=ledger.account()['version'],model_calls=0,source_network_calls=0,auth_read=False)
Path(__file__).with_name('real-store.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt))
