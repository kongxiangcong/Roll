"""Immutable complete experiment bindings and a separate continuous research ledger."""
import hashlib
import json
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from roll.accounts.ledger import encode, now, number
from roll.research.models import code_fingerprint
from roll.research.execution import engine_fingerprint, money as execution_money, fees
from roll.research.historical_costs import freeze as statutory_costs
from roll.research.corporate_actions import _holding_tax
from roll.research.statistics import method_manifest, fingerprint as statistics_fingerprint


def fingerprint(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def money(value): return execution_money(Decimal(value))


def shadow_code():
    return fingerprint({'shadow': hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n')).hexdigest(),
                        'execution': engine_fingerprint(),'statistics':statistics_fingerprint()})


class Position(BaseModel):
    model_config = ConfigDict(extra='forbid')
    instrument: str
    quantity: str
    acquisition_cost_yuan: str
    acquired_on: date

    @field_validator('quantity')
    @classmethod
    def quantity_valid(cls, value):
        number(value, 'quantity', 0)
        if Decimal(value) <= 0: raise ValueError('持仓必须为正整数股')
        return value

    @field_validator('acquisition_cost_yuan')
    @classmethod
    def cost_valid(cls, value): return number(value, 'acquisition_cost_yuan')


class Baseline(BaseModel):
    model_config = ConfigDict(extra='forbid')
    cash_yuan: str
    positions: list[Position] = Field(default_factory=list, max_length=30)

    @field_validator('cash_yuan')
    @classmethod
    def cash_valid(cls, value): return number(value, 'cash_yuan')


class CompleteFreezeCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    model_run_id: str
    attempt_ids: list[str]
    artifact_fingerprints: dict[str, str]
    baseline: Baseline
    cash_flow_policy: Literal['NO_EXTERNAL_FLOWS'] = 'NO_EXTERNAL_FLOWS'
    basis: str = Field(min_length=1, max_length=2000)


class AdvanceCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    through_date: date
    forecast_ids: list[str] = Field(default_factory=list, max_length=1000)
    expected_revision: int = Field(ge=0)


class ConditionalCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    forecast_ids: list[str] = Field(max_length=1000)


def calculate_policy(opportunities, cash, reserved, exposure, nav, occupied, policy):
    """The same ordinary deterministic calculation is reusable by ticket25."""
    decisions=[]
    for item in sorted(opportunities, key=lambda x: (-Decimal(str(x['probability'])), x['instrument'], x['forecast_id'])):
        reasons=[]
        if Decimal(str(item['probability'])) < Decimal(policy['probability_threshold']): reasons.append('BELOW_FROZEN_THRESHOLD')
        if item['instrument'] in occupied: reasons.append('OVERLAPPING_POSITION_OR_ORDER')
        required=Decimal(item['required_cash_yuan'])
        if required > cash-reserved: reasons.append('INSUFFICIENT_JOINT_CASH')
        if nav is None: reasons.append('VALUATION_UNKNOWN')
        elif exposure+reserved+required > nav*Decimal(policy['maximum_gross_exposure']): reasons.append('MAXIMUM_GROSS_EXPOSURE')
        reasons += item.get('input_gaps', [])
        decisions.append({**item, 'action': 'REFUSE' if reasons else 'BUY', 'reasons': reasons,
                          'model_loss_from_refusal': False})
        if not reasons:
            reserved+=required; occupied.add(item['instrument'])
    return decisions


def simulate(frozen, inputs, forecasts, through, comparator=None):
    """Replay only bars on/before each step; never use matured returns to select actions."""
    costs=frozen['design']['costs'];policy=frozen['policy'];cash=Decimal(frozen['baseline']['cash_yuan'])
    positions=[{**p, 'quantity': p['quantity'], 'entry_date': p['acquired_on'], 'exit_date': None,
                'cost_yuan': p['acquisition_cost_yuan'], 'forecast_id': 'BASELINE'} for p in frozen['baseline']['positions']]
    pending=[];opportunities=[];events=[];curve=[];entitlements=[];realized=Decimal('0')
    rows={(r['trade_date'],r['instrument']):r for r in inputs['facts']}
    forecasts_by_day={}
    for forecast in forecasts: forecasts_by_day.setdefault(forecast['observation_cutoff'][:10], []).append(forecast)
    days=inputs['sessions'];instruments=frozen['scope']['instruments'];missing=[]
    for index, day in enumerate(days):
        if day>through:break
        for symbol in instruments:
            if (day,symbol) not in rows:missing.append({'date':day,'instrument':symbol,'reason':'MISSING_DAILY_INPUT'})
        def bar(symbol):return rows.get((day,symbol))
        def usable(row):
            return bool(row and not row.get('errors') and row.get('completion_state')=='COMPLETE_REPORTED_HISTORICAL'
                and row.get('execution_evidence',{}).get('state') in {'CONFIRMED_NORMAL','REPORTED_NORMAL_RECONSTRUCTED'}
                and row.get('execution_evidence',{}).get('company_actions') in {'CONFIRMED_NONE','SOURCE_BOUND_CASH_AND_ANNUAL_SHARE_AUDIT'})
        def fee(gross, side, symbol, trade_day):
            schedule=inputs['statutory'].get(trade_day,{}).get(symbol)
            return Decimal(fees(gross,costs,side,schedule[side] if schedule else None)['total_yuan'])
        # Prior close decisions enter at NEXT_OPEN; daily evidence determines fills.
        for order in list(pending):
            if order['entry_date']>day:continue
            row=bar(order['instrument']);reason=None
            if not usable(row):reason='MISSING_OR_UNKNOWN_EXECUTION_INPUT'
            elif Decimal(row['volume_shares'])<Decimal(order['quantity']):reason='INSUFFICIENT_REPORTED_VOLUME'
            else:
                rule=frozen['rules'][order['instrument']];tick=Decimal(rule['price_tick_yuan'])
                price=(Decimal(row['open'])*(1+Decimal(costs['slippage_each_side_rate']))/tick).quantize(Decimal('1'),rounding=ROUND_HALF_UP)*tick
                if not Decimal(order['lower_yuan'])<=price<=Decimal(order['upper_yuan']):reason='OUTSIDE_FROZEN_PRICE_WINDOW'
                elif all(Decimal(row[k])==Decimal(order['upper_yuan']) for k in ['open','high','low','close']):reason='LOCKED_UPPER_LIMIT'
            if reason:
                order['execution_status']='NO_EXECUTION';order['execution_reasons']=[reason]
                events.append({'kind':'NO_FILL','date':day,'forecast_id':order['forecast_id'],'reason':reason})
            else:
                gross=price*Decimal(order['quantity']);paid=gross+fee(gross,'BUY',order['instrument'],day)
                if paid>cash or paid>Decimal(order['required_cash_yuan']):raise ValueError('FROZEN_RESERVATION_CONSERVATION_FAILURE')
                cash-=paid;order['execution_status']='FILLED'
                positions.append({'instrument':order['instrument'],'quantity':order['quantity'],'entry_date':day,
                    'exit_date':None if comparator=='START_HOLD' else order['maturity_date'],'cost_yuan':money(paid),'forecast_id':order['forecast_id']})
                events.append({'kind':'BUY_FILL','date':day,'instrument':order['instrument'],'quantity':order['quantity'],
                    'price_yuan':money(price),'cash_delta_yuan':money(-paid),'forecast_id':order['forecast_id']})
            pending.remove(order)
        # Entitlements follow the frozen record/payment dates independently of actual account cash flows.
        for event in inputs.get('cash_events',[]):
            if event['record_date']==day:
                for position in positions:
                    if event.get('instrument',position['instrument'])!=position['instrument']:continue
                    entitlements.append({'instrument':position['instrument'],'forecast_id':position['forecast_id'],
                        'entry_date':position['entry_date'],'payment_date':event['cash_payment_date'],
                        'gross':money(Decimal(position['quantity'])*Decimal(event['gross_cash_yuan_per_eligible_share'])),
                        'paid':False,'tax':None})
        for entitlement in entitlements:
            if not entitlement['paid'] and entitlement['payment_date']<=day:
                cash+=Decimal(entitlement['gross']);entitlement['paid']=True
                events.append({'kind':'CASH_DISTRIBUTION','date':day,'cash_delta_yuan':entitlement['gross'],'forecast_id':entitlement['forecast_id']})
        for position in list(positions):
            if not position['exit_date'] or position['exit_date']>day:continue
            row=bar(position['instrument'])
            if not usable(row):
                missing.append({'date':day,'instrument':position['instrument'],'reason':'BLOCKED_EXIT_OR_MISSING_DATA'});continue
            rule=frozen['rules'][position['instrument']];tick=Decimal(rule['price_tick_yuan'])
            price=(Decimal(row['close'])*(1-Decimal(costs['slippage_each_side_rate']))/tick).quantize(Decimal('1'),rounding=ROUND_HALF_UP)*tick
            previous=rows.get((days[index-1],position['instrument'])) if index else None
            if not previous:missing.append({'date':day,'reason':'EXIT_REFERENCE_MISSING'});continue
            adjustment=sum(Decimal(e['gross_cash_yuan_per_eligible_share']) for e in inputs.get('cash_events',[]) if e['ex_date']==day)
            limit=Decimal(rule['normal_price_limit_percent'])/100;reference=Decimal(previous['close'])-adjustment
            floor=Decimal(money(reference*(1-limit)));upper=Decimal(money(reference*(1+limit)))
            if not floor<=price<=upper or all(Decimal(row[k])==floor for k in ['open','high','low','close']):
                missing.append({'date':day,'reason':'BLOCKED_EXIT_PRICE_BAND'});continue
            gross=price*Decimal(position['quantity']);received=gross-fee(gross,'SELL',position['instrument'],day);rights=Decimal('0');tax=Decimal('0')
            for entitlement in entitlements:
                if entitlement['forecast_id']==position['forecast_id']:
                    withholding=Decimal(entitlement['gross'])*_holding_tax(date.fromisoformat(position['entry_date']),date.fromisoformat(day),True)
                    entitlement['tax']=money(withholding);tax+=Decimal(entitlement['tax']);rights+=Decimal(entitlement['gross'])
            received-=tax;cash+=received;realized+=received+rights-Decimal(position['cost_yuan'])
            events.append({'kind':'SELL_FILL','date':day,'instrument':position['instrument'],'quantity':position['quantity'],
                'price_yuan':money(price),'cash_delta_yuan':money(received),'forecast_id':position['forecast_id'],'dividend_tax_yuan':money(tax)})
            positions.remove(position)
        valuation=Decimal('0');valuation_known=True
        for position in positions:
            row=bar(position['instrument'])
            if not row or row.get('errors') or row.get('close') is None:valuation_known=False
            else:valuation+=Decimal(position['quantity'])*Decimal(row['close'])
        # Tax is withheld from sale cash once; unpaid receivable remains gross.
        receivable=sum(Decimal(e['gross']) for e in entitlements if not e['paid'])
        nav=cash+valuation+receivable if valuation_known else None
        reserved=sum(Decimal(o['required_cash_yuan']) for o in pending)
        candidates=forecasts_by_day.get(day,[])
        if comparator:
            candidates=[]
            for symbol in instruments:
                past=[r for (d,i),r in sorted(rows.items()) if d<=day and i==symbol and r.get('close') is not None][-20:]
                signal=comparator=='START_HOLD' and index==0 or comparator=='MA5_MA20' and len(past)==20 and sum(Decimal(r['close']) for r in past[-5:])/5>sum(Decimal(r['close']) for r in past)/20
                if signal:candidates.append({'forecast_id':comparator+':'+symbol+':'+day,'instrument':symbol,'probability':1})
        orders=[]
        for candidate in candidates:
            symbol=candidate['instrument'];row=bar(symbol);rule=frozen['rules'][symbol];limit=Decimal(rule['normal_price_limit_percent'])/100
            anchor=Decimal(row['close']) if row and row.get('close') else Decimal('0');qty=policy['quantity'];gaps=[]
            entry=days[index+1] if index+1<len(days) else None;maturity=days[index+20] if index+20<len(days) else None
            if not entry or not maturity:gaps.append('HORIZON_OUTSIDE_FROZEN_WINDOW')
            if not usable(row):gaps.append('MISSING_OR_UNKNOWN_OBSERVATION_INPUT')
            adjustment=sum(Decimal(e['gross_cash_yuan_per_eligible_share']) for e in inputs.get('cash_events',[]) if e['ex_date']==entry)
            upper=Decimal(money((anchor-adjustment)*(1+limit)));lower=money((anchor-adjustment)*(1-limit));gross=upper*Decimal(qty)
            reserve=gross+fee(gross,'BUY',symbol,entry) if entry else Decimal('0')
            orders.append({**candidate,'observation_date':day,'quantity':qty,'entry_date':entry,'maturity_date':maturity,
                'opportunity_key':fingerprint({'model':frozen['fingerprints']['model'],'instrument':symbol,'observation_date':day,'event':frozen['design']['event'],'horizon':20}),
                'lower_yuan':lower,'upper_yuan':money(upper),'required_cash_yuan':money(reserve),'input_gaps':gaps,
                'execution_status':'PENDING','namespace':'SHADOW','capability':'NOT_GRANTED'})
        decisions=calculate_policy(orders,cash,reserved,valuation,nav,{p['instrument'] for p in positions}|{p['instrument'] for p in pending},policy)
        opportunities.extend(decisions);pending.extend(d for d in decisions if d['action']=='BUY')
        curve.append({'date':day,'cash_yuan':money(cash),'inventory_value_yuan':money(valuation) if valuation_known else None,
            'receivable_yuan':money(receivable),'nav_yuan':money(nav) if nav is not None else None,
            'reserved_cash_yuan':money(sum(Decimal(o['required_cash_yuan']) for o in pending)),
            'realized_gain_yuan':money(realized),'namespace':'SHADOW'})
        curve[-1]['gross_exposure_fraction']=str(valuation/nav) if nav and valuation_known else None
    for opportunity in opportunities:
        if opportunity['action']=='REFUSE' and opportunity['maturity_date'] and opportunity['maturity_date']<=through:
            outcome=inputs.get('counterfactuals',{}).get(opportunity['forecast_id'])
            opportunity['counterfactual']={'diagnostic_only':True,'namespace':'HISTORICAL','result':outcome,
                'status':'MATURE' if outcome and outcome.get('scoreable') else 'UNSCORABLE'}
    return {'namespace':'SHADOW','cash_yuan':money(cash),'positions':positions,'events':events,'curve':curve,
        'opportunities':opportunities,'missing':missing,'entitlements':entitlements,
        'reserved_cash_yuan':money(sum(Decimal(o['required_cash_yuan']) for o in pending)),
        'nav_yuan':curve[-1]['nav_yuan'] if curve else None,'realized_gain_yuan':money(realized),
        'continuous_performance':True,'capability':'NOT_GRANTED','system_usable':False}


class ShadowLab:
    def __init__(self, registry, models):
        self.registry, self.models = registry, models
        self.ledger, self.evidence = registry.ledger, registry.evidence
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS research_complete_freezes(id TEXT PRIMARY KEY,protocol_id TEXT UNIQUE,value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS research_shadow_runs(freeze_id TEXT NOT NULL,revision INTEGER NOT NULL,value TEXT NOT NULL,PRIMARY KEY(freeze_id,revision))')
            db.execute('CREATE TABLE IF NOT EXISTS research_conditional_runs(id TEXT PRIMARY KEY,freeze_id TEXT NOT NULL,value TEXT NOT NULL)')

    def get(self, freeze_id):
        with self.ledger.connection() as db:
            row = db.execute('SELECT value FROM research_complete_freezes WHERE id=?', (freeze_id,)).fetchone()
        if not row: raise HTTPException(404, '完整实验冻结不存在')
        value=json.loads(row[0]);original=self.checked_archive(value['archive'])
        if original!={k:v for k,v in value.items() if k!='archive'}:
            raise HTTPException(409,'COMPLETE_PROTOCOL_CONTENT_BINDING_MISMATCH')
        if fingerprint({k:v for k,v in original.items() if k!='complete_protocol_fingerprint'})!=value['complete_protocol_fingerprint']:
            raise HTTPException(409,'COMPLETE_PROTOCOL_FINGERPRINT_MISMATCH')
        return value

    def list(self, protocol_id):
        self.registry.get(protocol_id)
        with self.ledger.connection() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT value FROM research_complete_freezes WHERE protocol_id=?', (protocol_id,))]

    def checked_archive(self, artifact):
        content = self.evidence.raw(artifact['sha256']).read_bytes()
        if hashlib.sha256(content).hexdigest() != artifact['sha256']:
            raise HTTPException(409, 'ARCHIVE_FINGERPRINT_MISMATCH')
        return json.loads(content)

    def freeze(self, protocol_id, command):
        protocol = self.registry.get(protocol_id)
        model = self.models.get(command.model_run_id)
        manifest = self.registry.attempt_manifest(protocol_id)
        gaps = []
        if self.list(protocol_id): raise HTTPException(409, '完整实验不可改写；修改模型、政策或基线须登记关联后继实验')
        if model['protocol_id'] not in manifest['lineage']: gaps.append('MODEL_OUTSIDE_LINKED_LINEAGE')
        if model.get('model_freeze_status') != 'FROZEN': gaps.append('MODEL_NOT_FROZEN')
        if model.get('calibrator_fit_status') != 'FITTED_UNVALIDATED': gaps.append('CALIBRATOR_NOT_FITTED')
        if model.get('code_fingerprint') != code_fingerprint(): gaps.append('MODEL_CODE_FINGERPRINT_MISMATCH')
        if command.artifact_fingerprints != model.get('artifact_fingerprints'): gaps.append('ARTIFACT_FINGERPRINT_MISMATCH')
        if set(command.attempt_ids) != set(manifest['attempt_ids']) or len(command.attempt_ids) != len(set(command.attempt_ids)): gaps.append('ATTEMPT_MANIFEST_INCOMPLETE')
        if any(a['status'] == 'RUNNING' for a in manifest['attempts']): gaps.append('ATTEMPT_STILL_RUNNING')
        if model.get('data_fingerprint') != protocol.get('data_fingerprint'): gaps.append('DATA_FINGERPRINT_MISMATCH')
        for field, key in [('model_artifact','model'),('calibrator_artifact','calibrator'),('input_archive','features_and_inputs')]:
            if (model.get(field) or {}).get('sha256')!=(model.get('artifact_fingerprints') or {}).get(key):gaps.append('INCONSISTENT_'+key.upper()+'_BINDING')
        design = protocol.get('design', {})
        required = ['candidates', 'costs', 'execution', 'g5', 'formal_monitoring', 'statistics', 'stopping', 'windows', 'baselines', 'primary_objective']
        gaps += ['MISSING_'+k.upper() for k in required if not design.get(k)]
        instruments = protocol['scope'].get('instruments', [])
        if Decimal(command.baseline.cash_yuan)==0 and not command.baseline.positions:gaps.append('EMPTY_ZERO_VALUE_BASELINE')
        if len(instruments)!=1:gaps.append('TRANSPARENT_MODEL_REQUIRES_SINGLE_INSTRUMENT_SCOPE')
        if len({p.instrument for p in command.baseline.positions})!=len(command.baseline.positions):gaps.append('DUPLICATE_BASELINE_INSTRUMENT')
        if any(p.instrument not in instruments for p in command.baseline.positions): gaps.append('BASELINE_OUTSIDE_SCOPE')
        if any(p.acquired_on.isoformat() >= design['windows']['CALIBRATION']['first_date'] for p in command.baseline.positions): gaps.append('BASELINE_ACQUISITION_NOT_BEFORE_WINDOW')
        if gaps:
            event = self.registry.event(protocol_id, 'COMPLETE_FREEZE_REFUSED', gaps=gaps)
            raise HTTPException(409, {'gaps': gaps, 'audit_event_id': event['event_id']})
        frozen_model = self.checked_archive(model['freeze_manifest'])
        if frozen_model.get('artifact_fingerprints')!=model['artifact_fingerprints']:
            raise HTTPException(409,'MODEL_FREEZE_MANIFEST_FINGERPRINT_MISMATCH')
        for field in ['model_artifact', 'calibrator_artifact', 'input_archive']:
            self.checked_archive(model[field])
        policy = {'version': '20-policy-v1', 'probability_threshold': '0.60', 'quantity': '200',
            'maximum_gross_exposure': design['primary_objective']['risk_constraints']['maximum_simulated_gross_exposure'],
            'ordering': 'descending_probability_then_instrument_then_forecast_id',
            'one_active_lot_per_instrument': True, 'exit': 'HORIZON_SESSION20_CLOSE',
            'cash_flow_policy': command.cash_flow_policy, 'rejected_outcomes': 'MATURE_PREDICTION_DIAGNOSTIC_ONLY',
            'joint_budget': 'reserve_upper_price_plus_fees_before_fills; no leverage or simultaneous opportunity sums'}
        inputs = self.checked_archive(model['input_archive'])
        part = inputs['parts']['CALIBRATION']
        rules = {i: next((f.get('execution_evidence',{}) for f in part['facts'] if f['instrument']==i),{}) for i in instruments}
        if model['evidence_kind'] != 'METHOD_CASE':
            from roll.research.reconstruction import rule as reconstruction_rule
            rules = {i: reconstruction_rule(self.evidence,protocol['scope']['identity_context'][i],part['metadata']['first_date'])
                     if model.get('data_use')=='RECONSTRUCTED_RESEARCH' else self.evidence.market.rules.rule(**{
                        k: protocol['scope']['identity_context'][i][k] for k in ['exchange','board','instrument_type']},
                        on=date.fromisoformat(part['metadata']['first_date'])) for i in instruments}
        if any(not all(r.get(k) for k in ['price_tick_yuan','normal_price_limit_percent','buy_minimum','buy_increment']) for r in rules.values()):
            raise HTTPException(409,'RULE_COVERAGE_INCOMPLETE')
        # Worked example checks joint budget with literal expected results, independently of market outcomes.
        example=[{'forecast_id':'A','instrument':'A','probability':.8,'required_cash_yuan':'30000'},
                 {'forecast_id':'B','instrument':'B','probability':.7,'required_cash_yuan':'30000'}]
        example_result=calculate_policy(example,Decimal('100000'),Decimal('0'),Decimal('0'),Decimal('100000'),set(),policy)
        if [r['action'] for r in example_result]!=['BUY','REFUSE']:raise HTTPException(409,'POLICY_METHOD_VALIDATION_FAILED')
        method_validation={'version':'20-method-v1','status':'DETERMINISTIC_POLICY_WORKED_EXAMPLE_PASSED',
            'sample_inputs':example,'expected_actions':['BUY','REFUSE'],'actual_actions':[r['action'] for r in example_result],
            'statistical_method':design['statistics'],'statistical_assumptions_validation':'PENDING_TICKET21',
            'method_code_fingerprint':shadow_code(),'statistical_pass':False}
        statistical_methods=method_manifest(design)
        bindings = {**model['artifact_fingerprints'], 'model_code': model['code_fingerprint'],
            'policy': fingerprint(policy), 'rules': fingerprint(rules), 'fees': fingerprint(design['costs']),
            'execution_missing': fingerprint(design['execution']), 'g5': fingerprint(design['g5']),
            'formal_monitoring': fingerprint(design['formal_monitoring']), 'shadow_code': shadow_code(), 'design': fingerprint(design),
            'validation_method':fingerprint(method_validation),'validation_code':statistics_fingerprint()}
        value = {'freeze_id': str(uuid4()), 'protocol_id': protocol_id, 'model_run_id': model['model_run_id'],
            'registered_at': now(), 'basis': command.basis, 'predecessor_protocol_id': protocol['predecessor_id'],
            'evidence_kind': model['evidence_kind'], 'data_use': model.get('data_use'), 'namespace': 'SHADOW',
            'baseline': command.baseline.model_dump(mode='json'), 'policy': policy, 'rules': rules, 'design': design,
            'scope': protocol['scope'], 'fingerprints': bindings, 'model_freeze_manifest': model['freeze_manifest'],
            'method_validation':method_validation,
            'statistical_methods':statistical_methods,
            'model_freeze': frozen_model, 'attempt_manifest': manifest, 'calibrator_fit_status': model['calibrator_fit_status'],
            'complete_experiment_frozen': True, 'system_usable': False, 'capability': 'NOT_GRANTED',
            'validation_verdict': None, 'forward_started_at': None, 'sealed_independence': protocol['sealed_independence'],
            'confirmatory_eligible': False,
            'validation_gaps': ['INDEPENDENT_CALIBRATION_UNVALIDATED', 'SEALED_INDEPENDENCE_UNPROVEN',
                'G1_G7_NOT_VERIFIED', 'REAL_FORWARD_NOT_STARTED'] + (['METHOD_CASE_ONLY'] if model['evidence_kind']=='METHOD_CASE' else ['RECONSTRUCTED_NOT_STRICT_PIT'] if model.get('data_use')=='RECONSTRUCTED_RESEARCH' else ['HISTORICAL_PIT_UNPROVEN'])}
        value['complete_protocol_fingerprint'] = fingerprint(value)
        value['archive'] = self.evidence.archive(encode(value).encode(), 'COMPLETE_EXPERIMENT_PROTOCOL', research_namespace='SHADOW')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM research_complete_freezes WHERE protocol_id=?', (protocol_id,)).fetchone():
                raise HTTPException(409, '完整实验已经冻结')
            family=self.registry.family(protocol_id,db)
            actual_attempts=[json.loads(r[0]) for pid in family for r in db.execute('SELECT value FROM research_attempts WHERE protocol_id=?',(pid,))]
            if {a['attempt_id'] for a in actual_attempts}!=set(command.attempt_ids):
                raise HTTPException(409,'ATTEMPT_MANIFEST_CHANGED_DURING_FREEZE')
            db.execute('INSERT INTO research_complete_freezes VALUES(?,?,?)', (value['freeze_id'], protocol_id, encode(value)))
            self.registry.event(protocol_id, 'COMPLETE_EXPERIMENT_FROZEN', db=db,
                freeze_id=value['freeze_id'], complete_protocol_fingerprint=value['complete_protocol_fingerprint'], capability='NOT_GRANTED')
            db.commit()
        return value

    def current(self, freeze_id):
        frozen=self.get(freeze_id)
        with self.ledger.connection() as db:
            row=db.execute('SELECT value FROM research_shadow_runs WHERE freeze_id=? ORDER BY revision DESC LIMIT 1',(freeze_id,)).fetchone()
        if row:return json.loads(row[0])
        return {'freeze_id':freeze_id,'revision':0,'through_date':None,'namespace':'SHADOW',
                'cash_yuan':frozen['baseline']['cash_yuan'],'positions':frozen['baseline']['positions'],
                'events':[],'curve':[],'opportunities':[],'reserved_cash_yuan':'0.00','capability':'NOT_GRANTED',
                'system_usable':False,'continuous_performance':True}

    def forecasts(self, frozen, identifiers):
        if len(identifiers)!=len(set(identifiers)):raise HTTPException(422,'重复预测编号')
        result=[]
        for identifier in identifiers:
            value=self.models.get_forecast(identifier)
            if value['model_run_id']!=frozen['model_run_id'] or value['artifact_fingerprints']!=frozen['model_freeze']['artifact_fingerprints']:
                raise HTTPException(409,'预测与完整冻结模型指纹不匹配')
            self.checked_archive(value['archive'])
            result.append(value)
        return result

    def simulation_input(self, frozen, forecasts):
        model=self.models.get(frozen['model_run_id']);inputs=self.checked_archive(model['input_archive'])
        part=inputs['parts']['CALIBRATION'];sessions=[];current=date.fromisoformat(part['metadata']['first_date'])
        identity=frozen['scope']['identity_context'];exchange=identity[frozen['scope']['instruments'][0]]['exchange']
        while current.isoformat()<=part['metadata']['last_date']:
            sessions.append(current.isoformat());following=self.evidence.market.rules.next_trading_day(exchange,current)
            if not following:break
            current=date.fromisoformat(following)
        result={'facts':part['facts'],'sessions':sessions,'window':part['metadata'],
                'cash_events':frozen['design'].get('research_assumptions',{}).get('cash_events',[]),'statutory':{},'counterfactuals':{}}
        if frozen['evidence_kind']!='METHOD_CASE':
            for day in sessions:
                result['statutory'][day]={i:statutory_costs(self.evidence,identity[i],day,day,frozen['design']['costs']) for i in frozen['scope']['instruments']}
        # Only isolated historical diagnostics. This does not affect continuous policy or cash.
        for forecast in forecasts:
            day=forecast['observation_cutoff'][:10]
            outcomes=self.registry.executions.support(model['protocol_id'],'CALIBRATION')['records']
            match=next((r for r in outcomes if r['observation_date']==day),None)
            if match:result['counterfactuals'][forecast['forecast_id']]=match['result']
        return result

    def advance(self, freeze_id, command):
        frozen=self.get(freeze_id);prior=self.current(freeze_id)
        if frozen['fingerprints']['shadow_code']!=shadow_code():raise HTTPException(409,'影子算法版本不匹配，须关联后继版本')
        if prior['revision']!=command.expected_revision:raise HTTPException(409,'影子版本冲突')
        through=command.through_date.isoformat()
        if prior['through_date'] and through<=prior['through_date']:raise HTTPException(409,'历史影子不可倒改或重置')
        old=[]
        if prior['revision']:
            original=self.checked_archive(prior['input_archive']);old=original['forecasts']
        forecasts=self.forecasts(frozen,command.forecast_ids)
        if any(f['observation_cutoff'][:10]>through or (prior['through_date'] and f['observation_cutoff'][:10]<=prior['through_date']) for f in forecasts):
            raise HTTPException(409,'不能补造已处理历史预测或消费未来机会')
        all_forecasts=[*old,*forecasts]
        if len({f['forecast_id'] for f in all_forecasts})!=len(all_forecasts):raise HTTPException(409,'机会已保存')
        inputs=self.simulation_input(frozen,all_forecasts)
        if through not in inputs['sessions']:raise HTTPException(422,'仅允许已冻结CAL窗口的真实日历交易日；不读SEALED或启动前向')
        output=simulate(frozen,inputs,all_forecasts,through)
        output['comparators']={name:simulate(frozen,inputs,[],through,name) for name in ['CASH','START_HOLD','MA5_MA20']}
        replay={'frozen':frozen,'inputs':inputs,'forecasts':all_forecasts,'through_date':through}
        archive=self.evidence.archive(encode(replay).encode(),'SHADOW_CONTINUOUS_INPUT',research_namespace='SHADOW')
        output.update(freeze_id=freeze_id,revision=prior['revision']+1,through_date=through,input_archive=archive,
                      complete_protocol_fingerprint=frozen['complete_protocol_fingerprint'],recorded_at=now())
        output['result_fingerprint']=fingerprint({k:v for k,v in output.items() if k not in {'recorded_at','input_archive'}})
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            revision=db.execute('SELECT COALESCE(MAX(revision),0) FROM research_shadow_runs WHERE freeze_id=?',(freeze_id,)).fetchone()[0]
            if revision!=command.expected_revision:raise HTTPException(409,'影子版本冲突')
            db.execute('INSERT INTO research_shadow_runs VALUES(?,?,?)',(freeze_id,output['revision'],encode(output)))
            self.registry.event(frozen['protocol_id'],'SHADOW_ADVANCED',db=db,freeze_id=freeze_id,revision=output['revision'],input_sha256=archive['sha256'],actual_account_mutated=False)
            db.commit()
        return output

    def replay(self, freeze_id):
        state=self.current(freeze_id)
        if not state['revision']:raise HTTPException(409,'尚无连续演化可重放')
        original=self.checked_archive(state['input_archive']);frozen=original['frozen']
        if frozen['fingerprints']['shadow_code']!=shadow_code():raise HTTPException(409,'原算法不同，不以新代码冒充重放')
        replay=simulate(frozen,original['inputs'],original['forecasts'],original['through_date'])
        comparisons={name:simulate(frozen,original['inputs'],[],original['through_date'],name) for name in ['CASH','START_HOLD','MA5_MA20']}
        matches=all(state[k]==v for k,v in replay.items()) and comparisons==state['comparators']
        return {'freeze_id':freeze_id,'revision':state['revision'],'matches_original':matches,'network_calls':0,'input_sha256':state['input_archive']['sha256']}

    def conditional(self, freeze_id, command):
        frozen=self.get(freeze_id);account=self.ledger.account();forecasts=self.forecasts(frozen,command.forecast_ids)
        cutoffs={f['observation_cutoff'][:10] for f in forecasts}
        if len(cutoffs)!=1:raise HTTPException(422,'一次账户条件诊断须使用同一个明确研究观察日')
        cutoff=next(iter(cutoffs));snapshot_at=now();valuation_inputs=[];valuation=Decimal('0');unknown=False
        input_data=self.simulation_input(frozen,forecasts);orders=[]
        for f in forecasts:
            day=f['observation_cutoff'][:10];row=next(r for r in input_data['facts'] if r['trade_date']==day and r['instrument']==f['instrument'])
            rule=frozen['rules'][f['instrument']];gross=Decimal(row['close'])*(1+Decimal(rule['normal_price_limit_percent'])/100)*Decimal(frozen['policy']['quantity'])
            reserve=gross+Decimal(fees(gross,frozen['design']['costs'],'BUY')['total_yuan'])
            orders.append({**f,'required_cash_yuan':money(reserve),'quantity':frozen['policy']['quantity']})
        for p in account['positions']:
            row=next((r for r in input_data['facts'] if r['instrument']==p['instrument'] and r['trade_date']==cutoff),None)
            valuation_inputs.append({'instrument':p['instrument'],'quantity':p['quantity'],'trade_date':cutoff,
                'price_yuan':row.get('close') if row else None,'raw_hash':row.get('raw_hash') if row else None})
            if not row or row.get('errors') or row.get('close') is None:unknown=True
            else:valuation+=Decimal(p['quantity'])*Decimal(row['close'])
        available=account.get('conservative_available')
        if account['cash_balance'] is None or available is None:
            decisions=[{**o,'action':'REFUSE','reasons':['ACCOUNT_AVAILABLE_CASH_UNKNOWN']} for o in orders]
        else:
            cash=Decimal(available);nav=Decimal(account['cash_balance'])+valuation
            decisions=calculate_policy(orders,cash,Decimal('0'),valuation,None if unknown else nav,
                {p['instrument'] for p in account['positions']},frozen['policy'])
        result={'diagnostic_id':str(uuid4()),'freeze_id':freeze_id,'recorded_at':now(),'namespace':'ACCOUNT_CONDITIONAL',
            'account_version':account['version'],'account_snapshot':account,'forecasts':forecasts,'decisions':decisions,
            'account_snapshot_recorded_at':snapshot_at,'price_as_of_date':cutoff,'valuation_inputs':valuation_inputs,
            'forecast_observation_cutoffs':[f['observation_cutoff'] for f in forecasts],
            'valuation_basis':'HISTORICAL_RAW_AT_FORECAST_CUTOFF_NOT_CURRENT_PRICE',
            'continuous_performance':False,'performance_included_in_shadow':False,'capability':'NOT_GRANTED',
            'scope':'ONE_ACCOUNT_SNAPSHOT_ONLY; no execution intent or actual transaction'}
        result['archive']=self.evidence.archive(encode(result).encode(),'ACCOUNT_CONDITIONAL_DIAGNOSTIC',research_namespace='ACCOUNT_CONDITIONAL')
        with self.ledger.connection() as db:db.execute('INSERT INTO research_conditional_runs VALUES(?,?,?)',(result['diagnostic_id'],freeze_id,encode(result)))
        return result

    def results(self, freeze_id):
        frozen=self.get(freeze_id)
        with self.ledger.connection() as db:
            diagnostics=[json.loads(r[0]) for r in db.execute('SELECT value FROM research_conditional_runs WHERE freeze_id=? ORDER BY rowid',(freeze_id,))]
        return {'ACTUAL':self.ledger.account(), 'HISTORICAL':{'namespace':'HISTORICAL','model_run_id':frozen['model_run_id'],
            'evidence_kind':frozen['evidence_kind'],'data_use':frozen['data_use'],'continuous_performance':False},
            'SHADOW':self.current(freeze_id),'ACCOUNT_CONDITIONAL':diagnostics}
