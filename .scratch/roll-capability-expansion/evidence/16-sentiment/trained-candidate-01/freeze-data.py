"""Data-only freeze, no model imports or outputs. One immutable candidate attempt."""
import json,hashlib,re,sys
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
p=Path(__file__).resolve().parent;b=p.parent
sys.path.insert(0,str(b/'train-06'))
from object_contract_candidate import project
load=lambda path:json.loads(path.read_bytes())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def normalize(r,label,split,event=None):
 r=dict(r);r['id']=r.get('review_id') or str(r.get('id',r.get('index')));r['label']=label;r['split']=split
 r['projection']=project(r['title'],r['summary']);r['input_text']=r['projection']['text'];r['input_sha256']=hashlib.sha256(r['input_text'].encode()).hexdigest()
 r['source_text_sha256']=hashlib.sha256((r['title']+'\n'+r['summary']).encode()).hexdigest()
 r['label_origin']='AGENT_NON_INDEPENDENT_BEFORE_TRAINING_OR_NEW_MODEL_OUTPUT'
 r['event_id']=event or event_group(r)
 return r
def event_group(r):
 t=r['projection']['text'];date=r['date'][:10];year=date[:4]
 if '铜箔' in t and any(v in t for v in ['分拆','上市','创业板','预案','更正']):return 'ISSUER-COPPER-FOIL-SPINOFF-2022-2026'
 if re.search('涨|跌|走高|走低|走强|走弱|上扬|重挫',t) and not re.search('利润|盈利|业绩|评级|目标价',t):return 'COMPANY-MARKET-SESSION-'+date
 if re.search('净利|利润|盈利|业绩预增|业绩预减|半年报|年报点评|季度业绩',t):
  years=re.findall(r'20[12][0-9]',t);fiscal=years[0] if years else str(int(year)-1) if date[5:7] in ['01','02','03'] and not re.search('一季|Q1|前三|三季',t) else year
  period='Q1' if re.search('一季|第一季|Q1|1Q|首季',t) else 'H1' if re.search('半年|中期|1H',t) else 'Q3' if re.search('三季|第三季|Q3',t) else 'FY'
  return 'ISSUER-REPORT-'+fiscal+'-'+period
 if re.search('股东大会|股东周年大会|股东会',t):
  y=re.search(r'(20[12][0-9])年',t);return 'ISSUER-AGM-'+(y[1] if y else year)+('-EXTRA' if '临时' in t else '')
 return 'ISSUER-DISCLOSURE-BUNDLE-'+date
train=[r for r in load(b/'train-08/training-reviewed-audit.json')['rows'] if r['include_eligible']]
# First stabilize all415 source/annotation choices, then deterministic hash selection400.
train=sorted(train,key=lambda r:hashlib.sha256((r['source_file']+'|'+r['review_id']).encode()).hexdigest())
correction=next(r for r in train if r['review_id']=='T375')
train=[correction]+[r for r in train if r is not correction][:399]
train=[normalize(r,r['label'],'TRAIN') for r in train]
dev=[normalize(r,r['label'],'DEVELOPMENT') for r in load(b/'train-08/development-reviewed-audit.json')['rows'] if r['include_eligible']][:120]
primary=[]
P=[1,4,5,6,8,11,13,14,15,17,18,19,22,24,25,26,27,29,31,34,36,37,39,40,41,42,43,45,47,48]
U=[1,2,3,7,8,9,11,12,13,15,19,20,21,28,31,33,34,35,36,37,41,43,47,49,83,96,110,116,117,141]
I=[1,2,6,7,9,11,14,17,18,20,22,25,26,27,28,29,31,33,34,36,37,50,59,60,65,66,67,70,71,72]
for label,name,ids in [('POSITIVE','primary-positive-annotation-pool.json',P),('NEUTRAL','primary-neutral-annotation-pool.json',U),('IRRELEVANT','primary-irrelevant-pool.json',I)]:
 pool=load(b/'train-06'/name)['rows']
 for n in ids:
  r=pool[n-1]
  if label=='IRRELEVANT':
   # Group same instrument/fund A/C classes and same daily report. Never label genuine issuer notices I merely because projection fails.
   title=r['title'];instrument=title.split('指数')[0]+'指数' if '指数' in title else title.split('净值')[0].rstrip('AC') if '净值' in title else title.split('股价')[0].split('收盘')[0]
   event='OTHER-OBJECT-'+instrument+'-'+r['date'][:10]
   rationale='Actual title/summary concerns fund/index/another issuer or sector; no target-company directional assertion. Individually read independently of projection rejection.'
  elif label=='POSITIVE':event='COMPANY-MARKET-SESSION-'+r['date'][:10];rationale='Explicit contemporaneous target company price rise; morning prior-session recap rows omitted.'
  else:
   event=None;rationale='No directional comparison in actual target snippet; procedural/ownership/absolute amount/explicit lack of direct mineral right. Not inferred full-article sentiment.'
   if n in [21]:event='ISSUER-PARENT-H-SHARE-PURCHASE-2025'
   if n in [34,35,36]:event='ISSUER-BOARD10-2025-06-13'
   if n in [83]:event='ISSUER-CHAIR-RETIREMENT-2026-07-07'
   if n in [96]:event='ISSUER-AGM-2025'
  row=normalize(r,label,'HOLDOUT_PRIMARY',event);row['label_rationale']=rationale;primary.append(row)
negative=load(b/'train-06/primary-negative-source-audit.json')['rows']
pool=load(b/'train-08/candidate-rows.json')['items']
for r in negative:
 if r['exclude_from_primary'] is not None:continue
 matches=[x for x in pool if x['source_file']==r['source_file'] and str(x.get('id',x.get('index')))==str(r['source_id'])]
 assert len(matches)==1,(r['source_file'],r['source_id'])
 row=normalize(matches[0],'NEGATIVE','HOLDOUT_PRIMARY',r['event_id']);assert row['input_sha256']==r['input_sha256']
 row['label_rationale']=r['label_basis'];row['event_date']=r['event_date'];row['id']='N'+str(len([x for x in primary if x['label']=='NEGATIVE'])+1).zfill(3);primary.append(row)
assert len(train)==400 and len(dev)==120 and len(primary)==120
assert len({r['input_sha256'] for r in train})==400
for rows in [train,dev,primary]:
 assert len({r['source_text_sha256'] for r in rows})==len(rows)
 scored=[r for r in rows if r['input_text']];assert len({r['input_sha256'] for r in scored})==len(scored)
 assert len({r['id'] for r in rows})==len(rows)
for a,c in [(train,dev),(train,primary),(dev,primary)]:
 assert not {r['input_sha256'] for r in a if r['input_text']}&{r['input_sha256'] for r in c if r['input_text']}
 assert not {r['event_id'] for r in a}&{r['event_id'] for r in c},[(r['id'],r['event_id'],r['title']) for r in a+c if r['event_id'] in ({r['event_id'] for r in a}&{r['event_id'] for r in c})]
assert all(r['date'][:10]<='2022-12-31' for r in train)
assert all('2023-01-01'<=r['date'][:10]<='2024-12-31' for r in dev)
assert all(r['date'][:10]>='2025-01-01' for r in primary)
support={label:{'rows':sum(r['label']==label for r in primary),'event_groups':len({r['event_id'] for r in primary if r['label']==label})} for label in ['POSITIVE','NEGATIVE','NEUTRAL','IRRELEVANT']}
assert all(x['rows']==30 and x['event_groups']>=10 for x in support.values()),support
assert all(not r['input_text'] for r in primary if r['label']=='IRRELEVANT')
# Named source/script files and all manifests are frozen before importing torch or fitting.
for name,rows in [('training.json',train),('development.json',dev),('primary.json',primary)]:
 assert not (p/name).exists();(p/name).write_bytes(json.dumps({'labeler':'AGENT_NON_INDEPENDENT','scope':'Actual archived title/summary; not whole-article labels','rows':rows},ensure_ascii=False,indent=2).encode())
settings={'seed':42,'cpu_threads':2,'precision':'float32','max_length':256,'learning_rate':2e-5,'batch_size':4,'maximum_epochs':2,'maximum_seconds':3600,'weight_decay':.01,'gradient_clip_norm':1.0}
freeze={'at':datetime.now(timezone.utc).isoformat(),'status':'FROZEN_BEFORE_TRAINING','complete_data_gate':True,'counts':{'TRAIN':400,'DEVELOPMENT':120,'HOLDOUT_PRIMARY':120},'support':support,'training_file':'training.json','training_sha256':sha(p/'training.json'),'training_script_sha256':sha(p/'train_candidate.py'),'training_settings':settings,'files':{n:sha(p/n) for n in ['training.json','development.json','primary.json','object_contract.py','protocol.md','freeze-data.py','train_candidate.py','infer.py','score.py']},'source_sha256':load(b/'train-08/candidate-inventory.json')['source_sha256'],'annotation_sha256':{str(f.relative_to(b)):sha(f) for f in [b/'train-06/training-annotations.json',b/'train-06/primary-negative-source-audit.json',b/'train-08/training-reviewed-audit.json',b/'train-08/development-reviewed-audit.json']},'confidence_floor':.65,'gates':{'binary_macro_f1':.60,'positive_recall':.55,'negative_recall':.55,'three_class_macro_f1':.60,'neutral_recall':.55,'irrelevant_rejection':.80,'maximum_total_rejection':.35,'maximum_cpu_p95_seconds':3.0},'limitations':['Non-independent agent labels','Only one issuer, stratified snippet challenge; not natural news flow coverage','Unknown overlap with base model original private training data','PDF correction body read as source evidence; labels still concern frozen snippet inputs','Distinct nonempty projected inputs; irrelevant rows have empty projection but distinct full source texts']}
(p/'training-freeze.json').write_bytes(json.dumps(freeze,ensure_ascii=False,indent=2).encode())
print('FROZEN',support,Counter(r['label'] for r in train),Counter(r['label'] for r in dev))
