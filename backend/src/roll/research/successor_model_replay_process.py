"""Execute archived model probabilities; private METHOD contract preserves decimals."""
from decimal import Decimal
import json,math,socket,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from roll.research.successor_shadow import simulate,source_fingerprint,usable
from roll.research.shadow import fingerprint
from roll.research.statistics import continuous_summary,fingerprint as statistics_fingerprint


def evaluate(payload):
    def denied(*args,**kwargs):raise RuntimeError('MODEL_REPLAY_NETWORK_DISABLED')
    socket.socket.connect=denied;socket.create_connection=denied;socket.getaddrinfo=denied
    frozen=payload['frozen'];model_input=payload['model_input'];calendar=payload['calendar'];method=payload['method'];predictions=payload['predictions'];previous=payload['predecessor']
    if frozen['source_fingerprint']!=source_fingerprint() or payload['statistics_code']!=statistics_fingerprint():raise ValueError('MODEL_REPLAY_ENGINE_CHANGED')
    if frozen['baseline']['positions']:raise ValueError('MODEL_REPLAY_REQUIRES_EMPTY_INITIAL_POSITIONS_NO_ASSUMED_LIQUIDATION')
    if previous!=calendar['frozen'] or model_input['evidence_kind']!='METHOD_CASE' or previous['evidence_kind']!='METHOD_CASE':raise ValueError('MODEL_REPLAY_ONLY_BOUND_METHOD_INPUT')
    if set(model_input['parts'])-{'DEVELOPMENT','CALIBRATION'}:raise ValueError('MODEL_REPLAY_NO_SEALED_INPUT')
    part=model_input['parts']['CALIBRATION'];window=part['metadata'];scope=previous['scope']['instruments']
    if calendar['inputs']['window']!=window or calendar['inputs']['facts']!=part['facts']:raise ValueError('MODEL_REPLAY_CALENDAR_FACT_BINDING_MISMATCH')
    if len(scope)!=1 or set(frozen['rules'])!=set(scope):raise ValueError('MODEL_REPLAY_SINGLE_FROZEN_SCOPE_REQUIRED')
    if any(window[k]!=previous['design']['windows']['CALIBRATION'][k] for k in ('first_date','last_date')):raise ValueError('MODEL_REPLAY_WINDOW_CHANGED')
    sessions=calendar['inputs']['sessions']
    if sessions!=sorted(set(sessions)) or any(not window['first_date']<=d<=window['last_date'] for d in sessions) or len(sessions)!=window['rows'] or not 1<=len(sessions)<=method['maximum_sessions']:raise ValueError('MODEL_REPLAY_REQUIRES_ENTIRE_SAVED_CALENDAR')
    if calendar['through_date']<window['last_date'] or sessions[0]!=window['first_date'] or sessions[-1]!=window['last_date']:raise ValueError('MODEL_REPLAY_CALENDAR_NOT_COMPLETE')
    symbol=scope[0];facts={};by_date={};rejections=[]
    for fact in part['facts']:
        key=(fact['instrument'],fact['trade_date'])
        if key in facts:raise ValueError('MODEL_REPLAY_DUPLICATE_FACT')
        facts[key]=fact
    for row in predictions:
        day=row['observation_date'];p=float(row['probability'])
        if day not in sessions or day in by_date or not math.isfinite(p) or not 0<=p<=1 or row['model_artifact_sha256']!=frozen['model_artifact_fingerprints']['model'] or row['prediction_phase']!='AFTER_CALIBRATOR_FIT_IN_SAMPLE':raise ValueError('MODEL_REPLAY_PREDICTION_IDENTITY_MISMATCH')
        by_date[day]=row
    start=frozen['baseline']['starting_session'];frames=[];curve=[{'session':start,'trade_date':None,'nav_yuan':frozen['baseline']['cash_yuan']}];exposures=[];states=[]
    first_examples=[r for r in model_input['examples']['CALIBRATION'] if r['observation_date']==sessions[0]]
    context_previous=first_examples[0]['feature_snapshot']['input_trade_dates'][-2] if len(first_examples)==1 else None
    def trusted(f):
        if not f:return False
        try:
            if any(not Decimal(str(f.get(k))).is_finite() or Decimal(str(f[k]))<=0 for k in ('open','high','low','close')):return False
        except (ValueError,ArithmeticError,TypeError):return False
        ev=f.get('execution_evidence',{})
        return f.get('evidence_kind')=='METHOD_CASE' and f.get('adjustment')=='RAW' and f.get('volume_unit')=='SHARE' and not f.get('errors') and f.get('completion_state')=='COMPLETE_REPORTED_HISTORICAL' and ev.get('state')=='CONFIRMED_NORMAL' and ev.get('company_actions')=='CONFIRMED_NONE' and ev.get('rule_scope')=='METHOD_CASE_ONLY'
    for index,day in enumerate(sessions,1):
        fact=facts.get((symbol,day));prior=facts.get((symbol,sessions[index-2] if index>1 else context_previous));known=trusted(fact) and trusted(prior)
        volume=None
        try:
            volume=Decimal(str(fact['volume_shares'])) if fact else None
            if volume is None or not volume.is_finite() or volume<0 or volume!=volume.to_integral_value():known=False
            if fact and any(not Decimal(str(fact.get(k))).is_finite() or Decimal(str(fact[k]))<=0 for k in ('open','high','low','close')):known=False
        except (ValueError,ArithmeticError,TypeError):known=False
        bar={'instrument':symbol,**{k+'_yuan':str(fact[k]) if fact and fact.get(k) is not None else None for k in ('open','high','low','close')},
            'reference_close_yuan':str(prior['close']) if trusted(prior) and prior.get('close') is not None else None,
            'volume_shares':int(volume) if volume is not None and volume.is_finite() and volume>=0 and volume==volume.to_integral_value() else None,
            'completion':'COMPLETE' if known else 'UNKNOWN','market_state':'NORMAL' if known else 'UNKNOWN','company_actions':'NONE' if known else 'UNKNOWN'}
        if not known or not usable(bar):
            bar.update(completion='UNKNOWN',market_state='UNKNOWN',company_actions='UNKNOWN');rejections.append({'trade_date':day,'session':start+index,'reason':'MISSING_OR_UNKNOWN_OR_INVALID_OR_PREVIOUS_FACT'})
        prediction=by_date.get(day);signals=[] if prediction is None else [{'instrument':symbol,'forecast_id':'SAVED_CAL:'+payload['prediction_archive']['sha256']+':'+day,'probability':str(prediction['probability'])}]
        frames.append({'session':start+index,'trade_date':day,'calendar_previous_session':start+index-1,'source_snapshot_id':'SAVED_CAL_METHOD:'+payload['model_input_archive']['sha256']+':'+day,'evidence_kind':'METHOD_CASE','bars':[bar],'signals':signals})
        state=simulate(frozen,frames);states.append(state)
        nav=Decimal(state['cash_yuan'])+sum((Decimal(bar['close_yuan'])*p['quantity'] for p in state['positions']),Decimal(0)) if not state['positions'] or usable(bar) else None
        curve.append({'session':start+index,'trade_date':day,'nav_yuan':str(nav) if nav is not None else None})
        if nav is not None and nav>0:exposures.append((nav-Decimal(state['cash_yuan']))/nav)
    peak=Decimal(0);drawdown=Decimal(0)
    for point in curve:
        if point['nav_yuan'] is None:continue
        nav=Decimal(point['nav_yuan']);peak=max(peak,nav)
        if peak>0:drawdown=max(drawdown,1-nav/peak)
    risk=previous['design']['primary_objective']['risk_constraints'];failures=[]
    if drawdown>Decimal(risk['maximum_drawdown']):failures.append('MAXIMUM_DRAWDOWN_EXCEEDED')
    if exposures and max(exposures)>Decimal(risk['maximum_simulated_gross_exposure'])+Decimal('1e-12'):failures.append('MAXIMUM_EXPOSURE_EXCEEDED')
    return {'frames':frames,'input_fingerprint':fingerprint(frames),'curve':curve,'economics':continuous_summary(curve),'result':states[-1],
        'calendar_sessions':sessions,'calendar_session_count':len(sessions),'prediction_count':len(predictions),'adapter_rejections':rejections,
        'observed_drawdown_lower_bound':str(drawdown),'maximum_observed_gross_exposure_fraction':str(max(exposures)) if exposures else None,'hard_failures':failures,
        'validation_verdict':'FAIL' if failures else 'INCONCLUSIVE','source_scope':'SAVED_CALIBRATION_FIT_IN_SAMPLE_NOT_INDEPENDENT',
        'execution_prediction_identity_aligned':True,'real_input_admitted':False,'independent_validation':False,'neighbor_stress_admitted':False,
        'new_prediction_calls':0,'new_fit_calls':0,'sealed_reads':0,'network_calls':0,'statistical_pass':False,'real_forward_started_at':None}


if __name__=='__main__':
    payload=json.loads(sys.stdin.read());Path(payload['output_file']).write_text(json.dumps(evaluate(payload),ensure_ascii=False,allow_nan=False),encoding='utf-8')
