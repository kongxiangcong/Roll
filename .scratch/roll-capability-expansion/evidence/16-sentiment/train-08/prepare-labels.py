"""Record reviewed labels, source/event embargo and candidate splits before any model run."""
import json,hashlib,re
from collections import Counter
from pathlib import Path
p=Path(__file__).resolve().parent;b=p.parent
load=lambda path:json.loads(path.read_bytes())
old=load(b/'train-06/training-annotations.json')['rows']
# Fiscal reporting release family covers forecast/final results and contemporaneous impairment notice.
# Old exposed revision and AGM chains cannot become training material via a different URL/title.
embargo_T=set([425,12,14,61,62,73,74,75,85,110,111,112,117,152,153,154,155,157,203,*range(209,220),*range(317,324),*range(356,366),367,368,369,*range(408,419)])
for r in old:
 i=int(r['review_id'][1:])
 if i in embargo_T:r.update(include_eligible=False,event_embargo='OLD_EXPOSED_REPORTING_OR_GOVERNANCE_CHAIN')
new=load(p/'additional-training-pool.json')['rows']
P={94,95,97,98,99,104,105,106};N={88,89,90,91,92,93,96}
embargo_A={6,7,8,9,10,11,12,13,15,16,17,18,19,*range(31,39),47,48,*range(56,60),*range(62,72),77,85,86,103,108}
uncertain_A={40,42,43,45,83,109}
for r in new:
 i=int(r['review_id'][1:]);r['label']='UNCERTAIN' if i in uncertain_A else 'POSITIVE' if i in P else 'NEGATIVE' if i in N else 'NEUTRAL'
 r['label_rationale']='Explicit projected company price rise/raised target' if i in P else 'Explicit projected company price decline' if i in N else 'Procedure/ownership/appointment/disclosure without directional comparison; snippet label only'
 r['annotation_origin']='AGENT_NON_INDEPENDENT_BEFORE_MODEL_OUTPUT'
 r['include_eligible']=i not in embargo_A|uncertain_A
 if i in embargo_A:r['event_embargo']='OLD_EXPOSED_REPORTING_OR_GOVERNANCE_CHAIN'
 if i in uncertain_A:r['label_rationale']='Lawsuit/closure/review title lacks sufficient single directional proposition'
allrows=old+new
train=[r for r in allrows if r['include_eligible']]
# Reproducible source-only ordering, no sampling by model result.
train=sorted(train,key=lambda r:(r['date'],r['source_file'],r['review_id']))
print('TRAIN eligible',len(train),Counter(r['label'] for r in train))
# Development texts were read individually; no fitting/model selection allowed.
dev=load(b/'train-06/development-annotation-pool.json')['rows']
DP={1,19,20,21,22,27,29,45,46,47,64,67,68,69,71,79,86,98,99,113,114,120,121,125,136,137,138,139,140,141,145,146,147}
DN={7,9,10,50,52,55,76,77,96,100,107,108,109,112,115,116,118,124,126,127,128,129,130,131,132,133,134,135,142,143,144,148,149,150}
DX={6,28,54,58,89,119}
DE={*range(11,17),*range(40,46),*range(50,59),118}
trainhash={r['input_sha256'] for r in train};devkeep=[]
for r in dev:
 i=int(r['review_id'][1:]);r['label']='UNCERTAIN' if i in DX else 'POSITIVE' if i in DP else 'NEGATIVE' if i in DN else 'NEUTRAL'
 r['input_text']=r['projection']['text'];r['input_sha256']=hashlib.sha256(r['input_text'].encode()).hexdigest()
 r['include_eligible']=i not in DE|DX and r['input_sha256'] not in trainhash
 r['annotation_origin']='AGENT_NON_INDEPENDENT_BEFORE_MODEL_OUTPUT'
 r['label_rationale']='Explicit growth/rise/favorable opinion' if i in DP else 'Explicit decline/downward target/unfavorable opinion' if i in DN else 'No directional assertion in projected source snippet'
 if r['include_eligible']:devkeep.append(r)
print('DEV eligible',len(devkeep),Counter(r['label'] for r in devkeep))
for name,obj in [('training-reviewed-audit.json',{'rows':allrows}),('development-reviewed-audit.json',{'rows':dev})]:
 (p/name).write_bytes(json.dumps(obj,ensure_ascii=False,indent=2).encode())
