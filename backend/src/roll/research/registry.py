"""Append-only experiment design registration; registration cannot grant qualification."""
import hashlib
import json
import os
from pathlib import Path
from typing import Literal
from datetime import datetime,timedelta,timezone
from calendar import monthrange
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field
from roll.accounts.ledger import encode,now
from roll.research.datasets import import_dataset,partition
from roll.research.design import proposal
from roll.agents.codex_process import owner_alive,process_creation


class ProtocolCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    dataset_id:str|None=None
    predecessor_id:str|None=None
    basis:str=Field(min_length=1,max_length=2000)


class AttemptCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    category:Literal['PRIMARY_FIT','G5_NEIGHBOR','CALIBRATION','FEATURE','HORIZON','THRESHOLD','PROMPT','MANUAL_SELECTION','ENGINEERING_REPLAY','RISK_POLICY_VALIDATION']
    partition:Literal['DEVELOPMENT','CALIBRATION','SEALED']
    configuration:dict
    basis:str=Field(min_length=1,max_length=2000)


class FinishCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    status:Literal['SUCCEEDED','FAILED','ABORTED']
    reason:str=Field(min_length=1,max_length=2000)
    artifact_fingerprints:dict=Field(default_factory=dict)


class FreezeCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    attempt_ids:list[str]


class ReasonCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    reason:str=Field(min_length=1,max_length=2000)


class CheckpointCommand(ReasonCommand):
    kind:Literal['OPERATIONS','SAFETY_STOP','USER_STOP','EARLY_PASS','STATISTICAL_FINAL']


def deadline_preview(start):
    if start.tzinfo is None:raise HTTPException(422,'起点预览需要带时区，不能登记实际前向起点')
    if start.year<2000:raise HTTPException(422,'本轮仅预览现代中国标准时间研究，不推断历史夏令时')
    local=start.astimezone(timezone(timedelta(hours=8)));month=local.month+3
    year=local.year+(month-1)//12;month=(month-1)%12+1
    deadline=local.replace(year=year,month=month,day=min(local.day,monthrange(year,month)[1]))
    return {'start':local.isoformat(),'deadline':deadline.isoformat(),'maximum_natural_months':3,
        'actual_forward_start':False,'owner':'tickets30/32; preview is not a published prediction or account funding authority'}


class ExperimentRegistry:
    def __init__(self,ledger,evidence):
        self.ledger=ledger
        self.evidence=evidence
        self.owner={'pid':os.getpid(),'creation_ticks':process_creation(os.getpid()),'nonce':str(uuid4())}
        with ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS research_protocols(id TEXT PRIMARY KEY,value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS research_datasets(id TEXT PRIMARY KEY,value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS research_attempts(id TEXT PRIMARY KEY,protocol_id TEXT NOT NULL,value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS research_events(ordinal INTEGER PRIMARY KEY AUTOINCREMENT,protocol_id TEXT NOT NULL,value TEXT NOT NULL)')
        self._interrupt_abandoned()

    def _interrupt_abandoned(self,owned=False):
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            terminal={e['attempt_id'] for row in db.execute('SELECT value FROM research_events')
                if (e:=json.loads(row[0]))['action'] in {'ATTEMPT_FINISHED','ATTEMPT_INTERRUPTED'}}
            for row in db.execute('SELECT value FROM research_attempts'):
                attempt=json.loads(row[0])
                abandoned=attempt.get('host_owner')==self.owner if owned else not owner_alive(attempt)
                if attempt['status']=='RUNNING' and attempt['attempt_id'] not in terminal and abandoned:
                    self.event(attempt['protocol_id'],'ATTEMPT_INTERRUPTED',db=db,attempt_id=attempt['attempt_id'],
                        reason='宿主已正常关闭，未完成尝试保留中断' if owned else '原宿主已停止或旧版本没有可验证身份，未完成尝试保留中断')
            db.commit()

    def close(self):self._interrupt_abandoned(owned=True)

    def event(self,protocol_id,action,db=None,**detail):
        value={'event_id':str(uuid4()),'recorded_at':now(),'protocol_id':protocol_id,'action':action,**detail}
        if db is not None:db.execute('INSERT INTO research_events(protocol_id,value) VALUES(?,?)',(protocol_id,encode(value)))
        else:
            with self.ledger.connection() as connection:connection.execute('INSERT INTO research_events(protocol_id,value) VALUES(?,?)',(protocol_id,encode(value)))
        return value

    def audit(self,protocol_id):
        self.get(protocol_id)
        with self.ledger.connection() as db:return [json.loads(r[0]) for r in db.execute('SELECT value FROM research_events WHERE protocol_id=? ORDER BY ordinal',(protocol_id,))]

    def attempts(self,protocol_id):
        self.get(protocol_id)
        with self.ledger.connection() as db:items=[json.loads(r[0]) for r in db.execute('SELECT value FROM research_attempts WHERE protocol_id=? ORDER BY rowid',(protocol_id,))]
        completions={e['attempt_id']:e for e in self.audit(protocol_id) if e['action'] in {'ATTEMPT_FINISHED','ATTEMPT_INTERRUPTED'}}
        return [{**a,**({'status':completions[a['attempt_id']].get('status','INTERRUPTED'),'completion':completions[a['attempt_id']]} if a['attempt_id'] in completions else {})} for a in items]

    def lineage(self,protocol_id):
        ids=[];current=self.get(protocol_id)
        while True:
            ids.append(current['protocol_id'])
            if not current['predecessor_id']:break
            current=self.get(current['predecessor_id'])
        return list(reversed(ids))

    def family(self,protocol_id,db=None):
        if db is None:
            with self.ledger.connection() as connection:return self.family(protocol_id,connection)
        records={p['protocol_id']:p for row in db.execute('SELECT value FROM research_protocols') if (p:=json.loads(row[0]))}
        def root(identifier):
            while records[identifier]['predecessor_id']:identifier=records[identifier]['predecessor_id']
            return identifier
        original=root(protocol_id)
        return [identifier for identifier in records if root(identifier)==original]

    def attempt_manifest(self,protocol_id):
        lineage=self.lineage(protocol_id);family=self.family(protocol_id)
        attempts=[a for pid in family for a in self.attempts(pid)]
        return {'lineage':lineage,'family_protocol_ids':family,'attempts':attempts,'attempt_ids':[a['attempt_id'] for a in attempts],
            'basis':'All linked family predecessors and sibling failures, aborts and interruptions remain required; this is not proof of unreported out-of-host work'}

    def start_attempt(self,protocol_id,command):
        protocol=self.get(protocol_id)
        if command.partition=='SEALED':
            self.event(protocol_id,'ATTEMPT_REFUSED',reason='完整冻结未完成，不能运行封存确认性尝试',configuration=command.model_dump())
            raise HTTPException(409,'完整冻结未完成')
        value={'attempt_id':str(uuid4()),'protocol_id':protocol_id,'started_at':now(),'status':'RUNNING','host_owner':self.owner,**command.model_dump(),
            'protocol_fingerprint':protocol['protocol_fingerprint'],'data_fingerprint':protocol.get('data_fingerprint'),
            'qualification':'NONE; 成功执行不等于模型或研究PASS'}
        # Configuration-change records are not fits. Actual executors must begin a
        # PRIMARY_FIT/G5_NEIGHBOR before computing; thresholds reuse frozen predictions.
        fits={'PRIMARY_FIT','G5_NEIGHBOR'}
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            family=self.family(protocol_id,db)
            prior=[json.loads(r[0]) for pid in family for r in db.execute('SELECT value FROM research_attempts WHERE protocol_id=?',(pid,))]
            over=(command.category in fits and sum(a['category'] in fits for a in prior)>=5) or (command.category=='CALIBRATION' and any(a['category']=='CALIBRATION' for a in prior))
            if over:
                self.event(protocol_id,'ATTEMPT_BUDGET_REFUSED',db=db,configuration=command.model_dump(),reason='五次拟合及一次校准预算包括失败和中止；不得选择性丢弃')
                db.commit()
                raise HTTPException(409,'预登记拟合/校准预算已用尽，保留超限请求')
            db.execute('INSERT INTO research_attempts VALUES(?,?,?)',(value['attempt_id'],protocol_id,encode(value)))
            self.event(protocol_id,'ATTEMPT_STARTED',db=db,attempt_id=value['attempt_id'],configuration=command.model_dump())
            db.commit()
        return value

    def finish_attempt(self,attempt_id,command):
        with self.ledger.connection() as db:row=db.execute('SELECT protocol_id FROM research_attempts WHERE id=?',(attempt_id,)).fetchone()
        if row is None:raise HTTPException(404,'研究尝试不存在')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior=[json.loads(r[0]) for r in db.execute('SELECT value FROM research_events WHERE protocol_id=?',(row[0],))]
            if any(e['action'] in {'ATTEMPT_FINISHED','ATTEMPT_INTERRUPTED'} and e['attempt_id']==attempt_id for e in prior):
                db.rollback();raise HTTPException(409,'已结束的尝试不能改写；新尝试须另登记')
            self.event(row[0],'ATTEMPT_FINISHED',db=db,attempt_id=attempt_id,**command.model_dump());db.commit()
        return next(a for a in self.attempts(row[0]) if a['attempt_id']==attempt_id)

    def freeze(self,protocol_id,command):
        protocol=self.get(protocol_id);attempts=self.attempt_manifest(protocol_id)['attempts'];gaps=list(protocol['freeze_gaps'])
        expected=[a['attempt_id'] for a in attempts]
        if len(command.attempt_ids)!=len(set(command.attempt_ids)) or set(command.attempt_ids)!=set(expected):gaps.append('ATTEMPT_MANIFEST_INCOMPLETE')
        if any(a['status']=='RUNNING' for a in attempts):gaps.append('ATTEMPT_STILL_RUNNING')
        event=self.event(protocol_id,'FREEZE_REFUSED',gaps=gaps,expected_attempt_ids=expected,submitted_attempt_ids=command.attempt_ids,
            reason='19/20实际模型、校准、政策及方法验收尚未完成，登记不会授予资格')
        raise HTTPException(409,{'gaps':gaps,'audit_event_id':event['event_id']})

    def dataset(self,dataset_id):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM research_datasets WHERE id=?',(dataset_id,)).fetchone()
        if row is None:raise HTTPException(404,'研究数据登记不存在')
        return json.loads(row[0])

    def datasets(self):
        with self.ledger.connection() as db:return [json.loads(r[0]) for r in db.execute('SELECT value FROM research_datasets ORDER BY rowid DESC')]

    def register_dataset(self,command):
        value=import_dataset(self.evidence,command)
        with self.ledger.connection() as db:db.execute('INSERT INTO research_datasets VALUES(?,?)',(value['dataset_id'],encode(value)))
        return value

    def partition(self,dataset_id,name):
        try:return partition(self.evidence,self.dataset(dataset_id),name)
        except HTTPException as exc:
            if name=='SEALED':
                for p in self.protocols():
                    if p['dataset_id']==dataset_id:self.event(p['protocol_id'],'SEALED_INPUT_ACCESS_REFUSED',reason='普通分片入口禁止封存输入',confirmatory_pass_look=False)
            raise exc

    def sealed_input(self,protocol_id,command):
        protocol=self.get(protocol_id)
        if not protocol['dataset_id']:raise HTTPException(409,'尚无登记数据')
        value=partition(self.evidence,self.dataset(protocol['dataset_id']),'SEALED',allow_sealed=True)
        event=self.event(protocol_id,'SEALED_INPUT_ACCESSED',reason=command.reason,partition='SEALED',
            data_fingerprint=protocol['data_fingerprint'],first_date=value['metadata']['first_date'],last_date=value['metadata']['last_date'],
            context_first_date=value['metadata']['context_first_date'],labels_or_candidate_results_computed=False,confirmatory_pass_look=False,
            independence='UNPROVEN; 输入可见不等于正式结果查看，重复区间不得重命名成独立封存')
        return {**value,'audit_event_id':event['event_id'],'confirmatory_pass_look':False}

    def archive_exposed(self,sha):
        for protocol in self.protocols():
            if not protocol['dataset_id']:continue
            dataset=self.dataset(protocol['dataset_id']);sealed=dataset['partitions']['SEALED']
            if sha in {a['sha256'] for a in dataset['original_archives']} or sha==sealed.get('artifact',{}).get('sha256'):
                self.event(protocol['protocol_id'],'ORIGINAL_ARCHIVE_EXPOSED',sha256=sha,reason='公开下载原容器，可能包含封存输入；工程哈希校验不是PASS查看',
                    exposure_scope='WHOLE_SOURCE_CONTAINER_OR_SEALED_PARTITION',confirmatory_pass_look=False,labels_or_candidate_results_computed=False)

    def market_input_exposed(self,value,route):
        facts=[]
        def visit(item):
            if isinstance(item,dict):
                if item.get('group')=='DAILY' and item.get('trade_date'):facts.append(item)
                elif item.get('instrument') and item.get('event_date') and item.get('kind'):
                    facts.append({**item,'trade_date':item['event_date']})
                else:
                    for child in item.values():visit(child)
            elif isinstance(item,list):
                for child in item:visit(child)
        visit(value)
        for protocol in self.protocols():
            if not protocol['dataset_id']:continue
            dataset=self.dataset(protocol['dataset_id']);sealed=dataset['partitions']['SEALED']
            matches=[f for f in facts if f.get('instrument') in dataset['scope']['instruments'] and sealed.get('first_date','9999')<=f['trade_date']<=sealed.get('last_date','0000')]
            if matches:self.event(protocol['protocol_id'],'SEALED_MARKET_INPUT_EXPOSED',route=route,rows=len(matches),
                first_date=min(f['trade_date'] for f in matches),last_date=max(f['trade_date'] for f in matches),
                confirmatory_pass_look=False,labels_or_candidate_results_computed=False)
        return value

    def checkpoint(self,protocol_id,command):
        self.get(protocol_id)
        if command.kind=='EARLY_PASS':
            event=self.event(protocol_id,'OPTIONAL_STOPPING_DEVIATION',**command.model_dump(),confirmatory_pass_look=False,accepted=False)
            raise HTTPException(409,{'reason':'未登记额外可判PASS查看；不能临时停止改判','audit_event_id':event['event_id']})
        if command.kind=='STATISTICAL_FINAL':
            event=self.event(protocol_id,'RESULT_ACCESS_REFUSED',**command.model_dump(),confirmatory_pass_look=False,accepted=False)
            raise HTTPException(409,{'reason':'19/20尚未完整冻结；21负责真实准入判定','audit_event_id':event['event_id']})
        return self.event(protocol_id,'OPERATIONAL_CHECKPOINT',**command.model_dump(),confirmatory_pass_look=False,accepted=True,
            validation_verdict=None,capability='NOT_GRANTED')

    def get(self,protocol_id):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM research_protocols WHERE id=?',(protocol_id,)).fetchone()
        if row is None:raise HTTPException(404,'研究协议不存在')
        return json.loads(row[0])

    def protocols(self):
        with self.ledger.connection() as db:return [json.loads(r[0]) for r in db.execute('SELECT value FROM research_protocols ORDER BY rowid DESC')]

    def register(self,command):
        predecessor=self.get(command.predecessor_id) if command.predecessor_id else None
        dataset=self.dataset(command.dataset_id) if command.dataset_id else None
        if dataset:
            overlapping=[p for p in self.protocols() if p.get('dataset_id') and set(p['scope'].get('instruments',[]))&set(dataset['scope']['instruments'])
                and self.dataset(p['dataset_id'])['coverage']['first_date']<=dataset['coverage']['last_date']
                and self.dataset(p['dataset_id'])['coverage']['last_date']>=dataset['coverage']['first_date']]
            if overlapping and (not predecessor or predecessor['protocol_id'] not in {p['protocol_id'] for p in overlapping}):
                for p in overlapping:self.event(p['protocol_id'],'UNLINKED_REUSE_REFUSED',reason=command.basis,data_fingerprint=dataset['data_fingerprint'])
                raise HTTPException(409,'重复证券/区间须关联前序；不能换名称恢复独立封存或继承资格')
        value={'protocol_id':str(uuid4()),'registered_at':now(),'status':'DRAFT','basis':command.basis,
            'predecessor_id':command.predecessor_id,'dataset_id':command.dataset_id,
            'sealed_independence':'UNPROVEN',
            'validation_verdict':None,'review_status':'PENDING','capability':'NOT_GRANTED',
            'forward_started_at':None,'forward_deadline':None,
            'scope':{'namespace':'HISTORICAL','selection':'CURRENT_FINITE_LIST_CONDITIONAL_RESEARCH',
                'historical_membership_reconstructed':False,'historical_point_in_time_proven':False},
            'freeze_gaps':['DATA_FINGERPRINT_MISSING','MODEL_ARTIFACT_MISSING','CALIBRATOR_ARTIFACT_MISSING',
                'POLICY_ARTIFACT_MISSING','VALIDATION_CODE_FINGERPRINT_MISSING','METHOD_VALIDATION_PENDING_TICKET20'],
            'ownership':{'model_freeze':'ticket19','complete_protocol_freeze':'ticket20','forward_start':'tickets30/32','risk_policy':'ticket22'},
            'registration_code_fingerprint':hashlib.sha256(encode({p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                for p in [Path(__file__),Path(__file__).with_name('datasets.py'),Path(__file__).with_name('design.py')]}).encode()).hexdigest()}
        if dataset:
            value.update(status='DESIGN_REGISTERED',data_fingerprint=dataset['data_fingerprint'],scope=dataset['scope'],
                design=proposal(dataset),freeze_gaps=[g for g in value['freeze_gaps'] if g!='DATA_FINGERPRINT_MISSING']+
                    ['SEALED_INDEPENDENCE_UNPROVEN','CURRENT_REVISION_NOT_HISTORICAL_PIT','COMPLETE_DAILY_INPUT_AND_STATUS_LIMITATIONS'])
        value['protocol_fingerprint']=hashlib.sha256(encode(value).encode()).hexdigest()
        with self.ledger.connection() as db:db.execute('INSERT INTO research_protocols VALUES(?,?)',(value['protocol_id'],encode(value)))
        self.event(value['protocol_id'],'PROTOCOL_REGISTERED',protocol_fingerprint=value['protocol_fingerprint'],predecessor_id=command.predecessor_id,
            confirmatory_pass_look=False,prior_engineering_exposure=dataset.get('engineering_exposure') if dataset else None)
        return value
