"""Offline arch reference; date groups are the resampling unit."""
import hashlib
import ast
from importlib.metadata import version
import json
import math
import random
from pathlib import Path
import socket
import sys
from statistics import fmean


def compare(case, method, np, MovingBlockBootstrap):
    rows=case['date_scores'];conditional=case['conditional'];block=case['block_sessions']
    if block not in method['block_sessions'] or len(rows)>method['limits']['calendar_sessions']:
        raise ValueError('UNREGISTERED_BLOCK_OR_CALENDAR_LIMIT')
    dates=[r['date'] for r in rows]
    if dates!=sorted(set(dates)):raise ValueError('CALENDAR_SCORES_MUST_BE_UNIQUE_AND_ORDERED')
    result={'calendar_sessions':len(rows),'block_sessions':block,'replicates':method['replicates'],'seed':method['seed'],
        'effective_block_upper_bound':len(rows)//block,'assumptions_verified':False,'statistical_pass':False,
        'interval_kind':'ONE_SIDED_95_ENDPOINTS_CENTRAL_90_RANGE','lower_95':None,'upper_95':None,
        'frozen_result':case['frozen_result'],'conditional':conditional,'evidence_kind':case['evidence_kind']}
    values=[]
    for row in rows:
        scores=row['scores']
        if (not scores and not conditional) or any(v is None for v in scores.values()):
            return {**result,'status':'INCOMPLETE_ALIGNED_CALENDAR_SCORES'}
        group=[float(v) for v in scores.values()]
        if any(not math.isfinite(v) for v in group):raise ValueError('NONFINITE_PAIRED_SCORE')
        values.append((sum(group),len(group)))
    if conditional:
        members=sum(count for _,count in values);days=sum(count>0 for _,count in values)
        result.update(member_count=members,member_calendar_sessions=days,calendar_effective_block_upper_bound=len(rows)//block,effective_block_upper_bound=days//block)
        if not members:return {**result,'status':'INSUFFICIENT_MEMBER_SUPPORT'}
    if len(rows)<block:return {**result,'status':'INSUFFICIENT_CALENDAR_SUPPORT'}
    data=np.asarray(values,dtype=np.float64)
    def statistic(sample):
        return float(np.sum(sample[:,0])/np.sum(sample[:,1])) if conditional else float(np.mean(sample[:,0]/sample[:,1]))
    mean=statistic(data);bootstrap=MovingBlockBootstrap(block,data,seed=method['seed'])
    estimates=[];indices_hash=hashlib.sha256();max_error=0.;first_indices=None
    for positional,_ in bootstrap.bootstrap(method['replicates']):
        index=bootstrap.index.tolist()
        indices_hash.update(json.dumps(index,separators=(',',':')).encode()+b'\n')
        if first_indices is None:first_indices=index
        selected=[rows[i]['scores'] for i in index]
        if conditional:
            count=sum(len(g) for g in selected)
            if not count:return {**result,'status':'INSUFFICIENT_RESAMPLED_MEMBER_SUPPORT'}
            expected=sum(sum(g.values()) for g in selected)/count
        else:expected=sum(sum(g.values())/len(g) for g in selected)/len(selected)
        actual=statistic(positional[0]);max_error=max(max_error,abs(actual-expected));estimates.append(actual)
    estimates.sort();lower=estimates[math.floor(.05*(len(estimates)-1))];upper=estimates[math.ceil(.95*(len(estimates)-1))]
    old=case['frozen_result'];tolerance=method['absolute_tolerance']
    point_error=None if old.get('mean') is None else mean-old['mean']
    consistent=max_error<=tolerance and point_error is not None and abs(point_error)<=tolerance
    if case.get('analytic_constant') is not None:
        constant=case['analytic_constant']
        consistent=consistent and all(abs(v-constant)<=tolerance for v in (mean,lower,upper,old['lower_95'],old['upper_95']))
    return {**result,'status':'NUMERICALLY_CONSISTENT' if consistent else 'IMPLEMENTATION_DIFFERENCE',
        'mean':mean,'lower_95':lower,'upper_95':upper,'same_indices_max_statistic_error':max_error,
        'point_difference':point_error,'resample_indices_sha256':indices_hash.hexdigest(),'first_resample_indices':first_indices,
        'endpoint_differences':{k:v-old[k] for k,v in [('lower_95',lower),('upper_95',upper)]},
        'random_convention':'arch NumPy default_rng PCG64; frozen Python random.Random MT19937; same integer seed does not imply same draws',
        'endpoint_comparison':'DESCRIPTIVE_ONLY_DIFFERENT_DRAWS; same rank endpoints, no tolerance claim on distribution endpoints'}


def evaluate(command):
    def denied(*args,**kwargs):raise RuntimeError('BLOCK_REFERENCE_NETWORK_DISABLED')
    socket.socket.connect=denied;socket.create_connection=denied;socket.getaddrinfo=denied
    import numpy as np
    import arch
    from arch.bootstrap import MovingBlockBootstrap
    if version('arch')!='8.0.0':raise ValueError('ARCH_PIN_MISMATCH')
    # Load only the two original pure numerical definitions, byte-bound to
    # the archived fingerprint. Importing the whole business module would
    # couple this isolated environment to ledger dependencies.
    frozen_path=Path(__file__).with_name('statistics.py')
    frozen_body=frozen_path.read_bytes().replace(b'\r\n',b'\n')
    if hashlib.sha256(frozen_body).hexdigest()!=command['frozen_method_sha256']:raise ValueError('FROZEN_METHOD_SHA_MISMATCH')
    definitions=[node for node in ast.parse(frozen_body).body if isinstance(node,ast.FunctionDef) and node.name in ('rounded','paired_block_interval')]
    if len(definitions)!=2:raise ValueError('FROZEN_METHOD_DEFINITIONS_MISSING')
    namespace={'math':math,'random':random,'fmean':fmean}
    exec(compile(ast.Module(body=definitions,type_ignores=[]),str(frozen_path),'exec'),namespace)
    cases={}
    for name,case in command['cases'].items():
        try:
            frozen=namespace['paired_block_interval'](case['date_scores'],block_sessions=case['block_sessions'],conditional=case['conditional'])
            cases[name]=compare({**case,'frozen_result':frozen},command['method'],np,MovingBlockBootstrap)
        except (ValueError,TypeError,KeyError,ZeroDivisionError) as error:
            cases[name]={'status':'SOURCE_INPUT_ERROR','error':str(error)[:200],'assumptions_verified':False}
    source=Path(arch.__file__).parent/'bootstrap/base.py'
    return {'library':{'name':'arch','version':version('arch'),'license':'NCSA','numpy':version('numpy'),'scipy':version('scipy'),
        'pandas':version('pandas'),'statsmodels':version('statsmodels'),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest()},
        'cases':cases,'network_calls':0,'new_fit_calls':0,'sealed_reads':0,'assumptions_verified':False,'capability':'NOT_GRANTED'}


if __name__=='__main__':
    command=json.loads(sys.stdin.read())
    Path(command['output_file']).write_text(json.dumps(evaluate(command),ensure_ascii=False,allow_nan=False),encoding='utf-8')
