"""Freeze and inspect exact report commands locally. NEVER starts a model/worker."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from roll.accounts.ledger import Ledger,encode
from roll.market.directory import MarketDirectory
from roll.market.evidence import EvidenceStore
from roll.research.company import CompanyResearch
from roll.research.company.report_template import SECTIONS


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--data-directory',required=True);parser.add_argument('--job-id',required=True);parser.add_argument('--output-directory',required=True)
    args=parser.parse_args();target=Path(args.output_directory);target.mkdir(parents=True,exist_ok=True)
    ledger=Ledger(Path(args.data_directory));research=CompanyResearch(EvidenceStore(ledger,MarketDirectory(ledger)))
    job=research.reports.get(args.job_id)
    if job['source_mode']!='REUSE' or not job['snapshot_id'] or job['source_quotes'] or job['risk_workpaper']:
        raise RuntimeError('This offline audit only advances pinned REUSE, with no extraction/analysis work')
    for _ in range(4):
        if job['stage']=='CHAPTERS':break
        if job.get('analysis_input_id'):raise RuntimeError('No model-bearing analysis phase may be advanced')
        job=research.reports.advance(job['job_id'])
    if job['stage']!='CHAPTERS' or job['status']!='QUEUED' or job['section_ids']:
        raise RuntimeError('Expected untouched queued chapter stage')
    packet=research.reports.input(job['input_id']);revision=research.reports.revision(job['host_revision_id']) if job.get('host_revision_id') else None;commands=[];findings=[];url_records=[];paths=[];keys=[]
    forbidden={'account','account_id','account_snapshot','holdings','positions','trades','decisions','capabilitygrant','forecastbundle','sealed','access_token','refresh_token','id_token','api_key','password','authorization'}
    absolute=re.compile(r'(?<![A-Za-z])[A-Za-z]:[\\/]|/Users/|/home/')
    secret=re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}|\beyJ[A-Za-z0-9_-]{40,}\.')
    def visit(value,path):
        if isinstance(value,dict):
            for key,child in value.items():
                here=path+'.'+key;keys.append(here)
                if key.casefold() in forbidden:findings.append(dict(kind='SENSITIVE_FIELD_NAME',path=here))
                visit(child,here)
        elif isinstance(value,list):
            for index,child in enumerate(value):visit(child,path+'['+str(index)+']')
        elif isinstance(value,str):
            if absolute.search(value):paths.append(dict(path=path,sample=value[:200]))
            if secret.search(value):findings.append(dict(kind='SECRET_PATTERN',path=path))
            if path.endswith('.source_url'):
                parsed=urlsplit(value)
                url_records.append(dict(path=path,url=value,hostname=parsed.hostname,credentials_present=bool(parsed.username or parsed.password)))
                if parsed.username or parsed.password:findings.append(dict(kind='URL_CREDENTIALS',path=path))
    for sid in SECTIONS:
        preview=research.reports.chapter_preview(job['job_id'],sid);command=preview['command'];wire=encode(command).encode()
        name='command-'+sid+'.json';(target/name).write_bytes(wire)
        prompt=json.loads(command['prompt']);visit(prompt,'command['+sid+'].prompt')
        commands.append(dict(will_execute=not revision or sid not in revision['reusable'],section_id=sid,file=name,sha256=hashlib.sha256(wire).hexdigest(),bytes=len(wire),model=command['model'],tools=command['tools'],
            input_sha256=preview['input_sha256'],instructions_sha256=hashlib.sha256(command['instructions'].encode()).hexdigest(),
            schema_sha256=hashlib.sha256(encode(command['output_schema']).encode()).hexdigest(),top_level_prompt_fields=list(prompt)))
    material_records=[]
    for material in packet['payload']['materials']:
        material_records.append({key:material[key] for key in ['material_id','source_id','source_kind','source_url','raw_sha256','origin_root_id','subject_name','period_start','period_end','received_at','scope','unit','currency']})
    result=dict(kind='OFFLINE_EXACT_COMMAND_REVIEW',job_id=job['job_id'],parent_job_id=job.get('parent_job_id'),stage=job['stage'],status=job['status'],
        model_calls=0,network_calls=0,auth_file_read=False,worker_started=False,input_id=packet['input_id'],input_sha256=packet['packet_sha256'],
        snapshot_id=job['snapshot_id'],core_sha256=packet['payload']['core_sha256'],template_binding=job['template_binding'],
        proposed_destination='OpenAI Codex / existing ChatGPT subscription / gpt-6.1-sol; no new API key',
        proposed_scope='Only four missing bounded chapters; eight existing raw outputs revalidated offline; public annual reports, ChinaBond/NYU/provider historical values and derived research assumptions; zero model tools/account/SEALED content' if revision else 'Twelve bounded report chapters from fixed public research inputs',
        host_revision_id=revision['revision_id'] if revision else None,compiler_version=revision['compiler_version'] if revision else None,
        original_code_hashes=packet['code_hashes'],execution_code_hashes=revision['execution_code_hashes'] if revision else packet['code_hashes'],
        commands=commands,materials=material_records,sensitive_field_or_secret_hits=findings,absolute_path_hits=paths,
        source_urls=sorted({item['url'] for item in url_records}),recursive_field_count=len(keys),account_version=ledger.account()['version'],
        historical_pit_eligible=False,core_origin='Reused ticket05 source-driven snapshot, not a new operating model call',
        current_status=packet['payload']['valuation_presentation']['status'],baseline_status=packet['payload']['valuation_binding']['baseline']['status'])
    (target/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    if revision:(target/'revision.json').write_text(json.dumps(revision,ensure_ascii=False,indent=2),encoding='utf-8')
    (target/'packet.json').write_text(json.dumps(packet,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({key:result[key] for key in ['kind','job_id','stage','status','model_calls','network_calls','auth_file_read','worker_started','input_sha256','sensitive_field_or_secret_hits','absolute_path_hits','account_version']},ensure_ascii=False))


if __name__=='__main__':main()
