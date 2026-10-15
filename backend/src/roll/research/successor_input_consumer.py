"""Source-packet pipeline; own state never mutates manual shadow or real clock."""
import asyncio,hashlib,json,os,sys
from datetime import date,datetime,timedelta
from pathlib import Path
from uuid import uuid4
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field,model_validator
from roll.accounts.ledger import encode,now
from roll.market.rules import SHANGHAI
from roll.research.shadow import fingerprint

METHOD=Path(__file__).with_name('reference')/'successor-input-consumer-v1.json'

class InputCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    purpose:Literal['RESEARCH','METHOD_VALIDATION']='RESEARCH'
    packet_id:str|None=Field(default=None,max_length=128)
    method_observation_date:date|None=None
    expected_revision:int=Field(ge=0)
    idempotency_key:str=Field(min_length=1,max_length=128)
    basis:str=Field(min_length=1,max_length=2000)

    @model_validator(mode='after')
    def exact_source(self):
        if self.purpose=='RESEARCH' and (not self.packet_id or self.method_observation_date):raise ValueError('Real consumer requires packet only')
        if self.purpose=='METHOD_VALIDATION' and (not self.method_observation_date or self.packet_id):raise ValueError('METHOD consumer requires observation date only')
        return self


def code():
    return hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')+Path(__file__).with_name('successor_input_consumer_process.py').read_bytes().replace(b'\r\n',b'\n')).hexdigest()


class SuccessorInputConsumers:
    def __init__(self,centers,prospective):
        self.centers=centers;self.prospective=prospective;self.ledger=centers.ledger;self.evidence=centers.evidence;self.shadow=centers.shadow;self.protocols=centers.checks.reviews.protocols
        with self.ledger.connection() as db:db.execute('CREATE TABLE IF NOT EXISTS research_successor_input_consumers(id TEXT PRIMARY KEY,binding_id TEXT NOT NULL,purpose TEXT NOT NULL,revision INTEGER NOT NULL,key TEXT NOT NULL,command_hash TEXT NOT NULL,value TEXT NOT NULL,UNIQUE(binding_id,purpose,key),UNIQUE(binding_id,purpose,revision))')

    async def run(self,payload,output):
        with (output/'stderr.log').open('wb') as errors:
            process=await asyncio.create_subprocess_exec(sys.executable,'-I','-B',str(Path(__file__).with_name('successor_input_consumer_process.py')),
                stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.DEVNULL,stderr=errors,creationflags=0x08000000 if os.name=='nt' else 0)
            try:await asyncio.wait_for(process.communicate(json.dumps({**payload,'output_file':str(output/'result.json')}).encode()),timeout=payload['method']['worker_seconds'])
            except (asyncio.TimeoutError,asyncio.CancelledError):
                if process.returncode is None:process.kill()
                await process.wait();raise HTTPException(409,'SUCCESSOR_INPUT_CONSUMER_INTERRUPTED')
        file=output/'result.json'
        if process.returncode!=0 or not file.exists() or file.stat().st_size>payload['method']['maximum_output_bytes']:raise HTTPException(409,'SUCCESSOR_INPUT_CONSUMER_WORKER_FAILED '+output.name)
        return json.loads(file.read_text(encoding='utf-8'))

    def calendar(self,symbol,identity,first,last):
        result=[];cursor=date.fromisoformat(first);end=date.fromisoformat(last)
        if (end-cursor).days>400:raise HTTPException(422,'INPUT_CONSUMER_CALENDAR_SPAN_LIMIT')
        while cursor<=end:
            info=self.evidence.market.rules.calendar(identity['exchange'],cursor,datetime.fromisoformat(cursor.isoformat()+'T16:00:00+08:00'))
            if info['is_trading_day'] is None:raise HTTPException(409,'INPUT_CONSUMER_CALENDAR_UNSUPPORTED')
            if info['is_trading_day']:result.append(cursor.isoformat())
            cursor+=timedelta(days=1)
        return result

    async def create(self,binding_id,command):
        digest=fingerprint(command.model_dump(mode='json'))
        with self.ledger.connection() as db:
            old=db.execute('SELECT command_hash,value FROM research_successor_input_consumers WHERE binding_id=? AND purpose=? AND key=?',(binding_id,command.purpose,command.idempotency_key)).fetchone()
            latest=db.execute('SELECT id,value FROM research_successor_input_consumers WHERE binding_id=? AND purpose=? ORDER BY revision DESC LIMIT 1',(binding_id,command.purpose)).fetchone()
        if old:
            if old[0]!=digest:raise HTTPException(409,'INPUT_CONSUMER_IDEMPOTENCY_CONFLICT')
            return self.get(json.loads(old[1])['consumer_id'])
        revision=json.loads(latest[1])['revision'] if latest else 0
        if revision!=command.expected_revision:raise HTTPException(409,'INPUT_CONSUMER_REVISION_CONFLICT')
        source=self.centers.get(binding_id);original=self.shadow.checked_archive(source['input_archive']);protocol=original['protocol'];previous=original['predecessor'];model=original['model']
        frozen=self.protocols.successor.get(protocol['successor_freeze_id'])
        if frozen['baseline']['positions']:raise HTTPException(409,'INPUT_CONSUMER_EMPTY_BASELINE_REQUIRED_NO_ASSUMED_LIQUIDATION')
        method_case=command.purpose=='METHOD_VALIDATION'
        if method_case and (os.environ.get('ROLL_ENV')!='test' or model['evidence_kind']!='METHOD_CASE'):raise HTTPException(403,'INPUT_CONSUMER_METHOD_TEST_ONLY')
        if not method_case and model['evidence_kind']=='METHOD_CASE':raise HTTPException(409,'INPUT_CONSUMER_METHOD_MODEL_CANNOT_BECOME_REAL')
        prior=self.get(latest[0]) if latest else None
        prior_payload=self.shadow.checked_archive(prior['input_archive']) if prior else None
        prior_frames=prior['frames'] if prior else [];gaps=[];packet=None;source_refs=list(prior_payload['source_refs']) if prior_payload else []
        if method_case:
            part=original['objects']['input_archive']['parts']['CALIBRATION'];day=command.method_observation_date.isoformat()
            if not part['metadata']['first_date']<=day<=part['metadata']['last_date']:raise HTTPException(403,'INPUT_CONSUMER_METHOD_CAL_ONLY')
            rows=part['facts'];cutoff=part['consumer_knowledge_cutoff'];identity='METHOD_INPUT:'+source['artifacts']['input_archive']['sha256']+':'+day
        else:
            if not self.prospective.post_close.replay(command.packet_id)['matches_original']:raise HTTPException(409,'INPUT_CONSUMER_PACKET_REPLAY_MISMATCH')
            with self.ledger.connection() as db:packet=json.loads(db.execute('SELECT value FROM post_close_packets WHERE id=?',(command.packet_id,)).fetchone()[0])
            stamp=datetime.fromisoformat(packet['knowledge_cutoff']);clock=datetime.fromisoformat(now());local=clock.astimezone(SHANGHAI);day=stamp.astimezone(SHANGHAI).date().isoformat()
            if stamp.tzinfo is None or stamp>clock or day!=local.date().isoformat() or stamp.astimezone(SHANGHAI).time().replace(tzinfo=None).isoformat()<'15:05:00':raise HTTPException(409,'INPUT_CONSUMER_CURRENT_POST_CLOSE_CUTOFF_REQUIRED')
            if datetime.fromisoformat(packet['created_at'])<datetime.fromisoformat(frozen['registered_at']):raise HTTPException(409,'INPUT_CONSUMER_PACKET_PREDATES_FREEZE')
            rows=packet['rows'];cutoff=packet['knowledge_cutoff'];identity='POST_CLOSE_PACKET:'+packet['packet_id'];gaps=list(packet['gaps'])
            if packet['instrument']!=previous['scope']['instruments'][0] or packet['evidence_kind']!='REAL_ACQUISITION' or any(v['evidence_kind']!='REAL_ACQUISITION' for v in packet['versions']):gaps.append('INPUT_CONSUMER_REAL_SCOPE_OR_ORIGIN_UNPROVEN')
            if not packet['forward_admissible']:gaps.append('INPUT_CONSUMER_PACKET_NOT_ADMISSIBLE')
            for context in packet['execution_context']:
                rule=context['rule'];symbol=context['instrument']
                if symbol not in frozen['rules'] or any(str(rule.get(k))!=str(frozen['rules'][symbol].get(k)) for k in ('price_tick_yuan','normal_price_limit_percent','buy_minimum','buy_increment')):gaps.append('INPUT_CONSUMER_CURRENT_RULE_MISMATCH')
            source_refs.append({'packet_id':packet['packet_id'],'archive':packet['archive']})
        symbol=previous['scope']['instruments'][0];scope=previous['scope']['identity_context'][symbol]
        if any(r.get('instrument')!=symbol for r in rows):gaps.append('INPUT_CONSUMER_MIXED_SCOPE')
        if len({(r['instrument'],r['trade_date']) for r in rows})!=len(rows):gaps.append('INPUT_CONSUMER_DUPLICATE_DATE')
        feature_calendar=self.calendar(symbol,scope,(date.fromisoformat(day)-timedelta(days=60)).isoformat(),day)[-21:]
        if not feature_calendar or feature_calendar[-1]!=day:gaps.append('INPUT_CONSUMER_NOT_TRADING_DAY')
        last=prior_frames[-1]['trade_date'] if prior_frames else None
        if last and day<=last:raise HTTPException(409,'INPUT_CONSUMER_NO_BACKFILL_OR_REWIND')
        advance_calendar=self.calendar(symbol,scope,(date.fromisoformat(last)+timedelta(days=1)).isoformat(),day) if last else [day]
        method_body=METHOD.read_bytes();method=json.loads(method_body)
        if len(prior_frames)+len(advance_calendar)>method['maximum_sessions']:raise HTTPException(422,'INPUT_CONSUMER_SESSION_LIMIT')
        payload={'source':source,'frozen':frozen,'model':model,'model_artifact':original['objects']['model_artifact'],'calibrator_artifact':original['objects']['calibrator_artifact'],
            'rows':rows,'purpose':command.purpose,'day':day,'cutoff':cutoff,'symbol':symbol,'source_identity':identity,'packet':packet,'source_refs':source_refs,
            'previous_frames':prior_frames,'feature_calendar':feature_calendar,'advance_calendar':advance_calendar,'gaps':gaps,'method':method}
        body=encode(payload).encode()
        if len(body)>method['maximum_input_bytes']:raise HTTPException(422,'INPUT_CONSUMER_INPUT_LIMIT')
        identifier=str(uuid4());output=self.evidence.directory/'successor-input-consumers'/identifier;output.mkdir(parents=True)
        result=await self.run(payload,output)
        value={**result,'consumer_id':identifier,'binding_id':binding_id,'purpose':command.purpose,'revision':revision+1,'source_manifest':source['archive'],
            'source_input':source['input_archive'],'method':self.evidence.archive(method_body,'SUCCESSOR_INPUT_CONSUMER_METHOD'),
            'input_archive':self.evidence.archive(body,'SUCCESSOR_INPUT_CONSUMER_INPUT'),'method_fingerprint':code(),'recorded_at':now(),'basis':command.basis}
        value['archive']=self.evidence.archive(encode(value).encode(),'SUCCESSOR_INPUT_CONSUMER_MANIFEST')
        self.ledger.crash_point('successor_input_after_archive')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE');old=db.execute('SELECT command_hash,value FROM research_successor_input_consumers WHERE binding_id=? AND purpose=? AND key=?',(binding_id,command.purpose,command.idempotency_key)).fetchone()
            if old:
                if old[0]!=digest:raise HTTPException(409,'INPUT_CONSUMER_IDEMPOTENCY_CONFLICT')
                return self.get(json.loads(old[1])['consumer_id'])
            actual=db.execute('SELECT COALESCE(MAX(revision),0) FROM research_successor_input_consumers WHERE binding_id=? AND purpose=?',(binding_id,command.purpose)).fetchone()[0]
            if actual!=revision:raise HTTPException(409,'INPUT_CONSUMER_CONCURRENT_REVISION_CONFLICT')
            db.execute('INSERT INTO research_successor_input_consumers VALUES(?,?,?,?,?,?,?)',(identifier,binding_id,command.purpose,revision+1,command.idempotency_key,digest,encode(value)))
            self.ledger.crash_point('successor_input_before_commit');db.commit()
        return value

    def get(self,identifier):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM research_successor_input_consumers WHERE id=?',(identifier,)).fetchone()
        if not row:raise HTTPException(404,'SUCCESSOR_INPUT_CONSUMER_NOT_FOUND')
        value=json.loads(row[0])
        if self.shadow.checked_archive(value['archive'])!={k:v for k,v in value.items() if k!='archive'}:raise HTTPException(409,'INPUT_CONSUMER_MANIFEST_MISMATCH')
        source=self.centers.get(value['binding_id']);payload=self.shadow.checked_archive(value['input_archive'])
        if source!=payload['source'] or self.protocols.successor.get(payload['frozen']['successor_freeze_id'])!=payload['frozen']:raise HTTPException(409,'INPUT_CONSUMER_NESTED_SOURCE_MISMATCH')
        for ref in payload['source_refs']:
            self.shadow.checked_archive(ref['archive'])
            if not self.prospective.post_close.replay(ref['packet_id'])['matches_original']:raise HTTPException(409,'INPUT_CONSUMER_PACKET_REPLAY_MISMATCH')
        self.shadow.checked_archive(value['method']);return value

    def listing(self,binding_id):
        self.centers.get(binding_id)
        with self.ledger.connection() as db:ids=[r[0] for r in db.execute('SELECT id FROM research_successor_input_consumers WHERE binding_id=? ORDER BY rowid',(binding_id,))]
        return [self.get(i) for i in ids]

    async def replay(self,identifier):
        value=self.get(identifier)
        if value['method_fingerprint']!=code():raise HTTPException(409,'INPUT_CONSUMER_CODE_CHANGED')
        payload=self.shadow.checked_archive(value['input_archive']);output=self.evidence.directory/'successor-input-consumers'/('replay-'+str(uuid4()));output.mkdir(parents=True)
        result=await self.run(payload,output)
        if any(value.get(k)!=v for k,v in result.items()):raise HTTPException(409,'INPUT_CONSUMER_REPLAY_MISMATCH')
        return {'matches_original':True,'new_fit_calls':0,'sealed_reads':0,'network_calls':0,'recomputed_saved_prediction':bool(result['new_prediction_calls'])}
