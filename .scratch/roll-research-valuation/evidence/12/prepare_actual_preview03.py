"""Read the real browser job and pure-local valuation preview; never execute."""
import hashlib
import json
from pathlib import Path
import httpx
from roll.accounts.ledger import encode
from roll.research.company.report_template import code_hashes

out=Path(__file__).parent/'next-request-preview03'
out.mkdir(exist_ok=True)
job_id='9797a495-41a9-4a53-9781-70cc61428841'
snapshot_id='c54935d7-760e-4dbd-9156-2f0b4a686a26'
with httpx.Client(base_url='http://127.0.0.1:8032',trust_env=False,timeout=90) as c:
    def get(path):
        r=c.get(path);r.raise_for_status();return r.json()
    job=get('/api/company-research/jobs/'+job_id)
    assert job['status']=='QUEUED' and job['stage']=='ACQUISITION' and not job['section_ids']
    assert job['snapshot_id']==snapshot_id and job['valuation_purpose']=='BASELINE_RESEARCH' and job['source_mode']=='REUSE'
    preview=get('/api/company-research/jobs/'+job_id+'/valuation/preview')
    assert preview['model_calls']==preview['network_calls']==0
    command=preview['command'];wire=encode(command).encode()
    assert hashlib.sha256(wire).hexdigest()==preview['command_sha256'] and command['tools']==[]
    prompt=json.loads(command['prompt'])
    assert prompt['snapshot']['snapshot_id']==snapshot_id and not prompt['snapshot'].get('economic_review_ids')
    assert not prompt['snapshot']['valuation_ids']
    assert prompt['valuation_purpose']=='BASELINE_RESEARCH'
    snapshot=get('/api/company-research/snapshots/'+snapshot_id)
    packet=get('/api/company-research/analysis/inputs/'+snapshot['input_id'])
    assert prompt['evidence']==packet['payload']
    old_report=get('/api/company-research/reports/b9cfb2a0-8f93-516a-a4cd-7b7801fd7911')
    assert old_report['snapshot_id']=='7a430e8b-4172-4598-af21-6fe8600b6b93'
    for name,value in [('actual-browser-job',job),('actual-valuation-preview',preview),('actual-unvalued-snapshot',snapshot),('actual-analysis-input',packet)]:
        (out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
(out/'lulu-valuation-command.wire.json').write_bytes(wire)
(out/'lulu-valuation-command.pretty.json').write_text(json.dumps(command,ensure_ascii=False,indent=2),encoding='utf-8')
prior=out.parent.parent/'final-review-fix'/'lulu-candidate-preview'/'command.json'
static=json.loads(prior.read_bytes())
static_prompt=json.loads(static['prompt'])
differences={k:dict(static=static_prompt.get(k),actual=prompt.get(k)) for k in set(static_prompt)|set(prompt) if static_prompt.get(k)!=prompt.get(k)}
assert all(command[k]==static[k] for k in ['model','tools','instructions','output_schema'])
assert set(differences)=={'request_cutoff'}
assert prompt['request_cutoff']==job['request_cutoff']
source_map=code_hashes()
source_root=Path(__file__).resolve().parents[4]/'backend/src/roll'
for name in ['research/company/report_valuation.py','agents/company_valuation_runtime.py','research/company/valuation_candidate_contract.md',
             'research/company/economics.py','research/company/valuation.py','research/company/calculator.py',
             'research/company/valuation_reference/fundamental_valuation.py']:
    source_map[name]=hashlib.sha256((source_root/name).read_bytes()).hexdigest()
for name,sha in source_map.items():
    assert hashlib.sha256((source_root/name).read_bytes()).hexdigest()==sha
jcc=out.parent/'next-request-preview'/'jcc-operating-analysis.wire.json'
assert hashlib.sha256(jcc.read_bytes()).hexdigest()=='a10d0bfd5249b96fc7cd9af37e2a99fc92e5e3cc0f25334339fe6e0d3a4f208f'
receipt=dict(kind='ACTUAL_BROWSER_QUEUED_JOB_LOCAL_PREVIEW_ONLY',job_id=job_id,snapshot_id=snapshot_id,
    job_status=job['status'],job_stage=job['stage'],request_cutoff=job['request_cutoff'],valuation_purpose=job['valuation_purpose'],
    source_mode=job['source_mode'],core_sha256=snapshot['core_sha256'],source_snapshot_sha256=snapshot['content_sha256'],
    analysis_input_id=packet['input_id'],analysis_input_sha256=packet['packet_sha256'],fact_count=len(packet['payload']['facts']),
    command_bytes=len(wire),command_sha256=preview['command_sha256'],static_command_sha256=hashlib.sha256(prior.read_bytes()).hexdigest(),
    command_nonprompt_fields_equal=True,prompt_differences=differences,code_hashes=source_map,
    report_worker_paused=True,model_calls=0,source_network_calls=0,auth_reads=0,
    prepared_from_browser='Chrome132238161; input000848; explicitBASELINE_RESEARCH/nonPIT; selectedoriginalc54935; REUSE',
    date_input_note='Attempted02:36 typed value was not persisted by browser form; actual saved request is00:50UTC Oct28, valid and later than source cutoff. Actual preview is authoritative.',
    jcc_command_sha256=hashlib.sha256(jcc.read_bytes()).hexdigest(),
    exposure='Public issuer source facts, host-derived facts/assumptions and internal research IDs; subsequent accepted candidate may add research forecasts. No existing valuation/result supplied.',
    exclusions=['Account/holdings/events','SEALED','Credentials','Old experiment budget/training writes','Source tools/files/browser/MCP/skills/subagents'],
    execution_scope_proposal=dict(destination='OpenAI via existing ChatGPT subscription CODEX',model='gpt-6.1-sol',tools=[],
        lulu_valuation_candidate=1,lulu_fixed_chapters=12,jcc_operating_analysis=1,total_normal_turns=14,
        additional_correction_attempts_maximum=2,total_turns_maximum=16,per_turn_seconds=90,runtime_operations=8,
        chapters='1-10, REVIEW, CHALLENGE only after candidate accepted and one derived fixed report input frozen',
        scope_limit='Same frozen companies/source packets and original facts; forecasts/IDs derived solely from accepted candidate. No broad source refresh or globally enabled daily auth.',
        not_send_authorization=True))
(out/'actual-preview-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:receipt[k] for k in ['job_id','job_status','request_cutoff','command_bytes','command_sha256','static_command_sha256','prompt_differences','model_calls']}))
