"""Saved arch comparisons are diagnostic archives, never qualification inputs."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field
from roll.accounts.ledger import encode,now

METHOD=Path(__file__).with_name('reference')/'block-reference-v1.json'


class BlockCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    idempotency_key:str=Field(min_length=1,max_length=128)
    basis:str=Field(min_length=1,max_length=2000)


def cases_for(source,probability):
    sessions=source['sessions']
    if len(sessions)>10000 or sessions!=sorted(set(sessions)):raise HTTPException(409,'BLOCK_REFERENCE_CALENDAR_INVALID')
    cases={}
    def add(name,rows,conditional,kind,constant=None):
        for block in (20,40):
            case={'date_scores':rows,'conditional':conditional,'block_sessions':block,'evidence_kind':kind}
            if constant is not None:case['analytic_constant']=constant
            cases[name+':'+str(block)]=case
    for name,phase in probability['phases'].items():
        if 'accepted_rows' not in phase:raise HTTPException(409,'BLOCK_REFERENCE_PROBABILITY_SOURCE_ERROR')
        rows=phase['accepted_rows'];groups={date:[] for date in sessions}
        unknown_dates={row['observation_date'] for row in phase.get('excluded',[]) if row.get('observation_date') in groups}
        for row in rows:
            if row['observation_date'] not in groups:raise HTTPException(409,'BLOCK_REFERENCE_EVENT_OUTSIDE_CALENDAR')
            groups[row['observation_date']].append(row)
        for conditional in (False,True):
            aligned=[]
            for date,group in groups.items():
                scores={}
                if not group:scores={'UNOBSERVED_MATURE_EVENT':None}
                for row in group:
                    if not conditional or row['probability']>=.60:
                        scores[row['canonical_key']]=(row['baseline_probability']-row['label'])**2-(row['probability']-row['label'])**2
                if date in unknown_dates:scores['EXCLUDED_UNMATURE_OR_UNKNOWN_EVENT']=None
                aligned.append({'date':date,'scores':scores})
            add('SOURCE:'+name+(' SELECTED_P_GE_0.60' if conditional else ' ALL'),aligned,conditional,source['source_evidence_kind'])
    constant=[{'date':f'METHOD_SLOT_{i:04d}','scores':{'A':0.,'B':.5}} for i in range(80)]
    varying=[{'date':f'METHOD_SLOT_{i:04d}','scores':{'A':(i%7-3)/10,'B':(i%5)/20}} for i in range(80)]
    conditional=[{'date':f'METHOD_SLOT_{i:04d}','scores':{} if i%3==0 else ({'A':.1} if i%3==1 else {'A':.3,'B':-.1})} for i in range(80)]
    add('METHOD:ANALYTIC_CONSTANT',constant,False,'METHOD',.25)
    add('METHOD:PAIRED_VARYING',varying,False,'METHOD')
    add('METHOD:CONDITIONAL_EMPTY_GROUPS',conditional,True,'METHOD')
    return cases


class BlockReferences:
    def __init__(self,probability):
        self.probability=probability;self.shadow=probability.shadow;self.ledger=probability.ledger;self.evidence=probability.evidence
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS research_block_references(id TEXT PRIMARY KEY,probability_id TEXT NOT NULL,key TEXT NOT NULL,command_hash TEXT NOT NULL,value TEXT NOT NULL,UNIQUE(probability_id,key))')

    async def create(self,probability_id,command):
        digest=hashlib.sha256(encode(command.model_dump()).encode()).hexdigest()
        with self.ledger.connection() as db:prior=db.execute('SELECT command_hash,value FROM research_block_references WHERE probability_id=? AND key=?',(probability_id,command.idempotency_key)).fetchone()
        if prior:
            if prior[0]!=digest:raise HTTPException(409,'BLOCK_REFERENCE_IDEMPOTENCY_CONFLICT')
            return self.get(json.loads(prior[1])['reference_id'])
        method_body=METHOD.read_bytes();method=json.loads(method_body)
        method_archive=self.evidence.archive(method_body,'BLOCK_REFERENCE_METHOD')
        probability=self.probability.get(probability_id);source=self.shadow.checked_archive(probability['source'])
        cases=cases_for(source,probability)
        input_archive=self.evidence.archive(encode(cases).encode(),'BLOCK_REFERENCE_INPUT')
        executable=os.environ.get('ROLL_ARCH_PYTHON')
        if not executable:raise HTTPException(409,'ARCH_ISOLATED_PYTHON_NOT_CONFIGURED')
        identifier=str(uuid4());output=self.evidence.directory/'block-reference'/identifier;output.mkdir(parents=True)
        frozen_sha=hashlib.sha256(Path(__file__).with_name('statistics.py').read_bytes().replace(b'\r\n',b'\n')).hexdigest()
        payload={'cases':cases,'method':method,'frozen_method_sha256':frozen_sha,'output_file':str(output/'result.json')}
        with (output/'stderr.log').open('wb') as errors:
            process=await asyncio.create_subprocess_exec(executable,'-I','-B',str(Path(__file__).with_name('block_process.py')),
                stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.DEVNULL,stderr=errors,
                env={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'},creationflags=0x08000000 if os.name=='nt' else 0)
            try:await asyncio.wait_for(process.communicate(json.dumps(payload).encode()),timeout=method['limits']['worker_seconds'])
            except (asyncio.TimeoutError,asyncio.CancelledError):
                if process.returncode is None:process.kill()
                await process.wait();raise HTTPException(409,'BLOCK_REFERENCE_INTERRUPTED')
        file=output/'result.json'
        if process.returncode!=0 or not file.exists() or file.stat().st_size>method['limits']['output_bytes']:raise HTTPException(409,'BLOCK_REFERENCE_WORKER_FAILED '+identifier)
        result=json.loads(file.read_text(encoding='utf-8'))
        value={**result,'reference_id':identifier,'probability_reference_id':probability_id,'freeze_id':probability['freeze_id'],
            'recorded_at':now(),'basis':command.basis,'cutoff':probability['cutoff'],'source_scope':probability['source_scope'],
            'source_evidence_kind':probability['source_evidence_kind'],'probability_manifest':probability['archive'],
            'source':input_archive,'method':method_archive,'absolute_tolerance':method['absolute_tolerance'],
            'method_fingerprint':hashlib.sha256(method_body+Path(__file__).read_bytes().replace(b'\r\n',b'\n')+Path(__file__).with_name('block_process.py').read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
            'frozen_method_fingerprint':frozen_sha,
            'system_usable':False,'independent_validity':False}
        value['archive']=self.evidence.archive(encode(value).encode(),'BLOCK_REFERENCE_MANIFEST')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT command_hash,value FROM research_block_references WHERE probability_id=? AND key=?',(probability_id,command.idempotency_key)).fetchone()
            if prior:
                if prior[0]!=digest:raise HTTPException(409,'BLOCK_REFERENCE_IDEMPOTENCY_CONFLICT')
                return self.get(json.loads(prior[1])['reference_id'])
            db.execute('INSERT INTO research_block_references VALUES(?,?,?,?,?)',(identifier,probability_id,command.idempotency_key,digest,encode(value)));db.commit()
        return value

    def get(self,identifier):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM research_block_references WHERE id=?',(identifier,)).fetchone()
        if not row:raise HTTPException(404,'BLOCK_REFERENCE_NOT_FOUND')
        value=json.loads(row[0]);manifest=self.shadow.checked_archive(value['archive'])
        if manifest!={k:v for k,v in value.items() if k!='archive'}:raise HTTPException(409,'BLOCK_REFERENCE_MANIFEST_MISMATCH')
        for key in ('source','method','probability_manifest'):self.shadow.checked_archive(value[key])
        return value

    def listing(self,probability_id):
        with self.ledger.connection() as db:identifiers=[r[0] for r in db.execute('SELECT id FROM research_block_references WHERE probability_id=? ORDER BY rowid',(probability_id,))]
        return [self.get(identifier) for identifier in identifiers]
