"""Running-only forward samples. Archive first, then one SQLite commit owns the clock."""
import json
import os
import math
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from roll.accounts.ledger import encode, now
from roll.market.rules import SHANGHAI
from roll.research.registry import deadline_preview
from roll.research.models import features, predict, code_fingerprint
from roll.research.shadow import simulate, fingerprint, shadow_code


def forward_features(facts, observation, cutoff, feature_names, economic_cash):
    """Same frozen four-feature mathematics, actual current knowledge semantics."""
    rows = sorted([r for r in facts if r['trade_date'] <= observation],key=lambda r:r['trade_date'])[-21:]
    if len(rows) != 21 or rows[-1]['trade_date'] != observation: raise ValueError('FORWARD_CONTIGUOUS_LOOKBACK_21_REQUIRED')
    prices, volumes = [], []
    for row in rows:
        if row.get('adjustment')!='RAW' or row.get('volume_unit')!='SHARE' or row.get('errors') or row.get('completion_state')!='COMPLETE_REPORTED_HISTORICAL':
            raise ValueError('FORWARD_INPUT_NOT_COMPLETE_RAW_SHARE')
        for field in ['available_at','received_at','known_at']:
            value = datetime.fromisoformat(row[field]) if row.get(field) else None
            if value is None or value.tzinfo is None or value > cutoff: raise ValueError('FORWARD_INPUT_NOT_AVAILABLE')
        price, volume = Decimal(row['close']), Decimal(row['volume_shares'])
        if not price.is_finite() or not volume.is_finite() or price<=0 or volume<=0: raise ValueError('FORWARD_NUMERIC_INPUT_INVALID')
        prices.append(price); volumes.append(volume)
    factors=[]
    for i in range(1,21):
        cash=Decimal(0)
        if economic_cash:
            for event in rows[i].get('cash_events_effective',[]):
                stamp=event.get('available_at') or event.get('source',{}).get('received_at')
                received=event.get('source',{}).get('received_at')
                if not stamp or not received or datetime.fromisoformat(stamp)>cutoff or datetime.fromisoformat(received)>cutoff:
                    raise ValueError('CASH_EVENT_NOT_AVAILABLE')
                if event.get('ex_date') != rows[i]['trade_date'] or not event.get('source',{}).get('sha256'):
                    raise ValueError('CASH_EVENT_EFFECTIVE_DATE_OR_SOURCE_UNKNOWN')
                amount=Decimal(event['gross_cash_yuan_per_eligible_share'])
                if not amount.is_finite() or amount<0: raise ValueError('CASH_EVENT_AMOUNT_INVALID')
                cash+=amount
        factors.append((prices[i]+cash)/prices[i-1])
    returns=[float(v-1) for v in factors]; mean=sum(returns)/20
    values=[float(math.prod(factors[-5:])-1),float(math.prod(factors)-1),
        math.sqrt(sum((v-mean)**2 for v in returns)/20),math.log(float(volumes[-1]/(sum(volumes[:-1])/20)))]
    return {'features':dict(zip(feature_names,values)),'values':values,'input_trade_dates':[r['trade_date'] for r in rows],
        'latest_input_trade_date':observation,'raw_hashes':sorted({r['raw_hash'] for r in rows}),
        'observation_cutoff':observation+'T15:05:00+08:00','consumer_knowledge_cutoff':cutoff.isoformat(),
        'availability_basis':'ACTUAL_HOST_RECEIPT_AT_FORWARD_CONSUMER'}


class ForwardCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    purpose: Literal['RESEARCH', 'METHOD_VALIDATION'] = 'RESEARCH'
    basis: str = Field(min_length=1, max_length=2000)


class CheckCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    basis: str = Field(min_length=1, max_length=2000)


class StopCommand(CheckCommand):
    kind: Literal['USER_STOP','SAFETY_STOP']


class ForwardArchive:
    def __init__(self, shadow, prospective, clock=None):
        self.shadow, self.prospective = shadow, prospective
        self.registry, self.models = shadow.registry, shadow.models
        self.ledger, self.evidence = shadow.ledger, shadow.evidence
        self.clock = clock if clock and os.environ.get('ROLL_ENV') == 'test' else lambda: datetime.now(timezone.utc)
        with self.ledger.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS research_forward_plans(freeze_id TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS research_forward_samples(id TEXT PRIMARY KEY, protocol_id TEXT NOT NULL,
                    checkpoint TEXT NOT NULL, trading_date TEXT NOT NULL, value TEXT NOT NULL,
                    UNIQUE(protocol_id,checkpoint,trading_date));
                CREATE TABLE IF NOT EXISTS research_forward_checks(id TEXT PRIMARY KEY, freeze_id TEXT NOT NULL,value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS research_forward_assessments(id TEXT PRIMARY KEY, freeze_id TEXT NOT NULL,value TEXT NOT NULL);
            ''')
        self.last_worker_check = None
        self.recovery = lambda: {'state':'NOT_RESTORED'}

    def plan(self, freeze_id):
        self.shadow.get(freeze_id)
        with self.ledger.connection() as db:
            row = db.execute('SELECT value FROM research_forward_plans WHERE freeze_id=?',(freeze_id,)).fetchone()
        if not row: raise HTTPException(404,'尚未登记前向归档')
        return json.loads(row[0])

    def register(self, freeze_id, command):
        frozen = self.shadow.get(freeze_id)
        method = command.purpose == 'METHOD_VALIDATION'
        if method and (os.environ.get('ROLL_ENV') != 'test' or frozen['evidence_kind'] != 'METHOD_CASE'):
            raise HTTPException(403,'METHOD 前向工程仅允许测试环境的合成冻结工件')
        if not method and frozen['evidence_kind'] == 'METHOD_CASE':
            raise HTTPException(409,'METHOD 工件不能开始真实前向研究')
        if not method and self.shadow.current(freeze_id)['revision']:
            raise HTTPException(409,'已演化历史影子不能重置为真实前向；须明确后继实验与冻结基线')
        value = {'freeze_id':freeze_id,'protocol_id':frozen['protocol_id'],'namespace':'METHOD_CASE' if method else 'FORWARD',
            'registered_at':self.clock().isoformat(),'checkpoint_id':'POST_CLOSE_1505_SHANGHAI',
            'checkpoint_time':'15:05:00','timezone':'Asia/Shanghai','basis':command.basis,
            'started_at':None,'deadline':None,'status':'WAITING_FOR_FIRST_PERSISTED_PREDICTION',
            'complete_protocol_fingerprint':frozen['complete_protocol_fingerprint'],
            'adapter_code_fingerprint':self.code(),'capability':'NOT_GRANTED','statistical_pass_checks_added':0}
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT value FROM research_forward_plans WHERE freeze_id=?',(freeze_id,)).fetchone()
            if old: return json.loads(old[0])
            db.execute('INSERT INTO research_forward_plans VALUES(?,?)',(freeze_id,encode(value)))
            self.registry.event(frozen['protocol_id'],'FORWARD_PLAN_REGISTERED',db=db,freeze_id=freeze_id,namespace=value['namespace'],actual_forward_start=False)
            db.commit()
        return value

    @staticmethod
    def code():
        from pathlib import Path
        import hashlib
        from roll.market.post_close_packet import code as packet_code
        return fingerprint({'forward':hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
            'post_close_packet':packet_code(),
            'prospective':hashlib.sha256(Path(__file__).with_name('prospective.py').read_bytes().replace(b'\r\n',b'\n')).hexdigest()})

    def rows(self, plan, frozen, checked):
        # The engineering namespace uses known synthetic external input. Never REAL.
        if plan['namespace'] == 'METHOD_CASE':
            model = self.models.get(frozen['model_run_id'])
            inputs = self.shadow.checked_archive(model['input_archive'])
            return inputs['parts']['CALIBRATION']['facts'], []
        symbol = frozen['scope']['instruments'][0]
        plans = [p for p in self.prospective.plans() if p['instrument']==symbol]
        if not plans: return [], ['CURRENT_HOST_PROSPECTIVE_PLAN_MISSING']
        versions = self.prospective.as_of(plans[0]['plan_id'],checked)['versions']
        if any(v['evidence_kind']!='REAL_ACQUISITION' for v in versions):
            return [], ['SYNTHETIC_PROSPECTIVE_INPUT_CANNOT_START_REAL_CLOCK']
        attempts=self.prospective.post_close.acquisitions(plans[0]['plan_id'],checked)
        audits=self.prospective.post_close.obligations(plans[0]['plan_id'],checked,protocol_id=plan['protocol_id'],
            checkpoint_day=checked.astimezone(SHANGHAI).date().isoformat())
        suspension=self.prospective.post_close.suspension_receipts(plans[0]['plan_id'],checked)
        stock=self.prospective.post_close.stock_suspensions.receipts(plans[0]['plan_id'],checked)
        company=self.prospective.post_close.company_contracts.receipts(plans[0]['plan_id'],checked)
        rows,gaps,_=self.prospective.post_close.inputs(versions,symbol,checked,attempts,audits,suspension,stock,company)
        return rows,gaps

    def sessions(self, frozen, first, last, gaps=None):
        exchange = frozen['scope']['identity_context'][frozen['scope']['instruments'][0]]['exchange']
        result = []; day = first
        while day <= last:
            info = self.evidence.market.rules.calendar(exchange,date.fromisoformat(day),datetime.fromisoformat(day+'T16:00:00+08:00'))
            if info['is_trading_day'] is None:
                if gaps is None:raise HTTPException(409,'FORWARD_CALENDAR_UNSUPPORTED')
                gaps.append('FORWARD_CALENDAR_UNSUPPORTED:'+day)
            if info['is_trading_day']: result.append(day)
            day = (date.fromisoformat(day)+timedelta(days=1)).isoformat()
        return result

    def state(self, freeze_id):
        plan = self.plan(freeze_id)
        with self.ledger.connection() as db:
            samples = [json.loads(r[0]) for r in db.execute('SELECT value FROM research_forward_samples WHERE protocol_id=? ORDER BY trading_date',(plan['protocol_id'],))]
            checks = [json.loads(r[0]) for r in db.execute('SELECT value FROM research_forward_checks WHERE freeze_id=? ORDER BY rowid',(freeze_id,))]
            assessment = db.execute('SELECT value FROM research_forward_assessments WHERE freeze_id=? ORDER BY rowid DESC LIMIT 1',(freeze_id,)).fetchone()
        real = plan['namespace'] == 'FORWARD'
        frozen = self.shadow.get(freeze_id)
        today = self.clock().astimezone(SHANGHAI).date().isoformat()
        last = min(today, plan['deadline'][:10]) if plan['deadline'] else today
        observed = {s['trading_date'] for s in samples}
        calendar_gaps=[]
        missing = [{'trading_date':day,'reason':'NO_PERSISTED_FORWARD_PREDICTION_NO_BACKFILL'}
            for day in self.sessions(frozen,datetime.fromisoformat(plan['registered_at']).astimezone(SHANGHAI).date().isoformat(),last,calendar_gaps)
            if day < today and day not in observed]
        return {**plan,'forward_started_at':plan['started_at'] if real else None,'forward_deadline':plan['deadline'] if real else None,
            'method_started_at':plan['started_at'] if not real else None,'method_deadline':plan['deadline'] if not real else None,
            'samples':samples,'checks':checks,'missing_checkpoints':missing,'calendar_gaps':calendar_gaps,
            'latest_assessment':json.loads(assessment[0]) if assessment else None,
            'shadow':json.loads(assessment[0])['shadow'] if assessment and (json.loads(assessment[0])['shadow'] or {}).get('revision')==len(samples) else samples[-1]['shadow'] if samples else None,
            'validation_status':'NOT_COMPLETED_BY_ARCHIVE','review_status':'PENDING','human_review':'未经人工独立复核'}

    def check(self, freeze_id, command):
        if self.recovery()['state']=='RECOVERY_LOCK':
            raise HTTPException(409,{'code':'FORWARD_RECOVERY_LOCK','reason':'恢复后当前输入、停止与版本尚未核实；不从保存计划补写样本或起点'})
        plan = self.plan(freeze_id); frozen = self.shadow.get(freeze_id); checked = self.clock(); local = checked.astimezone(SHANGHAI)
        if plan['namespace']=='METHOD_CASE' and os.environ.get('ROLL_ENV')!='test':
            raise HTTPException(403,'METHOD 工程采样仅允许测试环境')
        day = local.date().isoformat()
        current = self.state(freeze_id)
        for sample in current['samples']:
            if self.shadow.checked_archive(sample['archive']) != {k:v for k,v in sample.items() if k!='archive'}:
                raise HTTPException(409,'FORWARD_ARCHIVE_BINDING_MISMATCH')
        if plan['status'] == 'CLOSED': return current
        if plan['status']=='CLOSING':return self.close(plan,frozen,checked)
        if plan['deadline'] and checked >= datetime.fromisoformat(plan['deadline']):
            return self.close(plan,frozen,checked)
        if any(s['trading_date'] == day for s in current['samples']): return current
        calendar = self.evidence.market.rules.calendar(frozen['scope']['identity_context'][frozen['scope']['instruments'][0]]['exchange'],local.date(),local)
        gaps = []
        if calendar['is_trading_day'] is not True: gaps.append('NOT_A_KNOWN_TRADING_DAY')
        if local.time().replace(tzinfo=None).isoformat() < plan['checkpoint_time']: gaps.append('POST_CLOSE_CHECKPOINT_NOT_REACHED')
        if plan['namespace']=='FORWARD' and datetime.fromisoformat(plan['registered_at'])>datetime.fromisoformat(day+'T'+plan['checkpoint_time']+'+08:00'):
            gaps.append('CHECKPOINT_REGISTERED_AFTER_THIS_DAY_CHECKPOINT')
        if code_fingerprint() != frozen['fingerprints']['model_code'] or shadow_code() != frozen['fingerprints']['shadow_code']: gaps.append('FROZEN_CODE_CHANGED')
        if self.code() != plan['adapter_code_fingerprint']: gaps.append('FORWARD_ADAPTER_CODE_CHANGED_SUCCESSOR_REQUIRED')
        if plan['namespace']=='FORWARD':
            identity=frozen['scope']['identity_context'][frozen['scope']['instruments'][0]]
            rule=self.evidence.market.rules.rule(identity['exchange'],identity['board'],identity['instrument_type'],on=local.date())
            if rule.get('implementation_status')!='ADAPTED' or any(str(rule.get(k))!=str(frozen['rules'][frozen['scope']['instruments'][0]].get(k)) for k in ['price_tick_yuan','normal_price_limit_percent','buy_minimum','buy_increment']):
                gaps.append('CURRENT_RULES_DO_NOT_MATCH_FROZEN_EXECUTION_SCOPE')
            if len(self.horizon(frozen,day))!=20:gaps.append('FORWARD_TWENTY_SESSION_CALENDAR_NOT_KNOWN')
        if plan['namespace']=='FORWARD' and not gaps:
            collection=[p for p in self.prospective.plans() if p['instrument']==frozen['scope']['instruments'][0]]
            if collection:
                self.prospective.post_close.capture_once(collection[0]['plan_id'])
                checked=self.clock()
        rows, source_gaps = self.rows(plan,frozen,checked); gaps += source_gaps
        if gaps:
            self.record_check(plan,checked,gaps,command.basis)
            return self.state(freeze_id)
        model = self.models.get(frozen['model_run_id'])
        try:
            if plan['namespace']=='METHOD_CASE':
                method_cutoff = max([checked.isoformat(), *[r['available_at'] for r in rows]], key=datetime.fromisoformat)
                snapshot = features(rows,day,True,method_cutoff)
            else:
                snapshot = forward_features(rows,day,checked,model['fit']['feature_names'],frozen.get('data_use')=='RECONSTRUCTED_RESEARCH')
            self.models.check_feature_calendar(snapshot,self.registry.get(frozen['protocol_id']))
        except (ValueError,KeyError,ArithmeticError) as error:
            self.record_check(plan,checked,[str(error)],command.basis)
            return self.state(freeze_id)
        prediction = predict(model['fit'],snapshot,model['calibrator']['intercept_shift'])
        identity = fingerprint([plan['protocol_id'],plan['checkpoint_id'],day])
        forecast = {'forecast_id':identity,'model_run_id':frozen['model_run_id'],'instrument':frozen['scope']['instruments'][0],
            'observation_cutoff':day+'T15:05:00+08:00','consumer_knowledge_cutoff':checked.isoformat(),
            'feature_snapshot':snapshot,**prediction,'evidence_kind':plan['namespace'],'namespace':plan['namespace'],
            'artifact_fingerprints':model['artifact_fingerprints'],'horizon_sessions':20,'capability':'NOT_GRANTED',
            'actual_forward_prediction':plan['namespace']=='FORWARD'}
        forecasts = [s['forecast'] for s in current['samples']]+[forecast]
        first = current['samples'][0]['trading_date'] if current['samples'] else day
        inputs = self.simulation_inputs(plan,frozen,rows,first,day)
        result = simulate(frozen,inputs,forecasts,day)
        result['revision'] = len(forecasts)
        sample = {'sample_id':identity,'freeze_id':freeze_id,'protocol_id':plan['protocol_id'],'checkpoint_id':plan['checkpoint_id'],
            'trading_date':day,'recorded_at':checked.isoformat(),'evidence_kind':plan['namespace'],
            'forecast':forecast,'action':next(o for o in result['opportunities'] if o['forecast_id']==identity),'shadow':result,
            'replay_inputs':{'frozen':frozen,'inputs':inputs,'forecasts':forecasts,'through_date':day},
            'confirmatory_sample':plan['namespace']=='FORWARD','statistical_pass_check':False}
        sample['archive'] = self.evidence.archive(encode(sample).encode(),'FORWARD_CHECKPOINT',research_namespace=plan['namespace'])
        self.ledger.crash_point('forward_after_archive')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT 1 FROM research_forward_samples WHERE id=?',(identity,)).fetchone()
            if not existing:
                active = json.loads(db.execute('SELECT value FROM research_forward_plans WHERE freeze_id=?',(freeze_id,)).fetchone()[0])
                committed_at=self.clock()
                if active['status'] in {'CLOSED','CLOSING'} or (active['deadline'] and committed_at>=datetime.fromisoformat(active['deadline'])):
                    raise HTTPException(409,'FORWARD_CLOSED_DURING_COMPUTATION')
                count = db.execute('SELECT COUNT(*) FROM research_forward_samples WHERE protocol_id=?',(plan['protocol_id'],)).fetchone()[0]
                if count != len(current['samples']): raise HTTPException(409,'FORWARD_REVISION_CHANGED_RETRY')
                db.execute('INSERT INTO research_forward_samples VALUES(?,?,?,?,?)',(identity,plan['protocol_id'],plan['checkpoint_id'],day,encode(sample)))
                if active['started_at'] is None:
                    active.update(started_at=committed_at.isoformat(),deadline=deadline_preview(committed_at)['deadline'],status='RUNNING')
                    db.execute('UPDATE research_forward_plans SET value=? WHERE freeze_id=?',(encode(active),freeze_id))
                    self.registry.event(plan['protocol_id'],'FORWARD_FIRST_SAMPLE_PERSISTED',db=db,sample_id=identity,namespace=plan['namespace'],actual_forward_start=plan['namespace']=='FORWARD')
                    if plan['namespace'] == 'FORWARD':
                        protocol = json.loads(db.execute('SELECT value FROM research_protocols WHERE id=?',(plan['protocol_id'],)).fetchone()[0])
                        protocol.update(forward_started_at=active['started_at'],forward_deadline=active['deadline'])
                        db.execute('UPDATE research_protocols SET value=? WHERE id=?',(encode(protocol),plan['protocol_id']))
                self.ledger.crash_point('forward_before_commit')
            db.commit()
        self.ledger.crash_point('forward_after_commit')
        return self.state(freeze_id)

    def horizon(self, frozen, day):
        exchange = frozen['scope']['identity_context'][frozen['scope']['instruments'][0]]['exchange']
        result = []; current = date.fromisoformat(day)
        for _ in range(20):
            following = self.evidence.market.rules.next_trading_day(exchange,current)
            if following is None: break
            result.append(following); current = date.fromisoformat(following)
        return result

    def close(self, plan, frozen, checked, stop=None):
        # Reserve the sampling boundary first. A concurrent forecast cannot commit
        # after this claim; interrupted closure resumes at its original cutoff.
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            latest=json.loads(db.execute('SELECT value FROM research_forward_plans WHERE freeze_id=?',(plan['freeze_id'],)).fetchone()[0])
            if latest['status']=='CLOSED':
                db.commit();return self.state(plan['freeze_id'])
            if latest['status']!='CLOSING':
                cutoff = min(checked,datetime.fromisoformat(plan['deadline'])) if stop and plan['deadline'] else checked if stop else datetime.fromisoformat(plan['deadline'])
                latest.update(status='CLOSING',closing_cutoff=cutoff.isoformat(),closing_stop=stop.model_dump() if stop else None)
                db.execute('UPDATE research_forward_plans SET value=? WHERE freeze_id=?',(encode(latest),plan['freeze_id']))
            db.commit()
        cutoff=datetime.fromisoformat(latest['closing_cutoff'])
        stop=StopCommand(**latest['closing_stop']) if latest.get('closing_stop') else None
        self.ledger.crash_point('forward_after_close_claim')
        assessment = self.settle(plan['freeze_id'],CheckCommand(basis='Original endpoint mature-only settlement'),cutoff=cutoff)
        endpoint = {'cutoff':cutoff.isoformat(),'actual_checked_at':checked.isoformat(),'namespace':plan['namespace'],
            'mature':assessment['mature'],'unmatured':assessment['unmatured'],'unscorable':assessment['unscorable'],
            'validation_status':'INCOMPLETE','preliminary_verdict':'INCONCLUSIVE','review_status':'PENDING',
            'gaps':list(dict.fromkeys(assessment['gaps']+['FINAL_G1_G7_VALIDATION_REQUIRED','MODEL_TECHNICAL_REVIEW_REQUIRED'])),
            'statistical_pass_checks_added':0,'deadline_extended':False,'capability':'NOT_GRANTED'}
        if stop: endpoint.update(stop_reason=stop.kind,stop_basis=stop.basis)
        endpoint['archive'] = self.evidence.archive(encode(endpoint).encode(),'FORWARD_ENDPOINT',research_namespace=plan['namespace'])
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            latest = json.loads(db.execute('SELECT value FROM research_forward_plans WHERE freeze_id=?',(plan['freeze_id'],)).fetchone()[0])
            if latest['status'] != 'CLOSED':
                latest.update(status='CLOSED',endpoint=endpoint)
                db.execute('UPDATE research_forward_plans SET value=? WHERE freeze_id=?',(encode(latest),plan['freeze_id']))
                self.registry.event(plan['protocol_id'],'FORWARD_SAMPLING_CLOSED',db=db,cutoff=cutoff.isoformat(),namespace=plan['namespace'],confirmatory_pass_look=False)
                if plan['namespace']=='FORWARD':
                    protocol=json.loads(db.execute('SELECT value FROM research_protocols WHERE id=?',(plan['protocol_id'],)).fetchone()[0])
                    protocol.update(experiment_status='ENDED',forward_ended_at=cutoff.isoformat(),forward_endpoint_archive=endpoint['archive'],review_status='PENDING')
                    db.execute('UPDATE research_protocols SET value=? WHERE id=?',(encode(protocol),plan['protocol_id']))
            db.commit()
        return self.state(plan['freeze_id'])

    def stop(self, freeze_id, command):
        plan=self.plan(freeze_id)
        if plan['status']=='CLOSED':return self.state(freeze_id)
        return self.close(plan,self.shadow.get(freeze_id),self.clock(),command)

    def simulation_inputs(self, plan, frozen, rows, first, through):
        gaps=[]
        sessions = self.sessions(frozen,first,through,gaps)+self.horizon(frozen,through)
        events = {fingerprint(event):event for row in rows for event in row.get('cash_events_effective',[])}
        inputs = {'facts':rows,'sessions':sessions,'statutory':{},'cash_events':list(events.values()),'counterfactuals':{},'calendar_gaps':gaps}
        if plan['namespace']=='FORWARD':
            from roll.research.historical_costs import freeze as cost_schedule
            identity=frozen['scope']['identity_context']
            for day in sessions:
                if day<=through:
                    inputs['statutory'][day]={i:cost_schedule(self.evidence,identity[i],day,day,frozen['design']['costs']) for i in frozen['scope']['instruments']}
        return inputs

    def settle(self, freeze_id, command, cutoff=None):
        plan=self.plan(freeze_id); frozen=self.shadow.get(freeze_id)
        if self.code()!=plan['adapter_code_fingerprint'] or code_fingerprint()!=frozen['fingerprints']['model_code'] or shadow_code()!=frozen['fingerprints']['shadow_code']:
            raise HTTPException(409,'FORWARD_FROZEN_COMPUTATION_CHANGED_SUCCESSOR_REQUIRED')
        checked=cutoff or self.clock()
        if plan.get('closing_cutoff'):
            checked=datetime.fromisoformat(plan['closing_cutoff']);cutoff=checked
        elif plan.get('deadline') and checked>=datetime.fromisoformat(plan['deadline']):
            checked=datetime.fromisoformat(plan['deadline']);cutoff=checked
        through=checked.astimezone(SHANGHAI).date().isoformat()
        state=self.state(freeze_id); samples=state['samples']
        rows,gaps=self.rows(plan,frozen,checked)
        mature,unmatured,unscorable=[],[],[]
        inputs=self.simulation_inputs(plan,frozen,rows,samples[0]['trading_date'],through) if samples else None
        if inputs:gaps+=inputs['calendar_gaps']
        for sample in samples:
            if self.shadow.checked_archive(sample['archive'])!={k:v for k,v in sample.items() if k!='archive'}:
                raise HTTPException(409,'FORWARD_ARCHIVE_BINDING_MISMATCH')
            maturity=sample['action']['maturity_date']
            result={'sample_id':sample['sample_id'],'maturity_date':maturity,'label':None,'scoreable':False,
                'diagnostic_only':True,'continuous_return_included':False,'refused':sample['action']['action']=='REFUSE'}
            if maturity and datetime.fromisoformat(maturity+'T15:05:00+08:00')>checked:
                result['reason']='UNMATURED_AT_ORIGINAL_CUTOFF' if cutoff else 'TWENTY_SESSION_EVENT_NOT_MATURE'
                unmatured.append(result); continue
            selected=[r for r in rows if sample['trading_date']<=r['trade_date']<=(maturity or through)]
            known = all(plan['namespace']=='METHOD_CASE' or all(r.get(k) and datetime.fromisoformat(r[k])<=checked for k in ['available_at','received_at','known_at']) for r in selected)
            # A rejected opportunity has its own fixed-lot counterfactual, never changes the continuous portfolio.
            diagnostic={**frozen,'baseline':{'cash_yuan':'100000000.00','positions':[]},
                'policy':{**frozen['policy'],'probability_threshold':'0','maximum_gross_exposure':'1'}}
            counter=simulate(diagnostic,inputs,[sample['forecast']],min(through,maturity or through))
            sold=any(e['kind']=='SELL_FILL' and e['forecast_id']==sample['sample_id'] for e in counter['events'])
            if sold and known and not gaps and not counter['missing']:
                pnl=Decimal(counter['realized_gain_yuan'])
                result.update(label=int(pnl>0),scoreable=True,net_pnl_yuan=str(pnl),execution_basis='FROZEN_DAILY_SCENARIO_NOT_USER_EXECUTION')
                mature.append(result)
            else:
                result.update(reason='MATURE_RESULT_EVIDENCE_NOT_COMPLETE',execution_gaps=counter['missing'])
                unscorable.append(result)
        shadow=simulate(frozen,inputs,[s['forecast'] for s in samples],through) if samples else None
        if shadow:shadow['revision']=len(samples)
        value={'assessment_id':str(uuid4()),'freeze_id':freeze_id,'cutoff':checked.isoformat(),'recorded_at':self.clock().isoformat(),
            'basis':command.basis,'namespace':plan['namespace'],'mature':mature,'unmatured':unmatured,'unscorable':unscorable,
            'gaps':gaps,'shadow':shadow,'inputs':inputs,'sample_ids':[s['sample_id'] for s in samples],
            'statistical_pass_checks_added':0,'real_qualification':False}
        value['archive']=self.evidence.archive(encode(value).encode(),'FORWARD_MATURE_ASSESSMENT',research_namespace=plan['namespace'])
        with self.ledger.connection() as db:
            db.execute('INSERT INTO research_forward_assessments VALUES(?,?,?)',(value['assessment_id'],freeze_id,encode(value)))
        return value

    def record_check(self, plan, checked, gaps, basis):
        value = {'check_id':str(uuid4()),'checked_at':checked.isoformat(),'trading_date':checked.astimezone(SHANGHAI).date().isoformat(),
            'gaps':gaps,'basis':basis,'prediction_created':False,'statistical_pass_checks_added':0}
        with self.ledger.connection() as db: db.execute('INSERT INTO research_forward_checks VALUES(?,?,?)',(value['check_id'],plan['freeze_id'],encode(value)))

    def replay(self, freeze_id):
        state = self.state(freeze_id); matches = True
        frozen=self.shadow.get(freeze_id);model=self.models.get(frozen['model_run_id'])
        if self.code()!=state['adapter_code_fingerprint'] or code_fingerprint()!=frozen['fingerprints']['model_code'] or shadow_code()!=frozen['fingerprints']['shadow_code']:
            raise HTTPException(409,'FORWARD_FROZEN_COMPUTATION_CHANGED_SUCCESSOR_REQUIRED')
        for sample in state['samples']:
            original = self.shadow.checked_archive(sample['archive'])
            if original != {k:v for k,v in sample.items() if k!='archive'}: raise HTTPException(409,'FORWARD_ARCHIVE_BINDING_MISMATCH')
            values = sample['replay_inputs']
            prediction=predict(model['fit'],sample['forecast']['feature_snapshot'],model['calibrator']['intercept_shift'])
            matches=matches and all(sample['forecast'].get(k)==v for k,v in prediction.items())
            result = simulate(values['frozen'],values['inputs'],values['forecasts'],values['through_date']); result['revision'] = len(values['forecasts'])
            matches = matches and result == sample['shadow']
        if state.get('endpoint'):
            endpoint=state['endpoint'];original=self.shadow.checked_archive(endpoint['archive'])
            if original!={k:v for k,v in endpoint.items() if k!='archive'}:raise HTTPException(409,'FORWARD_ENDPOINT_ARCHIVE_BINDING_MISMATCH')
        with self.ledger.connection() as db: assessments=[json.loads(r[0]) for r in db.execute('SELECT value FROM research_forward_assessments WHERE freeze_id=?',(freeze_id,))]
        for assessment in assessments:
            if self.shadow.checked_archive(assessment['archive'])!={k:v for k,v in assessment.items() if k!='archive'}:
                raise HTTPException(409,'FORWARD_ASSESSMENT_ARCHIVE_BINDING_MISMATCH')
            if assessment['shadow']:
                sample_by_id={s['sample_id']:s for s in state['samples']}
                if any(identity not in sample_by_id for identity in assessment['sample_ids']):
                    raise HTTPException(409,'FORWARD_ASSESSMENT_SAMPLE_BINDING_MISMATCH')
                result=simulate(frozen,assessment['inputs'],[sample_by_id[identity]['forecast'] for identity in assessment['sample_ids']],datetime.fromisoformat(assessment['cutoff']).astimezone(SHANGHAI).date().isoformat())
                result['revision']=assessment['shadow']['revision']
                matches=matches and result==assessment['shadow']
        return {'freeze_id':freeze_id,'samples':len(state['samples']),'matches_original':matches,'network_calls':0,'statistical_pass_checks_added':0}

    def work(self):
        checked = self.clock()
        if self.last_worker_check and (checked-self.last_worker_check).total_seconds() < 60: return
        self.last_worker_check = checked
        with self.ledger.connection() as db: plans = [json.loads(r[0]) for r in db.execute('SELECT value FROM research_forward_plans')]
        for plan in plans:
            try: self.check(plan['freeze_id'],CheckCommand(basis='Existing single worker running-only checkpoint'))
            except HTTPException as error: self.record_check(plan,checked,[str(error.detail)],'Worker admission refusal')
