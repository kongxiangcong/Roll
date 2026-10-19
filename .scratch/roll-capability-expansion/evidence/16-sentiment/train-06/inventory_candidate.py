"""Source-only feasibility inventory; cue buckets are NOT gold labels."""
import hashlib,json,re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit
from object_contract_candidate import clean,project

out=Path(__file__).resolve().parent;base=out.parent
def canonical(url):
    u=urlsplit(url or '');return (u.hostname,u.path.rstrip('/'))
def textkey(row):
    return hashlib.sha256((clean(row.get('title'))+'\n'+clean(row.get('summary'))).encode()).hexdigest()
excluded_urls=set();excluded_text=set();excluded_titles=set();seen=set();items=[];sources={}
# Conservative: original two pools, old labels, and the complete exposed fresh02 set.
for name,key in [('corpus-attempt/corpus.json','items'),('corpus-name-attempt/corpus.json','items'),
                 ('labels-120.json','items'),('labels-holdout-30.json','items'),('fresh-02/frozen-evaluation.json','rows')]:
    body=(base/name).read_bytes();sources[name]=hashlib.sha256(body).hexdigest()
    for row in json.loads(body)[key]:
        if row.get('url'):excluded_urls.add(canonical(row['url']))
        excluded_text.add(textkey(row));excluded_titles.add(clean(row.get('title')))
counts=Counter()
for name in ('fresh-02/corpus.json','fresh-02/corpus04.json','fresh-02/corpus06.json','train-03/corpus.json',
             'train-03/sina-probe-corpus.json','train-03/remaining-corpus.json',
             'train-04/corpus.json','train-04/continuation-corpus.json',
             'train-05/corpus.json','train-05/continuation-corpus.json','train-06/corpus.json'):
    body=(base/name).read_bytes();sources[name]=hashlib.sha256(body).hexdigest()
    for row in json.loads(body)['items']:
        u=canonical(row['url']);t=textkey(row)
        if u in excluded_urls or t in excluded_text or clean(row['title']) in excluded_titles:
            counts['PREVIOUSLY_CAPTURED_OR_EVALUATED_CONSERVATIVE']+=1;continue
        if u in seen:counts['DUPLICATE_URL']+=1;continue
        seen.add(u)
        projection=project(row['title'],row['summary'])
        text=projection['text'];bucket='NO_OBJECT' if not text else 'DIRECTION_UNRESOLVED'
        if text:
            down=bool(re.search(r'跌|走低|走弱|回调|下[降滑]|减少|预减|预亏|亏损|停产|事故|处罚|风险',text))
            up=bool(re.search(r'涨|走高|走强|增[长加]|预增|上升|提升|扭亏|改善',text))
            bucket='BOTH_DIRECTION_CUES' if up and down else 'DOWN_CUE_REVIEW' if down else 'UP_CUE_REVIEW' if up else bucket
        item={**row,'source_file':name,'projection':projection,'cue_bucket':bucket,'text_sha256':t}
        items.append(item);counts[bucket]+=1
years={y:dict(Counter(r['cue_bucket'] for r in items if r['date'].startswith(y))) for y in sorted({r['date'][:4] for r in items})}
negative=[r for r in items if r['cue_bucket'] in ('DOWN_CUE_REVIEW','BOTH_DIRECTION_CUES')]
report={'status':'SOURCE_ONLY_NOT_TRAINING_READY','gold_labels':0,'counts':dict(counts),'remaining_unique':len(items),
        'by_year':years,'source_sha256':sources,'old_exclusions_are_not_relabeling':True,
        'cue_buckets_are_not_gold_labels':True,'no_model_calls':True}
periods={
    'TRAIN':[r for r in items if r['date'][:10]<='2022-12-31'],
    'DEVELOPMENT':[r for r in items if '2023-01-01'<=r['date'][:10]<='2024-12-31'],
    'HOLDOUT':[r for r in items if r['date'][:10]>='2025-01-01'],
}
report['fixed_period_source_upper_bounds']={name:{'raw_unique_candidates':len(rows),'object_projected_candidates':sum(bool(r['projection']['text']) for r in rows),
    'not_gold_labels':True,'cue_buckets':dict(Counter(r['cue_bucket'] for r in rows))} for name,rows in periods.items()}
report['training_400_raw_cardinality_gate']=len(periods['TRAIN'])>=400
report['training_started']=False
(out/'candidate-inventory.json').write_bytes(json.dumps(report,ensure_ascii=False,indent=2).encode())
(out/'candidate-rows.json').write_bytes(json.dumps({'items':items},ensure_ascii=False,indent=2).encode())
(out/'candidate-negative-review.txt').write_bytes('\n'.join(f"{r['source_file']}|{r.get('id',r.get('index'))}|{r['date']}|{r['projection']['text']}" for r in negative).encode())
print(json.dumps(report,ensure_ascii=False,indent=2));print('\nNEGATIVE CUE CANDIDATES (not labels)\n'+(out/'candidate-negative-review.txt').read_text(encoding='utf-8'))
