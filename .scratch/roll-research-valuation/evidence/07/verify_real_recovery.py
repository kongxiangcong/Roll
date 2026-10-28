"""Register early07 legacy originals without changing runs, then verify actual recovery."""
import json,hashlib
from pathlib import Path
from roll.accounts.ledger import Ledger
from roll.market.directory import MarketDirectory
from roll.market.evidence import EvidenceStore
from roll.research.company import CompanyResearch
from roll.runtime.assistance import Assistance
from roll.runtime.backups import Backups,restore_at_start

source=Path('D:/dsh-proj/Roll/.scratch/rv07-real01')
target=Path('D:/dsh-proj/Roll/.scratch/rv07-real-restored01')
if target.exists():
    raise RuntimeError('Fresh restore target required')
ledger=Ledger(source);evidence=EvidenceStore(ledger,MarketDirectory(ledger));research=CompanyResearch(evidence)
assistance=Assistance(ledger)
run_ids=['2becf239-5f19-42a7-95ed-19c898550c96','0d3e916d-5d09-41ba-a9f5-fc5a7ca5028c']
runs=[assistance.get(identifier) for identifier in run_ids]
originals=[]
for run in runs:
    for fact in run['sources']:
        # Initial real07 runs preceded the new archive-authority adapter. Preserve
        # their exact bytes and original receipt; do not rewrite their saved packet.
        raw=(source/'assistance-raw'/(fact['sha256']+'.bin')).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==fact['sha256']
        archive=evidence.archive(raw,'ASSISTANCE_DAILY_ORIGINAL',received_at=fact['received_at'],source_id=fact['source_id'],provider=fact['provider'])
        originals.append(dict(run_id=run['run_id'],source_id=fact['source_id'],sha256=fact['sha256'],archive=archive))
company_id='469c1865-a145-4a47-a8ec-3056eeff81a2';snapshot_id='e28c866f-5fa5-458d-a48a-1ed1869d40ea'
before=research.daily_view(company_id,snapshot_id)
backups=Backups(source);backup=backups.create();bundle=backups.export(backup['backup_id'])
restore=Backups(target);restore.stage_restore(bundle);restore_at_start(restore)
saved_ledger=Ledger(target);saved_evidence=EvidenceStore(saved_ledger,MarketDirectory(saved_ledger));saved=CompanyResearch(saved_evidence)
after=saved.daily_view(company_id,snapshot_id)
assert after['snapshot']==before['snapshot']==saved.analysis_snapshot(snapshot_id,'REPORT')
restored_assistance=Assistance(saved_ledger)
for old in runs:
    assert restored_assistance.get(old['run_id'])==old
    material=old['material']
    assert hashlib.sha256(__import__('roll.accounts.ledger',fromlist=['encode']).encode(material).encode()).hexdigest()==old['assessment']['material_sha256']
for original in originals:
    assert hashlib.sha256(saved_evidence.raw(original['sha256']).read_bytes()).hexdigest()==original['sha256']
assert saved_ledger.account()['version']==0
receipt=dict(source_directory=str(source),restore_directory=str(target),backup_id=backup['backup_id'],
    bundle_sha256=hashlib.sha256(bundle).hexdigest(),snapshot_id=snapshot_id,core_sha256=after['snapshot']['core_sha256'],
    saved_run_ids=run_ids,originals=originals,immutable_runs_preserved=True,DAILY_REPORT_same_core=True,
    saved_checks_preserved=after['latest_checks']==before['latest_checks'],account_version=0,network_calls=0,model_calls=0)
Path(__file__).with_name('real-recovery.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in receipt.items() if k!='originals'},ensure_ascii=False))
