"""Frozen primary gates; all abstentions remain in truth-label denominators."""
import hashlib
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path

out=Path(__file__).resolve().parent
repo=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(repo/'backend/src'))
from roll.market.sentiment_evaluation import evaluate_confusion

frozen=json.loads((out/'frozen-evaluation.json').read_bytes())
inference=json.loads((out/'inference.json').read_bytes())
assert inference['status']=='COMPLETE'
assert len(inference['rows'])==len(frozen['rows'])
expected={row['id']:row for row in frozen['rows']}
assert len({row['id'] for row in inference['rows']})==len(expected)
for row in inference['rows']:
    assert all(row[key]==expected[row['id']][key] for key in ('split','event_id','label','input_sha256'))


def metrics(rows):
    value=evaluate_confusion(dict(Counter(row['label']+'->'+row['prediction'] for row in rows)))
    value['binary_macro_f1']=value.pop('macro_f1')
    f1=[value['per_class'][label]['f1'] for label in ('POSITIVE','NEGATIVE','NEUTRAL')]
    value['three_class_macro_f1']=sum(f1)/3 if all(item is not None for item in f1) else None
    value['rows']=len(rows)
    value['event_groups']=len({row['event_id'] for row in rows})
    for label in value['per_class']:
        value['per_class'][label]['event_groups']=len({row['event_id'] for row in rows if row['label']==label})
    rejected=[row for row in rows if row['prediction'].startswith('ABSTAIN_')]
    value['reject_counts']=dict(Counter(row['prediction'] for row in rejected))
    value['abstain_coverage']=len(rejected)/len(rows)
    irrelevant=[row for row in rows if row['label']=='IRRELEVANT']
    value['irrelevant_rejection_rate']=sum(row['prediction'].startswith('ABSTAIN_') for row in irrelevant)/len(irrelevant) if irrelevant else None
    return value


values={split:metrics([row for row in inference['rows'] if row['split']==split]) for split in ('DEVELOPMENT','HOLDOUT_PRIMARY','HOLDOUT_STRESS')}
values['ALL_DIAGNOSTIC']=metrics([row for row in inference['rows'] if row['split']!='HOLDOUT_STRESS'])
latencies=sorted(row['latency_seconds'] for row in inference['rows'] if row['latency_seconds'] is not None)
latency={'model_calls':len(latencies),'p50_seconds':statistics.median(latencies),'p95_seconds':latencies[math.ceil(.95*len(latencies))-1]}
p=values['HOLDOUT_PRIMARY'];threshold=frozen['gates']
checks={
    'binary_macro_f1':p['binary_macro_f1'],'positive_recall':p['positive_recall'],'negative_recall':p['negative_recall'],
    'three_class_macro_f1':p['three_class_macro_f1'],'neutral_recall':p['per_class']['NEUTRAL']['recall'],
    'irrelevant_rejection_rate':p['irrelevant_rejection_rate'],'abstain_coverage':p['abstain_coverage'],'model_p95_seconds':latency['p95_seconds'],
}
gates={key:{'actual':actual,'threshold':threshold[key],'operator':'<=' if key in ('abstain_coverage','model_p95_seconds') else '>=',
            'passed':actual is not None and (actual<=threshold[key] if key in ('abstain_coverage','model_p95_seconds') else actual>=threshold[key])} for key,actual in checks.items()}
support_ok=p['rows']>=threshold['primary_count'] and all(p['per_class'][label]['support']>=30 and p['per_class'][label]['event_groups']>=threshold['minimum_event_groups_per_class'] for label in ('POSITIVE','NEGATIVE','NEUTRAL','IRRELEVANT'))
primary=[row for row in frozen['rows'] if row['split']=='HOLDOUT_PRIMARY'];dev=[row for row in frozen['rows'] if row['split']=='DEVELOPMENT']
isolation_ok=max(row['date'] for row in dev)<min(row['date'] for row in primary) and not ({row['event_id'] for row in dev}&{row['event_id'] for row in primary})
source_ok=True
for row in frozen['rows']:
    if row.get('pdf_reference'):
        ref=row['pdf_reference'];source_ok=source_ok and hashlib.sha256((out/ref['path']).read_bytes()).hexdigest()==ref['sha256']
predictions={row['id']:row for row in inference['rows']}
pair={'members':['04-137','04-145'],'same_input':predictions['04-137']['input_sha256']==predictions['04-145']['input_sha256'],
      'same_prediction':predictions['04-137']['prediction']==predictions['04-145']['prediction'],'counts_once_in_primary':True}
report={'evidence_kind':'REAL_LOCAL_FRESH_EVALUATION_NON_INDEPENDENT_LABELS','model':frozen['model'],'object_version':'sentiment-object-v2-fresh',
        'dataset_sha256':hashlib.sha256((out/'frozen-evaluation.json').read_bytes()).hexdigest(),'inference_sha256':hashlib.sha256((out/'inference.json').read_bytes()).hexdigest(),
        'splits':values,'gates':gates,'support_gate':support_ok,'event_time_isolation_gate':isolation_ok,'source_pdf_hash_gate':source_ok,
        'passed_frozen_gates':all(gate['passed'] for gate in gates.values()) and support_ok and isolation_ok and source_ok,
        'latency':latency,'cold_start_seconds':inference['cold_start_seconds'],'peak_working_set_bytes':inference['peak_working_set_bytes'],
        'hardware':inference['hardware'],'packages':inference['packages'],'republication_pair':pair,'source_features':frozen['source_features'],
        'limitations':frozen['limitations'],'capability':'RESEARCH_LIMITED','formal_grant':'NOT_GRANTED','old_holdout_reevaluated':False,
        'production_component_changed':False,'ticket_complete_requires_api_page_runtime_acceptance':True}
(out/'evaluation-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'passed_frozen_gates':report['passed_frozen_gates'],'primary':p,'gates':gates,'latency':latency,'pair':pair},ensure_ascii=False,indent=2))
