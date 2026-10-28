"""Read/copy actual authorized outputs and shared daily view; no model sends."""
import hashlib
import json
from pathlib import Path
import httpx
from roll.accounts.ledger import Ledger
from roll.market.directory import MarketDirectory
from roll.market.evidence import EvidenceStore
from roll.research.company import CompanyResearch

out=Path(__file__).parent
rawout=out/'authorized04-raw'
rawout.mkdir(exist_ok=True)
records={}
for label,store,receipt in [('lulu','rv12-real01','authorized04-first-result.json'),('jcc','rv12-daily01','authorized04-jcc-result.json')]:
    saved=json.loads((out/receipt).read_text(encoding='utf-8'))
    run=saved['run']
    ledger=Ledger(Path('D:/dsh-proj/Roll/.scratch')/store)
    research=CompanyResearch(EvidenceStore(ledger,MarketDirectory(ledger)))
    assert research.analysis_run(run['run_id'])==run
    assert run['resolved_model']=='gpt-6.1-sol' and run['model_provider']=='openai' and run['tools']==[] and run['model_executed']
    archive=run['candidate_output_archive']
    raw=research.evidence.raw(archive['sha256']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==archive['sha256']
    (rawout/(label+'-candidate.json')).write_bytes(raw)
    records[label]=dict(run_id=run['run_id'],status=run['status'],resolved_model=run['resolved_model'],
        provider=run['model_provider'],elapsed_seconds=run['elapsed_seconds'],raw_sha256=archive['sha256'],
        raw_bytes=len(raw),token_usage=run.get('token_usage'),tools=run['tools'],source_code_hashes=run['code_hashes'] if 'code_hashes' in run else run['execution_code_hashes'])
with httpx.Client(base_url='http://127.0.0.1:8033',trust_env=False,timeout=90) as c:
    cid='469c1865-a145-4a47-a8ec-3056eeff81a2'
    r=c.get('/api/company-research/companies/'+cid+'/daily');r.raise_for_status();daily=r.json()
    assert daily['snapshot']['snapshot_id']=='34f7ffea-f855-48b8-9a87-d1e33c4569b1'
    old=c.get('/api/company-research/snapshots/e28c866f-5fa5-458d-a48a-1ed1869d40ea');old.raise_for_status()
    assert old.json()['core_sha256']=='cce09e5c244b4a6cdf4293477c6d46d804de46ee4801ce8f5a60f05a4623fc52'
    assert not daily['valuation'].get('usable_range',False)
    protection={}
    for path in ['/api/account','/api/research/protocols','/api/research/feature-plans','/api/research/feature-snapshots','/api/capabilities/grants','/api/capabilities/events']:
        r=c.get(path);r.raise_for_status();protection[path]=r.json()
    assert protection['/api/account']['version']==0
with httpx.Client(base_url='http://127.0.0.1:8032',trust_env=False,timeout=90) as c:
    for path,value in json.loads((out/'restart-before.json').read_text(encoding='utf-8')).items():
        if not path.startswith('/api/company-research/reports/') and '/report-deliveries/' not in path:continue
        r=c.get(path);r.raise_for_status();assert r.json()==value
    r=c.get('/api/company-research/jobs/9797a495-41a9-4a53-9781-70cc61428841');r.raise_for_status();lulu_job=r.json()
    assert lulu_job['snapshot_id']=='c54935d7-760e-4dbd-9156-2f0b4a686a26' and lulu_job['valuation_build']['status']=='BLOCKED'
    assert not lulu_job['section_ids']
(out/'authorized04-jcc-daily.json').write_text(json.dumps(daily,ensure_ascii=False,indent=2),encoding='utf-8')
(out/'authorized04-protection.json').write_text(json.dumps(protection,ensure_ascii=False,indent=2),encoding='utf-8')
receipt=dict(actual_runs=records,model_calls_total=2,remaining_hard_budget=14,
    lulu_new_valuation=False,lulu_new_chapters=0,lulu_correction_attempts=0,lulu_job_status=lulu_job['status'],
    jcc_new_snapshot_id=daily['snapshot']['snapshot_id'],jcc_new_core_sha256=daily['snapshot']['core_sha256'],
    jcc_hypotheses=len(daily['snapshot']['core']['hypotheses']),jcc_valuation_usable=False,
    jcc_old_snapshot_unchanged=True,original_reports_delivery_unchanged=True,account_version=0,
    no_global_worker_auth=True,fit_started=False,sealed_read=False)
(out/'authorized04-capture-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(model_calls=2,lulu_status=records['lulu']['status'],jcc_status=records['jcc']['status'],
    jcc_snapshot_id=receipt['jcc_new_snapshot_id'],jcc_core_sha256=receipt['jcc_new_core_sha256'],
    jcc_hypotheses=receipt['jcc_hypotheses'],old_records_unchanged=True),ensure_ascii=False))
