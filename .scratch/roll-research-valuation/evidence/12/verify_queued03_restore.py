"""Targeted restore of new queued job and unexecuted exact candidate preview."""
import hashlib
import json
from pathlib import Path
import httpx
from roll.runtime.backups import Backups,restore_at_start
from roll.accounts.ledger import Ledger,encode
from roll.market.directory import MarketDirectory
from roll.market.evidence import EvidenceStore
from roll.research.company import CompanyResearch

out=Path(__file__).parent
target=Path('D:/dsh-proj/Roll/.scratch/rv12-queued-restored03')
if target.exists():raise RuntimeError('Never overwrite queued recovery evidence')
job_id='9797a495-41a9-4a53-9781-70cc61428841'
snapshot_id='c54935d7-760e-4dbd-9156-2f0b4a686a26'
report_id='b9cfb2a0-8f93-516a-a4cd-7b7801fd7911'
delivery_id='e3e6e93c-0a17-4bfc-92af-82b86aa86487'
expected_sha='4d5ae801204adb12cc09f2c2f2b391bb99d58f639ef34b3db8dff019f67f48fe'
with httpx.Client(base_url='http://127.0.0.1:8032',trust_env=False,timeout=100) as c:
    def get(path):
        r=c.get(path);r.raise_for_status();return r.json()
    job=get('/api/company-research/jobs/'+job_id)
    assert job['status']=='QUEUED' and not job['section_ids'] and not job.get('valuation_build')
    preview=get('/api/company-research/jobs/'+job_id+'/valuation/preview')
    snapshot=get('/api/company-research/snapshots/'+snapshot_id)
    packet=get('/api/company-research/analysis/inputs/'+snapshot['input_id'])
    report=get('/api/company-research/reports/'+report_id)
    delivery=get('/api/company-research/report-deliveries/'+delivery_id)
    r=c.post('/api/runtime/backups');r.raise_for_status();backup=r.json()
    r=c.get('/api/runtime/backups/'+backup['backup_id']+'/export');r.raise_for_status();bundle=r.content
restore=Backups(target);restore.stage_restore(bundle);restore_at_start(restore)
ledger=Ledger(target)
research=CompanyResearch(EvidenceStore(ledger,MarketDirectory(ledger)))
assert research.reports.get(job_id)==job
assert research.analysis_snapshot(snapshot_id)==snapshot
assert research.analysis_input(packet['input_id'])==packet
assert research.reports.read(report_id)==report
assert research.report_deliveries.read(delivery_id)==delivery
restored_preview=research.reports.valuation_preview(job_id)
assert preview==restored_preview
wire=encode(restored_preview['command']).encode()
assert hashlib.sha256(wire).hexdigest()==preview['command_sha256']==expected_sha
expected_files=json.loads((out/'live-receipt.json').read_text(encoding='utf-8'))['files']
file_shas={}
for name,value in expected_files.items():
    raw=research.report_deliveries.download(delivery_id,name)[0]
    sha=hashlib.sha256(raw).hexdigest();assert sha==value['sha256']
    file_shas[name]=sha
assert ledger.account()['version']==0
receipt=dict(backup_id=backup['backup_id'],bundle_bytes=len(bundle),target=str(target),job_id=job_id,
    job_status=job['status'],job_stage=job['stage'],section_count=0,valuation_attempt_created=False,
    snapshot_id=snapshot_id,input_id=packet['input_id'],input_sha256=packet['packet_sha256'],
    old_report_id=report_id,original_job_snapshot_input_report_delivery_equal=True,old_file_sha256=file_shas,
    actual_preview_sha256=expected_sha,restored_preview_sha256=hashlib.sha256(wire).hexdigest(),
    preview_full_object_equal=True,account_version=0,model_calls=0,source_network_calls=0,auth_read=False,
    source_commit='8dd639145f7daf2146f63ada8b9a5c6069c6bfca',report_worker_remains_paused=True)
(out/'queued03-restore-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:receipt[k] for k in ['backup_id','bundle_bytes','target','job_status','actual_preview_sha256','restored_preview_sha256','model_calls']}))
