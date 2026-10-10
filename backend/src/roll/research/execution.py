"""Frozen daily execution inputs and append-only label assessments, never account facts."""
import hashlib
import json
from datetime import date,datetime
from pathlib import Path
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP,ROUND_DOWN
from typing import Literal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field,field_validator
from roll.agents.codex_process import owner_alive
from roll.accounts.ledger import encode,now
from roll.market.rules import SHANGHAI
from roll.research import historical_costs
from roll.research import reconstruction


class ExecutionCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    partition:Literal['DEVELOPMENT','CALIBRATION','SEALED']
    observation_date:date
    label_as_of:datetime|None=None
    delay:Literal['NEXT_OPEN','NEXT_CLOSE','ONE_MORE_SESSION_OPEN','OUTSIDE_ALLOWED_PRICE_NO_FILL']='NEXT_OPEN'
    fill_fraction:Literal['0','0.50','1']='1'
    quantity:str|None=None
    path_policy:Literal['CONSERVATIVE','INTERVAL','UNDETERMINABLE']='CONSERVATIVE'
    method_barriers:dict[str,str]|None=None
    commission_scenario_rate:Literal['0.0003','0.0006','0.003']|None=None
    slippage_each_side_rate:Literal['0.0005','0.001','0.002']|None=None
    basis:str=Field(min_length=1,max_length=2000)

    @field_validator('quantity')
    @classmethod
    def valid_quantity(cls,value):
        if value is not None:
            try:number=Decimal(value)
            except InvalidOperation:raise ValueError('数量须为整数股') from None
            if not number.is_finite() or number<=0 or number!=number.to_integral_value() or number>1000000:raise ValueError('数量须为1至1000000的整数股')
        return value


class AssessmentCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    label_as_of:datetime
    basis:str=Field(min_length=1,max_length=2000)


def money(value):return str(value.quantize(Decimal('0.01'),rounding=ROUND_HALF_UP))


def fees(gross,costs,side,statutory=None):
    if statutory is not None:
        if statutory.get('status') not in {'VERIFIED_STATUTORY_SCHEDULE','CURRENT_DISPLAY_SCENARIO'} or statutory.get('side')!=side:
            raise ValueError('HISTORICAL_STATUTORY_COST_UNPROVEN')
        if Decimal(costs['extra_regulatory_charge'])!=0:
            raise ValueError('SCENARIO_COMMISSION_ALREADY_INCLUDES_REGULATORY_FEES')
        transfer=Decimal(statutory['transfer_each_side_rate']);stamp=Decimal(statutory['stamp_applied_rate'])
    else:transfer=Decimal(costs['transfer_each_side_rate']);stamp=Decimal(costs['stamp_sell_rate']) if side=='SELL' else Decimal('0')
    commission=max(Decimal(costs['minimum_commission_yuan']),gross*Decimal(costs['commission_scenario_rate']))
    result={'commission_yuan':money(commission),'transfer_yuan':money(gross*transfer),
        'stamp_yuan':money(gross*stamp),
        'extra_regulatory_yuan':money(Decimal(costs['extra_regulatory_charge']))}
    result['total_yuan']=money(sum(Decimal(v) for v in result.values()));return result


def number(value):
    try:
        result=Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation,ValueError):return None


def engine_fingerprint():
    # Only source text gets canonical LF hashing; archived provider bytes never do.
    return hashlib.sha256(encode({'execution_source':hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
        'historical_cost_schedule':historical_costs.schedule_fingerprint(),
        'reconstruction_cash_rules':reconstruction.fingerprint(),
        'corporate_action_source':hashlib.sha256(Path(__file__).with_name('corporate_actions.py').read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
        'cash_source_manifest':hashlib.sha256((Path(__file__).parent/'reference/cash-rights/sources.json').read_bytes()).hexdigest()}).encode()).hexdigest()


def evaluate(inputs,definition,label_as_of,available_at=None):
    result={'label_matures_at':definition['label_matures_at'],'maturity_date':definition['maturity_date'],
        'label_status':'UNSCORABLE','label':None,'scoreable':False,'eligible_for_training':False,
        'net_pnl_yuan':None,'label_available_at':None,'execution_status':'UNKNOWN','entry':None,'exit':None,
        'reasons':[],'training_restrictions':['METHOD_CASE_NOT_REAL_TRAINING_INPUT'] if inputs['evidence_kind']=='METHOD_CASE' else ['RECONSTRUCTED_NOT_STRICT_PIT_OR_FORMAL_QUALIFICATION'] if inputs.get('data_use')=='RECONSTRUCTED_RESEARCH' else ['HISTORICAL_PIT_AND_SPECIAL_STATUS_NOT_PROVEN']}
    reconstructed=inputs.get('data_use')=='RECONSTRUCTED_RESEARCH' and inputs['evidence_kind']=='REAL_ACQUISITION'
    maturity=definition['maturity_date'];matures_at=definition['label_matures_at']
    if (matures_at and label_as_of<datetime.fromisoformat(matures_at)) or (maturity and label_as_of.astimezone(SHANGHAI).date().isoformat()<maturity):
        result['label_status']='IMMATURE';result['reasons']=['TWENTY_SESSION_EVENT_NOT_MATURE']
        return result
    if maturity is None:result['reasons']=['CALENDAR_HORIZON_UNKNOWN'];return result
    completion=definition.get('maturity_evidence_available_at')
    if completion and label_as_of<datetime.fromisoformat(completion):
        result['label_status']='IMMATURE';result['reasons']=['COMPLETE_EXIT_BAR_NOT_YET_AVAILABLE_AT_ASSESSMENT'];return result
    if matures_at is None:result['reasons'].append('MATURITY_TIME_UNKNOWN')
    if completion is None:result['reasons'].append('COMPLETE_EXIT_BAR_AVAILABILITY_UNKNOWN')
    if inputs['evidence_kind']!='METHOD_CASE':
        schedule=definition.get('historical_costs')
        if not schedule:result['reasons'].append('HISTORICAL_COST_SCHEDULE_MISSING')
        else:
            for side in ['BUY','SELL']:
                result['reasons'].extend(schedule[side]['reasons'])
            result['cost_basis']=schedule
    rows={f['trade_date']:f for f in inputs['facts']};sessions=definition['scheduled_sessions'];rule=definition['rule']
    if rule.get('rule_scope')!='METHOD_CASE_ONLY' and rule.get('implementation_status')!='ADAPTED':result['reasons'].append('HISTORICAL_RULE_SCOPE_UNKNOWN')
    if maturity>inputs['partition_last_date']:result['reasons'].append('LABEL_SPANS_PARTITION_BOUNDARY')
    needed=[definition['observation_date'],*[d for d in sessions if d<=maturity]]
    terminal=definition.get('terminal_settlement')
    for day in needed:
        row=rows.get(day)
        if row is None:result['reasons'].append('MISSING_DAILY:'+day);continue
        if row.get('errors'):result['reasons'].append('INVALID_DAILY:'+day)
        reconstructed_suspended=reconstructed and row.get('execution_evidence',{}).get('state')=='REPORTED_SUSPENDED_RECONSTRUCTED'
        if row.get('completion_state')!='COMPLETE_REPORTED_HISTORICAL' and not (reconstructed_suspended and row.get('completion_state')=='SUSPENSION_PLACEHOLDER'):result['reasons'].append('INCOMPLETE_DAILY:'+day)
        available=row.get('available_at')
        if not available or datetime.fromisoformat(available)>datetime.fromisoformat(definition['consumer_knowledge_cutoff']):result['reasons'].append('NOT_AVAILABLE_TO_CONSUMER:'+day)
        state=row.get('execution_evidence',{})
        allowed_states={'CONFIRMED_NORMAL','CONFIRMED_SUSPENDED'}|({'REPORTED_NORMAL_RECONSTRUCTED','REPORTED_SUSPENDED_RECONSTRUCTED'} if reconstructed else set())
        if state.get('state') not in allowed_states:result['reasons'].append('HISTORICAL_STATUS_UNKNOWN')
        terminal_row=bool(terminal and day==maturity and row.get('terminal_settlement') and state.get('company_actions')=='CONFIRMED_TERMINAL_CASH_TREATMENT')
        if state.get('company_actions')!='CONFIRMED_NONE' and not terminal_row and not (reconstructed and state.get('company_actions')=='SOURCE_BOUND_CASH_AND_ANNUAL_SHARE_AUDIT'):result['reasons'].append('COMPANY_ACTIONS_UNKNOWN')
        settlement=row.get('terminal_settlement')
        if settlement and settlement.get('state')!='CONFIRMED_ALL_SHARES_CASH_SETTLED':result['reasons'].append('UNCONFIRMED_TERMINAL_SETTLEMENT')
        if not terminal_row and not reconstructed_suspended:
            if any(number(row.get(field)) is None or number(row.get(field))<=0 for field in ['open','high','low','close']):result['reasons'].append('INVALID_OHLC:'+day)
            elif not number(row['low'])<=min(number(row['open']),number(row['close']))<=max(number(row['open']),number(row['close']))<=number(row['high']):result['reasons'].append('INCONSISTENT_OHLC:'+day)
    result['reasons']=list(dict.fromkeys(result['reasons']))
    if result['reasons']:return result
    costs=definition['costs'];plan=definition['order'];quantity=Decimal(plan['quantity']);fraction=Decimal(plan['fill_fraction'])
    if inputs['evidence_kind']!='METHOD_CASE' and (not costs.get('commission_includes_regulatory_fees') or Decimal(costs['extra_regulatory_charge'])!=0):
        result['reasons']=['SCENARIO_COMMISSION_ALREADY_INCLUDES_REGULATORY_FEES'];return result
    step=Decimal(rule['buy_increment']);minimum=Decimal(rule['buy_minimum']);filled=(quantity*fraction/step).to_integral_value(rounding=ROUND_DOWN)*step
    result.update({'filled_quantity':str(filled),'unfilled_quantity':str(quantity-filled),'earliest_resale_date':plan['earliest_resale_date']})
    reason='OUTSIDE_FROZEN_PRICE_WINDOW' if plan['delay']=='OUTSIDE_ALLOWED_PRICE_NO_FILL' else ('DECLARED_MISSED_FILL' if fraction==0 else ('PARTIAL_BELOW_MINIMUM_LOT' if filled<minimum else None))
    day=plan['entry_date'];row=rows[day];price=number(row['close' if plan['delay']=='NEXT_CLOSE' else 'open'])
    if row.get('execution_evidence',{}).get('state') in {'CONFIRMED_SUSPENDED','REPORTED_SUSPENDED_RECONSTRUCTED'}:reason='CONFIRMED_SUSPENSION_ON_ENTRY'
    if reconstructed and reason=='CONFIRMED_SUSPENSION_ON_ENTRY':
        result.update(label_status='NO_EXECUTION',execution_status='NO_EXECUTION',filled_quantity='0',unfilled_quantity=str(quantity),reasons=[reason]);return result
    if row.get('volume_unit')!='SHARE' or number(row.get('volume_shares')) is None:
        result['reasons']=['EXECUTION_VOLUME_UNKNOWN'];return result
    if number(row['volume_shares'])==0:reason='ZERO_REPORTED_VOLUME'
    if number(row['volume_shares'])<filled and number(row['volume_shares'])!=0:result['reasons']=['DECLARED_FILL_EXCEEDS_REPORTED_VOLUME'];return result
    if not Decimal(plan['price_window']['lower_yuan'])<=price<=Decimal(plan['price_window']['upper_yuan']):reason='OUTSIDE_FROZEN_PRICE_WINDOW'
    if reason:
        result.update({'label_status':'NO_EXECUTION','execution_status':'NO_EXECUTION','filled_quantity':'0','unfilled_quantity':str(quantity),'net_pnl_yuan':'0.00','reasons':[reason]});return result
    if reconstructed and rows[maturity].get('execution_evidence',{}).get('state')=='REPORTED_SUSPENDED_RECONSTRUCTED':
        result.update(execution_status='BLOCKED_EXIT',reasons=['CONFIRMED_SUSPENSION_ON_EXIT']);return result
    tick=Decimal(rule['price_tick_yuan']);slip=Decimal(costs['slippage_each_side_rate'])
    entry_price=(price*(1+slip)/tick).quantize(Decimal('1'),rounding=ROUND_HALF_UP)*tick
    exit_price=Decimal(terminal['cash_per_share_yuan']) if terminal else (number(rows[maturity]['close'])*(1-slip)/tick).quantize(Decimal('1'),rounding=ROUND_HALF_UP)*tick
    if reconstructed:
        lower=Decimal(plan['price_window']['lower_yuan']);upper=Decimal(plan['price_window']['upper_yuan'])
        if all(number(row[k])==upper for k in ['open','high','low','close']) or entry_price>upper:
            result.update(label_status='NO_EXECUTION',execution_status='NO_EXECUTION',reasons=['LOCKED_UPPER_LIMIT_OR_SLIPPED_ENTRY_OUTSIDE_BAND']);return result
        exit_band=definition.get('exit_price_window')
        if not exit_band:result['reasons']=['EXIT_PRICE_BAND_UNKNOWN'];return result
        floor=Decimal(exit_band['lower_yuan']);ceiling=Decimal(exit_band['upper_yuan'])
        if all(number(rows[maturity][k])==floor for k in ['open','high','low','close']) or not floor<=exit_price<=ceiling:
            result.update(execution_status='BLOCKED_EXIT',reasons=['LOCKED_LOWER_LIMIT_OR_SLIPPED_EXIT_OUTSIDE_BAND']);return result
    path=None;exit_day=maturity
    barriers=definition.get('method_barriers')
    if barriers and not terminal:
        stop=Decimal(barriers['stop_price_yuan']);profit=Decimal(barriers['profit_price_yuan']);ignored=[];excluded=[]
        for d in sessions:
            if d>maturity:break
            bar=rows[d];touch_stop=Decimal(bar['low'])<=stop;touch_profit=Decimal(bar['high'])>=profit
            if d<plan['earliest_resale_date']:
                if touch_stop or touch_profit:ignored.append(d)
                continue
            if bar.get('execution_evidence',{}).get('state')=='CONFIRMED_SUSPENDED' or number(bar.get('volume_shares'))==0:
                if touch_stop or touch_profit:excluded.append(d)
                continue
            if bar.get('volume_unit')!='SHARE' or number(bar.get('volume_shares')) is None:
                result['reasons']=['TOUCH_EXIT_VOLUME_UNKNOWN:'+d];return result
            if touch_stop or touch_profit:
                # Daily touches prove neither ordering nor an actual fill. Include
                # the missed-touch horizon exit among the declared stress paths.
                candidates=[exit_price]
                if touch_stop:candidates.append((stop*(1-slip)/tick).quantize(Decimal('1'),rounding=ROUND_HALF_UP)*tick)
                if touch_profit:candidates.append((profit*(1-slip)/tick).quantize(Decimal('1'),rounding=ROUND_HALF_UP)*tick)
                path={'ambiguous_trade_date':d,'entry_day_touch_ignored_for_resale':ignored,'touches':{'stop':touch_stop,'profit':touch_profit},
                    'observed_fill_proven':False,'policy':definition['path_policy'],'missed_touch_horizon_exit_included':True,'excluded_unexecutable_touch_dates':excluded}
                buy=entry_price*filled;buyfees=fees(buy,costs,'BUY')
                pnls=[p*filled-Decimal(fees(p*filled,costs,'SELL')['total_yuan'])-buy-Decimal(buyfees['total_yuan']) for p in candidates]
                result['same_day_path']=path;result['net_pnl_interval_yuan']={'lower':money(min(pnls)),'upper':money(max(pnls))}
                if definition['path_policy']=='UNDETERMINABLE':result['reasons']=['DAILY_TOUCH_PATH_OR_FILL_UNDETERMINABLE'];return result
                if definition['path_policy']=='INTERVAL':
                    result.update({'label_status':'INTERVAL','execution_status':'SIMULATED_AMBIGUOUS','reasons':['DAILY_TOUCH_PATH_OR_FILL_UNDETERMINABLE']});return result
                exit_price=min(candidates);exit_day=d if exit_price!=candidates[0] else maturity;path['selected_bound']='LOWER';break
    if rows[maturity].get('execution_evidence',{}).get('state') in {'CONFIRMED_SUSPENDED','REPORTED_SUSPENDED_RECONSTRUCTED'} and not terminal:
        result.update({'execution_status':'BLOCKED_EXIT','reasons':['CONFIRMED_SUSPENSION_ON_EXIT']});return result
    if not terminal and (rows[maturity].get('volume_unit')!='SHARE' or number(rows[maturity].get('volume_shares')) is None or number(rows[maturity]['volume_shares'])<=0):
        result.update({'execution_status':'BLOCKED_EXIT','reasons':['EXIT_VOLUME_UNKNOWN_OR_ZERO']});return result
    if terminal:exit_price=Decimal(terminal['cash_per_share_yuan'])
    schedule=definition.get('historical_costs') if inputs['evidence_kind']!='METHOD_CASE' else None
    buy=entry_price*filled;sell=exit_price*filled
    buyfees=fees(buy,costs,'BUY',schedule['BUY'] if schedule else None)
    sellfees=fees(sell,costs,'SELL',schedule['SELL'] if schedule else None) if not terminal else {k:'0.00' for k in ['commission_yuan','transfer_yuan','stamp_yuan','extra_regulatory_yuan','total_yuan']}
    if buy+Decimal(buyfees['total_yuan'])>Decimal(plan['cash_budget_yuan']):result['reasons']=['CASH_OR_EXPOSURE_LIMIT'];return result
    if maturity<plan['earliest_resale_date']:result['reasons']=['T_PLUS_ONE_EXIT_NOT_ALLOWED'];return result
    pnl=sell-Decimal(sellfees['total_yuan'])-buy-Decimal(buyfees['total_yuan'])
    if reconstructed:
        try:rights=reconstruction.cash_economics(inputs['research_assumptions']['cash_events'],day,exit_day,filled,definition['consumer_knowledge_cutoff'])
        except ValueError as error:
            result['reasons']=[str(error)];return result
        result['cash_rights']=rights;pnl+=Decimal(rights['net_economic_entitlement_yuan'])
    result.update({'label_status':'MATURE','execution_status':'PARTIAL' if filled<quantity else 'FILLED','label':int(pnl>0),'scoreable':True,
        'net_pnl_yuan':money(pnl),'net_return_on_invested_cash':str(pnl/(buy+Decimal(buyfees['total_yuan']))),
        'entry':{'trade_date':day,'daily_price_field':'close' if plan['delay']=='NEXT_CLOSE' else 'open','price_yuan':money(entry_price),'gross_yuan':money(buy),'fees':buyfees},
        'exit':{'trade_date':exit_day,'daily_price_field':None if terminal or path else 'close','price_yuan':money(exit_price),'gross_yuan':money(sell),'fees':sellfees,
            **({'basis':'CONFIRMED_TERMINAL_CASH_SETTLEMENT'} if terminal else {})},
        'label_available_at':available_at,'execution_basis':'DAILY_SCENARIO_NOT_OBSERVED_BROKER_FILL','cost_basis':'FROZEN_RESEARCH_SCENARIO; UNKNOWN_ACTUAL_BROKER_TARIFF_NOT_ZERO'})
    result['eligible_for_training']=reconstructed
    return result


class DailyExecutions:
    def __init__(self,registry):
        self.registry=registry;self.ledger=registry.ledger;self.evidence=registry.evidence
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS research_executions(id TEXT PRIMARY KEY,protocol_id TEXT NOT NULL,value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS research_execution_results(id TEXT PRIMARY KEY,value TEXT NOT NULL)')
        with self.ledger.connection() as db:
            pending=[json.loads(r[0]) for r in db.execute('SELECT value FROM research_executions WHERE id NOT IN (SELECT id FROM research_execution_results)')]
        for item in pending:
            if not owner_alive(item):self._finish(item,{'status':'INTERRUPTED','reason':'原宿主停止或旧版本没有可验证身份；原定义和输入保留，不制造标签'})

    def _finish(self,run,completion):
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            inserted=db.execute('INSERT OR IGNORE INTO research_execution_results VALUES(?,?)',(run['execution_id'],encode(completion)))
            if inserted.rowcount:self.registry.event(run['protocol_id'],'EXECUTION_FINISHED',db=db,execution_id=run['execution_id'],status=completion['status'])
            db.commit()

    def get(self,identifier):
        with self.ledger.connection() as db:
            row=db.execute('SELECT value FROM research_executions WHERE id=?',(identifier,)).fetchone()
            if row is None:raise HTTPException(404,'日线执行记录不存在')
            completion=db.execute('SELECT value FROM research_execution_results WHERE id=?',(identifier,)).fetchone()
        return {**json.loads(row[0]),**(json.loads(completion[0]) if completion else {'status':'RUNNING'})}

    def create(self,protocol_id,command):
        protocol=self.registry.get(protocol_id)
        if command.partition=='SEALED':
            self.registry.event(protocol_id,'EXECUTION_REFUSED',reason='未冻结完整协议，日线执行不能读取封存输入',confirmatory_pass_look=False)
            raise HTTPException(403,'本票仅允许开发/校准日线执行；封存输入不开放给执行入口')
        dataset=self.registry.dataset(protocol['dataset_id']);part=self.registry.partition(dataset['dataset_id'],command.partition)
        if not part['metadata']['first_date']<=command.observation_date.isoformat()<=part['metadata']['last_date']:
            raise HTTPException(422,'观察日期必须处于登记分片的标签窗口；前置上下文不能拟合标签')
        facts=part['facts'];anchor=next((f for f in facts if f['trade_date']==command.observation_date.isoformat()),None)
        if anchor is None:raise HTTPException(422,'登记观察日无已归档原价日线')
        instrument=anchor['instrument'];identity=dataset['scope']['identity_context'][instrument]
        sessions=[];current=command.observation_date
        for _ in range(protocol['design']['horizon_sessions']):
            following=self.evidence.market.rules.next_trading_day(identity['exchange'],current)
            if following is None:break
            sessions.append(following);current=date.fromisoformat(following)
        maturity=sessions[-1] if len(sessions)==20 else None
        method=dataset['source_evidence_kind']=='METHOD_CASE'
        reconstructed=dataset.get('data_use')=='RECONSTRUCTED_RESEARCH' and dataset['source_evidence_kind']=='REAL_ACQUISITION'
        if command.method_barriers and not method:raise HTTPException(422,'额外触价路径仅用于明确METHOD压力；不能改写实际M0事件')
        if command.method_barriers:
            if set(command.method_barriers)!={'stop_price_yuan','profit_price_yuan'} or any(number(v) is None or number(v)<=0 for v in command.method_barriers.values()):raise HTTPException(422,'方法路径需要两个正数原价边界')
            if number(command.method_barriers['stop_price_yuan'])>=number(command.method_barriers['profit_price_yuan']):raise HTTPException(422,'方法止损边界必须低于止盈边界')
        rule=anchor.get('execution_evidence',{}) if method else reconstruction.rule(self.evidence,identity,command.observation_date.isoformat()) if reconstructed else self.evidence.market.rules.rule(identity['exchange'],identity['board'],identity['instrument_type'],on=command.observation_date)
        close=rule.get('close_time') if method and rule.get('rule_scope')=='METHOD_CASE_ONLY' else None
        clock_basis='METHOD_CASE_ONLY' if close else 'UNKNOWN'
        if not close and maturity:
            exit_rule=reconstruction.rule(self.evidence,identity,maturity) if reconstructed and maturity<=part['metadata']['last_date'] else self.evidence.market.rules.rule(identity['exchange'],identity['board'],identity['instrument_type'],on=date.fromisoformat(maturity))
            if exit_rule['implementation_status']=='ADAPTED':close='15:00:00';clock_basis='ARCHIVED_RULE_CALENDAR_ADAPTED_DATE'
        as_of=command.label_as_of or datetime.fromisoformat(now())
        if as_of.tzinfo is None:raise HTTPException(422,'标签评估时点需要时区，不把日期补午夜')
        if as_of>datetime.fromisoformat(now()):raise HTTPException(422,'评估截止不能晚于实际当前知识时间')
        definition={'version':'18-daily-v1','event':protocol['design']['event'],'horizon_sessions':20,
            'observation_date':command.observation_date.isoformat(),'scheduled_sessions':sessions,'maturity_date':maturity,
            'label_matures_at':datetime.fromisoformat(maturity+'T'+close).replace(tzinfo=SHANGHAI).isoformat() if maturity and close else None,
            'maturity_clock_basis':clock_basis,
            'maturity_rule':'TWENTY_CONFIRMED_TRADING_SESSIONS_AND_COMPLETE_EXIT_BAR_AVAILABLE',
            'execution':protocol['design']['execution'],'costs':protocol['design']['costs'],'rule':rule,
            'engine_sha256':engine_fingerprint(),'engine_fingerprint_basis':'SHA256_EXECUTION_COST_CASH_RECONSTRUCTION_CODE_AND_SOURCE_MANIFESTS_CANONICAL_LF',
            'calendar_proof':self.evidence.market.rules.calendar(identity['exchange'],command.observation_date),
            'consumer_knowledge_cutoff':now(),'label_as_of':as_of.isoformat(),'historical_point_in_time_proven':False}
        definition.update({'path_policy':command.path_policy,'method_barriers':command.method_barriers,'terminal_settlement':None})
        definition['costs']={**definition['costs']}
        for field in ['commission_scenario_rate','slippage_each_side_rate']:
            chosen=getattr(command,field)
            allowed=protocol['design']['g5']['commission_rates' if field=='commission_scenario_rate' else 'slippage_each_side_rates']
            if chosen is not None:
                if chosen not in allowed:raise HTTPException(422,'费用压力不在原登记邻域，不能修改旧协议参数')
                definition['costs'][field]=chosen
        definition['cost_fingerprint']=hashlib.sha256(encode(definition['costs']).encode()).hexdigest()
        definition['exit_rule']={'primary':'HORIZON_SESSION20_CLOSE','terminal':'ONLY_CONFIRMED_ALL_SHARES_FINAL_CASH_WITH_ARCHIVED_TIME',
            'method_touch_policy':command.path_policy if command.method_barriers else None,'actual_following_distribution':'UNKNOWN; DAILY_SCENARIO_IS_NOT_USER_EXECUTION_BEHAVIOR'}
        for f in facts:
            settlement=f.get('terminal_settlement')
            if f['trade_date'] not in sessions or not settlement:continue
            if settlement.get('state')!='CONFIRMED_ALL_SHARES_CASH_SETTLED' or settlement.get('exit_fee_treatment')!='FINAL_CASH_NO_ADDITIONAL_FEE':continue
            effective=settlement.get('effective_at');available=settlement.get('available_at')
            if not effective or not available:continue
            effective_time=datetime.fromisoformat(effective);available_time=datetime.fromisoformat(available)
            if effective_time.tzinfo is None or available_time.tzinfo is None:continue
            if effective_time.astimezone(SHANGHAI).date().isoformat()!=f['trade_date'] or available_time>datetime.fromisoformat(definition['consumer_knowledge_cutoff']):continue
            if number(settlement.get('cash_per_share_yuan')) is None or number(settlement['cash_per_share_yuan'])<0:continue
            definition.update({'terminal_settlement':{**settlement,'raw_hash':f['raw_hash']},'maturity_date':f['trade_date'],'label_matures_at':effective_time.isoformat()})
            break
        final_row=next((f for f in facts if f['trade_date']==definition['maturity_date']),None)
        terminal=definition['terminal_settlement']
        completion=None
        if terminal:completion=(terminal.get('method_settlement_available_at') if method else None) or terminal.get('available_at')
        elif final_row:completion=(final_row.get('method_completion_available_at') if method else None) or final_row.get('available_at')
        definition['maturity_evidence_available_at']=completion
        definition['maturity_evidence_clock_kind']='METHOD_SYNTHETIC_COMPLETION_CLOCK' if method and ((terminal and terminal.get('method_settlement_available_at')) or (final_row and final_row.get('method_completion_available_at'))) else 'ARCHIVED_EXTERNAL_AVAILABLE_AT'
        # Order size/window is frozen from the observation, never the later fill/outcome.
        anchor_price=number(anchor.get('close'));limit=number(rule.get('normal_price_limit_percent'))
        budget=Decimal(protocol['design']['execution']['synthetic_initial_cash_yuan'])*Decimal(protocol['design']['primary_objective']['risk_constraints']['maximum_simulated_gross_exposure'])
        lower=anchor_price*(1-limit/100) if anchor_price and limit else None;upper=anchor_price*(1+limit/100) if anchor_price and limit else None
        minimum=number(rule.get('buy_minimum'));step=number(rule.get('buy_increment'))
        entry_index=1 if command.delay=='ONE_MORE_SESSION_OPEN' else 0
        entry_date=sessions[entry_index] if len(sessions)>entry_index else None
        if not method:
            definition['historical_costs']=historical_costs.freeze(self.evidence,identity,entry_date,definition['maturity_date'],definition['costs'])
            definition['cost_fingerprint']=hashlib.sha256(encode({'scenario':definition['costs'],
                'historical_statutory_schedule':definition['historical_costs']}).encode()).hexdigest()
        transfer=definition['costs']['transfer_each_side_rate'] if method else definition['historical_costs']['BUY']['transfer_each_side_rate']
        quantity=command.quantity
        if quantity is None:
            quantity=str((budget/(upper*(1+Decimal(definition['costs']['slippage_each_side_rate']))*(1+Decimal(definition['costs']['commission_scenario_rate'])+Decimal(transfer)))/step).to_integral_value(rounding=ROUND_DOWN)*step) if upper and step and transfer is not None else '0'
        if minimum and step and (command.quantity is not None or transfer is not None) and (Decimal(quantity)<minimum or (Decimal(quantity)-minimum)%step):raise HTTPException(422,'计划股数不符合已冻结最小买入量/增量')
        earliest_resale=self.evidence.market.rules.next_trading_day(identity['exchange'],date.fromisoformat(entry_date)) if entry_date else None
        definition['order']={'delay':command.delay,'quantity':quantity,'fill_fraction':command.fill_fraction,'entry_date':entry_date,
            'earliest_resale_date':earliest_resale,'cash_budget_yuan':str(budget),
            'price_window':{'lower_yuan':money(lower) if lower else None,'upper_yuan':money(upper) if upper else None,'basis':'FROZEN_OBSERVATION_CLOSE_AND_SUPPORTED_NORMAL_RULE; UNKNOWN_STATUS_BLOCKS_EXECUTION'}}
        if reconstructed:
            # Ex-right reference belongs to label execution, never to observation features.
            events=dataset['research_assumptions']['cash_events']
            entry_reference=anchor_price-sum(Decimal(e['gross_cash_yuan_per_eligible_share']) for e in events if e['ex_date']==entry_date)
            definition['order']['price_window']={'lower_yuan':money(entry_reference*(1-limit/100)),'upper_yuan':money(entry_reference*(1+limit/100)),
                'basis':'RAW_OBSERVATION_CLOSE_MINUS_KNOWN_ENTRY_EFFECTIVE_CASH; rounded0.01; labels only'}
            previous=next((f for f in facts if len(sessions)>=2 and f['trade_date']==sessions[-2]),None)
            if previous:
                exit_reference=number(previous['close'])-sum(Decimal(e['gross_cash_yuan_per_eligible_share']) for e in events if e['ex_date']==maturity)
                definition['exit_price_window']={'lower_yuan':money(exit_reference*(1-limit/100)),'upper_yuan':money(exit_reference*(1+limit/100)),
                    'basis':'RAW_PREVIOUS_SESSION_MINUS_EFFECTIVE_CASH; no future feature consumption'}
            definition['version']='19-reconstructed-single-opportunity-v2'
            definition['research_assumptions_sha256']=dataset['assumptions_archive']['sha256']
        selected=[f for f in facts if f['trade_date'] in [command.observation_date.isoformat(),*sessions]]
        inputs={'namespace':'HISTORICAL','partition':command.partition,'evidence_kind':dataset['source_evidence_kind'],
            'data_use':dataset.get('data_use'),'research_assumptions':dataset.get('research_assumptions'),
            'data_fingerprint':dataset['data_fingerprint'],'partition_sha256':part['metadata']['artifact']['sha256'],
            'original_archives':dataset['original_archives'],'partition_last_date':part['metadata']['last_date'],'facts':selected,'definition':definition}
        archive=self.evidence.archive(encode(inputs).encode(),'RESEARCH_EXECUTION_INPUT',research_namespace='HISTORICAL')
        run={'execution_id':str(uuid4()),'protocol_id':protocol_id,'registered_at':now(),'host_owner':self.registry.owner,**command.model_dump(mode='json'),
            'namespace':'HISTORICAL','capability':'NOT_GRANTED','evidence_kind':dataset['source_evidence_kind'],
            'protocol_fingerprint':protocol['protocol_fingerprint'],'data_fingerprint':dataset['data_fingerprint'],
            'definition':definition,'input_archive':archive,'label_as_of':as_of.isoformat()}
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE');db.execute('INSERT INTO research_executions VALUES(?,?,?)',(run['execution_id'],protocol_id,encode(run)))
            self.registry.event(protocol_id,'EXECUTION_REGISTERED',db=db,execution_id=run['execution_id'],input_sha256=archive['sha256'],definition=definition)
            db.commit()
        result=evaluate(inputs,definition,as_of)
        completed=now()
        if result['label_status']=='MATURE':result['label_available_at']=completed
        self._finish(run,{'status':'COMPLETED','completed_at':completed,'result':result})
        return self.get(run['execution_id'])

    def assess(self,identifier,command):
        parent=self.get(identifier)
        if parent['status']!='COMPLETED':raise HTTPException(409,'只有完成记录可以新增复评，原中断记录保留')
        if command.label_as_of.tzinfo is None:raise HTTPException(422,'复评截止需要时区')
        if command.label_as_of>datetime.fromisoformat(now()):raise HTTPException(422,'复评截止不能晚于当前实际知识时间')
        inputs=json.loads(self.evidence.raw(parent['input_archive']['sha256']).read_text(encoding='utf-8'))
        if inputs['definition']['engine_sha256']!=engine_fingerprint():raise HTTPException(409,'原算法版本不同，不以新代码静默重算')
        definition={**inputs['definition'],'label_as_of':command.label_as_of.isoformat(),'consumer_knowledge_cutoff':now()}
        inputs={**inputs,'definition':definition,'parent_input_sha256':parent['input_archive']['sha256']}
        archive=self.evidence.archive(encode(inputs).encode(),'RESEARCH_EXECUTION_INPUT',research_namespace='HISTORICAL')
        run={k:v for k,v in parent.items() if k not in {'status','completed_at','result'}}
        run.update({'execution_id':str(uuid4()),'parent_execution_id':identifier,'root_execution_id':parent.get('root_execution_id',identifier),
            'registered_at':now(),'host_owner':self.registry.owner,'basis':command.basis,'label_as_of':command.label_as_of.isoformat(),'definition':definition,'input_archive':archive})
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE');db.execute('INSERT INTO research_executions VALUES(?,?,?)',(run['execution_id'],run['protocol_id'],encode(run)))
            self.registry.event(run['protocol_id'],'EXECUTION_REASSESSMENT_REGISTERED',db=db,execution_id=run['execution_id'],parent_execution_id=identifier,input_sha256=archive['sha256'])
            db.commit()
        result=evaluate(inputs,definition,command.label_as_of);completed=now()
        if result['label_status']=='MATURE':result['label_available_at']=completed
        self._finish(run,{'status':'COMPLETED','completed_at':completed,'result':result})
        return self.get(run['execution_id'])

    def support(self,protocol_id,partition=None):
        self.registry.get(protocol_id)
        with self.ledger.connection() as db:ids=[r[0] for r in db.execute('SELECT id FROM research_executions WHERE protocol_id=? ORDER BY rowid',(protocol_id,))]
        items=[self.get(i) for i in ids];items=[r for r in items if not partition or r['partition']==partition]
        latest={}
        for r in items:latest[r.get('root_execution_id',r['execution_id'])]=r
        counts={};records=[];reasons={}
        for r in latest.values():
            result=r.get('result',{});state=result.get('label_status',r['status']);counts[state]=counts.get(state,0)+1
            for reason in result.get('reasons',[]):reasons[reason]=reasons.get(reason,0)+1
            records.append({'execution_id':r['execution_id'],'observation_date':r['observation_date'],'partition':r['partition'],
                'evidence_kind':r['evidence_kind'],'namespace':r['namespace'],'input_sha256':r['input_archive']['sha256'],
                'data_fingerprint':r['data_fingerprint'],'code_fingerprint':r['definition']['engine_sha256'],'definition':r['definition'],'result':result})
        return {'protocol_id':protocol_id,'record_count':len(items),'opportunity_count':len({(r['partition'],r['observation_date']) for r in items}),
            'latest_assessment_counts':counts,'eligible_for_training_count':sum(r.get('result',{}).get('eligible_for_training',False) for r in latest.values()),
            'method_case_count':sum(r['evidence_kind']=='METHOD_CASE' for r in latest.values()),'reasons':reasons,'records':records,
            'independent_sample_count':None,'basis':'Latest assessment per frozen execution family; repeated dates/scenarios are not independent support. METHOD is not real training. No PIT/qualification grant.'}

    def replay(self,identifier):
        run=self.get(identifier);inputs=json.loads(self.evidence.raw(run['input_archive']['sha256']).read_text(encoding='utf-8'))
        if run['definition']['engine_sha256']!=engine_fingerprint():
            raise HTTPException(409,'执行代码版本不同；保留原结果，不能冒充原算法重算')
        result=evaluate(inputs,inputs['definition'],datetime.fromisoformat(inputs['definition']['label_as_of']),run.get('completed_at'))
        self.registry.event(run['protocol_id'],'EXECUTION_OFFLINE_REPLAY',execution_id=identifier,input_sha256=run['input_archive']['sha256'],network_calls=0)
        return {'execution_id':identifier,'input_sha256':run['input_archive']['sha256'],'network_calls':0,'result':result,'matches_original':result==run.get('result')}
