"""Bounded METHOD sensitivity around an unchanged saved successor engine."""
import copy
from decimal import Decimal
import hashlib,json
from pathlib import Path
import socket,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from roll.research.successor_shadow import simulate,source_fingerprint,usable
from roll.research.shadow import fingerprint,shadow_code
from roll.research.statistics import continuous_summary


def evaluate(payload):
    def denied(*args,**kwargs):raise RuntimeError('SUCCESSOR_STRESS_NETWORK_DISABLED')
    socket.socket.connect=denied;socket.create_connection=denied;socket.getaddrinfo=denied
    frozen=payload['frozen'];method=payload['method'];rows=payload['rows'];protocol=payload['protocol']
    if frozen['source_fingerprint']!=source_fingerprint():raise ValueError('SUCCESSOR_ENGINE_CHANGED')
    if payload['inherited_shadow_code']!=shadow_code():raise ValueError('INHERITED_ENGINE_DEPENDENCIES_CHANGED')
    if not rows or len(rows)>method['maximum_frames']:raise ValueError('SUCCESSOR_STRESS_PREFIX_LIMIT')
    commands=[];base_results=[]
    # Original frame bindings are checked inside the deadline. No mutable
    # later history is queried or consumed by this bounded prefix.
    for revision,command_hash,frame in rows:
        if revision!=len(commands)+1 or frame['command']['expected_revision']!=len(commands):raise ValueError('PREFIX_REVISION_MISMATCH')
        if fingerprint(frame['command'])!=command_hash or command_hash!=frame['input_fingerprint']:raise ValueError('PREFIX_INPUT_MISMATCH')
        commands.append(frame['command']);result=simulate(frozen,commands)
        if result!=frame['result'] or fingerprint(result)!=frame['result_fingerprint']:raise ValueError('PREFIX_RESULT_MISMATCH')
        base_results.append(result)
    prefix_hash=fingerprint(commands)
    def summarize(changed,results):
        baseline=changed['baseline'];curve=[{'session':baseline['starting_session'],'nav_yuan':baseline['cash_yuan'] if not baseline['positions'] else None}]
        for command,result in zip(commands,results):
            bars={b['instrument']:b for b in command['bars']}
            known=all(usable(bars.get(p['instrument'])) for p in result['positions'])
            nav=Decimal(result['cash_yuan'])+sum((Decimal(bars[p['instrument']]['close_yuan'])*p['quantity'] for p in result['positions']),Decimal(0)) if known else None
            curve.append({'session':command['session'],'nav_yuan':str(nav) if nav is not None else None})
        final=results[-1];fees=sum((Decimal(e['fees_yuan']) for e in final['events'] if 'fees_yuan' in e),Decimal(0))
        economics=continuous_summary(curve);maximum=protocol['design']['primary_objective']['risk_constraints']['maximum_drawdown']
        observed=[Decimal(p['nav_yuan']) for p in curve if p['nav_yuan'] is not None]
        peak=Decimal(0);drawdown=Decimal(0)
        for value in observed:
            peak=max(peak,value)
            if peak>0:drawdown=max(drawdown,1-value/peak)
        failures=['MAXIMUM_DRAWDOWN_EXCEEDED'] if drawdown>Decimal(maximum) else []
        return {'curve':curve,'economics':economics,'observed_drawdown_lower_bound':str(drawdown),'hard_failures':failures,'fees_yuan':str(fees),'events':final['events'],
            'input_gaps':final['gaps'],'result':final,'input_prefix_fingerprint':prefix_hash}
    base=summarize(frozen,base_results);scenarios=[]
    for field,grid in method['fields'].items():
        values=protocol['design']['g5'][grid]
        if not 1<=len(values)<=method['maximum_values_per_field'] or len(values)!=len(set(values)):raise ValueError('UNREGISTERED_COST_GRID_SIZE')
        for value in values:
            number=Decimal(value)
            if not number.is_finite() or number<0 or number>1:raise ValueError('INVALID_FROZEN_COST_RATE')
            changed=copy.deepcopy(frozen);changed['costs'][field]=value
            results=[simulate(changed,commands[:end]) for end in range(1,len(commands)+1)]
            summary=summarize(changed,results)
            scenarios.append({**summary,'component':field+'='+value,'field':field,'rate':value,'costs':changed['costs'],
                'input_fingerprint':fingerprint([changed,commands]),'result_fingerprint':fingerprint(summary),
                'status':'FAIL' if summary['hard_failures'] else 'INCONCLUSIVE'})
    return {'base':base,'scenarios':scenarios,'base_matches_saved_prefix':True,'input_prefix_fingerprint':prefix_hash,
        'G5_status':'FAIL' if base['hard_failures'] or any(s['hard_failures'] for s in scenarios) else 'INCONCLUSIVE','remaining_components':['REAL_INPUT_ADMISSION','COMMON_RISK_MATCHED_BENCHMARKS','TIME_SEGMENTS','EXECUTION_DELAYS','FROZEN_NEIGHBOR_ARTIFACTS','MIGRATION_SCOPE','INDEPENDENT_SUPPORT'],
        'risk_constraints':protocol['design']['primary_objective']['risk_constraints'],
        'assumptions_verified':False,'network_calls':0,'new_fit_calls':0,'sealed_reads':0}


if __name__=='__main__':
    payload=json.loads(sys.stdin.read());result=evaluate(payload)
    Path(payload['output_file']).write_text(json.dumps(result,ensure_ascii=False,allow_nan=False),encoding='utf-8')
