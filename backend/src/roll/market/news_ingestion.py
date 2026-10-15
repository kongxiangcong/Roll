"""Finite recent news observations with raw-first capture and offline derivation."""
import asyncio,hashlib,json,os
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field
from roll.accounts.ledger import encode,now
from roll.agents.codex_process import Job,owner_alive,process_creation
from roll.market.directory import ScopeCommand
from roll.market.news_contract import SDK_VERSION,SDK_SOURCE_SHA,EXTRACTOR_VERSION,SOURCE,body_url,list_rows


class NewsCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    idempotency_key:str=Field(min_length=1,max_length=128)
    basis:str=Field(min_length=1,max_length=2000)


class News:
    def __init__(self,evidence,sources):
        self.evidence,self.ledger,self.sources=evidence,evidence.ledger,sources;self.worker=None;self.tasks={};self.cancel_requested=set()
        with self.ledger.connection() as db:
            db.executescript('CREATE TABLE IF NOT EXISTS news_runs(id TEXT PRIMARY KEY,instrument TEXT,key TEXT,command_hash TEXT,value TEXT,UNIQUE(instrument,key));CREATE TABLE IF NOT EXISTS news_facts(id TEXT PRIMARY KEY,instrument TEXT,value TEXT);')
            pending=db.execute('SELECT id,value FROM news_runs').fetchall()
        for identifier,raw in pending:
            value=json.loads(raw)
            if value['status']!='RUNNING' or owner_alive(value):continue
            output=self.evidence.directory/'news-captures'/identifier
            try:
                manifest=json.loads((output/'capture.json').read_text(encoding='utf-8'))
                value['facts']=self.normalize(manifest,output,value)
            except Exception as error:value['errors'].append('RECOVERY:'+type(error).__name__)
            value.update(status='INTERRUPTED',finished_at=now(),errors=value['errors']+['HOST_INTERRUPTED_NO_AUTOMATIC_RETRY'])
            with self.ledger.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                current=json.loads(db.execute('SELECT value FROM news_runs WHERE id=?',(identifier,)).fetchone()[0])
                if current['status']!='RUNNING' or owner_alive(current):continue
                for fact in value['facts']:db.execute('INSERT OR IGNORE INTO news_facts VALUES(?,?,?)',(fact['fact_id'],value['instrument'],encode(fact)))
                db.execute('UPDATE news_runs SET value=? WHERE id=?',(encode(value),identifier))
                db.commit()

    def checked(self,value):
        for raw in value.get('originals',[]):self.evidence.raw(raw['sha256'])
        for fact in value.get('facts',[]):
            self.evidence.raw(fact['list_sha256'])
            if fact.get('body_sha256'):self.evidence.raw(fact['body_sha256'])
        return value

    def get(self,identifier):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM news_runs WHERE id=?',(identifier,)).fetchone()
        if not row:raise HTTPException(404,'NEWS_RUN_NOT_FOUND')
        return self.checked(json.loads(row[0]))

    def listing(self,instrument,known_by=None):
        stamp=known_by or datetime.fromisoformat(now())
        if stamp.tzinfo is None or stamp>datetime.fromisoformat(now()):raise HTTPException(422,'NEWS_CUTOFF_REQUIRES_PAST_AWARE_TIME')
        with self.ledger.connection() as db:
            runs=[json.loads(r[0]) for r in db.execute('SELECT value FROM news_runs WHERE instrument=? ORDER BY rowid DESC',(instrument,))]
            facts=[json.loads(r[0]) for r in db.execute('SELECT value FROM news_facts WHERE instrument=? ORDER BY rowid DESC',(instrument,))]
        facts=[f for f in facts if datetime.fromisoformat(f['available_at'])<=stamp]
        self.checked({'facts':facts})
        return {'instrument':instrument,'facts':facts,'known_by':stamp.isoformat(),'runs':[self.checked(r) for r in runs if r['finished_at'] and datetime.fromisoformat(r['finished_at'])<=stamp],
            'active_run_ids':[r['run_id'] for r in runs if r['status']=='RUNNING'] if known_by is None else [],'coverage':{'upstream_documented_maximum':100,'actual_sdk_page_size':10,'page':1,'sort':'UPSTREAM_DEFAULT','complete_history':False,'entity_association':'SEARCH_KEYWORD_ONLY_UNVERIFIED'},'network_calls':0,'system_usable':False,'capability':'NOT_GRANTED'}

    async def cancel(self,identifier):
        if identifier not in self.tasks:raise HTTPException(409,'NEWS_RUN_NOT_ACTIVE_IN_THIS_HOST')
        self.cancel_requested.add(identifier);self.tasks[identifier].cancel()
        return {'run_id':identifier,'cancellation_requested':True}

    async def child(self,executable,script,payload,seconds):
        environment={k:v for k,v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','TEMP','TMP'}}
        process=await asyncio.create_subprocess_exec(executable,'-B',str(Path(__file__).with_name(script)),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL,env=environment,creationflags=0x08000000 if os.name=='nt' else 0)
        job=None
        try:
            job=Job(process.pid)
            await asyncio.wait_for(process.communicate(encode(payload).encode('utf-8')),timeout=seconds)
            return process.returncode
        finally:
            if job:job.terminate();job.close()
            elif process.returncode is None:process.kill()
            await process.wait()

    async def process(self,instrument,output):
        executable=os.environ.get('ROLL_AKSHARE_PYTHON')
        if not executable:raise ValueError('AKSHARE_ISOLATED_PYTHON_NOT_CONFIGURED')
        try:await self.child(executable,'akshare_news_process.py',{'instrument':instrument,'output_directory':str(output)},18)
        except asyncio.TimeoutError:pass  # Read the persisted list/headlines and any received prefixes.
        manifest=json.loads((output/'capture.json').read_text(encoding='utf-8'))
        extractor=os.environ.get('ROLL_TRAFILATURA_PYTHON')
        if extractor and manifest['status']=='CAPTURED':
            try:
                await self.child(extractor,'trafilatura_process.py',{'output_directory':str(output)},60)
                manifest=json.loads((output/'capture.json').read_text(encoding='utf-8'))
            except (Exception,asyncio.CancelledError):
                if asyncio.current_task().cancelling():raise
                manifest['errors'].append('OFFLINE_EXTRACTOR_FAILED_OR_TIMEOUT')
        return manifest

    def archive(self,manifest,output,run):
        captures=manifest.get('captures',[])
        if len(captures)>8:raise ValueError('NEWS_CAPTURE_CALL_BUDGET')
        total=0;run.update(originals=[],capture_archive_bindings={},network_calls=0 if run['evidence_kind']=='METHOD_CASE' else len(captures),upstream_entity_count=len(captures))
        for i,c in enumerate(captures,1):
            path=output/f'{i:02}.raw'
            if not path.exists():continue
            size=path.stat().st_size
            if total+size>8*1024*1024:
                c['integrity_error']='NEWS_CAPTURE_BYTE_BUDGET'
                if i==1:raise ValueError(c['integrity_error'])
                continue
            total+=size
            raw=path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=c.get('sha256'):c['integrity_error']='NEWS_CAPTURE_SHA_MISMATCH'
            original=self.evidence.archive(raw,'NEWS_HTTP_ENTITY',source_id=SOURCE,source_url=c.get('url'),received_at=c.get('received_at'),role=c.get('role'),original_complete=c.get('original_complete',False),claimed_sha256=c.get('sha256'),integrity_verified=not c.get('integrity_error'),evidence_kind=run['evidence_kind'])
            run['originals'].append(original);run['capture_archive_bindings'][str(i)]=original['sha256']
            if i==1 and c.get('integrity_error'):raise ValueError(c['integrity_error'])
        return captures

    def normalize(self,manifest,output,run):
        captures=self.archive(manifest,output,run)
        if manifest.get('status')!='CAPTURED' or '1' not in run['capture_archive_bindings']:raise ValueError('NEWS_CAPTURE_INCOMPLETE')
        if manifest.get('sdk_version')!=SDK_VERSION or manifest.get('sdk_source_sha256')!=SDK_SOURCE_SHA:raise ValueError('NEWS_SDK_IDENTITY_MISMATCH')
        if not captures or captures[0].get('role')!='LIST' or not captures[0].get('original_complete') or captures[0].get('status_code')!=200:raise ValueError('NEWS_LIST_NOT_COMPLETE_200')
        from urllib.parse import urlsplit
        target=urlsplit(captures[0].get('url',''))
        if target.scheme!='https' or target.netloc!='search-api-web.eastmoney.com' or target.path!='/search/jsonp':raise ValueError('NEWS_LIST_CAPTURE_TARGET')
        rows=list_rows(self.evidence.raw(run['capture_archive_bindings']['1']).read_bytes());items=manifest.get('items',[])
        if len(rows)!=len(items):raise ValueError('NEWS_SDK_ROW_COUNT_MISMATCH')
        facts=[]
        for row,item in zip(rows,items):
            fields=item['fields']
            if fields.get('关键词')!='600362' or fields.get('新闻链接')!='http://finance.eastmoney.com/a/'+str(row['code'])+'.html':raise ValueError('NEWS_SDK_INSTRUMENT_OR_URL_MISMATCH')
            raw_index=run['originals'][0];body_sha=None;text=None;status=item.get('body_status','UNAVAILABLE');errors=list(item.get('errors',[]))
            ordinal=item.get('body_ordinal')
            if ordinal is not None:
                if not isinstance(ordinal,int) or not 2<=ordinal<=len(captures):raise ValueError('NEWS_BODY_CAPTURE_BINDING')
                captured=captures[ordinal-1]
                if captured.get('role')!='BODY' or captured.get('url')!=body_url(fields['新闻链接']):raise ValueError('NEWS_BODY_CAPTURE_URL_MISMATCH')
                body_sha=run['capture_archive_bindings'].get(str(ordinal))
                if captured.get('integrity_error') or not body_sha:
                    status='BODY_INTEGRITY_FAILED';errors.append(captured.get('integrity_error','NEWS_BODY_ORIGINAL_MISSING'))
                if status=='EXTRACTED':
                    if not body_sha or not captured.get('original_complete') or captured.get('status_code')!=200 or manifest.get('extractor_version')!=EXTRACTOR_VERSION or not item.get('text'):raise ValueError('NEWS_BODY_EXTRACTION_BINDING')
                    text=item['text']
            if text is None and status=='EXTRACTED':raise ValueError('NEWS_BODY_TEXT_WITHOUT_ORIGINAL')
            facts.append({'fact_id':str(uuid4()),'instrument':run['instrument'],'run_id':run['run_id'],'source_id':SOURCE,'sdk_version':SDK_VERSION,
                'title':fields['新闻标题'],'excerpt':fields.get('新闻内容'),'url':fields['新闻链接'],'media':fields.get('文章来源'),'reported_published_at':fields.get('发布时间'),'publication_timezone':'UPSTREAM_UNSPECIFIED',
                'first_received_at':raw_index['received_at'],'available_at':now(),'list_sha256':raw_index['sha256'],'body_sha256':body_sha,'body_status':status,'body_text':text,
                'body_received_at':captures[ordinal-1].get('received_at') if ordinal else None,'extracted_metadata':item.get('metadata') if text else None,'extractor_version':manifest.get('extractor_version') if text else None,
                'original_fields':fields,'evidence_kind':run['evidence_kind'],'errors':errors,'historical_pit_eligible':False,'system_usable':False,'association':'SEARCH_KEYWORD_ONLY_UNVERIFIED'})
        run['coverage']={'requested_page':1,'requested_page_size':10,'returned':len(rows),'body_limit':3,'complete_history':False,'sort':'UPSTREAM_DEFAULT','body_extracted':sum(bool(f['body_text']) for f in facts)}
        return facts

    async def collect(self,instrument,command):
        hashed=hashlib.sha256(encode(command.model_dump()).encode()).hexdigest()
        with self.ledger.connection() as db:prior=db.execute('SELECT command_hash,value FROM news_runs WHERE instrument=? AND key=?',(instrument,command.idempotency_key)).fetchone()
        if prior:
            if prior[0]!=hashed:raise HTTPException(409,'NEWS_IDEMPOTENCY_CONFLICT')
            return self.checked(json.loads(prior[1]))
        self.evidence.market.check_scope(ScopeCommand(instruments=[instrument],purpose='OBSERVATION'))
        denied=self.sources.access(SOURCE,instrument)
        if denied:raise HTTPException(409,denied)
        value={'run_id':str(uuid4()),'instrument':instrument,'basis':command.basis,'status':'RUNNING','started_at':now(),'finished_at':None,'originals':[],'facts':[],'errors':[],
            'evidence_kind':'METHOD_CASE' if self.worker else 'REAL_ACQUISITION','host_owner':{'pid':os.getpid(),'creation_ticks':process_creation(os.getpid())},'network_calls':0,'system_usable':False,
            'capture_plan':{'max_calls':8,'seconds':18,'max_bytes':8388608,'body_limit':3,'retries':0,'redirects':0}}
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT command_hash,value FROM news_runs WHERE instrument=? AND key=?',(instrument,command.idempotency_key)).fetchone()
            if prior:
                if prior[0]!=hashed:raise HTTPException(409,'NEWS_IDEMPOTENCY_CONFLICT')
                return self.checked(json.loads(prior[1]))
            if db.execute("SELECT 1 FROM news_runs WHERE instrument=? AND json_extract(value,'$.status')='RUNNING'",(instrument,)).fetchone():raise HTTPException(409,'NEWS_ALREADY_RUNNING')
            db.execute('INSERT INTO news_runs VALUES(?,?,?,?,?)',(value['run_id'],instrument,command.idempotency_key,hashed,encode(value)));db.commit()
        output=self.evidence.directory/'news-captures'/value['run_id']
        try:
            output.mkdir(parents=True);self.tasks[value['run_id']]=asyncio.current_task()
            manifest=await (self.worker or self.process)(instrument,output)
            facts=self.normalize(manifest,output,value)
            value.update(facts=facts,status='EMPTY' if not facts else 'COMPLETE' if all(f['body_text'] for f in facts) else 'PARTIAL',finished_at=now(),errors=manifest.get('errors',[]))
            with self.ledger.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                for fact in facts:db.execute('INSERT INTO news_facts VALUES(?,?,?)',(fact['fact_id'],instrument,encode(fact)))
                db.execute('UPDATE news_runs SET value=? WHERE id=?',(encode(value),value['run_id']))
                db.commit()
        except (Exception,asyncio.CancelledError) as error:
            if not value['originals'] and (output/'capture.json').exists():
                try:self.archive(json.loads((output/'capture.json').read_text(encoding='utf-8')),output,value)
                except Exception:pass
            value.update(status='CANCELLED' if isinstance(error,asyncio.CancelledError) else 'FAILED',finished_at=now(),errors=[str(error)[:300] if isinstance(error,ValueError) else type(error).__name__])
            with self.ledger.connection() as db:db.execute('UPDATE news_runs SET value=? WHERE id=?',(encode(value),value['run_id']))
            if isinstance(error,asyncio.CancelledError) and value['run_id'] not in self.cancel_requested:raise
        finally:self.tasks.pop(value['run_id'],None);self.cancel_requested.discard(value['run_id'])
        self.sources.outcome(SOURCE,value['status'] in ('COMPLETE','PARTIAL','EMPTY'),value['status'],value['run_id'])
        return value
