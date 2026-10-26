"""Score the one primary run using the existing audited abstention/FN/FP metric implementation."""
import hashlib,json,math,statistics,sys
from pathlib import Path
from collections import Counter
p=Path(__file__).resolve().parent;repo=p.parents[4]
sys.path.insert(0,str(repo/'backend/src'))
from roll.market.sentiment_evaluation import evaluate_confusion
f=json.loads((p/'training-freeze.json').read_bytes());i=json.loads((p/'inference.json').read_bytes())
assert i['status']=='COMPLETE' and len(i['rows'])==240
expected={r['id']:r for name in ['development.json','primary.json'] for r in json.loads((p/name).read_bytes())['rows']}
assert len(expected)==240 and len({r['id'] for r in i['rows']})==240
for r in i['rows']:assert all(r[k]==expected[r['id']][k] for k in ['label','split','input_sha256','event_id'])
def metric(rows):
 m=evaluate_confusion(dict(Counter(r['label']+'->'+r['prediction'] for r in rows)))
 m['binary_macro_f1']=m.pop('macro_f1');m['three_class_macro_f1']=sum(m['per_class'][k]['f1'] for k in ['POSITIVE','NEGATIVE','NEUTRAL'])/3
 m['total_rejection']=sum(r['prediction'].startswith('ABSTAIN_') for r in rows)/len(rows)
 ir=[r for r in rows if r['label']=='IRRELEVANT'];m['irrelevant_rejection']=sum(r['prediction'].startswith('ABSTAIN_') for r in ir)/len(ir) if ir else None
 for label,c in m['per_class'].items():c['event_groups']=len({r['event_id'] for r in rows if r['label']==label})
 return m
splits={s:metric([r for r in i['rows'] if r['split']==s]) for s in ['DEVELOPMENT','HOLDOUT_PRIMARY']}
m=splits['HOLDOUT_PRIMARY'];lat=sorted(r['latency_seconds'] for r in i['rows'] if r['split']=='HOLDOUT_PRIMARY' and r['latency_seconds'] is not None)
actual={'binary_macro_f1':m['binary_macro_f1'],'positive_recall':m['positive_recall'],'negative_recall':m['negative_recall'],'three_class_macro_f1':m['three_class_macro_f1'],'neutral_recall':m['per_class']['NEUTRAL']['recall'],'irrelevant_rejection':m['irrelevant_rejection'],'maximum_total_rejection':m['total_rejection'],'maximum_cpu_p95_seconds':lat[math.ceil(.95*len(lat))-1]}
gates={k:{'actual':v,'threshold':f['gates'][k],'operator':'<=' if k.startswith('maximum') else '>=','passed':v<=f['gates'][k] if k.startswith('maximum') else v>=f['gates'][k]} for k,v in actual.items()}
report={'evidence_kind':'REAL_SINGLE_TRAINED_CANDIDATE_OFFLINE_EVALUATION_NON_INDEPENDENT_LABELS','splits':splits,'gates':gates,'passed_frozen_gates':all(v['passed'] for v in gates.values()),'primary_model_calls':len(lat),'primary_p95_seconds':lat[math.ceil(.95*len(lat))-1],'all_model_calls':sum(r['latency_seconds'] is not None for r in i['rows']),'cold_start_seconds':i['cold_start_seconds'],'peak_working_set_bytes':i['peak_working_set_bytes'],'training_freeze_sha256':hashlib.sha256((p/'training-freeze.json').read_bytes()).hexdigest(),'inference_sha256':hashlib.sha256((p/'inference.json').read_bytes()).hexdigest(),'limitations':f['limitations'],'capability':'RESEARCH_LIMITED','formal_grant':'NOT_GRANTED','production_component_changed':False,'old_holdouts_reevaluated':False}
(p/'evaluation-results.json').write_bytes(json.dumps(report,ensure_ascii=False,indent=2).encode());print(json.dumps(report,ensure_ascii=False,indent=2))
