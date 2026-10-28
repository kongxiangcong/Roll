"""One-shot executor for the explicitly authorized frozen batch; no global auth.

Every possible model send reserves a durable slot first, including failures.
This entry initially permits only Lulu's exact first valuation candidate.
"""
import hashlib
import json
import os
import sys
from datetime import datetime,timezone
from pathlib import Path
from roll.accounts.ledger import Ledger,encode
from roll.market.directory import MarketDirectory
from roll.market.evidence import EvidenceStore
from roll.research.company import CompanyResearch
from roll.research.company.report_valuation import ReportValuationRuntime

OUT=Path(__file__).parent
RUNROOT=Path('D:/dsh-proj/Roll/.scratch/rv12-execution04')
RUNROOT.mkdir(exist_ok=True)
BUDGET=RUNROOT/'budget.json'
JOB='9797a495-41a9-4a53-9781-70cc61428841'
FIRST='4d5ae801204adb12cc09f2c2f2b391bb99d58f639ef34b3db8dff019f67f48fe'
JCC='a10d0bfd5249b96fc7cd9af37e2a99fc92e5e3cc0f25334339fe6e0d3a4f208f'
AUTH=Path('C:/Users/72449/.codex/auth.json')
for key in list(os.environ):
    if key.startswith(('ROLL_CODEX_','ROLL_DEEPSEEK_')):os.environ.pop(key,None)

def now():return datetime.now(timezone.utc).isoformat()
def reserve(kind,sha):
    lock=RUNROOT/'budget.lock'
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    try:
        budget=json.loads(BUDGET.read_text()) if BUDGET.exists() else dict(limit=16,normal_limit=14,correction_limit=2,attempts=[])
        if len(budget['attempts'])>=16:raise RuntimeError('AUTHORIZED_BATCH_BUDGET_EXHAUSTED')
        if any(a['kind']==kind for a in budget['attempts']):raise RuntimeError('EXPLICIT_CORRECTION_REQUIRED_NO_SILENT_RETRY')
        entry=dict(number=len(budget['attempts'])+1,kind=kind,command_sha256=sha,reserved_at=now(),status='RESERVED_COUNTS_EVEN_IF_FAILURE')
        budget['attempts'].append(entry)
        BUDGET.write_text(json.dumps(budget,indent=2),encoding='utf-8')
        return entry
    finally:
        os.close(fd);lock.unlink()

def main():
    mode=sys.argv[1]
    if mode not in {'lulu-first','jcc-first'}:raise RuntimeError('Only specifically enabled frozen first candidates are executable')
    expected=json.loads((OUT/'next-request-preview03/actual-preview-receipt.json').read_text(encoding='utf-8'))
    source_root=Path(__file__).resolve().parents[4]/'backend/src/roll'
    for path,sha in expected['code_hashes'].items():
        assert hashlib.sha256((source_root/path).read_bytes()).hexdigest()==sha,path
    assert hashlib.sha256((OUT/'next-request-preview03/lulu-valuation-command.wire.json').read_bytes()).hexdigest()==FIRST
    assert hashlib.sha256((OUT/'next-request-preview/jcc-operating-analysis.wire.json').read_bytes()).hexdigest()==JCC
    assert AUTH.is_file()  # no authentication contents are printed or inspected here
    if mode=='jcc-first':
        from roll.agents.company_analysis_runtime import command
        from roll.research.company.model_runtime import AnalysisRuntime
        ledger=Ledger(Path('D:/dsh-proj/Roll/.scratch/rv12-daily01'))
        research=CompanyResearch(EvidenceStore(ledger,MarketDirectory(ledger)))
        packet=research.analysis_input('4b2f8962-30d7-447e-a9db-ae2f077b783f')
        wire=encode(command(dict(model='gpt-6.1-sol'),packet)).encode()
        assert hashlib.sha256(wire).hexdigest()==JCC
        before=research.analysis_snapshot('e28c866f-5fa5-458d-a48a-1ed1869d40ea')
        reservation=reserve('JCC_OPERATING_FIRST',JCC)
        os.environ['ROLL_CODEX_AUTH_FILE']=str(AUTH)
        os.environ['ROLL_CODEX_MODEL']='gpt-6.1-sol'
        try:
            run=AnalysisRuntime(research).execute(packet['input_id'],timeout_seconds=90,model='gpt-6.1-sol')
        finally:
            os.environ.pop('ROLL_CODEX_AUTH_FILE',None)
            os.environ.pop('ROLL_CODEX_MODEL',None)
        assert research.analysis_snapshot(before['snapshot_id'])==before
        receipt=dict(reservation=reservation,run=run,original_snapshot_unchanged=True,
            global_worker_auth_changed=False,source_network_calls=0,account_version=ledger.account()['version'],finished_at=now())
        (OUT/'authorized04-jcc-result.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
        (OUT/'authorized04-budget02-snapshot.json').write_bytes(BUDGET.read_bytes())
        print(json.dumps(dict(run_id=run['run_id'],status=run['status'],model_executed=run.get('model_executed'),
            resolved_model=run.get('resolved_model'),provider=run.get('model_provider'),snapshot_id=run.get('snapshot_id'),
            error=run.get('error'),budget_reserved=len(json.loads(BUDGET.read_text())['attempts'])),ensure_ascii=False),flush=True)
        return
    ledger=Ledger(Path('D:/dsh-proj/Roll/.scratch/rv12-real01'))
    research=CompanyResearch(EvidenceStore(ledger,MarketDirectory(ledger)))
    reports=research.reports
    job=reports.get(JOB)
    assert job['status']=='QUEUED' and not job['section_ids'] and job['snapshot_id']=='c54935d7-760e-4dbd-9156-2f0b4a686a26'
    assert job['valuation_purpose']=='BASELINE_RESEARCH' and job['source_mode']=='REUSE'
    for _ in range(4):
        if job['stage']=='VALUATION':break
        assert job['stage'] in {'ACQUISITION','SHARED_FACTS','ANALYSIS'},job['stage']
        job=reports.advance(JOB)
    assert job['stage']=='VALUATION' and not job.get('analysis_input_id')
    wire=encode(ReportValuationRuntime(reports).command(job)).encode()
    assert hashlib.sha256(wire).hexdigest()==FIRST
    reservation=reserve('LULU_VALUATION_FIRST',FIRST)
    (OUT/'authorized04-before.json').write_text(json.dumps(dict(job=job,reservation=reservation,source_hashes=expected['code_hashes']),ensure_ascii=False,indent=2),encoding='utf-8')
    os.environ['ROLL_CODEX_AUTH_FILE']=str(AUTH)
    os.environ['ROLL_CODEX_MODEL']='gpt-6.1-sol'
    try:
        after=reports.advance(JOB)
    finally:
        os.environ.pop('ROLL_CODEX_AUTH_FILE',None)
        os.environ.pop('ROLL_CODEX_MODEL',None)
    build=after.get('valuation_build',{})
    run=research.analysis_run(build['run_id']) if build.get('run_id') else None
    receipt=dict(authorized_by='Human explicit reply 授权 to one14+2scope question; coordination257dcbaa',
        reservation=reservation,job_after=after,valuation_build=build,run=run,finished_at=now(),
        auth_global_worker_changed=False,source_network_calls=0,account_version=ledger.account()['version'])
    (OUT/'authorized04-first-result.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'authorized04-budget-snapshot.json').write_bytes(BUDGET.read_bytes())
    print(json.dumps(dict(job_id=JOB,job_status=after['status'],stage=after['stage'],build=build,
        run_status=run['status'] if run else None,resolved_model=run.get('resolved_model') if run else None,
        command_sha256=run.get('command_sha256') if run else None,model_executed=run.get('model_executed') if run else None,
        error=run.get('error') if run else None,budget_reserved=len(json.loads(BUDGET.read_text())['attempts'])),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
