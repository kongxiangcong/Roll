"""One bounded chapter per shared-worker turn, with exact commands archived."""
import hashlib
import json
import os
import re
import threading
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from roll.accounts.ledger import encode, now
from .service import fail, fingerprint, record
from .report_template import SECTIONS, reference_text, code_hashes, cell
from roll.agents.company_report_runtime import OUTPUT, INSTRUCTIONS
from .report_archive import archive


class ReportRuntime:
    def __init__(self, reports):
        self.reports, self.research, self.worker = reports, reports.research, reports.worker

    def save(self, run):
        value = record({k:v for k,v in run.items() if k!='content_sha256' and k!='candidate'})
        with self.research.transaction() as db:
            db.execute('INSERT INTO company_research_report_runs VALUES(?,?,?) ON CONFLICT(run_id) DO UPDATE SET value=excluded.value',
                (run['run_id'], run['company_id'], encode(value)))

    def command(self, job, packet, sid, verify_code=True):
        """Pure local preparation: no auth read, subprocess, model or network."""
        if sid not in SECTIONS:
            fail('INVALID_REPORT_SECTION','Chapter is outside the fixed report structure')
        if job.get('host_revision_id') and verify_code:
            from .report_revisions import ReportRevisions
            return ReportRevisions(self.reports).command(job,sid)
        if verify_code and packet['code_hashes']!=code_hashes():
            fail('INPUT_CHANGED','Report algorithms changed after freeze; restore the frozen version or start a new report',409)
        from importlib.metadata import version
        if verify_code and packet['runtime_versions']!={name:version(name) for name in packet['runtime_versions']}:
            fail('INPUT_CHANGED','Report dependency versions changed after freeze; do not mix chapter attempts',409)
        payload = packet['payload']
        prompt = dict(section_id=sid, title=SECTIONS[sid][0], requirements=SECTIONS[sid][1],
            input_sha256=packet['packet_sha256'], template=packet['template'],
            reference_content=reference_text(sid), company=payload['company'], CORE=payload['snapshot'],
            VALUATION={k:payload['valuation_binding'][k] for k in ['snapshot_id','economic_review_ids','valuation_ids','limitation']},
            current_valuation_status=payload['valuation_presentation']['status'],
            valuation_purpose=payload.get('valuation_purpose','CURRENT_PRICING'),
            facts=payload['facts'], references=payload['references'],
            peer_facts=payload['peer_facts'],peer_context=[dict(company=p['company'],snapshot_id=p['snapshot']['snapshot_id'],comparison_basis=p['comparison_basis'],limitation=p['limitation']) for p in payload['peers']],
            request_cutoff=payload['request_cutoff'], actual_obtained=payload['actually_obtained_through'],
            knowledge_frozen_at=payload['knowledge_frozen_at'], historical_pit_eligible=False,
            source_gaps=payload['source_gaps'],source_check_receipts=payload['acquisition'],
            unincorporated_material_ids=payload['unincorporated_material_ids'])
        if packet['template']['version']=='08.3':
            from .report_revisions import context_summary
            prompt['fixed_valuation_context']=context_summary(packet)
        command = dict(model=job['model'], tools=[], output_schema=OUTPUT, instructions=INSTRUCTIONS, prompt=encode(prompt))
        wire = encode(command).encode()
        if len(wire)>262144:
            fail('REPORT_INPUT_TOO_LARGE','Chapter command exceeds 256 KiB; narrow the selected shared snapshot')
        return command

    def execute(self, job, packet, sid, cancel=None):
        from roll.agents.codex_process import execute, process_creation
        revision=None
        if job.get('host_revision_id'):
            from .report_revisions import ReportRevisions
            revisions=ReportRevisions(self.reports);revision=revisions.get(job['host_revision_id'])
            revisions.command(job,sid) # verify execution code before reuse or new call
            reused=revisions.reuse(job,packet,sid)
            if reused:return reused
        with self.research.ledger.connection() as db:
            prior=db.execute("SELECT section_version_id FROM company_research_report_sections WHERE json_extract(value,'$.job_id')=? AND json_extract(value,'$.section_id')=? ORDER BY rowid LIMIT 1",(job['job_id'],sid)).fetchone()
        if prior:
            return self.research.analysis.read('report_sections','section_version_id',prior[0])
        command=self.command(job,packet,sid)
        wire=encode(command).encode()
        command_archive = archive(self.research.evidence,wire, 'REPORT_CHAPTER_EXACT_COMMAND')
        run = dict(run_id=str(uuid4()), company_id=job['company_id'], job_id=job['job_id'], input_id=packet['input_id'],
            section_id=sid, task_kind='COMPANY_REPORT_CHAPTER', model=job['model'], status='RUNNING', backend='CODEX',
            started_at=now(), tools=[], archives=[], command_archive=command_archive, command_sha256=hashlib.sha256(wire).hexdigest(),
            prompt_sha256=hashlib.sha256(command['prompt'].encode()).hexdigest(),instructions_sha256=hashlib.sha256(INSTRUCTIONS.encode()).hexdigest(),output_schema_sha256=fingerprint(OUTPUT),
            input_sha256=packet['packet_sha256'], template=packet['template'], model_executed=False,
            code_hashes=packet['code_hashes'],host_revision_id=job.get('host_revision_id'),
            execution_code_hashes=revision['execution_code_hashes'] if revision else packet['code_hashes'],
            evidence_kind='METHOD_CASE' if self.worker else 'CODEX_CHAPTER_ATTEMPT',
            limits=dict(timeout_seconds=90,runtime_operations=8,tool_calls=0),
            host_owner=dict(pid=os.getpid(),creation_ticks=process_creation(os.getpid())), formal_authority=False)
        self.save(run)
        rendered, refs = '', []
        try:
            configured = os.environ.get('ROLL_CODEX_AUTH_FILE')
            if not configured:
                raise FileNotFoundError()
            auth = json.loads(Path(configured).read_text(encoding='utf-8'))
            if auth.get('auth_mode')!='chatgpt' or not auth.get('tokens'):
                raise ValueError('CHATGPT_AUTH_REQUIRED')
            run['model_executed']=True
            execute(self, run, {'command':command}, cancel or threading.Event(), auth)
            if run['status']=='COMPLETE':
                if revision:
                    rendered,refs=revisions.render(run['candidate'],packet,sid,revision,run['candidate_output_archive']['sha256'])
                else:
                    rendered, refs = self.validate(run['candidate'], packet, sid)
        except (ValueError, OSError, HTTPException) as error:
            code = error.detail.get('code') if isinstance(error,HTTPException) and isinstance(error.detail,dict) else 'MODEL_UNAVAILABLE' if isinstance(error,OSError) else 'MODEL_OUTPUT_INVALID'
            details=error.detail if isinstance(error,HTTPException) and isinstance(error.detail,dict) else {}
            run.update(status='UNAVAILABLE' if isinstance(error,OSError) else 'FAILED',error=dict(code=code,type=type(error).__name__,reason=details.get('reason'),context=details.get('context',{})))
        except Exception as error:
            run.update(status='FAILED',error=dict(code='MODEL_OUTPUT_INVALID',type=type(error).__name__))
        finally:
            run['finished_at']=now()
            if not self.worker:
                run['evidence_kind']='REAL_MODEL_CHAPTER' if run.get('runtime_turn_id') and run['status']=='COMPLETE' else 'REAL_MODEL_ATTEMPT' if run.get('runtime_turn_id') else 'CODEX_ATTEMPT_NOT_CONFIRMED'
            self.save(run)
        if not rendered:
            rendered = '本章尚未完成有效模型写作；'+run['status']+'。已保存冻结输入与尝试，不能以占位内容视为研究完成。'
        section = record(dict(section_version_id=str(uuid4()),company_id=job['company_id'],job_id=job['job_id'],
            input_id=packet['input_id'],input_sha256=packet['packet_sha256'],section_id=sid,run_id=run['run_id'],
            host_revision_id=job.get('host_revision_id'),status=run['status'],rendered=rendered,reference_ids=refs, model=run.get('resolved_model',run['model']),
            evidence_kind=run['evidence_kind'],
            command_archive=command_archive, output_archive=run.get('candidate_output_archive'),
            gaps=run.get('candidate',{}).get('gaps',[]), verification='HOST_REFERENCES_AND_LITERAL_NUMBERS_ONLY_NOT_FACTUAL_ENDORSEMENT'))
        with self.research.transaction() as db:
            self.research.analysis.insert(db,'report_sections','section_version_id',section)
        return section

    def validate(self, candidate, packet, sid):
        import jsonschema
        jsonschema.validate(candidate,OUTPUT)
        if candidate['section_id']!=sid or candidate['input_sha256']!=packet['packet_sha256']:
            fail('INPUT_CHANGED','Chapter candidate refers to another frozen input',409)
        facts={f['version_id']:f for f in [*packet['payload']['facts'],*packet['payload']['peer_facts']]}
        refs, rendered = [], []
        for paragraph_index,para in enumerate(candidate['paragraphs']):
            text=re.sub(r'(?m)^[ \t]*#{1,6}[ \t]+(?:\d+(?:\.\d+)*[.、 \t]+)?([^\n]*)$',r'#### \1',para['text'])
            if any(i not in facts for i in para['fact_version_ids']):
                fail('UNKNOWN_CITATION','Chapter cites a fact outside its frozen snapshot')
            tokens=re.findall(r'\{\{fact:([^}]+)\}\}',text)
            if any(i not in para['fact_version_ids'] for i in tokens):
                fail('UNKNOWN_CITATION','Numeric insertion must cite the same paragraph fact')
            stripped=re.sub(r'\{\{fact:[^}]+\}\}','',text)
            self.check_text(stripped,paragraph_index=paragraph_index)
            text=text.replace('<','&lt;').replace('>','&gt;')
            for identifier in tokens:
                fact=facts[identifier]
                from .report_values import literal
                text=text.replace('{{fact:'+identifier+'}}',literal(fact,packet['payload']['materials']))
            for identifier in para['fact_version_ids']:
                fact=facts[identifier]
                text+=' [原件 '+cell(fact.get('page') or '页码未知')+' / '+cell(fact.get('table') or '表号未知')+'](/api/company-research/materials/'+fact['material_id']+'/original)'
            refs.extend(para['fact_version_ids'])
            rendered.append(text)
        rendered.extend('未完成：'+g for g in candidate['gaps'])
        for gap_index,gap in enumerate(candidate['gaps']):
            self.check_text(gap,gap_index=gap_index)
        return '\n\n'.join(rendered), sorted(set(refs))

    @staticmethod
    def check_text(text,**location):
        # A hypothetical minimum observation unit is not a disclosed company quantity.
        text=re.sub(r'(?:定义最小观察单位为同规格产品的|为同规格产品的)一罐，或规格固定的一箱', '概念观察单位', text)
        cn=r'[负正零〇○一二两三四五六七八九十百千万亿点]+'
        financial=rf'百分之{cn}|{cn}(?:万亿元|亿元|万元|港元|美元|欧元|英镑|元|个百分点|成|倍|吨|股|台|箱|桶|人)|{cn}[万亿](?![字行条项章节年天日家])|{cn}分之{cn}'
        rules=[('UNBOUND_ARABIC_NUMBER',r'[0-9]'),('UNBOUND_FINANCIAL_NUMBER',financial),
               ('UNTRUSTED_CHAPTER_CONTENT',r'<[A-Za-z!/][^>]*>|!\[|\]\(|```')]
        for code,pattern in rules:
            match=re.search(pattern,text)
            if match:
                fail(code,'Chapter candidate contains an unbound number or active content; original output retained',
                    **location,offending_sample=text[max(0,match.start()-16):min(len(text),match.end()+32)])
