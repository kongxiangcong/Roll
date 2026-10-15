"""Pinned numerical reference only; no estimator/calibrator fit or data download."""
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import socket
import sys


def evaluate_phase(phase,method,np,metrics,calibration_curve):
    unique={};excluded=[];duplicates=[]
    for row in phase['rows']:
        if not row['mature'] or row.get('label') not in (0,1):
            excluded.append(row);continue
        p=float(row['probability']);base=float(row['baseline_probability'])
        if not all(math.isfinite(v) and 0<=v<=1 for v in (p,base)):raise ValueError('INVALID_PROBABILITY')
        row={**row,'probability':p,'baseline_probability':base}
        key=row['canonical_key']
        if key in unique:
            if any(row[k]!=unique[key][k] for k in ('probability','baseline_probability','label')):raise ValueError('CONFLICTING_DUPLICATE_EVENT')
            duplicates.append(key)
        else:unique[key]=row
    rows=list(unique.values());tolerance=method['absolute_tolerance']
    value={'status':'SUPPORT_INSUFFICIENT','mature_unique':len(rows),'excluded':excluded,'duplicate_keys':duplicates,
        'accepted_rows':rows,'absolute_tolerance':tolerance,'sample_weight':'EQUAL_PER_CANONICAL_EVENT',
        'independent_calibration_validation':False,'library_aligned':{},'library_default':{},'differences':{},'aligned_bins':[]}
    if not rows:return value
    y=np.asarray([r['label'] for r in rows],dtype=int)
    p=np.asarray([r['probability'] for r in rows],dtype=np.float64)
    baseline=np.asarray([r['baseline_probability'] for r in rows],dtype=np.float64)
    # Old model reliability floors P0/P1 separately. Keep those two columns
    # explicit rather than silently substituting sklearn's default epsilon.
    probabilities=np.column_stack((np.maximum(1-p,1e-15),np.maximum(p,1e-15)))
    aligned={'brier':float(metrics.brier_score_loss(y,p,pos_label=1,labels=[0,1],scale_by_half=True)),
        'base_rate_brier':float(metrics.brier_score_loss(y,baseline,pos_label=1,labels=[0,1],scale_by_half=True)),
        'log_loss':float(metrics.log_loss(y,probabilities,labels=[0,1],normalize=True))}
    raw_log=float(metrics.log_loss(y,p,labels=[0,1],normalize=True))
    raw_true,raw_pred=calibration_curve(y,p,pos_label=1,n_bins=5,strategy='uniform')
    edges=np.linspace(0,1,6);raw_ids=np.searchsorted(edges[1:-1],p)
    occupied=sorted(set(int(i) for i in raw_ids))
    raw_bins=[{'bin':i,'count':int(np.sum(raw_ids==i)),'mean_probability':float(mean),'observed_frequency':float(actual)} for i,actual,mean in zip(occupied,raw_true,raw_pred)]
    roll_ids=[min(4,int(float(v)*5)) for v in p]
    bins=[]
    for i in range(5):
        mask=np.asarray([index==i for index in roll_ids])
        if not np.any(mask):
            bins.append({'bin':i,'count':0,'mean_probability':None,'observed_positive_rate':None});continue
        actual,mean=calibration_curve(y[mask],p[mask],pos_label=1,n_bins=1,strategy='uniform')
        bins.append({'bin':i,'count':int(np.sum(mask)),'mean_probability':float(mean[0]),'observed_positive_rate':float(actual[0])})
    old=phase['saved_metrics'];differences={name:None if old.get(name) is None else aligned[name]-float(old[name]) for name in aligned}
    bin_differences=[]
    for old_bin,new_bin in zip(old['reliability_bins'],bins):
        bin_differences.append({'bin':new_bin['bin'],'count_delta':new_bin['count']-old_bin['count'],
            'definedness_matches':all((old_bin[k] is None)==(new_bin[k] is None) for k in ('mean_probability','observed_positive_rate')),
            **{k:None if old_bin[k] is None or new_bin[k] is None else new_bin[k]-old_bin[k] for k in ('mean_probability','observed_positive_rate')}})
    consistent=len(old['reliability_bins'])==5 and all(v is not None and abs(v)<=tolerance for v in differences.values()) and all(
        b['count_delta']==0 and b['definedness_matches'] and all(b[k] is None or abs(b[k])<=tolerance for k in ('mean_probability','observed_positive_rate')) for b in bin_differences)
    status='NUMERICALLY_CONSISTENT' if consistent else 'IMPLEMENTATION_DIFFERENCE'
    if len(rows)!=old['count']:status='CONVENTION_DIFFERENCE_SAMPLE_SELECTION'
    value.update(status=status,library_aligned=aligned,library_default={'log_loss':raw_log,'log_epsilon':float(np.finfo(np.float64).eps),'bins':raw_bins},
        differences=differences,aligned_bins=bins,bin_differences=bin_differences,
        boundary_convention_differs=any(int(a)!=b for a,b in zip(raw_ids,roll_ids)),
        raw_log_default_difference=raw_log-aligned['log_loss'],unique_observation_dates=len({r['observation_date'] for r in rows}),
        saved_metrics=old)
    return value


def evaluate(command):
    def denied(*args,**kwargs):raise RuntimeError('REFERENCE_NETWORK_DISABLED')
    socket.socket.connect=denied;socket.create_connection=denied;socket.getaddrinfo=denied
    import numpy as np
    import sklearn
    from sklearn import metrics
    from sklearn.calibration import calibration_curve
    if version('scikit-learn')!='1.9.1':raise ValueError('SKLEARN_PIN_MISMATCH')
    library={'name':'scikit-learn','version':'1.9.1','license':'BSD-3-Clause','numpy':np.__version__,
        'source_sha256':{name:hashlib.sha256((Path(sklearn.__file__).parent/name).read_bytes()).hexdigest() for name in ('metrics/_classification.py','calibration.py')}}
    phases={}
    for name,phase in command['phases'].items():
        try:phases[name]=evaluate_phase(phase,command['method'],np,metrics,calibration_curve)
        except (ValueError,TypeError,KeyError) as error:
            phases[name]={'status':'SOURCE_INPUT_ERROR','error':str(error)[:200],'independent_calibration_validation':False}
    return {'library':library,'phases':phases,'network_calls':0,'new_fit_calls':0,'sealed_reads':0,
        'statistical_assumptions_verified':False,'capability':'NOT_GRANTED','system_usable':False}


if __name__=='__main__':
    command=json.loads(sys.stdin.read());result=evaluate(command)
    Path(command['output_file']).write_text(json.dumps(result,ensure_ascii=False,allow_nan=False),encoding='utf-8')
