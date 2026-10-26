"""Fixed METHOD boundary vectors, scored by the actual independent library."""
import copy
import json
import math
from pathlib import Path
import subprocess


def saved_metrics(rows):
    # Fixed old-model convention; no fit and no call to the reference library.
    bins=[]
    for index in range(5):
        group=[r for r in rows if min(4,int(float(r['probability'])*5))==index]
        bins.append({'count':len(group),'mean_probability':sum(float(r['probability']) for r in group)/len(group) if group else None,
            'observed_positive_rate':sum(r['label'] for r in group)/len(group) if group else None})
    return {'count':len(rows),'brier':sum((float(r['probability'])-r['label'])**2 for r in rows)/len(rows),
        'base_rate_brier':.25,'log_loss':-sum(r['label']*math.log(max(float(r['probability']),1e-15))+(1-r['label'])*math.log(max(1-float(r['probability']),1e-15)) for r in rows)/len(rows),
        'reliability_bins':bins}


def test_boundary_clipping_bins_single_class_missing_duplicates_and_numeric_error(tmp_path):
    root=Path(__file__).resolve().parents[3]
    python=root/'.scratch/rce-runtime/probability/Scripts/python.exe'
    rows=[{'canonical_key':str(i),'instrument':'METHOD:A','observation_date':'2026-06-'+('08' if i<3 else '09'),
        'probability':p,'baseline_probability':.5,'label':label,'mature':True} for i,(p,label) in enumerate(zip([0,1,.2,.8,.4,.6],[0,1,1,0,0,1]))]
    reference=saved_metrics(rows)
    phases={'boundary':{'rows':rows,'saved_metrics':reference}}
    single=[{**r,'label':0} for r in rows[:2]]
    phases['single']={'rows':single,'saved_metrics':saved_metrics(single)}
    duplicates=copy.deepcopy(rows)+[copy.deepcopy(rows[0])]
    phases['duplicates']={'rows':duplicates,'saved_metrics':saved_metrics(duplicates)}
    excluded=[{**rows[0],'mature':False,'probability':None},{**rows[1],'label':None}]
    phases['missing']={'rows':excluded,'saved_metrics':reference}
    phases['mixed']={'rows':copy.deepcopy(rows)+excluded,'saved_metrics':reference}
    phases['conflict']={'rows':rows+[{**rows[0],'probability':.5}],'saved_metrics':reference}
    phases['invalid']={'rows':[{**rows[0],'probability':2}],'saved_metrics':reference}
    wrong=copy.deepcopy(reference);wrong['brier']+=.01
    phases['error']={'rows':rows,'saved_metrics':wrong}
    output=tmp_path/'result.json'
    payload={'phases':phases,'method':{'absolute_tolerance':1e-12},'output_file':str(output)}
    completed=subprocess.run([str(python),'-I','-B',str(root/'backend/src/roll/research/probability_process.py')],input=json.dumps(payload),text=True,capture_output=True,timeout=20)
    assert completed.returncode==0,completed.stderr[-1000:]
    results=json.loads(output.read_text(encoding='utf-8'))
    assert results['new_fit_calls']==0 and results['network_calls']==0 and results['statistical_assumptions_verified'] is False
    result=results['phases']
    assert result['boundary']['status']=='NUMERICALLY_CONSISTENT'
    assert result['boundary']['boundary_convention_differs'] is True
    assert result['single']['status']=='NUMERICALLY_CONSISTENT'
    assert abs(result['single']['raw_log_default_difference'])>.1
    assert result['duplicates']['status']=='CONVENTION_DIFFERENCE_SAMPLE_SELECTION'
    assert result['duplicates']['mature_unique']==6 and len(result['duplicates']['duplicate_keys'])==1
    assert result['mixed']['status']=='NUMERICALLY_CONSISTENT' and len(result['mixed']['excluded'])==2
    assert result['boundary']['unique_observation_dates']==2
    assert result['missing']['status']=='SUPPORT_INSUFFICIENT'
    assert result['conflict']['status']==result['invalid']['status']=='SOURCE_INPUT_ERROR'
    assert result['error']['status']=='IMPLEMENTATION_DIFFERENCE'
