"""Run original registered control algorithms on explicit METHOD slot aliases."""
import hashlib,json
from pathlib import Path
import socket,sys
from decimal import Decimal
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from roll.research.shadow import simulate,shadow_code,fingerprint
from roll.research.successor_shadow import simulate as successor_simulate,source_fingerprint,usable
from roll.research.successor_cash import derive as cash_control
from roll.research.statistics import continuous_summary


def evaluate(payload):
    def denied(*args,**kwargs):raise RuntimeError('REGISTERED_CONTROLS_NETWORK_DISABLED')
    socket.socket.connect=denied;socket.create_connection=denied;socket.getaddrinfo=denied
    source=payload['source'];method=payload['method'];inputs=payload['input'];frozen=inputs['frozen'];legacy=payload['predecessor']
    if shadow_code()!=inputs['inherited_shadow_code'] or legacy['fingerprints']['shadow_code']!=shadow_code() or frozen['source_fingerprint']!=source_fingerprint():raise ValueError('ORIGINAL_CONTROL_ENGINE_CHANGED')
    adapter=Path(__file__).with_name('successor_cash.py')
    if hashlib.sha256(adapter.read_bytes().replace(b'\r\n',b'\n')).hexdigest()!=payload['cash_adapter_sha256']:raise ValueError('CASH_ADAPTER_CHANGED')
    commands=[frame['command'] for _,_,frame in inputs['rows']]
    if fingerprint(commands)!=source['input_prefix_fingerprint'] or successor_simulate(frozen,commands)!=source['base']['result']:raise ValueError('ORIGINAL_CANDIDATE_PREFIX_MISMATCH')
    cash=cash_control(source,inputs,method);slots=cash['declared_sessions'];first=slots[0]
    if (set(legacy['scope']['instruments'])!=set(frozen['rules']) or legacy['rules']!=frozen['rules'] or
        legacy['design']['costs']!=frozen['costs'] or int(legacy['policy']['quantity'])!=int(frozen['policy']['target_quantity']) or
        Decimal(legacy['policy']['maximum_gross_exposure'])!=Decimal(frozen['policy']['maximum_gross_exposure'])):raise ValueError('REGISTERED_CONTROL_COMMON_CONTRACT_MISMATCH')
    labels={session:f'METHOD_SLOT_{session:020d}' for session in slots};reverse={value:key for key,value in labels.items()};facts=[];previous={};rejections=[]
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
    # A derived execution contract is not presented as a modified old freeze.
    contract={'baseline':{'cash_yuan':frozen['baseline']['cash_yuan'],'positions':[]},'scope':legacy['scope'],
        'rules':legacy['rules'],'policy':legacy['policy'],'design':{'costs':frozen['costs'],'g5':legacy['design']['g5'],'event':legacy['design']['event']},
        'fingerprints':{'model':legacy['fingerprints']['model']}}
    execution={'sessions':[labels[s] for s in slots[1:]],'facts':facts,'cash_events':[],'statutory':{},'counterfactuals':{}}
    controls={};failures=list(cash['hard_failures'])
    for name in method['controls']:
        raw=simulate(contract,execution,[],labels[slots[-1]],name)
        curve=[{'session':first,'nav_yuan':frozen['baseline']['cash_yuan']}]+[{'session':reverse[r['date']],'nav_yuan':r['nav_yuan'],'gross_exposure_fraction':r['gross_exposure_fraction']} for r in raw['curve']]
        summary=continuous_summary(curve);candidate=cash['candidate']['economics']
        excess=candidate['maximum_drawdown']-summary['maximum_drawdown'] if candidate['maximum_drawdown'] is not None and summary['maximum_drawdown'] is not None else None
        execution_gaps=[{'forecast_id':r['forecast_id'],'date':r['observation_date'],'reasons':r['reasons']} for r in raw['opportunities'] if r['reasons']]
        eligibility=['NO_PRERUN_MA_CONTEXT_FOR_ORIGINAL_FULL_WINDOW'] if name=='MA5_MA20' else []
        if raw['missing'] or rejections:eligibility.append('MISSING_OR_UNKNOWN_DAILY_INPUT')
        if execution_gaps:eligibility.append('REFUSED_OR_UNSCORABLE_REGISTERED_OPPORTUNITY')
        controls[name]={'curve':curve,'economics':summary,'events':raw['events'],'input_gaps':raw['missing'],'opportunities':raw['opportunities'],
            'interval_return_difference':candidate['net_return']-summary['net_return'] if not eligibility and candidate['net_return'] is not None and summary['net_return'] is not None else None,
            'eligibility_gaps':eligibility,'execution_gaps':execution_gaps,
            'descriptive_drawdown_excess':excess,'risk_matched_excess_decision':'NOT_ADMITTED',
            'calendar_complete':not raw['missing'] and not rejections,'engine_result_fingerprint':fingerprint(raw),'evidence_kind':'METHOD_CASE'}
    return {'controls':controls,'candidate':cash['candidate'],'declared_sessions':slots,'label_to_method_session':reverse,
        'derived_execution_contract':contract,'derived_contract_fingerprint':fingerprint(contract),'adapter_facts_fingerprint':fingerprint(facts),'adapter_rejections':rejections,
        'original_registered_comparator_contract':legacy['method_validation']['comparator_contract'],
        'timing_contrast':{'candidate':'V2_NEW_LOT_ENTRY_PLUS_20_SLOTS; original migrated lot keeps its own horizon',
            'START_HOLD':'ORIGINAL_NO_AUTOMATIC_EXIT','MA5_MA20':'ORIGINAL_OBSERVATION_PLUS_20_SLOTS'},
        'risk_matched_qualification':False,'hard_failures':failures,'G4_status':'FAIL' if failures else 'INCONCLUSIVE',
        'limitations':['METHOD slots not real calendar/source authority','No admitted independent uncertainty or support','MA requires 21 complete prior slots; no synthetic pre-run context','Timing differences retained; no common-risk qualification'],
        'statistical_pass':False,'assumptions_verified':False,'network_calls':0,'new_fit_calls':0,'sealed_reads':0}


if __name__=='__main__':
    payload=json.loads(sys.stdin.read());Path(payload['output_file']).write_text(json.dumps(evaluate(payload),ensure_ascii=False,allow_nan=False),encoding='utf-8')
