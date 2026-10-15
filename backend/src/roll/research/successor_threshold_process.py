"""Entry-only frozen-grid sensitivity without fitting or new predictions."""
import copy,json,socket,sys
from decimal import Decimal
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from roll.research.successor_shadow import simulate,source_fingerprint,usable
from roll.research.shadow import fingerprint,shadow_code
from roll.research.statistics import continuous_summary,fingerprint as statistics_fingerprint


def evaluate(payload):
    def denied(*args,**kwargs):raise RuntimeError('SUCCESSOR_THRESHOLD_NETWORK_DISABLED')
    socket.socket.connect=denied;socket.create_connection=denied;socket.getaddrinfo=denied
    source=payload['source'];data=payload['input'];method=payload['method'];frozen=data['frozen'];rows=data['rows'];protocol=data['protocol']
    if frozen['source_fingerprint']!=source_fingerprint() or data['inherited_shadow_code']!=shadow_code() or protocol['statistical_methods']['code_fingerprint']!=statistics_fingerprint():raise ValueError('THRESHOLD_INHERITED_ENGINE_CHANGED')
    grid=protocol['design']['g5']['parameter_neighborhood']['probability_threshold']
    if grid!=method['grid'] or frozen['policy']['entry_threshold']!='0.60':raise ValueError('THRESHOLD_GRID_OR_BASE_NOT_REGISTERED')
    start=frozen['baseline']['starting_session'];last=rows[-1][2]['command']['session']
    if not 1<=len(rows)<=method['maximum_frames'] or not 1<=last-start<=method['maximum_declared_session_span']:raise ValueError('THRESHOLD_PREFIX_LIMIT')
    commands=[];base=[]
    for revision,digest,frame in rows:
        if revision!=len(commands)+1 or frame['command']['expected_revision']!=len(commands) or fingerprint(frame['command'])!=digest or frame['input_fingerprint']!=digest:raise ValueError('THRESHOLD_PREFIX_BINDING_MISMATCH')
        commands.append(frame['command']);result=simulate(frozen,commands)
        if result!=frame['result'] or fingerprint(result)!=frame['result_fingerprint']:raise ValueError('THRESHOLD_BASE_FULL_STATE_MISMATCH')
        base.append(result)
    if source['base']['result']!=base[-1] or fingerprint(commands)!=source['input_prefix_fingerprint']:raise ValueError('THRESHOLD_SOURCE_PREFIX_MISMATCH')
    cases=[]
    for threshold in grid:
        # A derived diagnostic contract, without original freeze IDs, hashes or
        # archives. Support and all other policy clauses remain frozen.
        contract={key:copy.deepcopy(frozen[key]) for key in ('baseline','costs','rules','policy','migrations','design')}
        contract['policy']['entry_threshold']=threshold
        results=base if threshold=='0.60' else [simulate(contract,commands[:end]) for end in range(1,len(commands)+1)]
        points={start:frozen['baseline']['cash_yuan'] if not frozen['baseline']['positions'] else None};exposures=[]
        for command,result in zip(commands,results):
            bars={b['instrument']:b for b in command['bars']}
            nav=Decimal(result['cash_yuan'])+sum((Decimal(bars[p['instrument']]['close_yuan'])*p['quantity'] for p in result['positions']),Decimal(0)) if all(usable(bars.get(p['instrument'])) for p in result['positions']) else None
            points[command['session']]=str(nav) if nav is not None else None
            if nav is not None and nav>0:exposures.append((nav-Decimal(result['cash_yuan']))/nav)
        curve=[{'session':s,'nav_yuan':points.get(s)} for s in range(start,last+1)];peak=Decimal(0);drawdown=Decimal(0)
        for p in curve:
            if p['nav_yuan'] is None:continue
            nav=Decimal(p['nav_yuan']);peak=max(peak,nav)
            if peak>0:drawdown=max(drawdown,1-nav/peak)
        risk=source['risk_constraints'];failures=[]
        if drawdown>Decimal(risk['maximum_drawdown']):failures.append('MAXIMUM_DRAWDOWN_EXCEEDED')
        if exposures and max(exposures)>Decimal(risk['maximum_simulated_gross_exposure'])+Decimal('1e-12'):failures.append('MAXIMUM_EXPOSURE_EXCEEDED')
        cases.append({'entry_threshold':threshold,'support_threshold':frozen['policy']['support_threshold'],'derived_policy':contract['policy'],
            'curve':curve,'economics':continuous_summary(curve),'result':results[-1],'input_prefix_fingerprint':fingerprint(commands),
            'hard_failures':failures,'observed_drawdown_lower_bound':str(drawdown),'maximum_observed_gross_exposure_fraction':str(max(exposures)) if exposures else None,
            'status':'FAIL' if failures else 'INCONCLUSIVE'})
    return {'scenarios':cases,'base_matches_saved_prefix':True,'G5_status':'FAIL' if any(c['hard_failures'] for c in cases) else 'INCONCLUSIVE',
        'evidence_kind':'METHOD_CASE','data_scope':'METHOD_DECLARED_SLOTS','partition':None,'winner_selected':False,
        'statistical_pass':False,'complete_experiment_frozen':False,'system_usable':False,'capability':'NOT_GRANTED',
        'limitations':['Entry threshold only; support threshold fixed','No paired benchmark or independent interval admission','Penalty/lookback neighbors require frozen model artifacts','No real-input authority or qualification'],
        'new_fit_calls':0,'sealed_reads':0,'network_calls':0}


if __name__=='__main__':
    payload=json.loads(sys.stdin.read());body=json.dumps(evaluate(payload),ensure_ascii=False,allow_nan=False).encode()
    if len(body)>payload['method']['maximum_output_bytes']:raise ValueError('THRESHOLD_OUTPUT_SIZE_LIMIT')
    Path(payload['output_file']).write_bytes(body)
