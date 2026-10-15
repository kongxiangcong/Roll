"""Finite AKShare observations: original entities before immutable income versions."""
import asyncio
from datetime import date,datetime
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import time
from uuid import uuid4
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field
from roll.accounts.ledger import encode,now
from roll.agents.codex_process import owner_alive,process_creation
from roll.market.directory import ScopeCommand
from roll.market.akshare_financial_process import SDK_VERSION,SDK_SOURCE_SHA

SOURCE='akshare-financial-em'
REFERENCE=Path(__file__).with_name('financial_reference')
FIELDS={'revenue':'TOTAL_OPERATE_INCOME','net_profit':'NETPROFIT','parent_net_profit':'PARENT_NETPROFIT'}


class IncomeCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    idempotency_key:str=Field(min_length=1,max_length=128)
    basis:str=Field(min_length=1,max_length=2000)


def decimal_text(value):
    if value is None:return None
    number=Decimal(str(value))
    if not number.is_finite():raise ValueError('FINANCIAL_NONFINITE_AMOUNT')
    return str(number)


class FinancialIncome:
    def __init__(self,evidence,sources,statement="INCOME"):
        if statement not in ("INCOME","SUPPLEMENT"):raise ValueError("FINANCIAL_STATEMENT_UNSUPPORTED")
        self.statement=statement
        self.run_table="financial_income_runs" if statement=="INCOME" else "financial_supplement_runs"
        self.evidence,self.ledger,self.sources=evidence,evidence.ledger,sources
        self.worker=None
        self.active={}
        self.tasks={}
        self.cancel_requested=set()
        with self.ledger.connection() as db:
            db.executescript(f'''
                CREATE TABLE IF NOT EXISTS {self.run_table}(id TEXT PRIMARY KEY,instrument TEXT NOT NULL,key TEXT NOT NULL,command_hash TEXT NOT NULL,value TEXT NOT NULL,UNIQUE(instrument,key));
                CREATE TABLE IF NOT EXISTS financial_income_facts(id TEXT PRIMARY KEY,instrument TEXT NOT NULL,identity TEXT NOT NULL,content_hash TEXT NOT NULL,value TEXT NOT NULL);
            ''')
            recovering=db.execute(f'SELECT id,value FROM {self.run_table}').fetchall()
        for identifier,raw in recovering:
            run=json.loads(raw)
            if run['status']=='RUNNING' and not owner_alive(run):
                output=self.evidence.directory/'financial-captures'/identifier
                if not run['originals'] and (output/'capture.json').exists():
                    try:self.archive_capture(json.loads((output/'capture.json').read_text()),output,run)
                    except Exception:pass
                run.update(status='INTERRUPTED',finished_at=now(),errors=['HOST_INTERRUPTED_NO_AUTOMATIC_RETRY'])
                with self.ledger.connection() as db:
                    db.execute(f'UPDATE {self.run_table} SET value=? WHERE id=?',(encode(run),identifier))

    def checked(self,run):
        for original in run['originals']:self.evidence.raw(original['sha256'])
        return run

    async def cancel(self,identifier):
        task=self.tasks.get(identifier)
        if task is None:raise HTTPException(409,'FINANCIAL_RUN_NOT_ACTIVE_IN_THIS_HOST')
        self.cancel_requested.add(identifier)
        task.cancel()
        return {'run_id':identifier,'cancellation_requested':True}

    def listing(self,instrument,cutoff=None):
        stamp=cutoff or datetime.fromisoformat(now())
        if stamp.tzinfo is None or stamp>datetime.fromisoformat(now()):raise HTTPException(422,'FINANCIAL_CUTOFF_REQUIRES_PAST_AWARE_TIME')
        with self.ledger.connection() as db:
            facts=[json.loads(r[0]) for r in db.execute(f"SELECT value FROM financial_income_facts WHERE instrument=? ORDER BY json_extract(value,'$.report_period') DESC,rowid DESC",(instrument,))]
            runs=[json.loads(r[0]) for r in db.execute(f'SELECT value FROM {self.run_table} WHERE instrument=? ORDER BY rowid DESC',(instrument,))]
        facts=[f for f in facts if (f['statement']=='INCOME')==(self.statement=='INCOME') and datetime.fromisoformat(f['available_at'])<=stamp]
        runs=[r for r in runs if r.get('statement','INCOME')==self.statement]
        for fact in facts:
            self.evidence.raw(fact['raw_sha256'])
            if fact['semantic_document']:self.evidence.raw(fact['semantic_document']['sha256'])
        return {'instrument':instrument,'known_by':stamp.isoformat(),'facts':facts,
            'active_run_ids':[r['run_id'] for r in runs if r['status']=='RUNNING'] if cutoff is None else [],
            'runs':[self.checked(r) for r in runs if r['finished_at'] and datetime.fromisoformat(r['finished_at'])<=stamp],
            'system_usable':False,'historical_pit_eligible':False,'network_calls':0,'capability':'NOT_GRANTED'}

    async def process(self,instrument,output):
        executable=os.environ.get('ROLL_AKSHARE_PYTHON')
        if not executable:raise ValueError('AKSHARE_ISOLATED_PYTHON_NOT_CONFIGURED')
        command={'instrument':instrument,'output_directory':str(output),'deadline_at':time.time()+18,'statement':self.statement}
        process=await asyncio.create_subprocess_exec(executable,'-B',str(Path(__file__).with_name('akshare_financial_process.py')),
            stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL,
            creationflags=0x08000000 if os.name=='nt' else 0)
        self.active[output.name]=process
        try:
            await asyncio.wait_for(process.communicate(json.dumps(command).encode()),timeout=18)
        except (asyncio.TimeoutError,asyncio.CancelledError):
            if process.returncode is None:process.kill()
            await process.wait()
            raise
        finally:self.active.pop(output.name,None)
        return json.loads((output/'capture.json').read_text(encoding='utf-8'))

    def archive_capture(self,manifest,output,run):
        if manifest.get('sdk_version')!=SDK_VERSION or manifest.get('sdk_source_sha256')!=SDK_SOURCE_SHA:
            raise ValueError('AKSHARE_CAPTURE_VERSION_MISMATCH')
        captures=manifest.get('captures',[])
        if len(captures)>8:raise ValueError('FINANCIAL_CAPTURE_CALL_BUDGET')
        total=0
        for ordinal,captured in enumerate(captures,1):
            # The file name is a host-controlled ordinal, never a worker-supplied path.
            filename=f"{ordinal:02}.raw"
            path=output/filename
            if not path.exists():continue
            if path.stat().st_size>8*1024*1024:raise ValueError('FINANCIAL_CAPTURE_BYTE_BUDGET')
            body=path.read_bytes();total+=len(body)
            original=self.evidence.archive(body,'AKSHARE_FINANCIAL_ENTITY',source_id=SOURCE,
                source_url=captured.get('url'),received_at=captured.get('received_at'),evidence_kind=run['evidence_kind'],
                role=captured.get('role'),original_complete=captured.get('original_complete',False))
            run['originals'].append(original)
            if total>8*1024*1024 or hashlib.sha256(body).hexdigest()!=captured.get('sha256'):
                raise ValueError('FINANCIAL_ENTITY_INTEGRITY_OR_BUDGET_MISMATCH')
        run['upstream_entity_count']=len(captures)
        run['network_calls']=0 if run['evidence_kind']=='METHOD_CASE' else len(captures)
        if manifest.get('status')!='CAPTURED' or len(run['originals'])!=len(captures):
            raise ValueError('FINANCIAL_CAPTURE_INCOMPLETE:'+','.join(manifest.get('errors',[])))
        if any(not c.get('original_complete') or c.get('status_code')!=200 for c in captures):raise ValueError('FINANCIAL_ENTITY_NOT_COMPLETE_200')
        return captures

    def facts(self,instrument,run,manifest,output):
        captures=self.archive_capture(manifest,output,run)
        if self.statement!='INCOME':
            from roll.market.financial_statements import normalize
            return normalize(self,instrument,run,manifest,captures)
        income=[i for i,c in enumerate(captures) if c.get('role')=='lrbAjaxNew']
        if len(income)!=1:raise ValueError('FINANCIAL_SINGLE_INCOME_ENTITY_REQUIRED')
        original=run['originals'][income[0]]
        rows=json.loads(self.evidence.raw(original['sha256']).read_bytes(),parse_float=Decimal).get('data')
        if not isinstance(rows,list) or not 1<=len(rows)<=5:raise ValueError('FINANCIAL_ROW_BUDGET_OR_SCHEMA')
        selected=manifest.get('date_selection',{}).get('selected_report_dates')
        if not selected or len(set(selected))!=len(rows):raise ValueError('FINANCIAL_PERIOD_SELECTION_MISMATCH')
        reference=json.loads((REFERENCE/'manifest.json').read_text())
        facts=[];seen=set()
        for row in rows:
            if row.get('SECUCODE')!='600362.SH' or instrument!='SSE:600362':raise ValueError('FINANCIAL_ROW_INSTRUMENT_MISMATCH')
            period=str(row.get('REPORT_DATE',''))[:10];date.fromisoformat(period)
            if period not in selected or period in seen:raise ValueError('FINANCIAL_PERIOD_DUPLICATED_OR_UNREQUESTED')
            seen.add(period)
            values={name:decimal_text(row.get(field)) for name,field in FIELDS.items()}
            proof=next((p for p in reference['periods'] if values['revenue'] is not None and p['report_period']==period and
                Decimal(p['revenue_yuan'])==Decimal(values['revenue']) and p['reported_update_date']==str(row.get('UPDATE_DATE',''))[:10]),None)
            document=None;available=now()
            if proof:
                body=(REFERENCE/proof['filename']).read_bytes()
                if hashlib.sha256(body).hexdigest()!=proof['sha256']:raise ValueError('FINANCIAL_SEMANTIC_DOCUMENT_CORRUPT')
                document=self.evidence.archive(body,'FINANCIAL_STATEMENT_SEMANTICS',extension='pdf',
                    source_url=proof['url'],received_at=proof['received_at'],page=proof['page'],
                    reference_basis=proof['basis'])
                available=max(available,proof['received_at'],key=datetime.fromisoformat)
            original_fields=json.loads(json.dumps(row,default=str,ensure_ascii=False))
            facts.append({'instrument':instrument,'statement':'INCOME','report_period':period,
                'reported_publication_date':row.get('NOTICE_DATE'),'reported_update_date':row.get('UPDATE_DATE'),
                'publication_precision':'DATE' if row.get('NOTICE_DATE') else 'UNKNOWN',
                'first_received_at':original['received_at'],'available_at':max(available,original['received_at'],key=datetime.fromisoformat),
                'currency':row.get('CURRENCY') if row.get('CURRENCY')=='CNY' else None,
                'unit':'YUAN' if proof else 'UNKNOWN','statement_scope':'CONSOLIDATED' if proof else 'UNKNOWN',
                'period_basis':'YEAR_TO_DATE' if proof else 'UNKNOWN','semantic_document':document,
                'values':values,'original_fields':original_fields,'raw_sha256':original['sha256'],
                'source_id':SOURCE,'sdk_version':SDK_VERSION,'evidence_kind':run['evidence_kind'],
                'historical_pit_eligible':False,'system_usable':False,'gaps':['HISTORICAL_REVISION_AVAILABILITY_UNPROVEN']+([] if proof else ['STATEMENT_SCOPE_AND_UNIT_UNVERIFIED'])})
        return facts

    async def collect(self,instrument,command):
        stored_key=command.idempotency_key
        command_hash=hashlib.sha256(encode(command.model_dump()).encode()).hexdigest()
        with self.ledger.connection() as db:
            old=db.execute(f'SELECT command_hash,value FROM {self.run_table} WHERE instrument=? AND key=?',(instrument,stored_key)).fetchone()
        if old:
            if old[0]!=command_hash:raise HTTPException(409,'FINANCIAL_IDEMPOTENCY_CONFLICT')
            return self.checked(json.loads(old[1]))
        self.evidence.market.check_scope(ScopeCommand(instruments=[instrument],purpose='OBSERVATION'))
        denied=self.sources.access(SOURCE,instrument)
        if denied:raise HTTPException(409,denied)
        run={'run_id':str(uuid4()),'instrument':instrument,'status':'RUNNING','started_at':now(),'finished_at':None,
            'statement':self.statement,'basis':command.basis,'originals':[],'facts':[],'errors':[],'upstream_entity_count':0,'network_calls':0,
            'evidence_kind':'METHOD_CASE' if self.worker is not None else 'REAL_ACQUISITION',
            'host_owner':{'pid':os.getpid(),'creation_ticks':process_creation(os.getpid())},
            'capture_plan':{'max_calls':8,'total_timeout_seconds':18,'max_bytes':8*1024*1024,'retries':0},'system_usable':False}
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute(f"SELECT 1 FROM {self.run_table} WHERE instrument=? AND json_extract(value,'$.status')='RUNNING'",(instrument,)).fetchone():raise HTTPException(409,'FINANCIAL_ACQUISITION_ALREADY_RUNNING')
            db.execute(f'INSERT INTO {self.run_table} VALUES(?,?,?,?,?)',(run['run_id'],instrument,stored_key,command_hash,encode(run)));db.commit()
        output=self.evidence.directory/'financial-captures'/run['run_id'];output.mkdir(parents=True)
        self.tasks[run['run_id']]=asyncio.current_task()
        try:
            manifest=await (self.worker or self.process)(instrument,output)
            normalized=self.facts(instrument,run,manifest,output)
            with self.ledger.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                for fact in normalized:
                    # Link revisions in the declared upstream stream even when a
                    # revision invalidates our semantic proof. This is lineage,
                    # never a claim that unknown scopes are financially comparable.
                    identity=encode([instrument,fact['statement'],fact['report_period'],SOURCE,'BY_REPORT_API'])
                    content=hashlib.sha256(encode([fact['original_fields'],fact['semantic_document'] and fact['semantic_document']['sha256'],fact['evidence_kind']]).encode()).hexdigest()
                    previous=db.execute(f'SELECT id,content_hash,value FROM financial_income_facts WHERE identity=? ORDER BY rowid DESC LIMIT 1',(identity,)).fetchone()
                    if previous and previous[1]==content:fact=json.loads(previous[2])
                    else:
                        prior_fact=json.loads(previous[2]) if previous else None
                        comparable=prior_fact is not None and all(fact[k] not in (None,'UNKNOWN') and fact[k]==prior_fact[k]
                            for k in ('statement_scope','currency','unit','period_basis'))
                        fact.update(fact_id=str(uuid4()),version=1 if previous is None else json.loads(previous[2])['version']+1,supersedes_id=previous[0] if previous else None)
                        fact.update(revision_lineage='SOURCE_STREAM_OBSERVATIONS_ONLY',comparable_with_superseded=comparable)
                        db.execute(f'INSERT INTO financial_income_facts VALUES(?,?,?,?,?)',(fact['fact_id'],instrument,identity,content,encode(fact)))
                    run['facts'].append(fact)
                run.update(status='COMPLETE',finished_at=now())
                db.execute(f'UPDATE {self.run_table} SET value=? WHERE id=?',(encode(run),run['run_id']));db.commit()
        except (Exception,asyncio.CancelledError) as error:
            # Preserve a worker journal even when its parent deadline or caller is cancelled.
            if not run['originals'] and (output/'capture.json').exists():
                try:self.archive_capture(json.loads((output/'capture.json').read_text()),output,run)
                except Exception:pass
            run.update(status='CANCELLED' if isinstance(error,asyncio.CancelledError) else 'FAILED',finished_at=now(),
                errors=[str(error)[:300] if isinstance(error,ValueError) else type(error).__name__])
            with self.ledger.connection() as db:db.execute(f'UPDATE {self.run_table} SET value=? WHERE id=?',(encode(run),run['run_id']))
            if isinstance(error,asyncio.CancelledError) and run['run_id'] not in self.cancel_requested:raise
        finally:
            self.tasks.pop(run['run_id'],None)
            self.cancel_requested.discard(run['run_id'])
        self.sources.outcome(SOURCE,run['status']=='COMPLETE',run['status'],run['run_id'])
        return run
