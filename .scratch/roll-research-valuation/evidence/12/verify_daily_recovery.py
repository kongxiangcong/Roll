"""Restore actual new public acquisitions and missing-auth analysis checkpoint."""
import hashlib
import json
from pathlib import Path
import httpx
from roll.runtime.backups import Backups,restore_at_start
from roll.app import create_app

out=Path(__file__).parent
target=Path('D:/dsh-proj/Roll/.scratch/rv12-daily-restored01')
if target.exists():raise RuntimeError('Never overwrite recovery evidence')
probe=json.loads((out/'public-probe-result.json').read_text(encoding='utf-8'))
job=probe['job']
observation=next(o for o in probe['observations'] if o['observation_id']==job['observation_id'])
payload=observation['payload']
with httpx.Client(base_url='http://127.0.0.1:8033',trust_env=False,timeout=100) as c:
    def get(path):
        r=c.get(path);r.raise_for_status();return r.json()
    run=get('/api/company-research/analysis/runs/'+payload['analysis_run_id'])
    assert run['status']=='UNAVAILABLE' and run['model_executed'] is False
    packet=get('/api/company-research/analysis/inputs/'+payload['analysis_input_id'])
    facts={i:get('/api/company-research/facts/'+i) for i in payload['financial_adaptation']['fact_version_ids']}
    materials={f['material_id']:get('/api/company-research/materials/'+f['material_id']) for f in facts.values()}
    snapshot=get('/api/company-research/snapshots/'+payload['snapshot_id'])
    r=c.post('/api/runtime/backups');r.raise_for_status();backup=r.json()
    r=c.get('/api/runtime/backups/'+backup['backup_id']+'/export');r.raise_for_status();bundle=r.content
restore=Backups(target);restore.stage_restore(bundle);restore_at_start(restore)
app=create_app(target,runtime_role='API')
research=app.state.company_research
assert app.state.observation_updates.get(job['job_id'])==job
assert research.analysis_run(run['run_id'])==run
assert research.analysis_input(packet['input_id'])==packet
assert research.analysis_snapshot(snapshot['snapshot_id'])==snapshot
for identifier,fact in facts.items():assert research.fact(identifier)==fact
for identifier,material in materials.items():
    assert research.material(identifier)==material
    assert hashlib.sha256(research.material_bytes(identifier)).hexdigest()==material['archive']['sha256']
assert app.state.ledger.account()['version']==0
receipt=dict(backup_id=backup['backup_id'],bundle_bytes=len(bundle),target=str(target),job_id=job['job_id'],
    job_status=job['status'],analysis_run_id=run['run_id'],analysis_status=run['status'],model_executed=False,
    fact_count=len(facts),material_count=len(materials),all_records_equal=True,all_material_hashes_valid=True,
    original_snapshot_id=snapshot['snapshot_id'],original_core_sha256=snapshot['core_sha256'],account_version=0,
    model_calls=0,source_network_calls=0,auth_read=False,sealed_read=False,natural_cycles=0)
(out/'daily-recovery-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(receipt))
