"""Read-only audit of closed supplementary source ledgers and the immutable dataset freeze."""
import hashlib,json
from pathlib import Path
from collections import Counter
p=Path(__file__).resolve().parent;b=p.parent
load=lambda f:json.loads(f.read_bytes())
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
summary=[]
for phase,receipts,dirs,cap in [
 ('train-04',['acquisition-receipt.json','continuation-receipt.json'],['source','source-continuation'],64),
 ('train-05',['acquisition-receipt.json','continuation-receipt.json'],['source','source-continuation'],20),
 ('train-06',['acquisition-receipt.json'],['source'],5),
 ('train-07',['acquisition-receipt.json'],['source'],16),
 ('train-08',['acquisition-receipt.json'],['source'],5)]:
 root=b/phase;count=0;size=0;seconds=0.;verified=0;failed=0
 for name,folder in zip(receipts,dirs):
  ledger=load(root/name);count+=len(ledger['requests']);size+=ledger['bytes'];seconds+=ledger.get('transfer_seconds',ledger.get('elapsed_seconds',0))
  for request in ledger['requests']:
   if 'sha256' not in request:failed+=1;continue
   candidates=[f for f in root.rglob(request['file']) if sha(f)==request['sha256']]
   assert len(candidates)==1,(phase,request['file'],len(candidates))
   assert candidates[0].stat().st_size==request['bytes'];verified+=1
 assert count==cap
 summary.append({'phase':phase,'http_attempts':count,'bytes':size,'seconds':seconds,'verified_raws':verified,'no_response_attempts':failed})
for phase,name in [('train-06','acquisition-freeze.json'),('train-07','acquisition-freeze.json'),('train-08','acquisition-freeze.json'),('train-08','pdf-freeze.json')]:
 for n,h in load(b/phase/name)['files'].items():assert sha(b/phase/n)==h,(phase,n)
pdf=load(b/'train-08/pdf-receipt.json');assert sha(b/'train-08/correction-20220223.pdf')==pdf['requests'][0]['sha256']
f=load(p/'training-freeze.json')
for name,h in f['files'].items():assert sha(p/name)==h,name
for name,h in f['source_sha256'].items():assert sha(b/name)==h,name
for name,h in f['annotation_sha256'].items():assert sha(b/name)==h,name
sets={name:load(p/(name+'.json'))['rows'] for name in ['training','development','primary']}
assert [len(sets[n]) for n in sets]==[400,120,120]
for name,rows in sets.items():
 assert len({r['source_text_sha256'] for r in rows})==len(rows)
 for r in rows:assert hashlib.sha256(r['input_text'].encode()).hexdigest()==r['input_sha256']
for a,c in [('training','development'),('training','primary'),('development','primary')]:
 assert not {r['event_id'] for r in sets[a]}&{r['event_id'] for r in sets[c]}
 assert not {r['input_sha256'] for r in sets[a] if r['input_text']}&{r['input_sha256'] for r in sets[c] if r['input_text']}
report={'status':'VERIFIED_BEFORE_INFERENCE','source_ledgers':summary,'pdf_http_attempts':1,'pdf_bytes':pdf['bytes'],'pdf_seconds':pdf['transfer_seconds'],'training_freeze_sha256':sha(p/'training-freeze.json'),'support':f['support'],'training_labels':dict(Counter(r['label'] for r in sets['training'])),'development_labels':dict(Counter(r['label'] for r in sets['development'])),'new_model_evaluation_count_at_audit':0,'limitations':f['limitations']}
(p/'source-verification.json').write_bytes(json.dumps(report,ensure_ascii=False,indent=2).encode());print(json.dumps(report,ensure_ascii=False,indent=2))
