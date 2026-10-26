"""Freeze the already audited08.2 commands BEFORE changing host presentation code."""
import argparse
import hashlib
import json
from pathlib import Path
from uuid import uuid4
from roll.accounts.ledger import Ledger,encode
from roll.market.directory import MarketDirectory
from roll.market.evidence import EvidenceStore
from roll.research.company import CompanyResearch
from roll.research.company.report_archive import archive
from roll.research.company.service import record

parser=argparse.ArgumentParser();parser.add_argument('--data-directory',required=True);parser.add_argument('--parent-job',required=True);parser.add_argument('--preview-directory',required=True);parser.add_argument('--output',required=True)
args=parser.parse_args();ledger=Ledger(Path(args.data_directory));research=CompanyResearch(EvidenceStore(ledger,MarketDirectory(ledger)))
job=research.reports.get(args.parent_job)
if job['status']!='CANCELLED':raise RuntimeError('Parent must be durably cancelled')
packet=research.reports.input(job['input_id']);directory=Path(args.preview_directory);audit=json.loads((directory/'audit.json').read_bytes())
commands={}
for entry in audit['commands']:
    wire=(directory/entry['file']).read_bytes()
    if hashlib.sha256(wire).hexdigest()!=entry['sha256']:raise RuntimeError('Audited command bytes changed')
    preview=research.reports.chapter_preview(job['job_id'],entry['section_id'])
    if encode(preview['command']).encode()!=wire:raise RuntimeError('Live original compiler differs from audited command')
    commands[entry['section_id']]=dict(sha256=entry['sha256'],archive=archive(research.evidence,wire,'REPORT_FROZEN_CHAPTER_COMMAND'))
plan=record(dict(plan_id=str(uuid4()),company_id=job['company_id'],parent_job_id=job['job_id'],input_id=packet['input_id'],
    input_sha256=packet['packet_sha256'],model=job['model'],generation_template=packet['template'],
    generation_code_hashes=packet['code_hashes'],generation_algorithm_archives=packet['algorithm_archives'],
    origin='EXACT_HOST_COMPILER_AND_INDEPENDENT_AUDIT_BEFORE_PRESENTATION_REVISION',commands=commands,
    network_calls=0,model_calls=0))
registered=archive(research.evidence,encode(plan).encode(),'REPORT_FROZEN_COMMAND_PLAN')
result=dict(plan=plan,archive=registered)
Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(plan_id=plan['plan_id'],plan_sha256=registered['sha256'],input_sha256=packet['packet_sha256'],commands=len(commands),network_calls=0,model_calls=0)))
