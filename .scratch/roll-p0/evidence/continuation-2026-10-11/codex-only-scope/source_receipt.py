import hashlib,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[5]
evidence=Path(__file__).parent
protected=json.loads((root/'.scratch/roll-p0/evidence/codex-review-repairs-2026-10-11/source-final.json').read_text(encoding='utf-8'))[:15]
paths=[r['path'] for r in protected]+['backend/src/roll/app.py','backend/src/roll/agents/settings.py','backend/src/roll/agents/deepseek_evidence.py','backend/src/roll/research/technical_review.py','frontend/src/components/backend-panel.tsx','frontend/src/pages/evidence.tsx']
receipt=[]
for name in paths:
    content=(root/name).read_bytes();receipt.append({'path':name,'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()})
assert receipt[:15]==protected
mode=sys.argv[1]
if mode=='final':assert receipt==json.loads((evidence/'source-after.json').read_text(encoding='utf-8'))
(evidence/('source-'+mode+'.json')).write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(mode+':12 model+3 calculation sources unchanged')
