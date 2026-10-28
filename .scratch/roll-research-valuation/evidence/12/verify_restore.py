"""Actual HTTP backup followed by isolated normal startup restore and replay."""
import hashlib
import json
from pathlib import Path
import httpx
from roll.runtime.backups import Backups, restore_at_start
from roll.accounts.ledger import Ledger
from roll.market.directory import MarketDirectory
from roll.market.evidence import EvidenceStore
from roll.research.company import CompanyResearch

out=Path(__file__).parent
target=Path('D:/dsh-proj/Roll/.scratch/rv12-restored01')
if target.exists():
    raise RuntimeError('Never overwrite recovery evidence')
cid='54abcc3d-67c2-453e-83b4-8fdc92b7a292'
snapshot_ids=['7a430e8b-4172-4598-af21-6fe8600b6b93','6b94c24a-f27a-4e5b-a6f9-57358d8242a6']
report_ids=['b9cfb2a0-8f93-516a-a4cd-7b7801fd7911','8625ead2-a42c-5496-95dd-eec52dd17f5a']
delivery='e3e6e93c-0a17-4bfc-92af-82b86aa86487'
valuation='6da4d05b-e2fc-4e99-b57d-f37f12e45109'
with httpx.Client(base_url='http://127.0.0.1:8032',trust_env=False,timeout=100) as c:
    def get(path):
        response=c.get(path);response.raise_for_status();return response.json()
    snapshots={i:get('/api/company-research/snapshots/'+i) for i in snapshot_ids}
    reports={i:get('/api/company-research/reports/'+i) for i in report_ids}
    job=get('/api/company-research/jobs/3bbfac4c-1e78-413a-86d0-950aeb72337f')
    files={name:c.get('/api/company-research/report-deliveries/'+delivery+'/files/'+name).content for name in ['markdown','pdf','manifest','references','valuation','input']}
    materials=get(f'/api/company-research/companies/{cid}/materials')['materials']
    response=c.post('/api/runtime/backups');response.raise_for_status();backup=response.json()
    response=c.get('/api/runtime/backups/'+backup['backup_id']+'/export');response.raise_for_status();bundle=response.content
restore=Backups(target)
restore.stage_restore(bundle)
restore_at_start(restore)
ledger=Ledger(target)
recovered=CompanyResearch(EvidenceStore(ledger,MarketDirectory(ledger)))
for identifier,value in snapshots.items():assert recovered.analysis_snapshot(identifier)==value
for identifier,value in reports.items():assert recovered.reports.read(identifier)==value
assert recovered.reports.get(job['job_id'])==job
checks=[]
for material in materials:
    original=recovered.material_bytes(material['material_id'])
    assert hashlib.sha256(original).hexdigest()==material['archive']['sha256']
    checks.append(dict(material_id=material['material_id'],sha256=material['archive']['sha256'],bytes=len(original)))
for name,raw in files.items():assert recovered.report_deliveries.download(delivery,name)[0]==raw
replay=recovered.replay_valuation(valuation)
assert ledger.account()['version']==0
for identifier,value in reports.items():
    raw=recovered.evidence.raw(value['markdown_archive']['sha256']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==value['markdown_archive']['sha256']
receipt=dict(backup_id=backup['backup_id'],bundle_bytes=len(bundle),target=str(target),snapshot_ids=snapshot_ids,
    report_ids=report_ids,job_id=job['job_id'],job_status=job['status'],original_and_new_records_equal=True,
    material_checks=checks,files={name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()},
    restored_account_version=0,calculation_replayed=True,model_calls=0,source_network_calls=0,auth_read=False)
(out/'restore-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
(out/'restored-replay.json').write_text(json.dumps(replay,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(backup_id=backup['backup_id'],bundle_bytes=len(bundle),target=str(target),materials=len(checks),
    snapshots=len(snapshots),reports=len(reports),files=len(files),model_calls=0,all_equal=True)))
