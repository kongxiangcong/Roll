"""Freeze reviewed labels and provenance before the first fresh evaluation."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

out = Path(__file__).resolve().parent
target = out/'frozen-evaluation.json'
assert not target.exists()
value = json.loads((out/'labels-draft.json').read_bytes())
pdfs = {}
for name,folder in (('pdf07-text.json','source-pdf07'),('pdf08-text.json','source-pdf08')):
    for item in json.loads((out/name).read_bytes()):
        pdfs['CNI-'+item['announcement_id']] = {'path':folder+'/'+item['announcement_id']+'.pdf','sha256':item['sha256'],'page_count':len(item['pages'])}
for row in value['rows']:
    if row['id'] in pdfs:
        row['pdf_reference'] = pdfs[row['id']]
    if row.get('visual_source'):
        row['visual_source']['pdf_sha256'] = pdfs[row['id']]['sha256']
        row['visual_source']['image_sha256'] = hashlib.sha256((out/row['visual_source']['image']).read_bytes()).hexdigest()
    if row['split']=='HOLDOUT_STRESS':
        original = next(item for item in value['rows'] if item['id']==row['paired_with'])
        assert original['summary']==row['summary']
        row['shared_summary_sha256'] = hashlib.sha256(row['summary'].encode()).hexdigest()
        original['shared_summary_sha256'] = row['shared_summary_sha256']
value['frozen_at'] = datetime.now(timezone.utc).isoformat()
value['design_document'] = 'final-split-design.md'
value['gates'] = {'primary_count':120,'minimum_event_groups_per_class':10,'binary_macro_f1':.60,'positive_recall':.55,'negative_recall':.55,
                  'three_class_macro_f1':.60,'neutral_recall':.55,'irrelevant_rejection_rate':.80,'abstain_coverage':.35,'model_p95_seconds':3.0}
value['confidence_floor'] = .65
value['model'] = {'id':'yiyanghkust/finbert-tone-chinese','revision':'e91b1a3af10e1e8c9c03429d3cd7d5e9a1c8000d','weights_sha256':'0c25b105902f90d1e039d511944af4f49d1490f6698e701f2704a714ca74e66b','label_mapping':{'0':'NEUTRAL','1':'POSITIVE','2':'NEGATIVE'}}
value['known_pre_inference_object_misses'] = [row['id'] for row in value['rows'] if row['split']=='HOLDOUT_PRIMARY' and row['label']!='IRRELEVANT' and row['projection']['reject_reason']]
value['source_features'] = {
    'real_negation_visual_transcription':['CNI-62167749'],
    'real_complete_archived_report_revision_chain':['CNI-63213186','CNI-63261941','CNI-63261942'],
    'real_later_correction_notices':['CNI-1208664534','CNI-1210301354'],
    'shared_summary_republication':['04-137','04-145'],
    'explicit_shared_multi_company_predicate':['04-75','04-79'],
}
target.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'primary':120,'support':value['support'],'known_object_misses':value['known_pre_inference_object_misses'],'source_features':value['source_features']},ensure_ascii=False,indent=2))
