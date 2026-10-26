"""Audit captured artifacts and reported metrics without executing the model."""
import hashlib
import json
import math
from pathlib import Path

out = Path(__file__).resolve().parent
repo = Path(__file__).resolve().parents[5]
manifest = json.loads((out/'freeze-manifest.json').read_bytes())
assert all(hashlib.sha256((out/name).read_bytes()).hexdigest()==digest for name,digest in manifest['files'].items())
assert hashlib.sha256((repo/'backend/src/roll/market/sentiment-reference.json').read_bytes()).hexdigest()==manifest['production_reference_sha256']
dataset = json.loads((out/'frozen-dataset.json').read_bytes())
assert all(hashlib.sha256((out.parent/name).read_bytes()).hexdigest()==digest for name,digest in dataset['source_sha256'].items())
dev = [row for row in dataset['included'] if row['split']=='DEVELOPMENT']
holdout = [row for row in dataset['included'] if row['split']=='HOLDOUT']
assert len(dev)+len(holdout)==138
assert max(row['date'] for row in dev)<min(row['date'] for row in holdout)
assert not ({row['group_id'] for row in dev}&{row['group_id'] for row in holdout})
inference = json.loads((out/'inference.json').read_bytes())
assert inference['status']=='COMPLETE' and inference['network_calls']==0 and not inference['training']
assert not any(inference['loading_info'].values())
report = json.loads((out/'evaluation-results.json').read_bytes())
assert hashlib.sha256((out/'inference.json').read_bytes()).hexdigest()==report['inference_sha256']
for split, value in report['splits'].items():
    rows = [row for row in inference['rows'] if split=='ALL_DIAGNOSTIC' or row['split']==split]
    assert len(rows)==value['rows']==sum(value['confusion'].values())
    for label, measured in value['per_class'].items():
        support = sum(row['label']==label for row in rows)
        tp = sum(row['label']==label and row['prediction']==label for row in rows)
        predicted = sum(row['prediction']==label for row in rows)
        assert measured['support']==support and measured['tp']==tp
        assert measured['fn']==support-tp and measured['fp']==predicted-tp
        if support:
            assert math.isclose(measured['recall'],tp/support)
            assert math.isclose(measured['f1'],2*tp/(support+predicted))
        else:
            assert measured['recall'] is None
    assert math.isclose(value['abstain_coverage'],sum(row['prediction'].startswith('ABSTAIN_') for row in rows)/len(rows))
assert report['passed_numerical_gates'] is False and report['ticket_16_complete'] is False
receipt = json.loads((out/'download03-receipt.json').read_bytes())
plan = json.loads((out/'download03-plan.json').read_bytes())
assert receipt['status']=='DOWNLOADED_VERIFIED'
assert all(hashlib.sha256((repo/plan['destination']/item['path']).read_bytes()).hexdigest()==item['sha256'] for item in receipt['artifacts'])
result = {'status':'PASS','checks':['six pinned model artifact hashes','frozen evaluation source hashes','138 labels and disjoint groups/dates','exact checkpoint loading','all split support/TP/FN/FP/recall/F1 independently recounted','all confusion row totals and abstention rates','production reference unchanged','numerical gate failure retained'], 'prediction_count':len(inference['rows']),'model_calls':report['latency']['model_calls'],'production_reference_unchanged':True}
(out/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
