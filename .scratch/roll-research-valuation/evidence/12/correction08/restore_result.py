"""Targeted actual correction result restore: no model replay or source fetch."""
import json,hashlib
from pathlib import Path
import httpx
from roll.runtime.backups import Backups,restore_at_start
from roll.accounts.ledger import Ledger
from roll.market.directory import MarketDirectory
from roll.market.evidence import EvidenceStore
from roll.research.company import CompanyResearch
H=Path(__file__).resolve().parent
target=Path('D:/dsh-proj/Roll/.scratch/rv12-economic-executed-restored08')
assert not target.exists(),'Never overwrite recovery evidence'
with httpx.Client(base_url='http://127.0.0.1:8035',trust_env=False,timeout=100) as c:
 def get(p):
  r=c.get(p);r.raise_for_status();return r.json()
 run=get('/api/company-research/analysis/runs/1527d3f7-8e75-4497-ad99-2e509a09481c')
 snapshot=get('/api/company-research/snapshots/06458222-c6de-497e-88c1-9c8363e74c97')
 packet=get('/api/company-research/analysis/inputs/6b1cbee7-9506-4ca0-afcd-5e7c10b68e9a')
 job=get('/api/company-research/jobs/a72ca482-f162-49cb-b0db-8002fc3d4a85')
 r=c.post('/api/runtime/backups');r.raise_for_status();backup=r.json()
 r=c.get('/api/runtime/backups/'+backup['backup_id']+'/export');r.raise_for_status();bundle=r.content
restore=Backups(target);restore.stage_restore(bundle);restore_at_start(restore)
ledger=Ledger(target);research=CompanyResearch(EvidenceStore(ledger,MarketDirectory(ledger)))
assert research.analysis_run(run['run_id'])==run
assert research.analysis_snapshot(snapshot['snapshot_id'])==snapshot
assert research.analysis_input(packet['input_id'])==packet
assert research.reports.get(job['job_id'])==job and not job['section_ids']
assert job['valuation_build']['status']=='BLOCKED' and not snapshot['valuation_ids']
preview=research.reports.valuation_preview(job['job_id'])
assert preview['command_sha256']=='a5690158f16be0c10b64b6d2110ecf41436ee5d88fe1c856587a85fdd5623b73'
for key in ['candidate_output_archive','command_archive']:
 archive=run[key];raw=research.evidence.raw(archive['sha256']).read_bytes()
 assert hashlib.sha256(raw).hexdigest()==archive['sha256']
 assert raw==(H/(key+'.raw')).read_bytes()
before=json.loads((H.parent/'economic-prep07/original-before.json').read_text(encoding='utf-8'))
assert research.analysis_input(before['input49']['input_id'])==before['input49']
assert research.analysis_snapshot(before['snapshot49']['snapshot_id'])==before['snapshot49']
assert research.reports.get(before['job_correction']['job_id'])==before['job_correction']
for key in ['run_correction','run_first']:assert research.analysis_run(before[key]['run_id'])==before[key]
materials=json.loads((H.parent/'economic-prep07/new-materials.json').read_text(encoding='utf-8'))
for row in materials:
    m=row['material'];assert research.material(m['material_id'])==m
    assert hashlib.sha256(research.evidence.raw(m['archive']['sha256']).read_bytes()).hexdigest()==row['source']['sha256']
assert ledger.account()['version']==0
receipt=dict(backup_id=backup['backup_id'],bundle_bytes=len(bundle),target=str(target),run_id=run['run_id'],status=run['status'],
 snapshot_id=snapshot['snapshot_id'],input_id=packet['input_id'],job_id=job['job_id'],raw_sha256=run['candidate_output_archive']['sha256'],
 archived_preview_sha256=preview['command_sha256'],all_records_equal=True,raw_hash_valid=True,original_objects_equal=True,new3_source_records_and_raw_sha_equal=True,
 model_calls=0,source_network_calls=0,auth_read=False,account_version=0)
(H/'restore-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(json.dumps(receipt))
