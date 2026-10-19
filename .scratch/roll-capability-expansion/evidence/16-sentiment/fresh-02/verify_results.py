"""Post-result integrity and independent arithmetic only; never calls the model."""
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

out = Path(__file__).resolve().parent
repo = out.parents[4]
def read(name):
    return json.loads((out/name).read_bytes())
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

manifest = read('evaluation-freeze.json')
for name, expected in manifest['files'].items():
    assert digest(out/name) == expected, name
assert digest(repo/'backend/src/roll/market/sentiment-reference.json') == manifest['production_reference_sha256']
frozen, inference, result = map(read, ('frozen-evaluation.json','inference.json','evaluation-results.json'))
assert inference['status'] == 'COMPLETE'
assert datetime.fromisoformat(manifest['frozen_at']) < datetime.fromisoformat(inference['started_at'])
assert inference['evaluation_freeze_sha256'] == digest(out/'evaluation-freeze.json')
assert result['inference_sha256'] == digest(out/'inference.json')
assert inference['old_holdout_loaded'] is False and inference['training'] is False and inference['network_calls'] == 0

raw_hashes = set()
for receipt, directory in [('acquisition-receipt.json','source-03'),('acquisition04-receipt.json','source-04'),
                           ('acquisition05-receipt.json','source-05'),('acquisition06-receipt.json','source-06'),
                           ('pdf07-receipt.json','source-pdf07'),('pdf08-receipt.json','source-pdf08')]:
    for item in read(receipt)['requests']:
        assert digest(out/directory/item['file']) == item['sha256']
        raw_hashes.add(item['sha256'])
source_rows = {}
for name, prefix in (('corpus.json','03'),('corpus04.json','04'),('corpus06.json',None)):
    for row in read(name)['items']:
        assert row['raw_sha256'] in raw_hashes
        source_id = row['id'] if prefix is None else prefix+'-'+str(row['index'])
        source_rows[(name,source_id)] = row
pred = {r['id']:r for r in inference['rows']}
assert len(pred) == len(frozen['rows']) == 134
events = defaultdict(set)
for row in frozen['rows']:
    source = source_rows[(row['source_file'],row['id'])]
    # Verified issuer-prefix and located PDF text adapters are recorded in the frozen row.
    assert row['url'] == source['url'] and row['date'] == source['date']
    assert row['raw_sha256'] == source['raw_sha256']
    assert digest(out/row['pdf_reference']['path']) == row['pdf_reference']['sha256'] if row.get('pdf_reference') else True
    actual = pred[row['id']]
    assert all(actual[k] == row[k] for k in ('label','split','event_id','input_sha256'))
    assert hashlib.sha256(row['projection']['text'].encode()).hexdigest() == row['input_sha256']
    events[row['split']].add(row['event_id'])
    if row['split']=='DEVELOPMENT':
        assert row['date'][:10] < '2016-01-01'
    else:
        assert row['date'][:10] >= '2016-01-01'
assert not events['DEVELOPMENT'] & (events['HOLDOUT_PRIMARY'] | events['HOLDOUT_STRESS'])

for split in ('DEVELOPMENT','HOLDOUT_PRIMARY','HOLDOUT_STRESS'):
    rows = [r for r in inference['rows'] if r['split']==split]
    confusion = Counter(r['label']+'->'+r['prediction'] for r in rows)
    published = result['splits'][split]
    assert dict(confusion) == published['confusion']
    fs = {}
    for label in ('POSITIVE','NEGATIVE','NEUTRAL','IRRELEVANT'):
        support = sum(r['label']==label for r in rows)
        tp = sum(r['label']==label and r['prediction']==label for r in rows)
        fp = sum(r['label']!=label and r['prediction']==label for r in rows)
        fn = support-tp
        m = published['per_class'][label]
        assert (support,tp,fp,fn)==(m['support'],m['tp'],m['fp'],m['fn'])
        recall = tp/support if support else None
        f1 = 2*tp/(2*tp+fp+fn) if support else None
        assert recall==m['recall'] and f1==m['f1']
        fs[label]=f1
    binary = (fs['POSITIVE']+fs['NEGATIVE'])/2 if all(fs[x] is not None for x in ('POSITIVE','NEGATIVE')) else None
    three = sum(fs[x] for x in ('POSITIVE','NEGATIVE','NEUTRAL'))/3 if all(fs[x] is not None for x in ('POSITIVE','NEGATIVE','NEUTRAL')) else None
    assert binary==published['binary_macro_f1'] and three==published['three_class_macro_f1']
    assert published['abstain_coverage']==sum(r['prediction'].startswith('ABSTAIN_') for r in rows)/len(rows)

failures=[name for name,g in result['gates'].items() if not g['passed']]
assert failures==['negative_recall'] and result['passed_frozen_gates'] is False
byid={r['id']:r for r in frozen['rows']}
groups=defaultdict(Counter)
for row in inference['rows']:
    if row['split']=='HOLDOUT_PRIMARY' and row['label']=='NEGATIVE':
        kind='ASSET_IMPAIRMENT_TITLE' if row['id'].startswith('CNI-') else 'EXPLICIT_PRICE_DECLINE'
        groups[kind][row['prediction']]+=1
report={'status':'VERIFIED','model_calls':100,'primary_rows':120,'frozen_files_unchanged':True,
        'raw_and_pdf_hashes_verified':len(raw_hashes),'production_reference_unchanged':True,
        'independent_arithmetic_matches':True,'failed_gates':failures,'negative_diagnostic':dict(groups),
        'no_new_inference':True,'not_a_new_accuracy_experiment':True}
(out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
