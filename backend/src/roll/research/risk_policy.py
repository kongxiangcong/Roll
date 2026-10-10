"""Independent deterministic research policy; never grants capability or writes an action."""
import hashlib,json
from pathlib import Path
from uuid import uuid4
from datetime import datetime
from decimal import Decimal,ROUND_CEILING,ROUND_DOWN,ROUND_HALF_UP,localcontext
from pydantic import BaseModel,ConfigDict,Field
from fastapi import HTTPException
from roll.accounts.ledger import encode,now,timestamp
from roll.accounts.reconcile import use_check,UseCheck
from roll.decisions.funding import Funding,LossFacts,evaluate_loss
from roll.market.rules import SHANGHAI
from roll.research.registry import AttemptCommand,FinishCommand


class PolicyCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    basis:str=Field(min_length=1,max_length=2000)


class PolicyEvaluationCommand(PolicyCommand):
    required_as_of:datetime
    valuation_id:str|None=None


def code_fingerprint():return hashlib.sha256(Path(__file__).read_text(encoding='utf-8').replace('\r\n','\n').encode()).hexdigest()


def dependencies():
    root=Path(__file__).resolve().parents[1]
    paths=['accounts/reconcile.py','accounts/valuation.py','decisions/funding.py','market/rules.py']
    return {relative:hashlib.sha256((root/relative).read_text(encoding='utf-8').replace('\r\n','\n').encode()).hexdigest() for relative in paths}


def yuan(value):return format(value.quantize(Decimal('.01'),rounding=ROUND_HALF_UP),'.2f')


def calculate(inputs):
    policy=inputs['policy'];account=inputs['account'];auth=inputs['authorization'];check=inputs['account_use_check'];when=datetime.fromisoformat(inputs['required_as_of']).astimezone(SHANGHAI)
    reasons=[];positions=[];loss=inputs['loss_result'];frozen=policy['authorization'];known_quotes={};total=Decimal(0);total_known=True
    if not frozen['version'] or not auth['version']:reasons.append('FUNDING_AUTHORIZATION_MISSING')
    elif auth['scope_kind']!='ACCOUNT' or auth['scope_id']!=frozen['scope_id'] or auth['loss_origin_at']!=frozen['loss_origin_at']:reasons.append('AUTHORIZATION_SCOPE_UNSUPPORTED_OR_CHANGED')
    elif not auth['enabled']:reasons.append('AUTHORIZATION_REVOKED')
    if not check['allowed']:reasons.extend(['REDUCTION_FACTS_NOT_FRESH_OR_KNOWN',*check['reasons']])
    if inputs.get('capture_consistent') is False:reasons.append('CURRENT_INPUT_VERSION_CHANGED_DURING_EVALUATION')
    for holding in account['positions']:
        instrument=holding['instrument'];quote=inputs['quotes'].get(instrument);quantity=holding['quantity'];problem=None
        if quantity is None or not quote or quote.get('last') is None:problem='POSITION_PRICE_OR_QUANTITY_UNKNOWN'
        elif quote.get('adjustment')!='RAW' or quote.get('currency')!='CNY' or quote.get('errors'):problem='RAW_PRICE_SCOPE_NOT_SUPPORTED'
        elif datetime.fromisoformat(quote['upstream_at']).astimezone(SHANGHAI).date()!=when.date() or datetime.fromisoformat(quote['upstream_at']).astimezone(SHANGHAI).time().replace(tzinfo=None)<datetime.fromisoformat(when.date().isoformat()+'T15:00:00').time():problem='PRICE_NOT_SAME_SESSION_COMPLETE_CLOSE'
        elif datetime.fromisoformat(quote['available_at'])>datetime.fromisoformat(inputs['consumer_knowledge_cutoff']):problem='PRICE_NOT_AVAILABLE_TO_CONSUMER'
        if problem:total_known=False;known_quotes[instrument]={'problem':problem};continue
        price=Decimal(quote['last']);value=Decimal(quantity)*price;total+=value;known_quotes[instrument]={'price':price,'exposure':value,'quote':quote}
    with localcontext() as context:
        context.prec=50
        for holding in sorted(account['positions'],key=lambda r:r['instrument']):
            instrument=holding['instrument'];quote=known_quotes[instrument];local=[];rule=inputs['rules'].get(instrument,{});identity=inputs['identities'].get(instrument,{})
            row={'instrument':instrument,'quantity':holding['quantity'],'sellable_quantity':holding['sellable_quantity'],'in_policy_scope':instrument in policy['scope'].get('instruments',[]),
                'triggered':None,'executable_quantity':None,'target_quantity':None,'exposure_yuan':None,'authorized_single_exposure_yuan':None,'reasons':local,'rule':rule,'identity':identity,'stress':None}
            positions.append(row)
            if not row['in_policy_scope']:local.append('OUTSIDE_FROZEN_POLICY_SCOPE_FACTS_RETAINED');continue
            if reasons:local.extend(reasons);continue
            if 'problem' in quote:local.append(quote['problem']);continue
            price=quote['price'];quantity=Decimal(holding['quantity']);single=min(Decimal(auth['single_exposure']),Decimal(frozen['single_exposure']));cap=min(Decimal(auth['total_exposure']),Decimal(frozen['total_exposure']))
            target_money=min(single,max(Decimal(0),cap-(total-quote['exposure']))) if total_known else single
            exceeded=quote['exposure']>target_money
            row.update(exposure_yuan=yuan(quote['exposure']),authorized_single_exposure_yuan=yuan(single),authorized_total_exposure_yuan=yuan(cap),portfolio_exposure_yuan=yuan(total) if total_known else None,
                target_exposure_yuan=yuan(target_money),triggered=exceeded,trigger_basis='CONFIRMED_AUTHORIZED_EXPOSURE_EXCESS' if exceeded else 'NO_KNOWN_EXCESS',authorization_version=auth['version'])
            if not total_known:local.append('TOTAL_EXPOSURE_UNKNOWN_SINGLE_CAP_BRANCH_ONLY')
            if not exceeded:
                if loss is None or loss['status']=='RESTRICTED':row['triggered']=None;local.append('LOSS_FACTS_UNKNOWN_NO_DEFAULT_JUDGMENT')
                elif loss['triggered']:local.append('CONFIRMED_LOSS_PAUSE_NO_IMPLICIT_LIQUIDATION_RULE');row['triggered']=True
                else:local.append('NOT_TRIGGERED_IS_A_FACT_NOT_HOLD_OR_WAIT')
                continue
            if rule.get('implementation_status')!='ADAPTED' or rule.get('rule_id')!=policy['rule_ids'].get(instrument):local.append('RULE_UNKNOWN_OR_OUTSIDE_FROZEN_VERSION');continue
            if identity.get('board')!='MAIN' or identity.get('instrument_type')!='STOCK' or identity.get('exchange') not in {'SSE','SZSE'}:local.append('SELL_QUANTITY_RULE_OUTSIDE_MAIN_A_SCOPE');continue
            status=quote['quote'].get('method_status') if quote['quote'].get('evidence_kind')=='METHOD_CASE' else quote['quote'].get('current_status')
            if status not in {'NORMAL','CONFIRMED_NORMAL'}:local.append('CURRENT_SPECIAL_STATUS_UNKNOWN_OR_NOT_NORMAL');continue
            calendar=inputs['calendars'].get(instrument,{})
            if calendar.get('is_trading_day') is not True:local.append('CALENDAR_CLOSED_OR_UNKNOWN');continue
            if holding['sellable_quantity'] is None:local.append('SELLABLE_QUANTITY_UNKNOWN');continue
            sellable=Decimal(holding['sellable_quantity']);minimum=Decimal('100');step=Decimal('100')
            needed=max(Decimal(0),quantity-(target_money/price).to_integral_value(rounding=ROUND_DOWN))
            desired=quantity if needed>=quantity else min(quantity,(needed/step).to_integral_value(rounding=ROUND_CEILING)*step)
            feasible=min(desired,sellable)
            if feasible!=quantity:feasible=(feasible/step).to_integral_value(rounding=ROUND_DOWN)*step
            if feasible<=0:local.append('NO_CONFIRMED_SELLABLE_LOT');continue
            if desired>feasible:local.append('SELLABLE_LIMIT_LEAVES_RESIDUAL_RISK')
            limit=Decimal(rule['normal_price_limit_percent'])/100;tick=Decimal(rule['price_tick_yuan']);up=(price*(1+limit)).quantize(tick,rounding=ROUND_HALF_UP);down=(price*(1-limit)).quantize(tick,rounding=ROUND_HALF_UP);remaining=quantity-feasible
            row.update(executable_quantity=format(feasible,'f'),target_quantity=format(remaining,'f'),desired_reduction_quantity=format(desired,'f'),
                target_reached_at_reference=remaining*price<=target_money,
                price_window={'reference_yuan':str(price),'source':'COMPLETE_REPORTED_RAW_CLOSE','next_price_not_guaranteed':True},
                stress={'gap_up':{'price_yuan':yuan(up),'remaining_exposure_yuan':yuan(remaining*up),'within_target':remaining*up<=target_money},
                    'gap_down':{'price_yuan':yuan(down),'remaining_exposure_yuan':yuan(remaining*down),'within_target':remaining*down<=target_money},
                    'limit_down_no_fill':{'filled_quantity':'0','remaining_quantity':format(quantity,'f'),'remaining_exposure_yuan':yuan(quantity*down),'risk_released':False},
                    'one_more_session_delay':{'filled_quantity':'0','remaining_quantity':format(quantity,'f'),'future_price':None,'future_exposure':None,'risk_released':False},
                    'partial_50_percent':{'filled_quantity':format((feasible/2/step).to_integral_value(rounding=ROUND_DOWN)*step,'f'),'risk_released':False},
                    'suspended':{'filled_quantity':'0','remaining_quantity':format(quantity,'f'),'risk_released':False}})
            if total_known:total-=feasible*price
    computable=[r for r in positions if r['executable_quantity'] is not None]
    gaps=[g for r in positions for g in r['reasons']]
    engineering='FAIL' if 'AUTHORIZATION_REVOKED' in reasons else 'PASS' if computable and not reasons else 'INCONCLUSIVE'
    method=inputs['evidence_kind']=='METHOD_CASE'
    verdict='FAIL' if engineering=='FAIL' else 'INCONCLUSIVE'
    return {'positions':positions,'executable_quantities':{r['instrument']:r['executable_quantity'] for r in computable} if computable else None,
        'validation_verdict':verdict,'engineering_verdict':engineering,'reasons':list(dict.fromkeys([*reasons,*gaps,*(['METHOD_EVIDENCE_NOT_FORMAL_QUALIFICATION'] if method else [])])),
        'display_state':'RESEARCH_POLICY_QUANTITIES_ONLY' if computable else 'FACTS_AND_PENDING_ONLY','formal_action':None,'capability':'NOT_GRANTED',
        'profit_model_dependency':False,'account_use_check':check,'loss_result':loss,'evidence_kind':inputs['evidence_kind'],'namespace':'ACCOUNT_CONDITIONAL',
        'gate_results':{'DATA':'INCONCLUSIVE' if method else engineering,'RULE_QUANTITY':engineering,'AUTHORIZATION':'FAIL' if 'AUTHORIZATION_REVOKED' in reasons else 'INCONCLUSIVE' if method or reasons else 'PASS','STRESS_EXECUTION':'PASS' if computable else 'INCONCLUSIVE','ONLINE_CONSISTENCY':'PENDING_REPLAY'},
        'qualification_restriction':'22 research validation only;24/25 require own actual evidence/review/grant/current conditions. Profit model G3/G4/G7 unchanged.'}


class IndependentRiskPolicies:
    def __init__(self,registry,valuations):
        self.registry=registry;self.ledger=registry.ledger;self.evidence=registry.evidence;self.valuations=valuations;self.funding=Funding(self.ledger)
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS research_risk_policies(id TEXT PRIMARY KEY,protocol_id TEXT NOT NULL,value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS research_risk_evaluations(id TEXT PRIMARY KEY,policy_id TEXT NOT NULL,value TEXT NOT NULL)')

    def get(self,identifier):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM research_risk_policies WHERE id=?',(identifier,)).fetchone()
        if row is None:raise HTTPException(404,'独立风险政策不存在')
        return json.loads(row[0])

    def list(self,protocol_id):
        self.registry.get(protocol_id)
        with self.ledger.connection() as db:return [json.loads(r[0]) for r in db.execute('SELECT value FROM research_risk_policies WHERE protocol_id=? ORDER BY rowid',(protocol_id,))]

    def register(self,protocol_id,command):
        protocol=self.registry.get(protocol_id);authorization=self.funding.current();scope=protocol.get('scope',{})
        gaps=[]
        if not authorization['version']:gaps.append('FUNDING_AUTHORIZATION_MISSING')
        members={m['instrument']:m for m in self.evidence.market.listing()['members']}
        identities={instrument:members.get(instrument,{}).get('identity',{}) for instrument in scope.get('instruments',[])}
        rules={instrument:self.evidence.market.rules.rule(identity.get('exchange'),identity.get('board'),identity.get('instrument_type')) for instrument,identity in identities.items()}
        material={'policy_type':'AUTHORIZED_EXPOSURE_CAP_V1','basis':command.basis,'scope':scope,'authorization':authorization,
            'evidence_kind':self.evidence.evidence_kind,'identities':identities,'rule_ids':{i:r.get('rule_id') for i,r in rules.items()},'rule_sources':rules,
            'profit_model_dependency':False,'required_gates':['DATA','RULE_QUANTITY','AUTHORIZATION','STRESS_EXECUTION','ONLINE_CONSISTENCY'],
            'rule':'Current and frozen10 single_exposure/total_exposure minimum caps; known excess minimal100-share sell lots, entire odd remainder permitted, intersect fresh confirmed sellable. Missing portfolio value limits total branch only. No new risk/implicit liquidation.',
            'freshness':'Same actual Shanghai session complete15:00 RAW close <= observation cutoff and original available_at <= consumer knowledge cutoff; research ACCOUNT_CONDITIONAL not current executable order',
            'sell_scope':'SSE/SZSE MAIN ordinary A, archived2026rule; no extrapolation to STAR/CHINEXT/BSE or special status',
            'stable_priority':'ascending explicit instrument identifier; current caps applied per position, final joint order plan not published here',
            'loss_branch':'Only same-scope09 complete loss facts; unknown does not become zero. Independent cap branch does not require cash/fee facts.',
            'recovery':'No automatic recovery from price rebound or increased authorization; repeat current scoped facts/rules/authorization and later24/27 controlled qualification checks.',
            'formal_action':None,'capability':'NOT_GRANTED','code_fingerprint':code_fingerprint(),'dependency_fingerprints':dependencies(),'gaps':gaps}
        digest=hashlib.sha256(encode(material).encode()).hexdigest();archive=self.evidence.archive(encode(material).encode(),'RESEARCH_RISK_POLICY')
        policy={'policy_id':str(uuid4()),'protocol_id':protocol_id,'registered_at':now(),'policy_fingerprint':digest,'material_archive':archive,**material}
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE');db.execute('INSERT INTO research_risk_policies VALUES(?,?,?)',(policy['policy_id'],protocol_id,encode(policy)))
            self.registry.event(protocol_id,'INDEPENDENT_RISK_POLICY_REGISTERED',db=db,policy_id=policy['policy_id'],policy_fingerprint=digest,gaps=gaps,capability='NOT_GRANTED');db.commit()
        return policy

    def evaluate(self,identifier,command):
        policy=self.get(identifier)
        if policy['code_fingerprint']!=code_fingerprint() or policy['dependency_fingerprints']!=dependencies():raise HTTPException(409,'政策或计算依赖代码版本不同，先保留历史并登记明确后继；不复活旧依据')
        self.evidence.raw(policy['material_archive']['sha256'])
        if command.required_as_of.tzinfo is None or command.required_as_of>datetime.fromisoformat(now()):raise HTTPException(422,'风险检查时点需要时区且不得晚于当前知识时间')
        attempt=self.registry.start_attempt(policy['protocol_id'],AttemptCommand(category='RISK_POLICY_VALIDATION',partition='DEVELOPMENT',configuration={'policy_fingerprint':policy['policy_fingerprint'],'required_as_of':command.required_as_of.isoformat()},basis=command.basis))
        account=self.ledger.account();pending=self.ledger.pending_drafts();history=self.ledger.events();authorization=self.funding.current();cutoff=now()
        check=use_check(account,pending,UseCheck(purpose='REDUCTION',required_as_of=command.required_as_of.isoformat()),timestamp,history)
        members={m['instrument']:m for m in self.evidence.market.listing()['members']};identities={i:members.get(i,{}).get('identity',{}) for i in {p['instrument'] for p in account['positions']}}
        rules={i:self.evidence.market.rules.rule(v.get('exchange'),v.get('board'),v.get('instrument_type'),command.required_as_of.astimezone(SHANGHAI).date()) for i,v in identities.items()}
        calendars={i:self.evidence.market.rules.calendar(v.get('exchange'),command.required_as_of.astimezone(SHANGHAI).date()) for i,v in identities.items()}
        loss=None
        if command.valuation_id:
            try:
                valuation=self.valuations.get(command.valuation_id,replay=True)
                if valuation['account_version']!=account['version'] or datetime.fromisoformat(valuation['as_of'])!=command.required_as_of:raise HTTPException(409,'损失事实账户版本/时点必须与本次风险检查一致')
                with self.ledger.connection() as db:prior=[json.loads(r[0]) for r in db.execute('SELECT value FROM research_risk_evaluations ORDER BY rowid')]
                previous=[e['loss_result'] for e in prior if e.get('loss_result') and e['loss_result'].get('scope_id')==authorization.get('scope_id') and e['loss_result'].get('origin_at')==authorization.get('loss_origin_at')]
                loss=evaluate_loss(authorization,LossFacts(**valuation['facts']),previous[-1] if previous else None)
            except HTTPException as error:
                self.registry.finish_attempt(attempt['attempt_id'],FinishCommand(status='FAILED',reason=str(error.detail)[:2000]));raise
        inputs={'policy':policy,'account':account,'pending':pending,'events':history,'authorization':authorization,'required_as_of':command.required_as_of.isoformat(),
            'consumer_knowledge_cutoff':cutoff,'account_use_check':check,'identities':identities,'rules':rules,'calendars':calendars,
            'quotes':self.valuations.quotes(account,command.required_as_of.isoformat(),cutoff),'loss_result':loss,'evidence_kind':self.evidence.evidence_kind}
        if policy['evidence_kind']=='METHOD_CASE' or any(q.get('evidence_kind')=='METHOD_CASE' for q in inputs['quotes'].values()):inputs['evidence_kind']='METHOD_CASE'
        inputs['capture_consistent']=self.ledger.account()['version']==account['version'] and self.funding.current()['version']==authorization['version'] and self.ledger.pending_drafts()==pending
        archive=self.evidence.archive(encode(inputs).encode(),'RESEARCH_RISK_INPUT')
        outcome=calculate(inputs)
        result={'evaluation_id':str(uuid4()),'policy_id':identifier,'protocol_id':policy['protocol_id'],'registered_at':now(),
            'required_as_of':command.required_as_of.isoformat(),'consumer_knowledge_cutoff':cutoff,'basis':command.basis,'attempt_id':attempt['attempt_id'],
            'policy_fingerprint':policy['policy_fingerprint'],'code_fingerprint':code_fingerprint(),'input_archive':archive,'authorization':authorization,'account_version':account['version'],**outcome}
        self.registry.finish_attempt(attempt['attempt_id'],FinishCommand(status='SUCCEEDED',reason='独立确定性检查完成；不足不是正式资格',artifact_fingerprints={'policy':policy['policy_fingerprint'],'input':archive['sha256']}))
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE');db.execute('INSERT INTO research_risk_evaluations VALUES(?,?,?)',(result['evaluation_id'],identifier,encode(result)))
            self.registry.event(policy['protocol_id'],'INDEPENDENT_RISK_POLICY_EVALUATED',db=db,evaluation_id=result['evaluation_id'],input_sha256=archive['sha256'],validation_verdict=result['validation_verdict'],formal_action=None);db.commit()
        return result

    def get_evaluation(self,identifier):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM research_risk_evaluations WHERE id=?',(identifier,)).fetchone()
        if row is None:raise HTTPException(404,'风险政策检查不存在')
        return json.loads(row[0])

    def evaluations(self,identifier):
        self.get(identifier)
        with self.ledger.connection() as db:return [json.loads(r[0]) for r in db.execute('SELECT value FROM research_risk_evaluations WHERE policy_id=? ORDER BY rowid',(identifier,))]

    def replay(self,identifier):
        run=self.get_evaluation(identifier)
        if run['code_fingerprint']!=code_fingerprint():raise HTTPException(409,'原政策代码版本不同，不冒充原输入重放')
        inputs=json.loads(self.evidence.raw(run['input_archive']['sha256']).read_text(encoding='utf-8'))
        if inputs['policy']['dependency_fingerprints']!=dependencies():raise HTTPException(409,'原规则/资金/数量依赖代码不同，不以新计算冒充原版本')
        for q in inputs['quotes'].values():self.evidence.raw(q['raw_hash'])
        result=calculate(inputs);match=all(run[k]==v for k,v in result.items())
        self.registry.event(run['protocol_id'],'INDEPENDENT_RISK_POLICY_REPLAY',evaluation_id=identifier,input_sha256=run['input_archive']['sha256'],matches_original=match,network_calls=0,online_consistency='PASS' if match else 'FAIL')
        return {'evaluation_id':identifier,'input_sha256':run['input_archive']['sha256'],'matches_original':match,'network_calls':0,'result':result,'online_consistency':'PASS' if match else 'FAIL'}

    def validation(self,identifier):
        policy=self.get(identifier);evaluations=self.evaluations(identifier)
        if not evaluations:return {'policy_id':identifier,'validation_verdict':'INCONCLUSIVE','reason':'尚无实际检查或在线一致性证据','capability':'NOT_GRANTED','formal_action':None}
        latest=evaluations[-1];events=[e for e in self.registry.audit(policy['protocol_id']) if e['action']=='INDEPENDENT_RISK_POLICY_REPLAY' and e['evaluation_id']==latest['evaluation_id'] and e['input_sha256']==latest['input_archive']['sha256']]
        gates=dict(latest['gate_results']);gates['ONLINE_CONSISTENCY']=events[-1]['online_consistency'] if events else 'INCONCLUSIVE'
        verdict='FAIL' if 'FAIL' in gates.values() else 'PASS' if all(v=='PASS' for v in gates.values()) else 'INCONCLUSIVE'
        if latest['authorization']['version']!=self.funding.current()['version'] or latest['account_version']!=self.ledger.account()['version']:verdict='INCONCLUSIVE'
        return {'policy_id':identifier,'policy_fingerprint':policy['policy_fingerprint'],'code_fingerprint':policy['code_fingerprint'],
            'evaluation_id':latest['evaluation_id'],'input_sha256':latest['input_archive']['sha256'],'gate_results':gates,'validation_verdict':verdict,
            'evidence_kind':latest['evidence_kind'],'reasons':latest['reasons'],'evaluated_scope':[r['instrument'] for r in latest['positions']],
            'capability':'NOT_GRANTED','formal_action':None,'profit_model_dependency':False,'later_authority':'24 technical review/deterministic grant;25 actual action chain, not this record'}
