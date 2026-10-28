"""Targeted persistence proof for the two new actual model results, no replay."""
import hashlib
import json
from pathlib import Path
import httpx
from roll.runtime.backups import Backups,restore_at_start
from roll.accounts.ledger import Ledger
from roll.market.directory import MarketDirectory
from roll.market.evidence import EvidenceStore
from roll.research.company import CompanyResearch

out=Path(__file__).parent
results=[]
for label,port,target_name,run_id in [
 ('lulu',8032,'rv12-executed-restored04','fff7d56d-2f44-4d46-9877-a56ab31c4489'),
 ('jcc',8033,'rv12-daily-executed-restored04','a572ee2d-62da-428f-a655-a48c1e32d988')]:
    target=Path('D:/dsh-proj/Roll/.scratch')/target_name
    if target.exists():raise RuntimeError('Never overwrite executed recovery evidence')
    with httpx.Client(base_url=f'http://127.0.0.1:{port}',trust_env=False,timeout=100) as c:
        def get(path):
            r=c.get(path);r.raise_for_status();return r.json()
        run=get('/api/company-research/analysis/runs/'+run_id)
        source_id=run.get('source_snapshot_id') or run.get('snapshot_id')
        snapshot=get('/api/company-research/snapshots/'+source_id)
        r=c.post('/api/runtime/backups');r.raise_for_status();backup=r.json()
        r=c.get('/api/runtime/backups/'+backup['backup_id']+'/export');r.raise_for_status();bundle=r.content
    restore=Backups(target);restore.stage_restore(bundle);restore_at_start(restore)
    ledger=Ledger(target)
    research=CompanyResearch(EvidenceStore(ledger,MarketDirectory(ledger)))
    assert research.analysis_run(run_id)==run
    assert research.analysis_snapshot(source_id)==snapshot
    original=research.evidence.raw(run['candidate_output_archive']['sha256']).read_bytes()
    assert hashlib.sha256(original).hexdigest()==run['candidate_output_archive']['sha256']
    if label=='lulu':
        job=research.reports.get('9797a495-41a9-4a53-9781-70cc61428841')
        preview=research.reports.valuation_preview(job['job_id'])
        assert job['valuation_build']['run_id']==run_id and job['valuation_build']['status']=='BLOCKED'
        assert preview['command_sha256']=='4d5ae801204adb12cc09f2c2f2b391bb99d58f639ef34b3db8dff019f67f48fe'
        assert not job['section_ids']
    else:
        daily=research.daily_view('469c1865-a145-4a47-a8ec-3056eeff81a2')
        assert daily['snapshot']['snapshot_id']=='34f7ffea-f855-48b8-9a87-d1e33c4569b1'
        assert research.analysis_snapshot('e28c866f-5fa5-458d-a48a-1ed1869d40ea')['core_sha256']=='cce09e5c244b4a6cdf4293477c6d46d804de46ee4801ce8f5a60f05a4623fc52'
    assert ledger.account()['version']==0
    results.append(dict(label=label,backup_id=backup['backup_id'],bundle_bytes=len(bundle),target=str(target),
        run_id=run_id,status=run['status'],snapshot_id=source_id,raw_sha256=run['candidate_output_archive']['sha256'],
        all_records_equal=True,raw_hash_valid=True,restoration_model_calls=0,source_network_calls=0,auth_read=False))
(out/'authorized04-restore-receipt.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(results))
