"""Paired fixed-scenario METHOD controls, preserving original timing contracts."""
import copy,hashlib,json,socket,sys
from decimal import Decimal
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from roll.research.shadow import simulate,shadow_code,fingerprint
from roll.research.successor_shadow import usable,source_fingerprint
from roll.research.statistics import continuous_summary,fingerprint as statistics_fingerprint


def evaluate(payload):
    def denied(*args,**kwargs):raise RuntimeError('SUCCESSOR_JOINT_NETWORK_DISABLED')
    socket.socket.connect=denied;socket.create_connection=denied;socket.getaddrinfo=denied
    source=payload['source'];registered=payload['controls'];entries=payload['entries'];original=payload['control_input'];inputs=original['input'];frozen=inputs['frozen'];slots=registered['declared_sessions']
    if shadow_code()!=inputs['inherited_shadow_code'] or frozen['source_fingerprint']!=source_fingerprint():raise ValueError('JOINT_INHERITED_ENGINE_CHANGED')
    if inputs['protocol']['statistical_methods']['code_fingerprint']!=statistics_fingerprint():raise ValueError('JOINT_STATISTICS_CHANGED')
    if len(slots)>payload['method']['maximum_declared_session_span']+1:raise ValueError('JOINT_DECLARED_SPAN_LIMIT')
    if entries['input_prefix_fingerprint']!=source['input_prefix_fingerprint']:raise ValueError('JOINT_ENTRY_PREFIX_MISMATCH')
    commands=[frame['command'] for _,_,frame in inputs['rows']]
    if fingerprint(commands)!=source['input_prefix_fingerprint']:raise ValueError('JOINT_INPUT_PREFIX_MISMATCH')
    # Reconstruct the exact archived registered-control adapter, without
    # changing bars, session indices, valuation fields or original algorithms.
    first=slots[0];labels={session:f'METHOD_SLOT_{session:020d}' for session in slots};reverse={value:key for key,value in labels.items()};facts=[];previous={};rejections=[]
    for command in commands:
        session=command['session']
        for bar in command['bars']:
            errors=[] if usable(bar) else ['UNTRUSTED_METHOD_INPUT_UNKNOWN']
            prior=previous.get(bar['instrument'])
            if session>first+1 and (not prior or prior[0]!=session-1 or prior[1] is None or not prior[2]):errors.append('METHOD_PREVIOUS_CLOSE_OR_STATUS_UNKNOWN')
            if prior and prior[0]==session-1 and prior[1] is not None and bar['reference_close_yuan'] is not None and Decimal(bar['reference_close_yuan'])!=Decimal(prior[1]):errors.append('METHOD_REFERENCE_CLOSE_DISAGREES_WITH_PREVIOUS_CLOSE')
            facts.append({'trade_date':labels[session],'instrument':bar['instrument'],
                **{key:bar[key+'_yuan'] for key in ('open','high','low','close')},'volume_shares':bar['volume_shares'],
                'errors':errors,'completion_state':'COMPLETE_REPORTED_HISTORICAL' if not errors else 'UNKNOWN',
                'execution_evidence':{'state':'CONFIRMED_NORMAL' if not errors else 'UNKNOWN','company_actions':'CONFIRMED_NONE' if not errors else 'UNKNOWN'}})
            previous[bar['instrument']]=(session,bar['close_yuan'],usable(bar))
            if errors:rejections.append({'session':session,'instrument':bar['instrument'],'reasons':errors})
    if fingerprint(facts)!=registered['adapter_facts_fingerprint'] or reverse!=registered['label_to_method_session'] or rejections!=registered['adapter_rejections']:raise ValueError('JOINT_ADAPTER_NOT_IDENTICAL')
    execution={'sessions':[labels[s] for s in slots[1:]],'facts':facts,'cash_events':[],'statutory':{},'counterfactuals':{}}
    scenarios=[];risk=source['risk_constraints']
    cases=[('ENTRY:'+s['scenario_id'],s,None,{'delay':s['delay'],'fill_fraction':s['fill_fraction']}) for s in entries['scenarios']]
    cases += [('COST:'+s['component'],s,s['costs'],None) for s in source['scenarios']]
    if len(cases)!=12:raise ValueError('JOINT_FIXED_SCENARIO_COUNT_MISMATCH')
    for identifier,candidate,costs,scenario in cases:
        contract=copy.deepcopy(registered['derived_execution_contract'])
        if costs is not None:contract['design']['costs']=costs
        points={p['session']:p['nav_yuan'] for p in candidate['curve']}
        curve=[{'session':s,'nav_yuan':points.get(s)} for s in slots];summary=continuous_summary(curve);controls={}
        for name in ('CASH','START_HOLD','MA5_MA20'):
            raw=simulate(contract,execution,[],labels[slots[-1]],name,execution_scenario=scenario)
            local=[{'session':first,'nav_yuan':frozen['baseline']['cash_yuan']}]+[{'session':reverse[r['date']],'nav_yuan':r['nav_yuan'],'gross_exposure_fraction':r['gross_exposure_fraction']} for r in raw['curve']]
            economics=continuous_summary(local)
            eligibility=['NO_PRERUN_MA_CONTEXT_FOR_ORIGINAL_FULL_WINDOW'] if name=='MA5_MA20' else []
            if raw['missing'] or rejections:eligibility.append('MISSING_OR_UNKNOWN_DAILY_INPUT')
            refused=[r for r in raw['opportunities'] if r['reasons']]
            if refused:eligibility.append('REFUSED_OR_UNSCORABLE_REGISTERED_OPPORTUNITY')
            observed=[Decimal(str(p['gross_exposure_fraction'])) for p in local if p.get('gross_exposure_fraction') is not None]
            if observed and max(observed)>Decimal(risk['maximum_simulated_gross_exposure'])+Decimal('1e-12'):eligibility.append('CONTROL_EXPOSURE_BOUND_EXCEEDED')
            if economics['maximum_drawdown'] is not None and Decimal(str(economics['maximum_drawdown']))>Decimal(risk['maximum_drawdown']):eligibility.append('CONTROL_DRAWDOWN_BOUND_EXCEEDED')
            fees=Decimal(0)
            for event in raw['events']:
                if event['kind'] not in {'BUY_FILL','SELL_FILL'}:continue
                gross=Decimal(event['price_yuan'])*Decimal(event['quantity']);delta=Decimal(event['cash_delta_yuan'])
                fees+=-delta-gross if event['kind']=='BUY_FILL' else gross-delta
            controls[name]={'curve':local,'economics':economics,'events':raw['events'],'fees_yuan':str(fees),
                'eligibility_gaps':eligibility,'input_gaps':raw['missing'],'opportunities':raw['opportunities'],
                'interval_return_difference':summary['net_return']-economics['net_return'] if not eligibility and summary['net_return'] is not None and economics['net_return'] is not None else None,
                'risk_matched_decision':'NOT_ADMITTED','engine_result_fingerprint':fingerprint(raw)}
        scenarios.append({'scenario_id':identifier,'candidate':{'curve':curve,'economics':summary,'fees_yuan':candidate['fees_yuan'],'hard_failures':candidate['hard_failures']},
            'controls':controls,'costs':contract['design']['costs'],'execution_scenario':scenario,'risk_matched':False,
            'status':'FAIL' if candidate['hard_failures'] else 'INCONCLUSIVE'})
    return {'scenarios':scenarios,'G5_status':'FAIL' if source['G5_status']=='FAIL' or entries['G5_status']=='FAIL' else 'INCONCLUSIVE',
        'adapter_facts_fingerprint':fingerprint(facts),'input_prefix_fingerprint':source['input_prefix_fingerprint'],
        'timing_contrast':registered['timing_contrast'],'risk_matched_qualification':False,'statistical_pass':False,
        'limitations':['METHOD_SLOT aliases are not real trading dates or authority','Original comparator timing differs from candidate lot timing','MA missing prerun context never cropped','No independent paired intervals','Early SELL and horizon exits are not stressed','Cost scenarios lack saved full exposure history'],
        'network_calls':0,'new_fit_calls':0,'sealed_reads':0}


if __name__=='__main__':
    payload=json.loads(sys.stdin.read());result=evaluate(payload);body=json.dumps(result,ensure_ascii=False,allow_nan=False).encode()
    if len(body)>payload['method']['maximum_output_bytes']:raise ValueError('JOINT_OUTPUT_SIZE_LIMIT')
    Path(payload['output_file']).write_bytes(body)
