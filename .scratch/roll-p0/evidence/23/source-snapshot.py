"""Source and original model-fingerprint dependency preservation evidence."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4]
paths=['backend/src/roll/app.py','backend/src/roll/agents/settings.py','backend/src/roll/agents/codex_process.py','backend/src/roll/agents/deepseek_process.py','backend/src/roll/agents/review_runtime.py','backend/src/roll/research/technical_review.py',
    'frontend/src/pages/technical-review.tsx','frontend/src/pages/validation.tsx','frontend/src/pages/risk-policies.tsx','backend/tests/application/test_technical_review.py','frontend/tests/e2e/technical-review.spec.ts']
protected=['research/'+name+'.py' for name in ['models','execution','reconstruction','datasets','design','historical_costs','corporate_actions','registry','training_preflight']]+['market/rules.py','research/reference/reconstruction/sources.json','research/reference/cash-rights/sources.json']
def sha(raw):return hashlib.sha256(raw).hexdigest()
sources={p:{'sha256':sha((ROOT/p).read_bytes()),'normalized_sha256':sha((ROOT/p).read_bytes().replace(b'\r\n',b'\n'))} for p in paths}
unchanged={}
for path in protected:
    relative='backend/src/roll/'+path
    original=subprocess.run(['git','show','eabc7a3ae3462821bedc80c2d6c8b2a88d04b19c:'+relative],cwd=ROOT,capture_output=True,check=True).stdout
    current=(ROOT/relative).read_bytes()
    unchanged[relative]={'original_normalized_sha256':sha(original.replace(b'\r\n',b'\n')),'current_normalized_sha256':sha(current.replace(b'\r\n',b'\n')),'unchanged':original.replace(b'\r\n',b'\n')==current.replace(b'\r\n',b'\n')}
assert all(row['unchanged'] for row in unchanged.values())
Path(sys.argv[1]).write_text(json.dumps({'sources':sources,'protected_original_model_dependencies':unchanged},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
