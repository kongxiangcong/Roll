"""Bounded entry-only METHOD sensitivities on one immutable source prefix."""
from decimal import Decimal
import json,socket,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from roll.research.successor_shadow import simulate as original,source_fingerprint,usable
from roll.research.successor_entry_engine import simulate
from roll.research.shadow import fingerprint,shadow_code
from roll.research.statistics import continuous_summary,fingerprint as statistics_fingerprint


def evaluate(payload):
    def denied(*args,**kwargs):raise RuntimeError('SUCCESSOR_ENTRY_NETWORK_DISABLED')
    socket.socket.connect=denied;socket.create_connection=denied;socket.getaddrinfo=denied
    source=payload['source'];data=payload['input'];method=payload['method'];frozen=data['frozen'];rows=data['rows'];protocol=data['protocol']
    if source_fingerprint()!=frozen['source_fingerprint'] or data['inherited_shadow_code']!=shadow_code():raise ValueError('ENTRY_INHERITED_ENGINE_CHANGED')
    if protocol['statistical_methods']['code_fingerprint']!=statistics_fingerprint():raise ValueError('ENTRY_STATISTICS_CHANGED')
    if not 1<=len(rows)<=method['maximum_frames']:raise ValueError('ENTRY_FRAME_LIMIT')
    start=frozen['baseline']['starting_session'];last=rows[-1][2]['command']['session']
    if not 1<=last-start<=method['maximum_declared_session_span']:raise ValueError('ENTRY_SPAN_LIMIT_NO_COMPRESSION')
    commands=[];base=[]
    for revision,digest,frame in rows:
        if revision!=len(commands)+1 or frame['command']['expected_revision']!=len(commands):raise ValueError('ENTRY_PREFIX_REVISION_MISMATCH')
        if fingerprint(frame['command'])!=digest or digest!=frame['input_fingerprint']:raise ValueError('ENTRY_PREFIX_INPUT_MISMATCH')
        commands.append(frame['command']);old=original(frozen,commands);new=simulate(frozen,commands)
        if old!=frame['result'] or fingerprint(old)!=frame['result_fingerprint'] or new!=old:raise ValueError('ENTRY_DEFAULT_FULL_STATE_NOT_EQUIVALENT')
        base.append(old)
    if base[-1]!=source['base']['result'] or fingerprint(commands)!=source['input_prefix_fingerprint']:raise ValueError('ENTRY_SOURCE_PREFIX_MISMATCH')
    g5=protocol['design']['g5']
    if g5['delays']!=method['delays'] or not protocol['design']['execution']['partial_or_missed'].startswith('0/50/100% execution stress') or {Decimal(v) for v in method['partial_fractions']}!={Decimal('0'),Decimal('0.50'),Decimal('1')}:raise ValueError('ENTRY_GRID_NOT_ORIGINAL_FROZEN_GRID')
    scenarios=[]
    grid=[{'delay':delay,'fill_fraction':'1'} for delay in method['delays']]+[{'delay':'NEXT_OPEN','fill_fraction':fraction} for fraction in method['partial_fractions'] if Decimal(fraction)!=1]
    for scenario in grid:
        default=scenario['delay']=='NEXT_OPEN' and Decimal(scenario['fill_fraction'])==1
        results=base if default else [simulate(frozen,commands[:end],scenario) for end in range(1,len(commands)+1)]
        points={start:frozen['baseline']['cash_yuan'] if not frozen['baseline']['positions'] else None};exposures=[]
        for command,result in zip(commands,results):
            bars={b['instrument']:b for b in command['bars']}
            nav=Decimal(result['cash_yuan'])+sum((Decimal(bars[p['instrument']]['close_yuan'])*p['quantity'] for p in result['positions']),Decimal(0)) if all(usable(bars.get(p['instrument'])) for p in result['positions']) else None
            points[command['session']]=str(nav) if nav is not None else None
            if nav is not None and nav>0:exposures.append((nav-Decimal(result['cash_yuan']))/nav)
        curve=[{'session':s,'nav_yuan':points.get(s)} for s in range(start,last+1)]
        peak=Decimal(0);drawdown=Decimal(0)
        for point in curve:
            if point['nav_yuan'] is None:continue
            nav=Decimal(point['nav_yuan']);peak=max(peak,nav)
            if peak>0:drawdown=max(drawdown,1-nav/peak)
        risk=source['risk_constraints'];failures=[]
        if drawdown>Decimal(risk['maximum_drawdown']):failures.append('MAXIMUM_DRAWDOWN_EXCEEDED')
        if exposures and max(exposures)>Decimal(risk['maximum_simulated_gross_exposure'])+Decimal('1e-12'):failures.append('MAXIMUM_EXPOSURE_EXCEEDED')
        final=results[-1]
        scenarios.append({'scenario_id':scenario['delay']+':'+scenario['fill_fraction'],**scenario,'curve':curve,'economics':continuous_summary(curve),
            'result':final,'entry_attempts':final.get('entry_stress_trace',[]),'input_gaps':final['gaps'],
            'fees_yuan':str(sum((Decimal(e['fees_yuan']) for e in final['events'] if 'fees_yuan' in e),Decimal(0))),
            'maximum_observed_gross_exposure_fraction':str(max(exposures)) if exposures else None,
            'observed_drawdown_lower_bound':str(drawdown),'hard_failures':failures,'status':'FAIL' if failures else 'INCONCLUSIVE'})
    return {'scenarios':scenarios,'base_matches_saved_prefix':True,'input_prefix_fingerprint':fingerprint(commands),
        'G5_status':'FAIL' if source['base']['hard_failures'] or any(s['hard_failures'] for s in scenarios) else 'INCONCLUSIVE',
        'scope':method['scope'],'assumptions_verified':False,'statistical_pass':False,
        'remaining_components':['EARLY_SELL_STRESS','HORIZON_EXIT_STRESS','JOINT_COMPARATOR_STRESS','REAL_INPUTS','INDEPENDENT_SUPPORT','NEIGHBOR_ARTIFACTS','COMPLETE_FREEZE'],
        'calendar_kind':'DECLARED_METHOD_SESSION_SLOTS_NOT_REAL_TRADING_DATES','network_calls':0,'new_fit_calls':0,'sealed_reads':0}


if __name__=='__main__':
    payload=json.loads(sys.stdin.read());result=evaluate(payload)
    Path(payload['output_file']).write_text(json.dumps(result,ensure_ascii=False,allow_nan=False),encoding='utf-8')
