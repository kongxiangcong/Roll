import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
from roll.research.statistics import paired_block_interval
from roll.research.block_reference import cases_for


def test_same_day_excluded_name_cannot_disappear_from_paired_source():
    source={'sessions':['2026-06-08','2026-06-09'],'source_evidence_kind':'METHOD'}
    row={'observation_date':'2026-06-08','canonical_key':'A','probability':.7,'baseline_probability':.5,'label':1}
    probability={'phases':{'PHASE':{'accepted_rows':[row,{**row,'canonical_key':'B','probability':.8}],
        'excluded':[{'observation_date':'2026-06-08','canonical_key':'C','mature':False}]}}}
    cases=cases_for(source,probability)
    for key,case in cases.items():
        if not key.startswith('SOURCE:'):continue
        assert set(case['date_scores'][0]['scores'])=={'A','B','EXCLUDED_UNMATURE_OR_UNKNOWN_EVENT'}
        assert case['date_scores'][0]['scores']['EXCLUDED_UNMATURE_OR_UNKNOWN_EVENT'] is None
        assert case['date_scores'][1]['scores']=={'UNOBSERVED_MATURE_EVENT':None}


def test_real_arch_handles_missing_empty_group_dates_and_same_day_pairing(tmp_path):
    root=Path(__file__).resolve().parents[3]
    method=json.loads((root/'backend/src/roll/research/reference/block-reference-v1.json').read_text())
    rows=[{'date':f'METHOD:{i:03}','scores':{'A':float(i%7),'B':float(-i%3)}} for i in range(80)]
    conditional=[{**r,'scores':{} if i%3==0 else r['scores']} for i,r in enumerate(rows)]
    missing=copy.deepcopy(rows);missing[21]['scores']={'A':None}
    empty=[{**r,'scores':{}} for r in rows]
    def case(data,selected=False,block=20):
        return {'date_scores':data,'conditional':selected,'block_sessions':block,'evidence_kind':'METHOD',
            'frozen_result':paired_block_interval(data,block_sessions=block,conditional=selected)}
    cases={'paired20':case(rows),'paired40':case(rows,block=40),'conditional':case(conditional,True),
        'missing':case(missing),'missing_conditional':case(missing,True),'empty':case(empty,True),'short':case(rows[:19]),'no_dates':case([])}
    cases['duplicate_dates']={**cases['paired20'],'date_scores':rows+[rows[-1]]}
    cases['wrong_block']={**cases['paired20'],'block_sessions':2}
    output=tmp_path/'result.json'
    process=subprocess.run([str(root/'.scratch/rce-runtime/arch/Scripts/python.exe'),'-I','-B',str(root/'backend/src/roll/research/block_process.py')],
        input=json.dumps({'cases':cases,'method':method,'frozen_method_sha256':hashlib.sha256((root/'backend/src/roll/research/statistics.py').read_bytes().replace(b'\r\n',b'\n')).hexdigest(),'output_file':str(output)}),text=True,capture_output=True,timeout=30,
        env={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'})
    assert process.returncode==0,process.stderr[-1000:]
    values=json.loads(output.read_text(encoding='utf-8'))['cases']
    for name in ('paired20','paired40','conditional'):
        assert values[name]['status']=='NUMERICALLY_CONSISTENT',values[name]
        assert values[name]['same_indices_max_statistic_error']<=1e-12
        assert len(values[name]['first_resample_indices'])==80
        # Every block has consecutive date indices; all names in a date stay together.
        block=values[name]['block_sessions'];indices=values[name]['first_resample_indices']
        assert all(indices[i]+1==indices[i+1] for i in range(79) if (i+1)%block)
    assert values['conditional']['member_calendar_sessions']==53
    assert values['conditional']['effective_block_upper_bound']==2
    assert values['missing']['status']==values['missing_conditional']['status']=='INCOMPLETE_ALIGNED_CALENDAR_SCORES'
    assert values['empty']['status']=='INSUFFICIENT_MEMBER_SUPPORT'
    assert values['short']['status']==values['no_dates']['status']=='INSUFFICIENT_CALENDAR_SUPPORT'
    assert values['duplicate_dates']['status']==values['wrong_block']['status']=='SOURCE_INPUT_ERROR'
