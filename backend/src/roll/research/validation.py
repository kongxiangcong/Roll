"""Append-only automatic checks against immutable experiment and ledger inputs.

Current historical diagnostics do not consume SEALED or create forward evidence.
Numeric method proof and missing real qualification evidence remain separate.
"""
import copy
import hashlib
import json
import math
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import fmean
from typing import Literal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from roll.accounts.ledger import encode, now
from roll.research.shadow import fingerprint, simulate, shadow_code
from roll.research.models import code_fingerprint
from roll.research.statistics import continuous_summary, probability_summary, paired_block_interval
from roll.agents.codex_process import owner_alive


class ValidationCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    purpose: Literal['DIAGNOSTIC', 'CONFIRMATORY'] = 'DIAGNOSTIC'
    expected_complete_protocol_fingerprint: str
    basis: str = Field(min_length=1, max_length=2000)


def validation_code():
    return hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def gate(status, reasons, details=None):
    return {'status': status, 'reasons': reasons, 'details': details or {}}


def combine(gates):
    """A hard failure cannot be cancelled by favorable or insufficient gates."""
    states = [g['status'] for g in gates.values()]
    return 'FAIL' if 'FAIL' in states else 'INCONCLUSIVE' if any(s != 'PASS' for s in states) else 'PASS'


def interval_decision(interval, boundary, minimum_blocks, assumptions_verified):
    if not assumptions_verified or interval['effective_block_upper_bound']<minimum_blocks or interval['lower_95'] is None:
        return 'INCONCLUSIVE'
    if interval['lower_95']>boundary:return 'PASS'
    if interval['upper_95']<boundary:return 'FAIL'
    return 'INCONCLUSIVE'


def gate_combination_method(frozen):
    cases=[]
    for inputs,expected in [({'G1':gate('FAIL',[]),'G7':gate('INCONCLUSIVE',[]),'G2':gate('PASS',[])},'FAIL'),
        ({'G1':gate('PASS',[]),'G7':gate('INCONCLUSIVE',[])},'INCONCLUSIVE')]:
        cases.append({'input':inputs,'expected':expected,'actual':combine(inputs)})
    interval=frozen['statistical_methods']['worked_examples']['boundary_crossing']
    actual=interval_decision(interval,0,2,True)
    cases.append({'input':interval,'expected':'INCONCLUSIVE','actual':actual,'evidence_kind':'METHOD_CASE'})
    return {'evidence_kind':'METHOD_CASE','method_fingerprint':validation_code(),'cases':cases,
        'checks_passed':all(c['expected']==c['actual'] for c in cases),'confers_real_pass':False}


def continuous_checks(frozen, candidate, comparators):
    design = frozen['design']; limits = design['primary_objective']['risk_constraints']
    summary = continuous_summary(candidate['curve'])
    opportunities = candidate['opportunities']
    unique = {r['opportunity_key'] for r in opportunities}
    selected = len({r['opportunity_key'] for r in opportunities if r['action']=='BUY'})
    coverage = selected / len(unique) if unique else 0
    exposures = [float(r['gross_exposure_fraction']) for r in candidate['curve'] if r.get('gross_exposure_fraction') is not None]
    hard = []
    if summary['maximum_drawdown'] is not None and summary['maximum_drawdown'] > float(limits['maximum_drawdown']):
        hard.append('MAXIMUM_DRAWDOWN_EXCEEDED')
    if exposures and max(exposures) > float(limits['maximum_simulated_gross_exposure']) + 1e-12:
        hard.append('MAXIMUM_EXPOSURE_EXCEEDED')
    if unique and coverage < float(limits['minimum_decision_coverage']): hard.append('MINIMUM_DECISION_COVERAGE_NOT_MET')
    comparisons = {}
    dates = [r['date'] for r in candidate['curve']]
    for name, reference in comparators.items():
        baseline = continuous_summary(reference['curve']); matched = {r['date']: r for r in reference['curve']}
        scores = []
        # Each overlapping20-session score comes from a single continuous trajectory.
        # Missing valuations retain their calendar slot rather than compressing time.
        for i, day in enumerate(dates[:-20]):
            first = candidate['curve'][i]; last = candidate['curve'][i+20]
            bfirst = matched.get(day); blast = matched.get(dates[i+20])
            values = [first.get('nav_yuan'), last.get('nav_yuan'), (bfirst or {}).get('nav_yuan'), (blast or {}).get('nav_yuan')]
            score = float(values[1])/float(values[0])-float(values[3])/float(values[2]) if all(v is not None for v in values) else None
            scores.append({'date': day, 'scores': {'MATCHED_NAV': score}})
        intervals = [paired_block_interval(scores, block_sessions=b) for b in [20,40]]
        if summary['maximum_drawdown'] is not None and baseline['maximum_drawdown'] is not None and name != 'CASH':
            if summary['maximum_drawdown']-baseline['maximum_drawdown'] > float(limits['candidate_drawdown_excess_over_risk_matched_baseline']):
                hard.append('DRAWDOWN_EXCESS_'+name)
        comparisons[name] = {'baseline': baseline, 'paired20_session_nav_intervals': intervals,
            'statistical_status':combine({str(i):gate(interval_decision(v,float(design['primary_objective']['minimum_improvement_nav_return']),design['statistics']['minimum_effective_time_blocks'],False),[]) for i,v in enumerate(intervals)}),
            'same_baseline_and_constraints': True, 'risk_difference': 'CASH zero exposure is explicit; START_HOLD/MA use frozen50% cap'}
    sells = [e for e in candidate['events'] if e['kind']=='SELL_FILL']
    gains = [float(r['realized_gain_yuan']) for r in candidate['curve']]
    increments=[b-a for a,b in zip([float(candidate.get('carry_in_realized_gain_yuan',0)),*gains[:-1]],gains)]
    losses=-sum(v for v in increments if v<0);profits=sum(v for v in increments if v>0)
    navs=[float(r['nav_yuan']) if r['nav_yuan'] is not None else None for r in candidate['curve']]
    returns=sorted(b/a-1 for a,b in zip(navs,navs[1:]) if a is not None and b is not None and a>0)
    entry_dates={**candidate.get('carry_in_entry_dates',{}),**{e['forecast_id']:e['date'] for e in candidate['events'] if e['kind']=='BUY_FILL'}}
    holding_calendar=candidate.get('holding_calendar',dates)
    hold_sessions=[holding_calendar.index(e['date'])-holding_calendar.index(entry_dates[e['forecast_id']]) for e in sells
        if e['forecast_id'] in entry_dates and e['date'] in holding_calendar and entry_dates[e['forecast_id']] in holding_calendar]
    return {'basis': 'CONSTRAINED_CONTINUOUS_NAV', 'candidate': summary, 'comparisons': comparisons,
        'decision_coverage': coverage, 'unique_opportunities': len(unique), 'selected': selected,
        'average_gross_exposure': fmean(exposures) if exposures else None,
        'maximum_gross_exposure': max(exposures) if exposures else None,
        'closed_positions': len(sells), 'holding_policy': frozen['policy']['exit'],
        'carry_in_realized_gain_yuan':candidate.get('carry_in_realized_gain_yuan','0'),'carry_in_entry_dates':candidate.get('carry_in_entry_dates',{}),
        'observed_holding_sessions':hold_sessions,'occupied_session_fraction':sum(v>0 for v in exposures)/len(exposures) if exposures else None,
        'profit_loss_ratio':profits/losses if losses else None,'profit_loss_ratio_limitation':'No finite loss denominator remains unknown; never infinite safety',
        'worst_session_nav_return':returns[0] if returns else None,'empirical_lower5_percent_nav_return':returns[int((len(returns)-1)*.05)] if returns else None,
        'tail_uncertainty':'Empirical descriptive tail; dependent small support cannot establish tail bound',
        'missing': candidate['missing'], 'realized_gain_yuan': gains[-1] if gains else None,
        'tail_evidence': 'Dependent continuous20-session intervals and maximum drawdown; insufficient support does not establish tail safety',
        'hard_failures': sorted(set(hard)), 'statistical_assumptions_verified': False}


def probability_checks(frozen, original):
    model = original['model']; base = original['model_artifact']['base_rate']; inputs = original['replay']['inputs']
    rows = []
    for forecast in original['replay']['forecasts']:
        outcome = inputs.get('counterfactuals', {}).get(forecast['forecast_id']) or {}
        rows.append({'canonical_key': fingerprint([forecast['instrument'], forecast['observation_cutoff'][:10], frozen['design']['event'],20]),
            'instrument': forecast['instrument'], 'observation_date': forecast['observation_cutoff'][:10],
            'probability': forecast['probability'], 'baseline_probability': base,
            'label': outcome.get('label'), 'mature': bool(outcome.get('scoreable') and outcome.get('maturity_date') and outcome['maturity_date'] <= original['replay']['through_date'])})
    result = probability_summary(rows, inputs['sessions'], float(frozen['policy']['probability_threshold']))
    date_scores = []
    for day in inputs['sessions']:
        group = {r['canonical_key']: (r['baseline_probability']-r['label'])**2-(r['probability']-r['label'])**2
            for r in rows if r['mature'] and r['label'] in (0,1) and r['observation_date']==day}
        date_scores.append({'date': day, 'scores': group or {'MISSING_CHECKPOINT':None}})
    # Unobserved checkpoint days cannot be silently converted into independent observations.
    result['dependent_brier_improvement_intervals'] = [paired_block_interval(date_scores, block_sessions=b) for b in [20,40]]
    selected_dates=[]
    for day in inputs['sessions']:
        scores={r['canonical_key']:(r['baseline_probability']-r['label'])**2-(r['probability']-r['label'])**2 for r in rows
            if r['mature'] and r['label'] in (0,1) and r['probability']>=float(frozen['policy']['probability_threshold']) and r['observation_date']==day}
        selected_dates.append({'date':day,'scores':scores or {'MISSING_SELECTED':None}})
    result['selected_dependent_loss_intervals']=[paired_block_interval(selected_dates,block_sessions=b) for b in [20,40]]
    for bin_result in result['reliability_bins']:
        scores=[]
        for day in inputs['sessions']:
            group={r['canonical_key']:r['probability']-r['label'] for r in rows if r['mature'] and r['label'] in (0,1)
                and min(4,int(r['probability']*5))==bin_result['bin'] and r['observation_date']==day}
            scores.append({'date':day,'scores':group or {'MISSING_BIN':None}})
        bin_result['dependent_probability_error_intervals']=[paired_block_interval(scores,block_sessions=b) for b in [20,40]]
    result['unobserved_checkpoint_sessions'] = sum(any(v is None for v in r['scores'].values()) for r in date_scores)
    result['independent_calibration_test'] = False
    result['simple_rule_comparison'] = {'state':'INCOMPLETE', 'reason':'MA5_MA20 is a decision signal, not a frozen calibrated probability model'}
    result['support_requirements'] = frozen['design']['statistics']
    result['fit_window_reused'] = 'CALIBRATION_DIAGNOSTIC_ONLY'
    result['model_run_id'] = model['model_run_id']
    return result


def g5_checks(frozen, replay):
    inputs, forecasts, through = replay['inputs'], replay['forecasts'], replay['through_date']
    sections = {'time_segments': [], 'cost_pressure': [], 'delays': [], 'parameter_neighborhood': [], 'migration_scope': []}
    def run(label, changed, facts=inputs, opportunities=forecasts, scenario=None):
        candidate = simulate(changed, facts, opportunities, through, execution_scenario=scenario)
        comparators = {n:simulate(changed,facts,[],through,n,execution_scenario=scenario) for n in ['CASH','START_HOLD','MA5_MA20']}
        details = continuous_checks(changed, candidate, comparators)
        return {'component': label, 'status': 'FAIL' if details['hard_failures'] else 'INCONCLUSIVE',
            'execution_events':candidate['events'],'execution_opportunities':candidate['opportunities'],'scenario':scenario,
            'method_fingerprint': validation_code(), 'input_fingerprint': fingerprint([changed,facts,opportunities,through,scenario]),
            'thresholds': changed['design']['primary_objective'], 'details': details,
            'result_fingerprint': fingerprint(details), 'limitations': ['Dependent support/assumptions remain unverified; no winner selection']}
    days = [d for d in inputs['sessions'] if d <= through]
    # Segments preserve the trajectory and original baseline. No reset/concatenation.
    for index in range(3):
        segment = days[len(days)*index//3:len(days)*(index+1)//3]
        full = simulate(frozen,inputs,forecasts,through)
        references = {n:simulate(frozen,inputs,[],through,n) for n in ['CASH','START_HOLD','MA5_MA20']}
        preceding=[r for r in full['curve'] if segment and r['date']<segment[0]]
        full['carry_in_realized_gain_yuan']=preceding[-1]['realized_gain_yuan'] if preceding else '0'
        full['holding_calendar']=[r['date'] for r in full['curve']]
        full['carry_in_entry_dates']={e['forecast_id']:e['date'] for e in full['events'] if segment and e['kind']=='BUY_FILL' and e['date']<segment[0]}
        full['events']=[e for e in full['events'] if e['date'] in segment]
        full['curve'] = [r for r in full['curve'] if r['date'] in segment]
        full['opportunities'] = [r for r in full['opportunities'] if r['observation_date'] in segment]
        for reference in references.values(): reference['curve'] = [r for r in reference['curve'] if r['date'] in segment]
        details = continuous_checks(frozen,full,references)
        sections['time_segments'].append({'component':str(index+1),'first_date':segment[0] if segment else None,'last_date':segment[-1] if segment else None,
            'status':'FAIL' if details['hard_failures'] else 'INCONCLUSIVE','details':details,'input_fingerprint':fingerprint(replay),
            'method_fingerprint':validation_code(),'thresholds':frozen['design']['primary_objective'],'result_fingerprint':fingerprint(details)})
    for field, key in [('commission_scenario_rate','commission_rates'),('slippage_each_side_rate','slippage_each_side_rates')]:
        for value in frozen['design']['g5'][key]:
            changed = copy.deepcopy(frozen); changed['design']['costs'][field] = value
            sections['cost_pressure'].append(run(field+'='+value,changed))
    for value in frozen['design']['g5']['parameter_neighborhood']['probability_threshold']:
        changed = copy.deepcopy(frozen); changed['policy']['probability_threshold'] = value
        sections['parameter_neighborhood'].append(run('probability_threshold='+value,changed))
    for field in ['penalty','lookback_sessions']:
        for value in frozen['design']['g5']['parameter_neighborhood'][field]:
            sections['parameter_neighborhood'].append({'component':field+'='+str(value),'status':'INCOMPLETE',
                'reason':'No preregistered frozen neighbor artifact; cannot tune after full freeze or bypass family fit budget',
                'method_fingerprint':validation_code(),'input_fingerprint':fingerprint(replay),'thresholds':frozen['design']['g5']['required'],
                'result_fingerprint':fingerprint({'missing_neighbor':field,'value':value})})
    for delay in frozen['design']['g5']['delays']:
        sections['delays'].append(run(delay,frozen,scenario={'delay':delay,'fill_fraction':'1'}))
    for fraction in ['0','0.50','1']:
        sections['delays'].append(run('NEXT_OPEN_FILL='+fraction,frozen,scenario={'delay':'NEXT_OPEN','fill_fraction':fraction}))
    sections['migration_scope'].append({'component':'REGISTERED_SCOPE','status':'INCONCLUSIVE','scope':frozen['scope'],
        'reason':'Conditional current-name history; no evidence for other securities/boards or regime migration',
        'input_fingerprint':fingerprint(replay),'method_fingerprint':validation_code(),'result_fingerprint':fingerprint(frozen['scope'])})
    return sections


def monitor_frozen(frozen, reference_bounds, observations, executions, results, elapsed_review_sessions, expiry=False):
    """Deterministic operational/maturity checks shared with ongoing monitoring.

    reference_bounds must be fixed from DEVELOPMENT; this function never fits on
    incoming observations, changes a historic verdict, or creates a PASS look.
    """
    latest=observations[-20:]; complete=outside=0
    for item in latest:
        if not item or any(k not in item or item[k] is None or not math.isfinite(float(item[k])) for k in reference_bounds): continue
        complete+=1
        outside+=any(float(item[k])<bounds[0] or float(item[k])>bounds[1] for k,bounds in reference_bounds.items())
    reasons=[]
    if complete/20 < .80: reasons.append('REQUIRED_FEATURE_COVERAGE_BELOW80_PERCENT')
    if outside/20 >= .20: reasons.append('FEATURE_OUTSIDE_DEV_REFERENCE_AT_LEAST20_PERCENT')
    execution=[]
    declared=frozen['design']['g5']
    for record in executions:
        failures=[]; missing=[]
        for field in ['delay','fill_fraction','commission_scenario_rate','slippage_each_side_rate','price_in_frozen_window']:
            if record.get(field) is None: missing.append(field)
        if record.get('delay') is not None and record['delay'] not in declared['delays']: failures.append('DELAY_OUTSIDE_FROZEN_SCENARIOS')
        if record.get('fill_fraction') is not None:
            try:
                fraction=Decimal(str(record['fill_fraction']))
                if not fraction.is_finite() or not 0<=fraction<=1:failures.append('FILL_FRACTION_INVALID_OR_OUTSIDE0_TO1')
            except InvalidOperation:failures.append('FILL_FRACTION_INVALID_OR_OUTSIDE0_TO1')
        for field,key in [('commission_scenario_rate','commission_rates'),('slippage_each_side_rate','slippage_each_side_rates')]:
            if record.get(field) is not None:
                try:
                    rate=Decimal(str(record[field]))
                    if not rate.is_finite() or rate<0 or rate>max(Decimal(v) for v in declared[key]):failures.append(field.upper()+'_OUTSIDE_FROZEN_BOUND')
                except InvalidOperation:failures.append(field.upper()+'_INVALID')
        if record.get('price_in_frozen_window') is False: failures.append('PRICE_OUTSIDE_FROZEN_WINDOW')
        execution.append({'restrict':bool(failures or missing),'failures':failures,'missing':missing,'statistical_pass_look':False,
            'fraction_basis':'0..1 bounded partial/missed/full execution; stress0/.50/1 do not claim measured user behavior'})
    mature=[r for r in results if r.get('mature') and r.get('label') in [0,1]]
    registered=elapsed_review_sessions==30 or expiry
    maturity={'review_status':'INCONCLUSIVE' if registered else 'NOT_AT_REGISTERED_CHECKPOINT',
        'mature_count':len(mature) if registered else None,'excluded_unmatured':len(results)-len(mature),
        'missing_count':sum(r.get('label') is None for r in results),'statistical_pass_look':False,
        'reason':'Mature monitoring only; qualified dependent uncertainty still required' if registered else 'Operational checks do not add an early statistical review'}
    return {'restrict':bool(reasons or any(r['restrict'] for r in execution)), 'drift_reasons':reasons,
        'complete_feature_observations':complete,'out_of_reference_observations':outside,'execution':execution,'maturity':maturity,
        'confirmation_pass_look':False,'historic_verdict_mutated':False}


def monitoring_method(frozen):
    """Literal sentinel examples prove semantics, never actual user/forward observations."""
    configuration = frozen['design']['formal_monitoring']
    reference={'fixed_feature':[0,1]}
    def drift(outside, available):
        observations=[{'fixed_feature':2}]*outside+[{'fixed_feature':.5}]*(available-outside)+[None]*(20-available)
        return monitor_frozen(frozen,reference,observations,[],[],0)
    examples = [{'input':{'outside':3,'available':20},'expected_restrict':False,'actual':drift(3,20)},
        {'input':{'outside':4,'available':20},'expected_restrict':True,'actual':drift(4,20)},
        {'input':{'outside':0,'available':15},'expected_restrict':True,'actual':drift(0,15)}]
    good={'delay':'NEXT_OPEN','fill_fraction':'0.50','commission_scenario_rate':'0.003','slippage_each_side_rate':'0.002','price_in_frozen_window':True}
    execution_cases=[]
    for record,expected in [(good,False),({**good,'delay':'TWO_MORE_SESSIONS_OPEN'},True),({**good,'commission_scenario_rate':'0.0031'},True),({**good,'price_in_frozen_window':False},True),({**good,'fill_fraction':None},True),({**good,'fill_fraction':.5},False),({**good,'fill_fraction':'0.60'},False),({**good,'commission_scenario_rate':'NaN'},True)]:
        actual=monitor_frozen(frozen,reference,[{'fixed_feature':.5}]*20,[record],[],0)['execution'][0]
        execution_cases.append({'input':record,'expected_restrict':expected,'actual':actual})
    results=[{'mature':True,'label':1},{'mature':False,'label':None}]
    maturity_cases=[]
    for sessions,expiry,status in [(29,False,'NOT_AT_REGISTERED_CHECKPOINT'),(30,False,'INCONCLUSIVE'),(0,True,'INCONCLUSIVE'),(31,False,'NOT_AT_REGISTERED_CHECKPOINT')]:
        actual=monitor_frozen(frozen,reference,[{'fixed_feature':.5}]*20,[],results,sessions,expiry)['maturity']
        maturity_cases.append({'input':{'elapsed_sessions':sessions,'expiry':expiry,'results':results},'expected_status':status,'actual':actual})
    checks=all(r['actual']['restrict']==r['expected_restrict'] for r in examples+execution_cases) and all(r['actual']['review_status']==r['expected_status'] for r in maturity_cases)
    return {'evidence_kind':'METHOD_CASE','configuration':configuration,'configuration_fingerprint':fingerprint(configuration),
        'method_fingerprint':validation_code(),'reference_basis':'1st/99th DEVELOPMENT feature percentiles only; worked bounds0..1 are fixed synthetic inputs',
        'reference_bounds':reference,'examples':examples,'execution_cases':execution_cases,'maturity_cases':maturity_cases,'checks_passed':checks,
        'mature_review':{'checkpoint':'REGISTERED30_SESSION_OR_EXPIRY','unmatured_scored':False,'insufficient':'INCONCLUSIVE','extra_pass_look':False},
        'checkpoint_contract':'elapsed_review_sessions is relative to the last registered review boundary, persisted/uniquely consumed by27;31 is a missed checkpoint gap, no new statistical review',
        'actual_user_execution_evidence':False,'actual_drift_evidence':False,'G7_evidence':False}


def evaluate(original):
    frozen=original['frozen']; state=original['state']; probability=probability_checks(frozen,original)
    economics=continuous_checks(frozen,state,state['comparators']); robustness=g5_checks(frozen,original['replay'])
    robust_hard=[group+'/'+str(item['component'])+'/'+reason for group,items in robustness.items() for item in items
        for reason in item.get('details',{}).get('hard_failures',[])]
    gates={'G1':gate('INCONCLUSIVE',['STRICT_HISTORICAL_PIT_AND_INDEPENDENCE_UNPROVEN'],{'evidence_kind':frozen['evidence_kind'],'data_use':frozen.get('data_use')}),
        'G2':gate('INCONCLUSIVE' if original['replay_matches'] else 'FAIL',['COMPLETE_DEPLOYMENT_ENGINEERING_EVIDENCE_NOT_BOUND'] if original['replay_matches'] else ['CONTINUOUS_REPLAY_MISMATCH'],{'input_integrity_checked':True,'continuous_replay_matches':original['replay_matches'],'replay_subcheck':'PASS' if original['replay_matches'] else 'FAIL','scope':'Current frozen continuous algorithm; account/permission/recovery acceptance remains deployment responsibility'}),
        'G3':gate('INCONCLUSIVE',['INDEPENDENT_CALIBRATION_UNVALIDATED','DEPENDENT_SUPPORT_OR_ASSUMPTIONS_UNVERIFIED'],probability),
        'G4':gate('FAIL' if economics['hard_failures'] else 'INCONCLUSIVE',economics['hard_failures'] or ['DEPENDENT_NAV_SUPPORT_OR_ASSUMPTIONS_UNVERIFIED'],economics),
        'G5':gate('FAIL' if robust_hard else 'INCONCLUSIVE', robust_hard or ['REQUIRED_COMPONENTS_OR_SUPPORT_INCOMPLETE'],robustness),
        'G6':gate('INCONCLUSIVE',['REAL_FORWARD_ENGINEERING_CONSISTENCY_NOT_RECORDED'],{'historical_replay_matches':original['replay_matches'],'method_proof_does_not_prove_actual_online':True}),
        'G7':gate('INCONCLUSIVE',['REAL_ARCHIVED_MATURE_FORWARD_RESULTS_MISSING'],{'mature_real_forward_count':0,'forward_started_at':None})}
    return {'gates':gates,'validation_verdict':combine(gates),'monitoring_method_validation':monitoring_method(frozen),
        'monitoring_dev_reference':development_reference(original['model_input']),
        'gate_combination_method':gate_combination_method(frozen),
        'incomplete_checks':[key+'/'+str(item['component']) for key,items in robustness.items() for item in items if item['status']=='INCOMPLETE'],
        'preliminary':True,'statistical_pass':False}


def development_reference(model_input):
    examples=model_input['examples']['DEVELOPMENT'];bounds={}
    for feature in examples[0]['feature_snapshot']['features'] if examples else []:
        values=sorted(float(r['feature_snapshot']['features'][feature]) for r in examples)
        def quantile(p):
            offset=(len(values)-1)*p;index=int(offset)
            return values[index]+(values[min(index+1,len(values)-1)]-values[index])*(offset-index)
        bounds[feature]=[quantile(.01),quantile(.99)]
    value={'source':'FROZEN_DEVELOPMENT_ONLY','method':'Linear empirical1st/99th percentile; no incoming-data refit',
        'bounds':bounds,'observation_dates':[r['observation_date'] for r in examples],
        'input_fingerprint':fingerprint(examples),'method_fingerprint':validation_code()}
    return {**value,'reference_fingerprint':fingerprint(value)}


class AutomaticValidation:
    def __init__(self,shadow):
        self.shadow=shadow;self.registry=shadow.registry;self.ledger=shadow.ledger;self.evidence=shadow.evidence
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS research_validations(id TEXT PRIMARY KEY,freeze_id TEXT NOT NULL,value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS research_validation_attempts(id TEXT PRIMARY KEY,freeze_id TEXT NOT NULL,value TEXT NOT NULL)')
            for row in db.execute('SELECT id,value FROM research_validation_attempts'):
                attempt=json.loads(row[1])
                if attempt['status']=='RUNNING' and not owner_alive(attempt):
                    attempt.update(status='INTERRUPTED',finished_at=now(),reason='Original validation host stopped; inputs and attempt retained')
                    db.execute('UPDATE research_validation_attempts SET value=? WHERE id=?',(encode(attempt),row[0]))

    def attempts(self,freeze_id):
        self.shadow.get(freeze_id)
        with self.ledger.connection() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT value FROM research_validation_attempts WHERE freeze_id=? ORDER BY rowid',(freeze_id,))]

    def list(self,freeze_id):
        self.shadow.get(freeze_id)
        with self.ledger.connection() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT value FROM research_validations WHERE freeze_id=? ORDER BY rowid',(freeze_id,))]

    def get(self,identifier):
        with self.ledger.connection() as db: row=db.execute('SELECT value FROM research_validations WHERE id=?',(identifier,)).fetchone()
        if not row: raise HTTPException(404,'验证记录不存在')
        value=json.loads(row[0]); archived=self.shadow.checked_archive(value['manifest_archive'])
        if archived != {k:v for k,v in value.items() if k!='manifest_archive'}: raise HTTPException(409,'VALIDATION_MANIFEST_BINDING_MISMATCH')
        return value

    def create(self,freeze_id,command):
        frozen=self.shadow.get(freeze_id)
        if command.expected_complete_protocol_fingerprint != frozen['complete_protocol_fingerprint']:
            raise HTTPException(409,'COMPLETE_PROTOCOL_FINGERPRINT_MISMATCH')
        if frozen['fingerprints']['shadow_code'] != shadow_code() or frozen['fingerprints']['model_code'] != code_fingerprint():
            raise HTTPException(409,'FROZEN_CODE_CHANGED_SUCCESSOR_REQUIRED')
        if command.purpose=='CONFIRMATORY':
            admission=self.confirmation_admission(frozen)
            event=self.registry.event(frozen['protocol_id'],'CONFIRMATORY_VALIDATION_REFUSED',freeze_id=freeze_id,
                admission=admission,gaps=admission['gaps'],sealed_read=False,confirmatory_pass_look=False)
            raise HTTPException(409,{'code':'CONFIRMATORY_EVIDENCE_NOT_ADMITTED',**admission,'audit_event_id':event['event_id'],'sealed_read':False})
        state=self.shadow.current(freeze_id)
        if not state['revision']: raise HTTPException(409,'连续历史尚无输入，先归档机会并推进；不读取SEALED补缺')
        replay=self.shadow.checked_archive(state['input_archive']); model=self.shadow.models.get(frozen['model_run_id'])
        for field in ['calibrator_artifact','input_archive','freeze_manifest']:
            self.shadow.checked_archive(model[field])
        original={'frozen':frozen,'state':state,'replay':replay,'model':model,'model_artifact':self.shadow.checked_archive(model['model_artifact']),
            'model_input':self.shadow.checked_archive(model['input_archive']),
            'replay_matches':self.shadow.replay(freeze_id)['matches_original'],'validation_code_fingerprint':validation_code()}
        input_archive=self.evidence.archive(encode(original).encode(),'AUTOMATIC_VALIDATION_INPUT',research_namespace='HISTORICAL')
        identifier=str(uuid4())
        attempt={'validation_attempt_id':identifier,'freeze_id':freeze_id,'status':'RUNNING','started_at':now(),
            'host_owner':self.registry.owner,'command':command.model_dump(),'input_archive':input_archive,'confirmation_pass_look':False}
        with self.ledger.connection() as db:
            db.execute('INSERT INTO research_validation_attempts VALUES(?,?,?)',(identifier,freeze_id,encode(attempt)))
        try:result=evaluate(original)
        except Exception as error:
            attempt.update(status='FAILED',finished_at=now(),reason=type(error).__name__)
            with self.ledger.connection() as db:db.execute('UPDATE research_validation_attempts SET value=? WHERE id=?',(encode(attempt),identifier))
            raise
        attempt.update(status='SUCCEEDED',finished_at=now(),result_fingerprint=fingerprint(result))
        value={'validation_id':identifier,'freeze_id':freeze_id,'protocol_id':frozen['protocol_id'],'recorded_at':now(),'basis':command.basis,
            'validation_attempt':attempt,'validation_attempt_manifest':[attempt if a['validation_attempt_id']==identifier else a for a in self.attempts(freeze_id)],
            'purpose':command.purpose,'namespace':'HISTORICAL','evidence_kind':frozen['evidence_kind'],'complete_protocol_fingerprint':frozen['complete_protocol_fingerprint'],
            'candidate_fingerprints':frozen['fingerprints'],'primary_objective':frozen['design']['primary_objective'],'baseline':frozen['baseline'],
            'comparators':frozen['design']['baselines'],'windows':frozen['design']['windows'],'attempt_manifest':self.registry.attempt_manifest(frozen['protocol_id']),
            'statistics':frozen['design']['statistics'],'stopping':frozen['design']['stopping'],'costs':frozen['design']['costs'],'execution':frozen['design']['execution'],
            'scope':frozen['scope'],'evidence_cutoff':state['through_date'],'review_due_at':None,'review_due_reason':'Formal qualification expiry not registered',
            'limitations':frozen['validation_gaps'],'unresolved_items':['Real confirmatory admission','Independent probability validity','G5 missing fixed neighbors','Real G6/G7','Technical review'],
            'experiment_status':'RUNNING_DIAGNOSTIC','review_status':'PENDING_TECHNICAL_REVIEW','capability_status':'NOT_GRANTED','system_usable':False,
            'confirmation_pass_look':False,'sealed_read':False,'input_archive':input_archive,'validation_code_fingerprint':validation_code(),**result}
        value['result_fingerprint']=fingerprint(result)
        value['manifest_archive']=self.evidence.archive(encode(value).encode(),'VALIDATION_MANIFEST',research_namespace='HISTORICAL')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('UPDATE research_validation_attempts SET value=? WHERE id=?',(encode(attempt),identifier))
            db.execute('INSERT INTO research_validations VALUES(?,?,?)',(value['validation_id'],freeze_id,encode(value)))
            self.registry.event(frozen['protocol_id'],'AUTOMATIC_VALIDATION_RECORDED',db=db,validation_id=value['validation_id'],
                input_sha256=input_archive['sha256'],output_sha256=value['manifest_archive']['sha256'],validation_verdict=value['validation_verdict'],confirmatory_pass_look=False,sealed_read=False)
            db.commit()
        return value

    def confirmation_admission(self,frozen):
        """Inspect host metadata before any protected test outcomes are consumed.

        This concrete candidate has no admitted independent statistical/forward
        package. Client claims and engine test success cannot supply those facts.
        Later validation delivery must link real independently admitted evidence.
        """
        protocol=self.registry.get(frozen['protocol_id']);dataset=self.registry.dataset(protocol['dataset_id'])
        attempts=self.registry.attempt_manifest(frozen['protocol_id'])
        audit=[e for pid in attempts['family_protocol_ids'] for e in self.registry.audit(pid)]
        exposures=[e['event_id'] for e in audit if e['action'] in {'SEALED_INPUT_ACCESSED','ORIGINAL_ARCHIVE_EXPOSED'}]
        gaps=[]
        if dataset['source_evidence_kind']!='REAL_ACQUISITION':gaps.append('METHOD_OR_PUBLIC_SOURCE_NOT_REAL_CONFIRMATION')
        if dataset.get('data_use')!='STRICT_HISTORICAL_AS_OF':gaps.append('STRICT_HISTORICAL_PIT_NOT_PROVEN')
        if protocol['sealed_independence']!='VERIFIED_INDEPENDENT_UNUSED' or exposures:gaps.append('SEALED_INDEPENDENCE_UNPROVEN_OR_EXPOSED')
        if not frozen['statistical_methods']['real_sampling_assumptions_verified']:gaps.append('STATISTICAL_ASSUMPTIONS_NOT_VERIFIED')
        if not protocol.get('forward_started_at'):gaps.append('REAL_FORWARD_NOT_STARTED')
        if protocol.get('validation_verdict') is not None:gaps.append('FINAL_CONFIRMATORY_LOOK_ALREADY_USED')
        # Ordinary registry checkpoints do not admit early/final statistical PASS.
        gaps.append('INDEPENDENT_FINAL_VALIDATION_PACKAGE_NOT_ADMITTED')
        if any(a['status']=='RUNNING' for a in attempts['attempts']):gaps.append('FAMILY_ATTEMPT_STILL_RUNNING')
        return {'admitted':False,'gaps':gaps,'attempt_manifest':attempts,'prior_sealed_exposure_event_ids':exposures,
            'protocol_fingerprint':frozen['complete_protocol_fingerprint'],'candidate_fingerprints':frozen['fingerprints'],
            'sealed_metadata':dataset['partitions'].get('SEALED'),'input_content_consumed':False,'confirmation_pass_look':False}

    def replay(self,identifier):
        value=self.get(identifier);original=self.shadow.checked_archive(value['input_archive'])
        if value['validation_code_fingerprint'] != validation_code() or original['frozen']['fingerprints']['shadow_code'] != shadow_code():
            raise HTTPException(409,'VALIDATION_CODE_CHANGED_SUCCESSOR_REQUIRED')
        result=evaluate(original)
        return {'validation_id':identifier,'matches_original':fingerprint(result)==value['result_fingerprint'],'network_calls':0,
            'input_sha256':value['input_archive']['sha256'],'result_fingerprint':fingerprint(result),'confirmation_pass_look':False}
