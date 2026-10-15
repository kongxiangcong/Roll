"""Immutable derivatives of saved reports; no trading/statistical authority."""
import asyncio
from datetime import datetime
import hashlib
import html
import json
import os
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field
from roll.accounts.ledger import encode,now


class PerformanceCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_shadow_revision:int=Field(ge=0)
    idempotency_key:str=Field(min_length=1,max_length=128)
    basis:str=Field(min_length=1,max_length=2000)
    valuation_id:str|None=None
    decision_id:str|None=None
    evaluation_id:str|None=None
    intent_id:str|None=None
    monitoring_check_id:str|None=None


class PerformanceReports:
    def __init__(self,reports):
        self.reports=reports;self.evidence=reports.shadow.evidence;self.ledger=reports.shadow.ledger
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS research_performance_reports(id TEXT PRIMARY KEY,freeze_id TEXT NOT NULL,key TEXT NOT NULL,command_hash TEXT NOT NULL,value TEXT NOT NULL,UNIQUE(freeze_id,key))')

    async def create(self,freeze_id,command):
        command_hash=hashlib.sha256(encode(command.model_dump()).encode()).hexdigest()
        with self.ledger.connection() as db:prior=db.execute('SELECT command_hash,value FROM research_performance_reports WHERE freeze_id=? AND key=?',(freeze_id,command.idempotency_key)).fetchone()
        if prior:
            if prior[0]!=command_hash:raise HTTPException(409,'PERFORMANCE_IDEMPOTENCY_CONFLICT')
            return self.get(json.loads(prior[1])['performance_report_id'])
        options=command.model_dump(exclude={'expected_shadow_revision','idempotency_key','basis'})
        source=self.reports.get(freeze_id,**options)
        state=source['platform']['state']
        if state['revision']!=command.expected_shadow_revision:raise HTTPException(409,'PERFORMANCE_SOURCE_REVISION_CHANGED')
        sessions=[]
        if state.get('input_archive'):
            original=self.reports.shadow.checked_archive(state['input_archive'])
            sessions=[d for d in original['inputs']['sessions'] if d<=state['through_date']]
        if len(sessions)>3650:raise HTTPException(422,'PERFORMANCE_SAVED_WINDOW_LIMIT_3650_SESSIONS')
        executable=os.environ.get('ROLL_QUANTSTATS_PYTHON')
        if not executable:raise HTTPException(409,'QUANTSTATS_ISOLATED_PYTHON_NOT_CONFIGURED')
        identifier=str(uuid4());output=self.evidence.directory/'performance-renders'/identifier;output.mkdir(parents=True)
        inputs={'curves':source['curves'],'sessions':sessions,'output_directory':str(output),
            'benchmarks':{name:state.get('comparators',{}).get(name,{}).get('curve',[]) for name in ('CASH','START_HOLD','MA5_MA20')
                if name in state.get('comparators',{})}}
        source_archive=self.evidence.archive(encode(source).encode(),'SAVED_PERFORMANCE_SOURCE')
        input_archive=self.evidence.archive(encode(inputs).encode(),'QUANTSTATS_INPUT')
        with (output/'stderr.log').open('wb') as errors:
            process=await asyncio.create_subprocess_exec(executable,'-I','-B',str(Path(__file__).with_name('performance_process.py')),
                stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.DEVNULL,stderr=errors,
                env={**os.environ,'MPLCONFIGDIR':str(output/'matplotlib'),'MPLBACKEND':'Agg'},creationflags=0x08000000 if os.name=='nt' else 0)
            try:await asyncio.wait_for(process.communicate(json.dumps(inputs).encode()),timeout=30)
            except (asyncio.TimeoutError,asyncio.CancelledError):
                if process.returncode is None:process.kill()
                await process.wait()
                raise HTTPException(409,'QUANTSTATS_RENDER_INTERRUPTED')
        if process.returncode!=0:raise HTTPException(409,'QUANTSTATS_RENDER_FAILED; saved stderr '+identifier)
        result_file=output/'result.json'
        if not result_file.exists() or result_file.stat().st_size>8*1024*1024:raise HTTPException(409,'QUANTSTATS_RESULT_SIZE_OR_MISSING')
        result=json.loads(result_file.read_text(encoding='utf-8'));figures={};total=0
        for name in source['curves']:
            file=output/(name+'.svg')
            if not file.exists():continue
            total+=file.stat().st_size
            if total>8*1024*1024:raise HTTPException(409,'QUANTSTATS_FIGURE_SIZE_LIMIT')
            figures[name]=self.evidence.archive(file.read_bytes(),'QUANTSTATS_FIGURE',extension='svg')
        renderer_hash=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')+Path(__file__).with_name('performance_process.py').read_bytes().replace(b'\r\n',b'\n')).hexdigest()
        value={**result,'performance_report_id':identifier,'freeze_id':freeze_id,'source_revision':state['revision'],'created_at':now(),
            'basis':command.basis,'source_report':source_archive,'input_archive':input_archive,'figures':figures,
            'source_evidence_kind':source['evidence_kind'],'original_fingerprints':source['original_fingerprints'],
            'complete_protocol_fingerprint':source['complete_protocol_fingerprint'],'renderer_fingerprint':renderer_hash,
            'resource_plan':{'timeout_seconds':30,'maximum_sessions':3650,'maximum_result_bytes':8*1024*1024,'maximum_figure_bytes':8*1024*1024},
            'system_usable':False,'capability':'NOT_GRANTED'}
        # Original report remains byte-bound separately; offline export has no
        # remote assets or URLs and never invokes the library on subsequent reads.
        text='<!doctype html><html><meta charset="utf-8"><title>Roll saved performance</title><style>body{font:16px system-ui;max-width:1000px;margin:32px auto;padding:0 16px;color:#253b30}svg{width:100%;height:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left}table{border-collapse:collapse}</style><body><h1>Roll saved performance · NOT_GRANTED</h1>'
        text+='<p>QuantStats '+html.escape(result['library']['version'])+' · '+html.escape(source['evidence_kind'])+' · first saved close anchor; partial calendar months. Saved benchmarks are descriptive, not risk-matching qualification.</p>'
        for name,section in result['namespaces'].items():
            text+='<h2>'+name+'</h2><p>'+html.escape(section['status'])+'</p>'
            if section['status']=='DESCRIPTIVE_SAVED_CLOSE_INTERVAL':
                text+='<p>'+html.escape(' to '.join(section['window']))+'</p><table><tr><th>Interval return</th><th>Maximum drawdown</th><th>252-period annualized return</th></tr><tr>'
                for key in ('total_return','maximum_drawdown','annualized_return'):
                    number=section.get(key);text+='<td>'+('Not calculated: insufficient observed periods' if number is None else f'{number*100:.2f}%')+'</td>'
                text+='</tr></table>'
                for label,baseline in section.get('benchmarks',{}).items():
                    text+='<h3>Saved baseline '+html.escape(label)+'</h3><p>'+html.escape(baseline['status'])+'</p>'
                    if baseline['status']=='DESCRIPTIVE_SAVED_CLOSE_INTERVAL':
                        text+='<p>Interval return '+f"{baseline['total_return']*100:.2f}%"+'; maximum drawdown '+f"{baseline['maximum_drawdown']*100:.2f}%"+'; descriptive return difference '+f"{baseline['interval_return_difference']*100:.2f}%"+'</p>'
            if name in figures:text+=self.evidence.raw(figures[name]['sha256']).read_text(encoding='utf-8')
        text+='<details><summary>Saved inputs, coverage and method fingerprints</summary><pre>'+html.escape(json.dumps({k:v for k,v in value.items() if k not in {'source_report','input_archive','figures','original_fingerprints'}},ensure_ascii=False,indent=2))+'</pre></details>'
        text+='</body></html>'
        value['export']=self.evidence.archive(text.encode(),'QUANTSTATS_OFFLINE_REPORT',extension='html')
        value['archive']=self.evidence.archive(encode(value).encode(),'QUANTSTATS_REPORT_MANIFEST')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT command_hash,value FROM research_performance_reports WHERE freeze_id=? AND key=?',(freeze_id,command.idempotency_key)).fetchone()
            if prior:
                if prior[0]!=command_hash:raise HTTPException(409,'PERFORMANCE_IDEMPOTENCY_CONFLICT')
                return self.get(json.loads(prior[1])['performance_report_id'])
            db.execute('INSERT INTO research_performance_reports VALUES(?,?,?,?,?)',(identifier,freeze_id,command.idempotency_key,command_hash,encode(value)));db.commit()
        return value

    def get(self,identifier):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM research_performance_reports WHERE id=?',(identifier,)).fetchone()
        if not row:raise HTTPException(404,'PERFORMANCE_REPORT_NOT_FOUND')
        value=json.loads(row[0]);archived=json.loads(self.evidence.raw(value['archive']['sha256']).read_bytes())
        if archived!={k:v for k,v in value.items() if k!='archive'}:raise HTTPException(409,'PERFORMANCE_MANIFEST_MISMATCH')
        for original in [value['source_report'],value['input_archive'],value['export'],*value['figures'].values()]:self.evidence.raw(original['sha256'])
        return value

    def listing(self,freeze_id):
        with self.ledger.connection() as db:identifiers=[r[0] for r in db.execute('SELECT id FROM research_performance_reports WHERE freeze_id=? ORDER BY rowid DESC',(freeze_id,))]
        return [self.get(identifier) for identifier in identifiers]
