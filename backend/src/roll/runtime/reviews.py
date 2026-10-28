"""On-demand facts and actual coverage; no forecast or account-event writer."""
import hashlib
import json
import os
import threading
import time
import calendar as month_calendar
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from roll.accounts.ledger import encode, now
from roll.market.rules import SHANGHAI
from roll.market.evidence import DataRequest
from roll.market.verification_input import VerificationCommand as VerificationRequest
from roll.accounts.reconcile import consistency
from roll.agents.codex_process import process_creation,owner_alive

# Four fixed broad backgrounds each need DAILY and QUOTE; holdings share this cap.
LIMITS={'attempts':3,'backoff_seconds':[1,2],'timeout_seconds':8,'http_calls_per_attempt':8,'recursive_tasks':0}


class ReviewCancellation:
    def __init__(self,reviews,identifier):self.reviews,self.identifier=reviews,identifier
    def is_set(self):return self.reviews.stop.is_set() or self.reviews.get(self.identifier)['status']=='CANCELLED'


class ReviewCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    mode:Literal['ON_DEMAND','POST_CLOSE','HISTORICAL','RECOVERY']='ON_DEMAND'
    cutoff:datetime|None=None
    refresh_missing:bool=False


class MaintenanceCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    kind:Literal['ONCE','WEEKLY','MONTHLY']
    exchange:Literal['SSE','SZSE']='SSE'
    first_due_at:datetime


class Reviews:
    def __init__(self,ledger,market,evidence,clock=None,worker_enabled=True):
        self.ledger,self.market,self.evidence=ledger,market,evidence
        self.capabilities = None
        self.monitoring = None
        self.worker_enabled=worker_enabled
        self.resolutions=None
        self.forward=None
        self.dated_daily=None
        self.clock=clock or (lambda:datetime.now(timezone.utc))
        self.owner={'pid':os.getpid(),'creation_ticks':process_creation(os.getpid()),'nonce':str(uuid4())}
        self.stop=threading.Event()
        self.cancel_event=threading.Event()
        self.thread=None
        self.session_id=str(uuid4())
        self.session_started_at=None
        self.start_lock=threading.Lock()
        self.worker_error=None
        self.last_day_audit=None
        with ledger.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS review_tasks(id TEXT PRIMARY KEY, task_key TEXT UNIQUE NOT NULL, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS review_worker(slot INTEGER PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS review_audits(id TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS review_sessions(id TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS review_coverage_gaps(id TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS review_maintenance(id TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS review_maintenance_checks(id TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS review_verification_requests(id TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS review_running_days(day TEXT PRIMARY KEY, audit_id TEXT NOT NULL);
            ''')
            db.execute('CREATE TABLE IF NOT EXISTS schema_migrations(name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO schema_migrations VALUES(?,?)',('15-reviews-v1',now()))

    def start(self):
        if not self.worker_enabled:return False
        with self.start_lock:self.acquire_worker()
        return bool(self.thread and self.thread.is_alive())

    def acquire_worker(self):
        if self.thread and self.thread.is_alive():return
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT value FROM review_worker WHERE slot=1').fetchone()
            if old and json.loads(old[0]).get('worker_status')!='FAILED' and owner_alive(json.loads(old[0])):return
            self.session_id=str(uuid4())
            self.session_started_at=self.clock().isoformat()
            previous=db.execute('SELECT value FROM review_sessions ORDER BY rowid DESC LIMIT 1').fetchone()
            if previous:
                previous=json.loads(previous[0])
                end=previous.get('ended_at') or previous['last_seen_at']
                if datetime.fromisoformat(end)<self.clock():
                    failure=previous.get('close_reason')=='WORKER_EXCEPTION'
                    gap={'start':end,'end':self.session_started_at,'reason':'MODULE_FAILURE_COVERAGE_GAP' if failure else 'NORMAL_OFFLINE_NO_COVERAGE_PROMISED' if previous.get('ended_at') else 'PROCESS_OR_SLEEP_GAP_UNOBSERVED',
                        'monitoring_fault':failure,'previous_session_id':previous['session_id'],'session_id':self.session_id,
                        'forward_predictions_reconstructed':False,'expired_opportunities_sent':False}
                    gap_id=hashlib.sha256(encode(gap).encode()).hexdigest()
                    db.execute('INSERT OR IGNORE INTO review_coverage_gaps VALUES(?,?)',(gap_id,encode(gap)))
            db.execute('INSERT INTO review_sessions VALUES(?,?)',(self.session_id,encode({'session_id':self.session_id,
                'started_at':self.session_started_at,'last_seen_at':self.session_started_at,'ended_at':None,'host_owner':self.owner})))
            for row in db.execute('SELECT id,value FROM review_tasks'):
                task=json.loads(row['value'])
                if task['status']=='RUNNING':
                    if task['attempts']>=LIMITS['attempts']:
                        task.update(status='FAILED',finished_at=now(),recovery_reason='ATTEMPT_LIMIT_AFTER_INTERRUPTION')
                        task['module_errors'].append({'code':'ATTEMPT_LIMIT_AFTER_INTERRUPTION','message':'三次实际中断已耗尽同任务尝试上限，未发布第四次观察'})
                        audit=self.audit(task,task['frozen_result'])
                        task['audit_id']=audit['audit_id']
                        db.execute('INSERT INTO review_audits VALUES(?,?)',(audit['audit_id'],encode(audit)))
                    else:task.update(status='QUEUED',recovery_reason='INTERRUPTED_ATTEMPT_RESUMED_WITH_SAME_IDENTITY',retry_at=now())
                    db.execute('UPDATE review_tasks SET value=? WHERE id=?',(encode(task),row['id']))
            db.execute('INSERT OR REPLACE INTO review_worker VALUES(1,?)',(encode({'host_owner':self.owner,'started_at':now(),'heartbeat_at':now()}),))
            db.commit()
        self.worker_error=None
        self.thread=threading.Thread(target=self.run,name='roll-review-worker',daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set();self.cancel_event.set()
        if self.thread:self.thread.join(timeout=LIMITS['timeout_seconds']+1)
        # A blocked boundary cannot hand its lease to a second live worker.
        # The actual worker's finally block releases it if the finite join expires.
        if self.thread and self.thread.is_alive():return
        self.release_lease()

    def release_lease(self,error=None):
        with self.ledger.connection() as db:
            row=db.execute('SELECT value FROM review_worker WHERE slot=1').fetchone()
            if row and json.loads(row[0])['host_owner']==self.owner:
                session=json.loads(db.execute('SELECT value FROM review_sessions WHERE id=?',(self.session_id,)).fetchone()[0])
                if not session.get('ended_at'):
                    session.update(ended_at=self.clock().isoformat(),close_reason='WORKER_EXCEPTION' if error else 'NORMAL_CLOSE_NO_ALWAYS_ON_REQUIREMENT',worker_error=error)
                db.execute('UPDATE review_sessions SET value=? WHERE id=?',(encode(session),self.session_id))
                if error:
                    worker=json.loads(row[0]);worker.update(worker_status='FAILED',last_worker_error=error)
                    db.execute('UPDATE review_worker SET value=? WHERE slot=1',(encode(worker),))
                elif json.loads(row[0]).get('worker_status')!='FAILED':db.execute('DELETE FROM review_worker WHERE slot=1')

    def run(self):
        try:self.work()
        except Exception as error:self.worker_error={'code':type(error).__name__,'message':str(error)[:300],'occurred_at':now()}
        finally:self.release_lease(self.worker_error)

    def work(self):
        while not self.stop.is_set():
            identifier=None
            with self.ledger.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                owner=db.execute('SELECT value FROM review_worker WHERE slot=1').fetchone()
                if not owner or json.loads(owner[0])['host_owner']!=self.owner:return
                db.execute('UPDATE review_worker SET value=? WHERE slot=1',(encode({'host_owner':self.owner,'heartbeat_at':now()}),))
                session=json.loads(db.execute('SELECT value FROM review_sessions WHERE id=?',(self.session_id,)).fetchone()[0])
                seen=self.clock()
                if (seen-datetime.fromisoformat(session['last_seen_at'])).total_seconds()>60:
                    gap={'start':session['last_seen_at'],'end':seen.isoformat(),'reason':'RUNNING_HEARTBEAT_GAP_UNOBSERVED',
                         'monitoring_fault':False,'session_id':self.session_id,'forward_predictions_reconstructed':False,'expired_opportunities_sent':False}
                    db.execute('INSERT OR IGNORE INTO review_coverage_gaps VALUES(?,?)',(hashlib.sha256(encode(gap).encode()).hexdigest(),encode(gap)))
                session['last_seen_at']=self.clock().isoformat()
                db.execute('UPDATE review_sessions SET value=? WHERE id=?',(encode(session),self.session_id))
                for row in db.execute('SELECT id,value FROM review_tasks ORDER BY rowid'):
                    task=json.loads(row['value'])
                    if task['status'] not in {'QUEUED','RETRY_WAIT'} or datetime.fromisoformat(task['retry_at'])>datetime.now(timezone.utc):continue
                    task.update(status='RUNNING',attempts=task['attempts']+1,last_attempt_at=now(),host_owner=self.owner)
                    db.execute('UPDATE review_tasks SET value=? WHERE id=?',(encode(task),row['id']))
                    identifier=row['id'];break
                db.commit()
            if identifier:
                try:self.perform(identifier)
                except Exception as error:self.finish_error(identifier,error)
            self.check_maintenance()
            self.check_running_day()
            if hasattr(self, 'notifications'): self.notifications.work(self.owner)
            if self.monitoring:
                try:self.monitoring.check_post_close(self.clock())
                except HTTPException as error:self.worker_error={'code':'CAPABILITY_MONITORING_RETRY_REQUIRED','message':str(error.detail),'occurred_at':now()}
            if getattr(self, 'observation_updates', None) and (not self.capabilities or self.capabilities.lifecycle()['observations_allowed']):
                self.observation_updates.work(self.clock(), self.stop)
            if not self.capabilities or self.capabilities.lifecycle()['observations_allowed']:
                if self.dated_daily:self.dated_daily.work()
                if self.forward:self.forward.work()
            if getattr(self,'company_reports',None):
                self.company_reports.work(self.owner,self.stop)
            self.stop.wait(.05)

    def check_running_day(self):
        clock=self.clock()
        day=clock.astimezone(SHANGHAI).date().isoformat()
        if self.last_day_audit==day:return
        with self.ledger.connection() as db:
            if db.execute('SELECT 1 FROM review_running_days WHERE day=?',(day,)).fetchone():
                self.last_day_audit=day;return
        account=self.ledger.account()
        listing=self.market.listing()
        _,_,gaps,versions=self.facts_at(listing,clock)
        calendar=self.market.rules.calendar('SSE',clock.astimezone(SHANGHAI).date(),clock)
        audit=self.audit({'task_id':None,'inputs':{'trading_date':day,'phase':calendar['phase']},'frozen_account':account,'module_errors':[]},
            {'snapshot_id':None,'account_version':account['version'],'data_versions':versions,'gaps':gaps})
        audit.update(origin='RUNNING_DAY_CHECK',actual_seen_at=clock.isoformat())
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM review_running_days WHERE day=?',(day,)).fetchone():
                db.execute('INSERT INTO review_audits VALUES(?,?)',(audit['audit_id'],encode(audit)))
                db.execute('INSERT INTO review_running_days VALUES(?,?)',(day,audit['audit_id']))
            db.commit()
        self.last_day_audit=day

    def audits(self):
        with self.ledger.connection() as db:return [json.loads(row[0]) for row in db.execute('SELECT value FROM review_audits ORDER BY rowid DESC')]

    def health(self):
        if not self.stop.is_set() and self.thread is None:self.start()
        tasks=self.history()
        with self.ledger.connection() as db:
            row=db.execute('SELECT value FROM review_worker WHERE slot=1').fetchone()
        worker=json.loads(row[0]) if row else None
        last_error=next((s['worker_error'] for s in reversed(self.coverage()['sessions']) if s.get('worker_error')),None)
        return {'worker_limit':1,'worker_state':'FAILED' if worker and worker.get('worker_status')=='FAILED' else 'RUNNING' if worker and owner_alive(worker) else 'STOPPED',
            'last_worker_error':last_error,
            'worker':worker,'technical_limits':LIMITS,'backlog':sum(t['status'] in {'QUEUED','RETRY_WAIT'} for t in tasks),
            'running':sum(t['status']=='RUNNING' for t in tasks)}

    def coverage(self):
        with self.ledger.connection() as db:
            sessions=[json.loads(r[0]) for r in db.execute('SELECT value FROM review_sessions ORDER BY rowid')]
            gaps=[json.loads(r[0]) for r in db.execute('SELECT value FROM review_coverage_gaps ORDER BY rowid')]
        return {'sessions':sessions,'gaps':gaps,'promise':'ACTUAL_OBSERVATIONS_ONLY_NO_ALWAYS_ON_REQUIREMENT',
                'forward_predictions_reconstructed':False,'expired_opportunities_sent':False}

    def calendar_due(self,exchange,value):
        local=value.astimezone(SHANGHAI)
        info=self.market.rules.calendar(exchange,local.date(),local)
        if info['is_trading_day'] is None:raise HTTPException(422,'维护日期的交易所日历未适配，不按工作日猜测')
        if info['is_trading_day'] is False:
            next_day=self.market.rules.next_trading_day(exchange,local.date())
            if next_day is None:raise HTTPException(422,'下一维护交易日未知')
            local=local.replace(year=int(next_day[:4]),month=int(next_day[5:7]),day=int(next_day[8:10]))
        return local

    def register_maintenance(self,command:MaintenanceCommand):
        if command.first_due_at.tzinfo is None:raise HTTPException(422,'维护时间须带时区')
        due=self.calendar_due(command.exchange,command.first_due_at)
        content=command.model_dump(mode='json')
        identity=hashlib.sha256(encode({**content,'first_due_at':due.isoformat()}).encode()).hexdigest()
        schedule={**content,'schedule_id':identity,'next_due_at':due.isoformat(),'next_nominal_at':command.first_due_at.astimezone(SHANGHAI).isoformat(),'registered_at':now(),
            'calendar_version':command.exchange+'-2026','status':'ACTIVE','business_checks_owner':'CAPABILITY_LIFECYCLE'}
        with self.ledger.connection() as db:
            db.execute('INSERT OR IGNORE INTO review_maintenance VALUES(?,?)',(identity,encode(schedule)))
            schedule=json.loads(db.execute('SELECT value FROM review_maintenance WHERE id=?',(identity,)).fetchone()[0])
        return schedule

    def next_maintenance(self,schedule,due):
        if schedule['kind']=='ONCE':return None
        due=datetime.fromisoformat(schedule.get('next_nominal_at',due.isoformat()))
        if schedule['kind']=='WEEKLY':candidate=due+timedelta(days=7)
        else:
            year=due.year+(due.month==12);month=due.month%12+1
            day=min(datetime.fromisoformat(schedule['first_due_at']).day,month_calendar.monthrange(year,month)[1])
            candidate=due.replace(year=year,month=month,day=day)
        schedule['next_nominal_at']=candidate.isoformat()
        try:return self.calendar_due(schedule['exchange'],candidate)
        except HTTPException:return None

    def check_maintenance(self):
        checked=self.clock()
        checked_any=False
        with self.ledger.connection() as read:
            due = any(json.loads(row[0]).get('next_due_at') and datetime.fromisoformat(json.loads(row[0])['next_due_at']) <= checked
                      for row in read.execute('SELECT value FROM review_maintenance'))
        prepared = self.monitoring.prepare_maintenance(checked) if due and self.monitoring else []
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            business_checks = None
            for row in db.execute('SELECT id,value FROM review_maintenance'):
                schedule=json.loads(row['value'])
                if not schedule['next_due_at'] or datetime.fromisoformat(schedule['next_due_at'])>checked:continue
                due=datetime.fromisoformat(schedule['next_due_at'])
                key=hashlib.sha256((schedule['schedule_id']+'|'+due.isoformat()).encode()).hexdigest()
                checked_any=True
                account=self.ledger.account(db=db)
                state,reasons=consistency(account,self.ledger.pending_drafts())
                if business_checks is None and self.monitoring:business_checks=self.monitoring.apply_maintenance(prepared,db)
                entry={'check_id':key,'schedule_id':schedule['schedule_id'],'scheduled_at':due.isoformat(),'checked_at':checked.isoformat(),
                    'status':'OVERDUE_CHECKED' if (checked-due).total_seconds()>1 else 'DUE_CHECKED',
                    'late_seconds':max(0,(checked-due).total_seconds()),'account_version':account['version'],
                    'calendar_version':schedule['calendar_version'],'runtime_check':{'state':state,'account_reasons':reasons,'service_seen_at':checked.isoformat()},
                    'business_checks':business_checks if business_checks is not None else {name:{'status':'NOT_CONNECTED','value':None} for name in ['mature_labels','qualification_expiry','new_experiment_conditions']},
                    'statistical_pass_checks_added':0,'retrained':False,'missed_due_instants':[]}
                candidate=self.next_maintenance(schedule,due)
                while candidate and candidate<=checked:
                    entry['missed_due_instants'].append(candidate.isoformat())
                    candidate=self.next_maintenance(schedule,candidate)
                schedule.update(next_due_at=candidate.isoformat() if candidate else None,status='ACTIVE' if candidate else 'FINISHED_OR_CALENDAR_UNSUPPORTED')
                self.ledger.crash_point('maintenance_before_commit')
                db.execute('INSERT OR IGNORE INTO review_maintenance_checks VALUES(?,?)',(key,encode(entry)))
                db.execute('UPDATE review_maintenance SET value=? WHERE id=?',(encode(schedule),row['id']))
            db.commit()
            if checked_any:self.ledger.crash_point('maintenance_after_commit')
        return self.maintenance_checks()

    def maintenance(self):
        with self.ledger.connection() as db:return [json.loads(r[0]) for r in db.execute('SELECT value FROM review_maintenance ORDER BY rowid')]

    def maintenance_checks(self):
        with self.ledger.connection() as db:return [json.loads(r[0]) for r in db.execute('SELECT value FROM review_maintenance_checks ORDER BY rowid')]

    def perform(self,identifier):
        task=self.get(identifier)
        if task['status']=='CANCELLED':return
        if self.capabilities and not self.capabilities.lifecycle()['observations_allowed']:return
        self.cancel_event.clear()
        started=time.monotonic()
        error=False
        network=0
        deadline=started+LIMITS['timeout_seconds']
        if task['refresh_missing']:
            cutoff=min(datetime.fromisoformat(task['inputs']['cutoff']),datetime.now(timezone.utc))
            gaps=task['frozen_result']['gaps']
            members={m['instrument'] for m in task['frozen_listing']['members']}
            stock_objects=sorted({g['instrument'] for g in gaps if g['instrument'] in members})
            stock_groups=[g for g in ['QUOTE','DAILY','STATUS','ADJUSTMENTS','ANNOUNCEMENTS','PERFORMANCE','MAJOR_EVENTS'] if any(x['group']==g and x['instrument'] in members for x in gaps)]
            background_objects=sorted({g['instrument'] for g in gaps if g['instrument'] not in members})
            remaining_calls=LIMITS['http_calls_per_attempt'];remaining_bytes=4194304
            requests=[(stock_objects,stock_groups,'OBSERVATION'),(background_objects,['DAILY','QUOTE'],'BACKGROUND')]
            for objects,groups,purpose in requests:
                if not objects or not groups or remaining_calls<1 or remaining_bytes<1 or time.monotonic()>=deadline:continue
                request=self.evidence.request(DataRequest(instruments=objects,groups=groups,purpose=purpose,
                    start_date=cutoff.astimezone(SHANGHAI).date()-timedelta(days=40),end_date=cutoff.astimezone(SHANGHAI).date(),
                    cutoff=cutoff,timeout_seconds=LIMITS['timeout_seconds'],max_calls=remaining_calls))
                limits={'deadline':deadline,'max_response_bytes':1048576,'max_total_bytes':remaining_bytes,'host_owner':self.owner}
                run=self.evidence.retrieve(request['request_id'],acquisition_limits=limits,cancel_event=ReviewCancellation(self,identifier))
                task['retrieval_runs'].append(run['run_id'])
                remaining_calls-=len(run['tools']);remaining_bytes-=run.get('retrieved_bytes',0)
                error=error or run['status']=='FAILED'
                task['module_errors'].extend({'run_id':run['run_id'],**g} for g in run['gaps']
                    if g['code'].endswith(('Error','Timeout')) or g['code'] in {'REQUEST_FAILED','PARSE_FAILED'})
                network+=sum(max(0,(datetime.fromisoformat(t['finished_at'])-datetime.fromisoformat(t['started_at'])).total_seconds()) for t in run['tools'] if t.get('finished_at'))
        acquisition=time.monotonic()-started if task['refresh_missing'] else 0
        local_started=time.monotonic()
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            latest=json.loads(db.execute('SELECT value FROM review_tasks WHERE id=?',(identifier,)).fetchone()[0])
            if latest['status']=='CANCELLED':return
            if self.capabilities and not self.capabilities.lifecycle(db)['observations_allowed']:return
            if self.stop.is_set():
                task.update(status='QUEUED',retry_at=now(),recovery_reason='NORMAL_CLOSE_PENDING_ATTEMPT')
            elif error and task['attempts']<LIMITS['attempts'] and time.monotonic()<deadline:
                task.update(status='RETRY_WAIT',retry_at=(datetime.now(timezone.utc)+timedelta(seconds=LIMITS['backoff_seconds'][task['attempts']-1])).isoformat())
            else:
                result=task['frozen_result']
                if task['refresh_missing']:
                    cutoff=datetime.fromisoformat(task['inputs']['cutoff'])
                    knowledge=self.clock()
                    instruments,observations,gaps,versions=self.facts_at(task['frozen_listing'],cutoff,knowledge)
                    result.update(instruments=instruments,observations=observations,gaps=gaps,data_versions=versions,
                        source_assessments=self.source_assessments(versions,knowledge),
                        knowledge_cutoff=knowledge.isoformat(),observed_at=knowledge.isoformat(),
                        knowledge_basis='ACTUAL_COMPLETION_NO_BACKDATED_KNOWLEDGE')
                task.update(status='TIMED_OUT' if time.monotonic()>=deadline else 'PARTIAL' if result['gaps'] else 'COMPLETE',
                            finished_at=now(),result=result)
                previous=next((json.loads(row[0]) for row in db.execute('SELECT value FROM review_tasks ORDER BY rowid DESC')
                    if json.loads(row[0]).get('result')),None)
                semantic={'account_version':result['account_version'],'phase':result['calendar']['phase'],
                          'gaps':result['gaps'],'instruments':[],'observations':[]}
                for item in result['instruments']:
                    semantic['instruments'].append({'instrument':item['instrument'],'role':item['role'],'quote_status':item['quote_status'],
                        'quote':{k:item['quote'].get(k) for k in ['last','upstream_at','raw_hash','errors']} if item['quote'] else None,
                        'daily':{k:item['last_complete_daily'].get(k) for k in ['trade_date','close','raw_hash','completion_state']} if item['last_complete_daily'] else None,
                        'company':[{k:f.get(k) for k in ['group','raw_hash','document_hash','disclosure_date','state','title']} for f in item['company_facts']]})
                semantic['observations']=[{k:o.get(k) for k in ['kind','instrument','state','title','basis_raw_hashes']} for o in result['observations']]
                fingerprint=hashlib.sha256(encode(semantic).encode()).hexdigest()
                result['state_fingerprint']=fingerprint
                result['previous_snapshot_id']=previous['result']['snapshot_id'] if previous else None
                result['change']='NO_SUBSTANTIAL_CHANGE' if previous and previous['result'].get('state_fingerprint')==fingerprint else 'NEW_INFORMATION'
                result['coverage']['unobserved_trigger_sequence']='NOT_RECONSTRUCTED'
                if hasattr(self, 'notifications'): self.notifications.review_completed(db, task, result)
                audit=self.audit(task,result,db)
                db.execute('INSERT INTO review_audits VALUES(?,?)',(audit['audit_id'],encode(audit)))
                task['audit_id']=audit['audit_id']
            task['timing']['network_seconds']+=round(network,6)
            task['timing']['acquisition_seconds']+=round(acquisition,6)
            task['timing']['local_seconds']+=round(time.monotonic()-local_started+max(0,acquisition-network),6)
            self.ledger.crash_point('review_before_commit')
            db.execute('UPDATE review_tasks SET value=? WHERE id=?',(encode(task),identifier))
            db.commit()
            self.ledger.crash_point('review_after_commit')

    def finish_error(self,identifier,error):
        with self.ledger.connection() as db:
            row=db.execute('SELECT value FROM review_tasks WHERE id=?',(identifier,)).fetchone()
            task=json.loads(row[0])
            if task['status']=='CANCELLED':return
            task.update(status='FAILED',finished_at=now())
            task['module_errors'].append({'code':type(error).__name__,'message':str(error)[:300]})
            audit=self.audit(task,task['frozen_result'])
            task['audit_id']=audit['audit_id']
            db.execute('INSERT INTO review_audits VALUES(?,?)',(audit['audit_id'],encode(audit)))
            db.execute('UPDATE review_tasks SET value=? WHERE id=?',(encode(task),identifier))

    def audit(self,task,result,db=None):
        state,reasons=consistency(task['frozen_account'],self.ledger.pending_drafts())
        metrics={name:{'status':'NOT_CONNECTED','value':None} for name in ['unfinished_execution_intents','invalidated_actions','duplicate_notifications','action_flips','shadow_records']}
        if hasattr(self, 'actions'): metrics.update(self.actions.metrics())
        if hasattr(self, 'intents'): metrics.update(self.intents.metrics())
        if hasattr(self, 'notifications'): metrics.update(self.notifications.metrics(db))
        if hasattr(self, 'reports'): metrics.update(self.reports.metrics(db))
        metrics.update(data_coverage={'status':'CHECKED','value':len(result['gaps']),'gaps':result['gaps']},
            account_differences={'status':'CHECKED','value':len(reasons),'state':state,'reasons':reasons},
            module_errors={'status':'CHECKED','value':len(task['module_errors']),'errors':task['module_errors']})
        return {'audit_id':str(uuid4()),'task_id':task['task_id'],'trade_date':task['inputs']['trading_date'],
            'phase':task['inputs']['phase'],'checked_at':now(),'account_version':result['account_version'],
            'snapshot_id':result['snapshot_id'],'data_versions':result['data_versions'],'metrics':metrics,
            'critical_review':{'status':'NOT_REQUIRED','reason':'普通运行摘要不自动升级为多源核验'}}

    def get_audit(self,identifier):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM review_audits WHERE id=?',(identifier,)).fetchone()
        if row is None:raise HTTPException(404,'运行审计不存在')
        return json.loads(row[0])

    def cancel(self,identifier):
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT value FROM review_tasks WHERE id=?',(identifier,)).fetchone()
            if row is None:raise HTTPException(404,'观察任务不存在')
            task=json.loads(row[0])
            if task['status'] in {'QUEUED','RUNNING','RETRY_WAIT'}:
                task.update(status='CANCELLED',finished_at=now(),cancel_reason='USER_CANCELLED_NO_OBSERVATION_PUBLISHED')
                db.execute('UPDATE review_tasks SET value=? WHERE id=?',(encode(task),identifier))
            db.commit()
        return task

    def restrict_observations(self,db,event):
        """Cancel related pending observations in the lifecycle writer chain."""
        for identifier,raw in db.execute('SELECT id,value FROM review_tasks').fetchall():
            task=json.loads(raw)
            if task['status'] not in {'QUEUED','RUNNING','RETRY_WAIT'}:continue
            task.update(status='CANCELLED',finished_at=event['recorded_at'],cancel_reason='ALL_MONITOR_SUSPENDED',lifecycle_event_id=event['event_id'])
            db.execute('UPDATE review_tasks SET value=? WHERE id=?',(encode(task),identifier))

    def facts_at(self,listing,cutoff,knowledge=None):
        knowledge=knowledge or cutoff
        related={m['instrument'] for m in listing['members']}
        objects=[{'instrument':m['instrument'],'role':'HOLDING' if m['holding'] else 'WATCH'} for m in listing['members']]
        objects.extend({'instrument':i['instrument'],'role':'BACKGROUND','name':i['name']} for i in listing['background_indices']
            if not i.get('related_instruments') or related.intersection(i['related_instruments']))
        scope={i['instrument'] for i in objects}
        snapshots=self.evidence.snapshots(available_before=knowledge)
        facts=[]
        observations=[]
        versions=[]
        for snapshot in snapshots:
            selected=[]
            for fact in snapshot['facts']:
                if fact['instrument'] not in scope:continue
                if fact.get('upstream_at') and datetime.fromisoformat(fact['upstream_at'])>cutoff:continue
                date_value=fact.get('trade_date') or fact.get('disclosure_date')
                if date_value and date_value[:10]>cutoff.astimezone(SHANGHAI).date().isoformat():continue
                selected.append({**fact,'snapshot_id':snapshot['snapshot_id'],'run_id':snapshot['run_id'],
                                 'evidence_kind':snapshot['evidence_kind']})
            if not selected:continue
            facts.extend(selected)
            versions.append(snapshot['snapshot_id'])
            hashes={f['raw_hash'] for f in selected}
            observations.extend({**o,'observed_at':o.get('observed_at') or snapshot['created_at'],'available_time_basis':'ORIGINAL_OBSERVATION_TIME' if o.get('observed_at') else 'ORIGINAL_SNAPSHOT_ACTUAL_PUBLICATION_TIME',
                'snapshot_id':snapshot['snapshot_id'],'run_id':snapshot['run_id']} for o in snapshot['observations']
                if set(o['basis_raw_hashes']) & hashes and datetime.fromisoformat(o.get('observed_at') or snapshot['created_at'])<=knowledge)
        instruments=[]
        gaps=[]
        facts=list({(f['instrument'],f['group'],f['raw_hash'],f.get('trade_date'),f.get('art_code'),f.get('report_period')):f for f in reversed(facts)}.values())
        observations=list({(o['instrument'],o['kind'],tuple(o['basis_raw_hashes'])):o for o in reversed(observations)}.values())
        session=cutoff.astimezone(SHANGHAI).date()
        calendar=self.market.rules.calendar('SSE',session,cutoff)
        if calendar['is_trading_day'] is False or calendar['phase'] in {'PRE_OPEN','OPENING_AUCTION','PRE_CONTINUOUS'}:
            for offset in range(1,15):
                candidate=session-timedelta(days=offset)
                if self.market.rules.calendar('SSE',candidate)['is_trading_day'] is True:
                    session=candidate;break
        for obj in objects:
            own=[f for f in facts if f['instrument']==obj['instrument']]
            quotes=[f for f in own if f['group']=='QUOTE' and f.get('last') is not None and f.get('upstream_at') is not None and not f.get('errors')]
            quote=max(quotes,key=lambda f:(f['upstream_at'],f['available_at'])) if quotes else None
            bars=[f for f in own if f['group']=='DAILY' and f.get('adjustment')=='RAW']
            complete=[f for f in bars if f.get('completion_state','').startswith('COMPLETE') and not f.get('errors')]
            last=max(complete,key=lambda f:(f['trade_date'],f['available_at'])) if complete else None
            incomplete=[f for f in bars if not f.get('completion_state','').startswith('COMPLETE')]
            incomplete=max(incomplete,key=lambda f:(f['trade_date'],f['available_at'])) if incomplete else None
            status='MISSING' if not quote else 'OBSERVED_SESSION' if quote['trade_date']==session.isoformat() else 'STALE_PREVIOUS_SESSION'
            if status!='OBSERVED_SESSION':gaps.append({'instrument':obj['instrument'],'group':'QUOTE','code':status})
            if not last:gaps.append({'instrument':obj['instrument'],'group':'DAILY','code':'NO_COMPLETE_DAILY'})
            if calendar['phase']=='AFTER_CLOSE' and calendar['is_trading_day'] is True and (not last or last['trade_date']!=session.isoformat()):
                gaps.append({'instrument':obj['instrument'],'group':'DAILY','code':'POST_CLOSE_DAILY_INCOMPLETE'})
            if obj['role']!='BACKGROUND':
                for group in ['STATUS','ADJUSTMENTS','ANNOUNCEMENTS','PERFORMANCE','MAJOR_EVENTS']:
                    group_facts=[f for f in own if f['group']==group]
                    if not group_facts or group=='STATUS' and all(f.get('state')=='UNKNOWN' for f in group_facts):
                        gaps.append({'instrument':obj['instrument'],'group':group,'code':'CURRENT_STATUS_UNKNOWN' if group=='STATUS' else 'NO_ACQUIRED_FACT'})
            instruments.append({**obj,'quote':quote,'quote_status':status,'last_complete_daily':last,
                'incomplete_daily':incomplete,'company_facts':[f for f in own if f['group'] not in {'QUOTE','DAILY'}]})
        return instruments,observations,gaps,versions

    def source_assessments(self,versions,knowledge):
        if not self.resolutions:return []
        result=[]
        for resolution in self.resolutions.history():
            if resolution['status']!='COMPLETED' or datetime.fromisoformat(resolution['finished_at'])>knowledge:continue
            refs=[a['run_id'] for a in resolution['attempts'] if self.evidence.get('retrieval_runs',a['run_id']).get('snapshot_id') in versions]
            if not refs:continue
            invalidations=[d for d in self.resolutions.dependencies(target_id=resolution['resolution_id']) if datetime.fromisoformat(d['recorded_at'])<=knowledge]
            result.append({'resolution_id':resolution['resolution_id'],'state':resolution['state'],'source_checks':resolution['source_checks'],
                'freshness':resolution['freshness'],'run_ids':refs,'dependency_status':'INVALIDATED' if invalidations else 'CURRENT','invalidations':invalidations})
        return result

    def submit(self,command:ReviewCommand):
        if self.capabilities and not self.capabilities.lifecycle()['observations_allowed']:
            raise HTTPException(409, 'ALL_MONITOR_SUSPENDED')
        if not self.stop.is_set() and self.thread is None:self.start()
        started=self.clock()
        cutoff=command.cutoff or started
        if cutoff.tzinfo is None or cutoff>started:
            raise HTTPException(422,'观察截止须带时区且不能晚于当前实际运行时点')
        local=cutoff.astimezone(SHANGHAI)
        calendar=self.market.rules.calendar('SSE',local.date(),local)
        if command.mode=='POST_CLOSE' and calendar['phase'] not in {'AFTER_CLOSE','CLOSED'}:
            raise HTTPException(422,'盘后复盘须在适用日历的盘后或休市阶段；当前可按需观察')
        account=self.ledger.account()
        listing=self.market.listing()
        knowledge=started if command.mode=='HISTORICAL' else cutoff
        instruments,observations,gaps,versions=self.facts_at(listing,cutoff,knowledge)
        identity={'mode':command.mode,'trading_date':local.date().isoformat(),'phase':calendar['phase'],
                  'cutoff':cutoff.isoformat(),'account_version':account['version'],'list_version':listing['version'],
                  'data_versions':versions,
                  'shadow_version':None}
        result={'snapshot_id':str(uuid4()),'previous_snapshot_id':None,'calendar':calendar,
                'account_version':account['version'],'account_confirmed_at':account['confirmed_at'],
                'account_effective_at':account['effective_at'],'cutoff':cutoff.isoformat(),
                'account_basis':'CURRENT_CONFIRMED_ACCOUNT_NOT_PAST_ACCOUNT_PROOF' if command.mode=='HISTORICAL' else 'CURRENT_CONFIRMED_ACCOUNT',
                'observed_at':started.isoformat(),'formal_judgment':'DISABLED','forecast':None,
                'knowledge_cutoff':knowledge.isoformat(),'knowledge_basis':'RETROSPECTIVE_ACTUAL_RUN' if command.mode=='HISTORICAL' else 'KNOWN_AT_REQUEST_CUTOFF',
                'forward_sample_created':False,'coverage':{'intraday_observed':calendar['phase']=='CONTINUOUS' and any(i['quote_status']=='OBSERVED_SESSION' for i in instruments),'minute_capture_promised':False},
                'instruments':instruments,'observations':observations,'data_versions':versions,'gaps':gaps}
        result['source_assessments']=self.source_assessments(versions,knowledge)
        identity['refresh_missing']=command.refresh_missing
        task_key=hashlib.sha256(encode({**identity,'cutoff':cutoff.astimezone(timezone.utc).isoformat()}).encode()).hexdigest()
        task={'task_id':str(uuid4()),'task_key':task_key,'inputs':identity,'status':'QUEUED','attempts':0,
              'refresh_missing':command.refresh_missing,'frozen_listing':listing,'frozen_account':account,'frozen_result':result,
              'retrieval_runs':[],'module_errors':[],'timing':{'network_seconds':0,'acquisition_seconds':0,'local_seconds':0},
              'retry_at':now(),'created_at':now(),'finished_at':None,'result':None}
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if self.capabilities and not self.capabilities.lifecycle(db)['observations_allowed']:
                raise HTTPException(409, 'ALL_MONITOR_SUSPENDED')
            old=db.execute('SELECT value FROM review_tasks WHERE task_key=?',(task_key,)).fetchone()
            if old:return json.loads(old[0])
            db.execute('INSERT INTO review_tasks VALUES(?,?,?)',(task['task_id'],task_key,encode(task)))
            db.commit()
        return task

    def summary(self):
        clock=self.clock()
        calendar=self.market.rules.calendar('SSE',clock.astimezone(SHANGHAI).date(),clock)
        tasks=self.history()
        latest=next((t for t in tasks if t.get('result')),None)
        compact={k:latest[k] for k in ['task_id','status','attempts','result','audit_id','timing','module_errors']} if latest else None
        gaps=self.coverage()['gaps']
        return {'calendar':calendar,'latest':compact,'health':self.health(),'coverage_gap':gaps[-1] if gaps else None}

    def replay(self,identifier):
        task=self.get(identifier)
        if not task.get('result'):raise HTTPException(409,'该任务尚无已发布观察')
        run_ids={i['run_id'] for item in task['result']['instruments'] for i in [item['quote'],item['last_complete_daily'],item['incomplete_daily'],*item['company_facts']] if i}
        for run_id in run_ids:self.evidence.replay(run_id)
        self.ledger.account(task['result']['account_version']) if task['result']['account_version'] else None
        return {'task_id':identifier,'result':task['result'],'replay_kind':'IMMUTABLE_ARCHIVE_ONLY','network_calls':0,'verified_run_ids':sorted(run_ids)}

    def verification_request(self,identifier,command:VerificationRequest):
        task=self.get(identifier)
        if not task.get('result'):raise HTTPException(409,'重点复盘须关联已发布观察')
        cutoff=datetime.fromisoformat(task['result']['knowledge_cutoff'])
        if command.knowledge_cutoff is not None and command.knowledge_cutoff!=cutoff:raise HTTPException(422,'重点复盘知识截止须保持原观察已保存时点')
        if not command.reason.strip() or len({f.fact_id for f in command.facts})!=len(command.facts):raise HTTPException(422,'疑点说明须非空，决定性事实标识须唯一')
        originals=[]
        for item in command.facts:
            for reference in item.references:
                if reference.snapshot_id not in task['result']['data_versions']:raise HTTPException(422,'核验引用须属于该观察实际保存的数据版本')
                snapshot=self.evidence.get('market_evidence_snapshots',reference.snapshot_id)
                if reference.fact_index>=len(snapshot['facts']):raise HTTPException(422,'原事实下标不存在')
                fact=snapshot['facts'][reference.fact_index]
                event_cutoff=datetime.fromisoformat(task['result']['cutoff'])
                date=fact.get('trade_date') or fact.get('disclosure_date')
                if fact['instrument'] not in {i['instrument'] for i in task['result']['instruments']} or datetime.fromisoformat(fact['available_at'])>cutoff or (date and date[:10]>event_cutoff.astimezone(SHANGHAI).date().isoformat()) or (fact.get('upstream_at') and datetime.fromisoformat(fact['upstream_at'])>event_cutoff):
                    raise HTTPException(422,'决定性原事实须属于原观察对象及实际可得/事件截止，不能借同快照混入其他对象或后知事实')
                if item.field not in fact:raise HTTPException(422,'原事实不存在该决定性字段')
                self.evidence.raw(fact['raw_hash'])
                originals.append({'fact_id':item.fact_id,'reference':reference.model_dump(),'field':item.field,'value':fact[item.field],
                    'raw_hash':fact['raw_hash'],'instrument':fact['instrument'],'available_at':fact['available_at']})
        payload=command.model_dump(mode='json',exclude_none=True)
        payload['knowledge_cutoff']=cutoff.isoformat()
        key=hashlib.sha256(encode({'task_id':identifier,'request':payload}).encode()).hexdigest()
        value={'request_id':key,'task_id':identifier,'snapshot_id':task['result']['snapshot_id'],'audit_id':task['audit_id'],
            'request':payload,'original_fact_values':originals,'status':'PENDING_CONSUMER_14','verification_id':None,'created_at':now()}
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT OR IGNORE INTO review_verification_requests VALUES(?,?)',(key,encode(value)))
            value=json.loads(db.execute('SELECT value FROM review_verification_requests WHERE id=?',(key,)).fetchone()[0])
            audit=json.loads(db.execute('SELECT value FROM review_audits WHERE id=?',(task['audit_id'],)).fetchone()[0])
            audit['critical_review']={'status':value['status'],'request_id':key,'verification_id':value['verification_id'],'trigger':command.trigger,'reason':command.reason}
            db.execute('UPDATE review_audits SET value=? WHERE id=?',(encode(audit),task['audit_id']))
            db.commit()
        return value

    def get(self,identifier):
        if not self.stop.is_set() and self.thread is None:self.start()
        with self.ledger.connection() as db:
            row=db.execute('SELECT value FROM review_tasks WHERE id=?',(identifier,)).fetchone()
        if row is None:raise HTTPException(404,'观察任务不存在')
        return json.loads(row[0])

    def history(self):
        with self.ledger.connection() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT value FROM review_tasks ORDER BY rowid DESC')]
