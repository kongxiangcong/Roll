"""Limited research sentiment classification over saved news facts; no trading or return meaning."""
import asyncio,hashlib,json,os
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field
from roll.accounts.ledger import encode,now
from roll.market.news_events import associate,group_facts
from roll.market.sentiment_contract import VERSION as REJECT_VERSION,final_label,pre_reject

REFERENCE=Path(__file__).with_name('sentiment-reference.json')
VERSION='sentiment-classification-v1'


class SentimentCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    idempotency_key:str=Field(min_length=1,max_length=128)
    basis:str=Field(min_length=1,max_length=2000)


class Sentiment:
    def __init__(self,evidence):
        self.evidence,self.ledger=evidence,evidence.ledger;self.worker=None
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS sentiment_runs(id TEXT PRIMARY KEY,instrument TEXT,key TEXT,command_hash TEXT,value TEXT,UNIQUE(instrument,key))')
            db.execute('CREATE TABLE IF NOT EXISTS sentiment_facts(fact_id TEXT,reference_sha256 TEXT,value TEXT,PRIMARY KEY(fact_id,reference_sha256))')
            db.execute('CREATE TABLE IF NOT EXISTS sentiment_references(sha256 TEXT PRIMARY KEY,value TEXT,created_at TEXT)')

    def reference(self):
        body=REFERENCE.read_bytes();value=json.loads(body)
        if value.get('status')!='VERIFIED':raise ValueError('SENTIMENT_RUNTIME_NOT_VERIFIED')
        model=Path(value['model_directory']).resolve()
        for item in value['artifacts']:
            path=(model/item['path']).resolve()
            if not path.is_relative_to(model) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:
                raise ValueError('SENTIMENT_RUNTIME_FINGERPRINT_MISMATCH')
        return hashlib.sha256(body).hexdigest(),value

    def identities(self):
        with self.ledger.connection() as db:
            rows=db.execute('SELECT instrument,identity FROM market_identities ORDER BY revision').fetchall()
        latest={}
        for instrument,raw in rows:latest[instrument]=json.loads(raw)
        return [{'instrument':instrument,'name':value.get('name',''),'code':value.get('code')} for instrument,value in sorted(latest.items())]

    def facts(self,instrument):
        with self.ledger.connection() as db:
            rows=db.execute('SELECT value FROM news_facts WHERE instrument=? ORDER BY rowid',(instrument,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    async def child(self,run_id,payload):
        executable=os.environ.get('ROLL_SENTIMENT_PYTHON')
        if not executable:raise ValueError('SENTIMENT_ISOLATED_PYTHON_NOT_CONFIGURED')
        output=self.evidence.directory/'sentiment-runs'/run_id
        output.mkdir(parents=True,exist_ok=True)
        payload={**payload,'output':str(output/'result.json')}
        environment={k:v for k,v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','TEMP','TMP','USERPROFILE','HOME','HOMEDRIVE','HOMEPATH','APPDATA','LOCALAPPDATA','USERNAME','USER','NUMBER_OF_PROCESSORS'}}
        environment.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HOME=str(output/'cache'),TORCH_HOME=str(output/'cache'),OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
        process=await asyncio.create_subprocess_exec(executable,'-I','-B',str(Path(__file__).with_name('sentiment_process.py')),
            stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL,env=environment,
            creationflags=0x08000000 if os.name=='nt' else 0)
        try:
            await asyncio.wait_for(process.communicate(encode(payload).encode()),timeout=120)
        finally:
            if process.returncode is None:process.kill()
            await process.wait()
        path=output/'result.json'
        if not path.exists():raise ValueError('SENTIMENT_OUTPUT_MISSING')
        return json.loads(path.read_text(encoding='utf-8'))

    async def classify(self,instrument,command):
        hashed=hashlib.sha256(encode(command.model_dump()).encode()).hexdigest()
        with self.ledger.connection() as db:prior=db.execute('SELECT command_hash,value FROM sentiment_runs WHERE instrument=? AND key=?',(instrument,command.idempotency_key)).fetchone()
        if prior:
            if prior[0]!=hashed:raise HTTPException(409,'SENTIMENT_IDEMPOTENCY_CONFLICT')
            return json.loads(prior[1])
        reference_sha,reference=self.reference()
        facts=self.facts(instrument)
        if not facts:raise HTTPException(409,'SENTIMENT_NO_SAVED_NEWS')
        identities=self.identities();associations={fact['fact_id']:associate(fact,identities) for fact in facts}
        memberships,_=group_facts(facts,associations)
        items=[];pre={}
        for fact in facts:
            text=(fact.get('title') or '')+'\n'+(fact.get('body_text') or fact.get('excerpt') or '')
            reason=pre_reject(fact.get('title'),text,associations[fact['fact_id']]['classification'])
            pre[fact['fact_id']]=reason
            items.append({'fact_id':fact['fact_id'],'text':text,'reason':reason})
        value={'run_id':str(uuid4()),'instrument':instrument,'basis':command.basis,'status':'RUNNING','started_at':now(),'finished_at':None,
            'reference_sha256':reference_sha,'reference':reference,'reject_layer':REJECT_VERSION,'classification_version':VERSION,
            'evidence_kind':'METHOD_CASE' if self.worker else 'REAL_LOCAL_CLASSIFICATION','facts':[],'errors':[],'network_calls':0,
            'system_usable':False,'capability':'RESEARCH_LIMITED'}
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT command_hash,value FROM sentiment_runs WHERE instrument=? AND key=?',(instrument,command.idempotency_key)).fetchone()
            if prior:
                if prior[0]!=hashed:raise HTTPException(409,'SENTIMENT_IDEMPOTENCY_CONFLICT')
                return json.loads(prior[1])
            if db.execute("SELECT 1 FROM sentiment_runs WHERE instrument=? AND json_extract(value,'$.status')='RUNNING'",(instrument,)).fetchone():raise HTTPException(409,'SENTIMENT_ALREADY_RUNNING')
            db.execute('INSERT INTO sentiment_runs VALUES(?,?,?,?,?)',(value['run_id'],instrument,command.idempotency_key,hashed,encode(value)));db.commit()
        try:
            eligible=[item for item in items if item['reason'] is None]
            predictions={}
            if eligible:
                if self.worker:predictions=await self.worker(instrument,eligible)
                else:
                    payload=await self.child(value['run_id'],{'reference':reference,'model_directory':reference['model_directory'],
                        'items':[{'fact_id':item['fact_id'],'text':item['text']} for item in eligible]})
                    if payload.get('status')!='SUCCESS':raise ValueError('SENTIMENT_INFERENCE_FAILED:'+'|'.join(payload.get('errors',[]))[:200])
                    predictions={row['fact_id']:row for row in payload['predictions']}
            results=[]
            for item in items:
                fact=next(fact for fact in facts if fact['fact_id']==item['fact_id'])
                prediction=predictions.get(item['fact_id'])
                if item['reason'] is None and not prediction:raise ValueError('SENTIMENT_PREDICTION_MISSING')
                prob_positive=prediction['prob_positive'] if prediction else None
                prob_negative=prediction['prob_negative'] if prediction else None
                label,confidence,reason=final_label(prob_positive,prob_negative,item['reason'])
                text_sha=hashlib.sha256(item['text'].encode()).hexdigest()
                results.append({'fact_id':fact['fact_id'],'title':fact.get('title'),'media':fact.get('media'),'event_id':memberships[fact['fact_id']]['event_id'],
                    'association':associations[fact['fact_id']]['classification'],'text_sha256':text_sha,'label':label,'confidence':confidence,
                    'reject_reason':reason,'prob_positive':prob_positive,'prob_negative':prob_negative})
            counts={};rejects={}
            for row in results:
                key=row['label'] or row['reject_reason']
                counts[key]=counts.get(key,0)+1
                if row['reject_reason']:rejects[row['reject_reason']]=rejects.get(row['reject_reason'],0)+1
            value.update(status='COMPLETE',finished_at=now(),facts=results,counts=counts,reject_counts=rejects,
                covered=sum(1 for row in results if row['label']),total=len(results),
                coverage=round(sum(1 for row in results if row['label'])/len(results),4) if results else 0)
            with self.ledger.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('INSERT OR IGNORE INTO sentiment_references VALUES(?,?,?)',(reference_sha,encode(reference),now()))
                for row in results:db.execute('INSERT OR IGNORE INTO sentiment_facts VALUES(?,?,?)',(row['fact_id'],reference_sha,encode(row)))
                db.execute('UPDATE sentiment_runs SET value=? WHERE id=?',(encode(value),value['run_id']))
                db.commit()
        except (Exception,asyncio.CancelledError) as error:
            value.update(status='CANCELLED' if isinstance(error,asyncio.CancelledError) else 'FAILED',finished_at=now(),errors=[str(error)[:300] if isinstance(error,ValueError) else type(error).__name__])
            with self.ledger.connection() as db:db.execute('UPDATE sentiment_runs SET value=? WHERE id=?',(encode(value),value['run_id']))
            if isinstance(error,asyncio.CancelledError):raise
        return value

    def get(self,identifier):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM sentiment_runs WHERE id=?',(identifier,)).fetchone()
        if not row:raise HTTPException(404,'SENTIMENT_RUN_NOT_FOUND')
        return json.loads(row[0])

    def listing(self,instrument,known_by=None):
        stamp=known_by or datetime.fromisoformat(now())
        if stamp.tzinfo is None or stamp>datetime.fromisoformat(now()):raise HTTPException(422,'SENTIMENT_CUTOFF_REQUIRES_PAST_AWARE_TIME')
        with self.ledger.connection() as db:
            rows=[json.loads(row[0]) for row in db.execute('SELECT value FROM sentiment_runs WHERE instrument=? ORDER BY rowid DESC',(instrument,))]
        runs=[row for row in rows if row.get('finished_at') and datetime.fromisoformat(row['finished_at'])<=stamp and row['status']=='COMPLETE']
        if not runs:raise HTTPException(404,'SENTIMENT_CLASSIFICATION_NOT_FOUND')
        run=runs[0];reference=run['reference']
        return {'instrument':instrument,'run':run,'facts':run['facts'],'counts':run['counts'],'reject_counts':run['reject_counts'],
            'coverage':run['coverage'],'model':reference.get('model'),'license':reference.get('license'),'weights_sha256':reference.get('weights_sha256'),
            'evaluation':reference.get('evaluation'),'reject_layer':run['reject_layer'],'known_by':stamp.isoformat(),
            'network_calls':0,'system_usable':False,'capability':'RESEARCH_LIMITED'}
