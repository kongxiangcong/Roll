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
target=Path('D:/dsh-proj/Roll/.scratch/rv12-correction-restored06')
assert not target.exists(),'Never overwrite recovery evidence'
with httpx.Client(base_url='http://127.0.0.1:8034',trust_env=False,timeout=100) as c:
 def get(p):
  r=c.get(p);r.raise_for_status();return r.json()
 run=get('/api/company-research/analysis/runs/bf290081-a8b0-4441-82e4-21c7bf3aa3dc')
 snapshot=get('/api/company-research/snapshots/50604854-d481-4f98-bc0c-33def10cfe4a')
 packet=get('/api/company-research/analysis/inputs/8877427a-9073-47fc-954c-267023e5b028')
 job=get('/api/company-research/jobs/ecf287d8-cfe4-4c18-8388-c95d59ac44e6')
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
assert preview['command_sha256']=='692adaf2b2d7b89d98cea163827e2c752c5b29eaef4ad84ee80226386900f983'
for key in ['candidate_output_archive','command_archive']:
 archive=run[key];raw=research.evidence.raw(archive['sha256']).read_bytes()
 assert hashlib.sha256(raw).hexdigest()==archive['sha256']
 assert raw==(H/(key+'.raw')).read_bytes()
before=json.loads((H.parent/'capital-prep05/original-before.json').read_text(encoding='utf-8'))
assert research.analysis_input(before['input']['input_id'])==before['input']
assert research.analysis_snapshot(before['snapshot']['snapshot_id'])==before['snapshot']
assert research.reports.get(before['job']['job_id'])==before['job']
assert ledger.account()['version']==0
receipt=dict(backup_id=backup['backup_id'],bundle_bytes=len(bundle),target=str(target),run_id=run['run_id'],status=run['status'],
 snapshot_id=snapshot['snapshot_id'],input_id=packet['input_id'],job_id=job['job_id'],raw_sha256=run['candidate_output_archive']['sha256'],
 archived_preview_sha256=preview['command_sha256'],all_records_equal=True,raw_hash_valid=True,original_objects_equal=True,
 model_calls=0,source_network_calls=0,auth_read=False,account_version=0)
(H/'restore-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(json.dumps(receipt))
