"""Restore an existing03 backup into a fresh07 store; originals remain read-only."""
import json
from pathlib import Path
from roll.runtime.backups import Backups, restore_at_start
from roll.accounts.ledger import Ledger
from roll.market.directory import MarketDirectory, WatchCommand
from roll.market.evidence import EvidenceStore
from roll.research.company import CompanyResearch, CompanyCommand

source = Path('D:/dsh-proj/Roll/.scratch/rv03-real-data')
target = Path('D:/dsh-proj/Roll/.scratch/rv07-real01')
if target.exists():
    raise RuntimeError('Fresh target required')
backups = Backups(source)
available = backups.list()
backup_id = available[0]['backup_id']
raw = backups.export(backup_id)
restore = Backups(target)
restore.stage_restore(raw)
restore_at_start(restore)
ledger = Ledger(target)
market = MarketDirectory(ledger)
research = CompanyResearch(EvidenceStore(ledger, market))
identity = research.resolve('SSE:600362')
company_id = identity['company']['company_id']
market.watch(WatchCommand(instrument='SSE:600362', operation='ADD', expected_list_version=market.listing()['version']))
other = research.register(CompanyCommand(legal_name='承德露露股份公司', aliases=['承德露露'], jurisdiction='CN', accounting_standard='CAS', year_end='12-31', industry='NON_FINANCIAL',
    identity_basis='Reuse ticket05 issuer identity only;07 does not import its financial facts or valuation', listings=[dict(exchange='SZSE',code='000848',share_class='A',currency='CNY')]))
market.watch(WatchCommand(instrument='SZSE:000848', operation='ADD', expected_list_version=market.listing()['version']))
view = research.daily_view(company_id)
receipt = dict(source_backup_id=backup_id, data_directory=str(target), company_id=company_id,
    snapshot_id=view['snapshot']['snapshot_id'], core_sha256=view['snapshot']['core_sha256'],
    second_company_id=other['company_id'], second_company_data='IDENTITY_ONLY_NO_FACTS_OR_SNAPSHOT',
    valuation_status=view['valuation']['status'], original_store_modified=False, account_version=ledger.account()['version'],
    restored_snapshot_count=research.analysis_snapshots(company_id)['total'], network_calls=0, model_calls=0)
Path(__file__).with_name('real-prepare.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(receipt,ensure_ascii=False))
