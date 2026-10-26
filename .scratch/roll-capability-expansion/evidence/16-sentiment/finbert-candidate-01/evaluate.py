"""Reproducible metrics from frozen labels and saved offline predictions."""
import hashlib
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path

out = Path(__file__).resolve().parent
repo = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(repo / 'backend' / 'src'))
from roll.market.sentiment_evaluation import evaluate_confusion

frozen = json.loads((out / 'frozen-dataset.json').read_bytes())
inference = json.loads((out / 'inference.json').read_bytes())
assert inference['status'] == 'COMPLETE'
expected = {row['index']:row for row in frozen['included']}
assert len(inference['rows']) == len(expected)
assert len({row['index'] for row in inference['rows']}) == len(expected)
for row in inference['rows']:
    source = expected[row['index']]
    assert all(source[key] == row[key] for key in ('group_id','split','label','input_sha256'))


def metrics(rows):
    confusion = dict(Counter(row['label']+'->'+row['prediction'] for row in rows))
    value = evaluate_confusion(confusion)
    value['binary_macro_f1'] = value.pop('macro_f1')
    f1 = [value['per_class'][label]['f1'] for label in ('POSITIVE','NEGATIVE','NEUTRAL')]
    value['three_class_macro_f1'] = sum(f1)/3 if all(item is not None for item in f1) else None
    value['rows'] = len(rows)
    value['event_groups'] = len({row['group_id'] for row in rows})
    for label in value['per_class']:
        value['per_class'][label]['event_groups'] = len({row['group_id'] for row in rows if row['label']==label})
    rejects = [row for row in rows if row['prediction'].startswith('ABSTAIN_')]
    value['reject_counts'] = dict(Counter(row['prediction'] for row in rejects))
    value['abstain_coverage'] = len(rejects)/len(rows)
    irrelevant = [row for row in rows if row['label']=='IRRELEVANT']
    value['irrelevant_rejection_rate'] = sum(row['prediction'].startswith('ABSTAIN_') for row in irrelevant)/len(irrelevant) if irrelevant else None
    return value


values = {name:metrics([row for row in inference['rows'] if row['split']==name]) for name in ('DEVELOPMENT','HOLDOUT')}
values['ALL_DIAGNOSTIC'] = metrics(inference['rows'])
latencies = sorted(row['latency_seconds'] for row in inference['rows'] if row['latency_seconds'] is not None)
latency = {'model_calls':len(latencies),'p50_seconds':statistics.median(latencies) if latencies else None,'p95_seconds':latencies[math.ceil(.95*len(latencies))-1] if latencies else None}
holdout = values['HOLDOUT']
gate_inputs = {
    'binary_macro_f1': (holdout['binary_macro_f1'], .60, '>='),
    'positive_recall': (holdout['positive_recall'], .55, '>='),
    'negative_recall': (holdout['negative_recall'], .55, '>='),
    'three_class_macro_f1': (holdout['three_class_macro_f1'], .60, '>='),
    'neutral_recall': (holdout['per_class']['NEUTRAL']['recall'], .55, '>='),
    'irrelevant_rejection_rate': (holdout['irrelevant_rejection_rate'], .80, '>='),
    'abstain_coverage': (holdout['abstain_coverage'], .35, '<='),
    'model_p95_seconds': (latency['p95_seconds'], 3.0, '<='),
}
gates = {key:{'actual':actual,'threshold':threshold,'operator':operator,'passed':actual is not None and (actual>=threshold if operator=='>=' else actual<=threshold)} for key,(actual,threshold,operator) in gate_inputs.items()}
report = {
    'candidate':inference['model'],'revision':inference['revision'],'evidence_kind':'REAL_LOCAL_CANDIDATE_EVALUATION_NON_INDEPENDENT_LABELS',
    'dataset_sha256':hashlib.sha256((out/'frozen-dataset.json').read_bytes()).hexdigest(),
    'inference_sha256':hashlib.sha256((out/'inference.json').read_bytes()).hexdigest(),
    'splits':values,'latency':latency,'cold_start_seconds':inference['cold_start_seconds'],
    'peak_working_set_bytes':inference.get('peak_working_set_bytes'),'hardware':inference['hardware'],'packages':inference['packages'],
    'gates':gates,'passed_numerical_gates':all(gate['passed'] for gate in gates.values()),
    'ticket_16_complete':False,'production_reference_changed':False,'capability':'RESEARCH_LIMITED',
    'limitations':frozen['limitations']+['HOLDOUT_COVERAGE_GATES_STRUCTURALLY_INCOMPATIBLE_SEE_PREFLIGHT','NO_INDEPENDENT_VALIDITY_CLAIM','NOT_FINBERT2','NO_TRADING_OR_RETURN_PROBABILITY'],
}
(out / 'evaluation-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
