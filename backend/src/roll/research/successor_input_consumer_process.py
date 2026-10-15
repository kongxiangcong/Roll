"""Compute frozen source features/prediction and independent successor state."""
import json,math,socket,sys
from decimal import Decimal
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from roll.research.models import features,predict,code_fingerprint
from roll.research.forward import forward_features
from roll.research.successor_shadow import simulate,source_fingerprint,usable
from roll.research.shadow import fingerprint


def evaluate(payload):
    def denied(*args,**kwargs):raise RuntimeError('INPUT_CONSUMER_NETWORK_DISABLED')
    socket.socket.connect=denied;socket.create_connection=denied;socket.getaddrinfo=denied
    frozen=payload['frozen'];run=payload['model'];rows=payload['rows'];method=payload['method'];day=payload['day'];method_case=payload['purpose']=='METHOD_VALIDATION'
    if frozen['source_fingerprint']!=source_fingerprint() or run['code_fingerprint']!=code_fingerprint():raise ValueError('INPUT_CONSUMER_FROZEN_CODE_CHANGED')
    if frozen['baseline']['positions']:raise ValueError('INPUT_CONSUMER_EMPTY_BASELINE_REQUIRED')
    gaps=list(payload['gaps']);snapshot=None;forecast=None;prediction_calls=0;frames=list(payload['previous_frames'])
    if not gaps:
        try:
            if method_case:snapshot=features(rows,day,True,payload['cutoff'])
            else:
                from datetime import datetime
                snapshot=forward_features(rows,day,datetime.fromisoformat(payload['cutoff']),run['fit']['feature_names'],run.get('data_use')=='RECONSTRUCTED_RESEARCH')
            if snapshot['input_trade_dates']!=payload['feature_calendar']:raise ValueError('INPUT_CONSUMER_CONTIGUOUS_FEATURE_CALENDAR_REQUIRED')
        except (ValueError,KeyError,ArithmeticError) as error:gaps.append(str(error));snapshot=None
    if not gaps:
        symbol=payload['symbol'];matching=[r for r in rows if r['instrument']==symbol and r['trade_date']==day]
        if len(matching)!=1:raise ValueError('INPUT_CONSUMER_CURRENT_BAR_NOT_UNIQUE')
        row=matching[0];earlier=[r for r in rows if r['instrument']==symbol and r['trade_date']==snapshot['input_trade_dates'][-2]]
        if len(earlier)!=1:raise ValueError('INPUT_CONSUMER_PREVIOUS_BAR_NOT_UNIQUE')
        ev=row.get('execution_evidence',{});rule=frozen['rules'][symbol]
        if ev.get('state')!='CONFIRMED_NORMAL' or ev.get('company_actions')!='CONFIRMED_NONE':gaps.append('INPUT_CONSUMER_EXECUTION_STATUS_ACTION_AUTHORITY_UNKNOWN')
        for key in ('price_tick_yuan','normal_price_limit_percent','buy_minimum','buy_increment'):
            if key in ev and Decimal(str(ev[key]))!=Decimal(str(rule[key])):gaps.append('INPUT_CONSUMER_EXECUTION_RULE_MISMATCH:'+key)
        try:
            volume=Decimal(row['volume_shares'])
            if not volume.is_finite() or volume<0 or volume!=volume.to_integral_value():raise ValueError()
            bar={'instrument':symbol,**{k+'_yuan':str(row[k]) for k in ('open','high','low','close')},'reference_close_yuan':str(earlier[0]['close']),
                'volume_shares':int(volume),'completion':'COMPLETE','market_state':'NORMAL','company_actions':'NONE'}
            if not usable(bar):raise ValueError()
        except (ValueError,ArithmeticError,KeyError,TypeError):gaps.append('INPUT_CONSUMER_EXECUTION_BAR_INVALID')
        if gaps:forecast=None
        else:
            prediction=predict(payload['model_artifact']['fit'],snapshot,payload['calibrator_artifact']['intercept_shift'])
            if any(not math.isfinite(float(v)) for v in prediction.values()) or not 0<=prediction['probability']<=1:raise ValueError('INPUT_CONSUMER_INVALID_FROZEN_PREDICTION')
            forecast={'forecast_id':fingerprint([frozen['successor_freeze_id'],payload['purpose'],payload['source_identity'],day]),'model_run_id':run['model_run_id'],
                'observation_date':day,'feature_snapshot':snapshot,**prediction,'artifact_fingerprints':run['artifact_fingerprints'],'source_identity':payload['source_identity'],
                'evidence_kind':'METHOD_CASE' if method_case else 'REAL_ACQUISITION','independent_validation':False,'actual_forward_prediction':False}
            prediction_calls=1
            for date in payload['advance_calendar']:
                session=frozen['baseline']['starting_session']+len(frames)+1;current=date==day
                frames.append({'session':session,'trade_date':date,'calendar_previous_session':session-1,'evidence_kind':'METHOD_CASE' if method_case else 'REAL_ACQUISITION',
                    'source_snapshot_id':payload['source_identity']+':'+date,'bars':[bar] if current else [],
                    'signals':[{'instrument':symbol,'forecast_id':forecast['forecast_id'],'probability':str(forecast['probability'])}] if current else []})
    if len(frames)>method['maximum_sessions']:raise ValueError('INPUT_CONSUMER_SESSION_LIMIT')
    result=simulate(frozen,frames)
    return {'status':'INPUT_CONSUMED' if forecast else 'REFUSED','gaps':sorted(set(gaps)),'forecast':forecast,'frames':frames,'result':result,
        'day':day,'input_fingerprint':fingerprint(frames),'new_prediction_calls':prediction_calls,'new_fit_calls':0,'sealed_reads':0,'network_calls':0,
        'real_input_consumed':bool(forecast and not method_case),'evidence_kind':'METHOD_CASE' if method_case else 'REAL_ACQUISITION',
        'complete_experiment_frozen':False,'system_usable':False,'capability':'NOT_GRANTED','statistical_pass':False,'real_forward_started_at':None}


if __name__=='__main__':
    payload=json.loads(sys.stdin.read());Path(payload['output_file']).write_text(json.dumps(evaluate(payload),ensure_ascii=False,allow_nan=False),encoding='utf-8')
