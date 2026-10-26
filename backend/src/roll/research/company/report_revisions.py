"""Append-only host revalidation. No old input, attempt or section is rewritten."""
import ast
import copy
import hashlib
import json
from pathlib import Path
from typing import Literal
from uuid import uuid4,uuid5,NAMESPACE_URL
from pydantic import Field
from roll.accounts.ledger import encode,now
from .models import Command
from .service import record,verified,fingerprint,fail
from .report_archive import archive
from .report_template import SECTIONS,code_hashes,reference_text,table,cell

VERSION='08.3'
COMPILER='fixed-packet-context-2'


class NegativeFinding(Command):
    section_id:str
    output_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
    location:Literal['PARAGRAPH','GAP']
    index:int=Field(ge=0,le=29)
    fact_version_ids:list[str]=Field(default_factory=list,max_length=30)
    reason:str=Field(min_length=10,max_length=2000)
    missing_basis:str=Field(min_length=10,max_length=2000)


class RevisionCommand(Command):
    parent_job_id:str
    command_plan_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
    idempotency_key:str=Field(min_length=1,max_length=128)
    findings:list[NegativeFinding]=Field(default_factory=list,max_length=40)


def read_json(research,digest):
    return json.loads(research.evidence.raw(digest).read_bytes())


def context_summary(packet):
    """Only fixed packet paths, bounded selection and explicit omissions, no latest lookup."""
    binding=packet['payload']['valuation_binding'];model=binding.get('fixed_operating_model')
    if not model:return dict(status='NO_FIXED_MODEL',source_input_sha256=packet['packet_sha256'])
    result=dict(source_input_sha256=packet['packet_sha256'],operating_model_id=model['operating_model_id'],
        operating_model_sha256=model['content_sha256'],assumptions=model['assumptions'],config=model['config'],
        method_applicability=model['economic_basis'].get('applicability'),wacc=model['economic_basis'].get('wacc'),
        normalization_schedule=model['normalization_schedule'],
        annual_cashflows=[dict(name=s['name'],years=[{k:y.get(k) for k in ['period','revenue','operating_profit','tax','nopat','fcff','normalized_inputs']} for y in s['years']]) for s in model['cashflows']],
        scenario_drivers=model['drivers'].get('scenarios',[]),
        omitted_paths=['fixed_operating_model.economic_basis.assumption_basis','fixed_operating_model.cashflows[*].years[*].derivation','full provenance remains in frozen report input and host chapter9'],
        scope='Included fixed research assumptions are not missing report-wide; chapter-level omissions must be described as chapter context limits. Do not copy financial values; explain host chapter9 without new numbers.')
    if len(encode(result).encode())>45000:fail('REPORT_CONTEXT_TOO_LARGE','Fixed model context exceeds 45 KiB; narrow explicitly in a new compiler revision')
    return result


class ReportRevisions:
    def __init__(self,reports):
        self.reports,self.research=reports,reports.research

    def get(self,identifier):
        return self.research.analysis.read('report_revisions','revision_id',identifier)

    def command(self,job,sid):
        revision=self.get(job['host_revision_id'])
        if revision['execution_code_hashes']!=code_hashes():fail('INPUT_CHANGED','Host revision code changed; create a new append-only revision',409)
        if sid not in SECTIONS:fail('INVALID_REPORT_SECTION','Chapter is outside the fixed report structure')
        from importlib.metadata import version
        packet=self.reports.input(revision['input_id'])
        if packet['runtime_versions']!={name:version(name) for name in packet['runtime_versions']}:fail('INPUT_CHANGED','Frozen runtime dependencies changed',409)
        command=read_json(self.research,revision['commands'][sid]['sha256'])
        return command

    def validate_plan(self,packet,parent,plan):
        if (plan['parent_job_id']!=parent['job_id'] or plan['input_id']!=packet['input_id'] or
            plan['input_sha256']!=packet['packet_sha256'] or plan['model']!=packet['model'] or
            plan['generation_code_hashes']!=packet['code_hashes'] or set(plan['commands'])!=set(SECTIONS)):
            fail('REVISION_PLAN_INVALID','Plan must bind all exact original chapter commands and frozen code',409)
        source=self.research.evidence.raw(packet['algorithm_archives']['agents/company_report_runtime.py']['sha256']).read_text(encoding='utf-8-sig')
        constants={}
        for node in ast.parse(source).body:
            if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in {'OUTPUT','INSTRUCTIONS'}:
                constants[node.targets[0].id]=ast.literal_eval(node.value)
        from .report_runtime import ReportRuntime
        # Rebuild the known compiler shape using archived literal schema/instructions. Never execute archived source.
        for sid,item in plan['commands'].items():
            command=read_json(self.research,item['sha256'])
            expected=ReportRuntime(self.reports).command(parent,packet,sid,verify_code=False)
            expected.update(output_schema=constants['OUTPUT'],instructions=constants['INSTRUCTIONS'])
            if command!=expected or item['archive']['sha256']!=item['sha256']:
                fail('REVISION_PLAN_INVALID','Original command differs from its exact known compiler contract',409,section_id=sid)
        return plan

    def start(self,command):
        parent=self.reports.get(command.parent_job_id)
        if parent['status'] not in {'CANCELLED','FAILED','PARTIAL','COMPLETE','INTERRUPTED'} or parent.get('host_revision_id'):
            fail('REVISION_PARENT_INVALID','Revision needs a terminal original generation job',409)
        packet=self.reports.input(parent['input_id']);request=command.model_dump();request_sha=fingerprint(request)
        with self.research.ledger.connection() as db:
            prior=db.execute("SELECT value FROM company_research_jobs WHERE company_id=? AND json_extract(value,'$.idempotency_key')=?",(parent['company_id'],command.idempotency_key)).fetchone()
        if prior:
            job=verified(json.loads(prior[0]))
            if job['request_sha256']!=request_sha:fail('IDEMPOTENCY_CONFLICT','Revision key binds another request',409)
            return job
        plan=verified(read_json(self.research,command.command_plan_sha256));self.validate_plan(packet,parent,plan)
        source_sections=self.reports.sections(parent);reusable={}
        for section in source_sections:
            run=self.research.analysis.read('report_runs','run_id',section['run_id'])
            if not run.get('candidate_output_archive'):continue
            sid=section['section_id']
            if (run['command_sha256']!=plan['commands'][sid]['sha256'] or run['input_sha256']!=packet['packet_sha256'] or
                run.get('resolved_model')!=packet['model'] or run.get('tools')):
                fail('REVISION_SOURCE_INVALID','Source output must bind the exact command, fixed model and zero tools',409)
            candidate=read_json(self.research,run['candidate_output_archive']['sha256'])
            if candidate['section_id']!=sid or candidate['input_sha256']!=packet['packet_sha256']:
                fail('REVISION_SOURCE_INVALID','Source output refers to another section or input',409)
            reusable[sid]=dict(section_version_id=section['section_version_id'],run_id=run['run_id'],output_archive=run['candidate_output_archive'])
        locations=[(f.section_id,f.output_sha256,f.location,f.index) for f in command.findings]
        if len(locations)!=len(set(locations)):fail('REVISION_FINDING_INVALID','Each raw output location can be quarantined once',409)
        for finding in command.findings:
            source=reusable.get(finding.section_id)
            if not source or source['output_archive']['sha256']!=finding.output_sha256:
                fail('REVISION_FINDING_INVALID','Negative finding must bind an exact retained output',409)
            candidate=read_json(self.research,finding.output_sha256);items=candidate['paragraphs' if finding.location=='PARAGRAPH' else 'gaps']
            if finding.index>=len(items):fail('REVISION_FINDING_INVALID','Negative finding location is outside source output',409)
            allowed=items[finding.index]['fact_version_ids'] if finding.location=='PARAGRAPH' else [f['version_id'] for f in packet['payload']['facts']]
            if not set(finding.fact_version_ids)<=set(allowed):fail('REVISION_FINDING_INVALID','Finding cites facts outside the bound source location',409)
        commands={}
        for sid,item in plan['commands'].items():
            value=read_json(self.research,item['sha256'])
            if sid not in reusable:
                prompt=json.loads(value['prompt']);prompt['fixed_valuation_context']=context_summary(packet)
                value['prompt']=encode(prompt)
            wire=encode(value).encode()
            if len(wire)>262144:fail('REPORT_INPUT_TOO_LARGE','Revised command exceeds 256 KiB')
            registered=archive(self.research.evidence,wire,'REPORT_REVISION_EXACT_COMMAND')
            commands[sid]=dict(sha256=registered['sha256'],archive=registered,origin='ORIGINAL_EXACT_COMMAND' if sid in reusable else COMPILER,original_sha256=item['sha256'])
        hashes=code_hashes();root=Path(__file__).parents[2]
        revision=record(dict(revision_id=str(uuid4()),company_id=parent['company_id'],parent_job_id=parent['job_id'],
            input_id=packet['input_id'],input_sha256=packet['packet_sha256'],core_sha256=packet['payload']['core_sha256'],
            host_version=VERSION,compiler_version=COMPILER,original_plan_sha256=command.command_plan_sha256,
            generation_code_hashes=packet['code_hashes'],execution_code_hashes=hashes,
            execution_algorithm_archives={name:archive(self.research.evidence,(root/name).read_bytes(),'REPORT_REVISION_ALGORITHM_SOURCE') for name in hashes},
            commands=commands,reusable=reusable,findings=[f.model_dump()|dict(disposition='QUARANTINE',factual_endorsement=False) for f in command.findings],
            missing_model_calls=sum(sid not in reusable for sid in SECTIONS),model=packet['model'],authorization='TASK_PUBLIC_RESEARCH_SCOPE_REVIEW_REQUIRED_BEFORE_WORKER_START'))
        revision_archive=archive(self.research.evidence,encode(revision).encode(),'REPORT_HOST_REVISION')
        job=record({k:v for k,v in parent.items() if k not in {'content_sha256','created_at','error','quality','markdown_archive','worker_lease_owner','phase_started_at','last_advanced_at'}}|dict(
            job_id=str(uuid4()),parent_job_id=parent['job_id'],parent_report_id=parent['report_id'],idempotency_key=command.idempotency_key,request_sha256=request_sha,
            stage='CHAPTERS',status='QUEUED',attempts=0,checkpoints=[],errors=[],section_ids=[],report_id=None,host_owner=None,cancel_requested_at=None,
            host_revision_id=revision['revision_id'],host_revision_archive=revision_archive))
        with self.research.transaction() as db:
            if db.execute("SELECT count(*) FROM company_research_jobs WHERE json_extract(value,'$.status') IN ('QUEUED','RUNNING')").fetchone()[0]>=16:fail('QUEUE_FULL','Report queue is full',409)
            self.research.analysis.insert(db,'report_revisions','revision_id',revision)
            self.research.analysis.insert(db,'jobs','job_id',job)
        return job

    def reuse(self,job,packet,sid):
        revision=self.get(job['host_revision_id']);source=revision['reusable'].get(sid)
        if not source:return None
        from .report_runtime import ReportRuntime
        run=self.research.analysis.read('report_runs','run_id',source['run_id']);candidate=read_json(self.research,source['output_archive']['sha256'])
        rendered,refs=self.render(candidate,packet,sid,revision,source['output_archive']['sha256'])
        section=record(dict(section_version_id=str(uuid4()),company_id=job['company_id'],job_id=job['job_id'],input_id=packet['input_id'],
            input_sha256=packet['packet_sha256'],section_id=sid,run_id=source['run_id'],source_section_version_id=source['section_version_id'],
            host_revision_id=revision['revision_id'],status='COMPLETE',rendered=rendered,reference_ids=refs,model=run['resolved_model'],
            evidence_kind='METHOD_CASE' if run['evidence_kind']=='METHOD_CASE' else 'REAL_MODEL_OUTPUT_REVALIDATED',command_archive=run['command_archive'],output_archive=source['output_archive'],
            gaps=[g for i,g in enumerate(candidate['gaps']) if not any(f['section_id']==sid and f['location']=='GAP' and f['index']==i for f in revision['findings'])],source_gaps=candidate['gaps'],verification='NEW_HOST_REFERENCE_VALIDATION_NOT_FACTUAL_ENDORSEMENT',model_calls=0))
        with self.research.transaction() as db:self.research.analysis.insert(db,'report_sections','section_version_id',section)
        return section

    def render(self,candidate,packet,sid,revision,output_sha):
        from .report_runtime import ReportRuntime
        candidate=copy.deepcopy(candidate);warnings=[]
        for location,key in [('PARAGRAPH','paragraphs'),('GAP','gaps')]:
            findings=[f for f in revision['findings'] if f['section_id']==sid and f['output_sha256']==output_sha and f['location']==location]
            for finding in sorted(findings,key=lambda f:f['index'],reverse=True):
                del candidate[key][finding['index']]
                warnings.append('研究限制：'+cell(finding['reason'])+'；仍缺：'+cell(finding['missing_basis'])+'。相关原文保留，详见附录K核对记录。')
        rendered,refs=ReportRuntime(self.reports).validate(candidate,packet,sid)
        return rendered+ ('\n\n'+ '\n\n'.join(warnings) if warnings else ''),refs

    def presentation_packet(self,job,packet):
        value=copy.deepcopy(packet);revision=self.get(job['host_revision_id']);value['report_id']=str(uuid5(NAMESPACE_URL,'roll-company-report:'+job['job_id']))
        value['host_revision']=revision
        from .report_values import typed_packet
        return typed_packet(value)
