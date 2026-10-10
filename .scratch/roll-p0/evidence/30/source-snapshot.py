"""Scoped final source and protected dependencies, without runtime inputs."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
paths=['backend/src/roll/app.py','backend/src/roll/runtime/reviews.py','backend/src/roll/research/forward.py','backend/tests/application/test_forward.py','backend/tests/application/test_forward_adapter.py','backend/tests/recovery/test_forward_process.py','backend/tests/support/forward_method_app.py','frontend/src/components/forward-panel.tsx','frontend/src/pages/shadow.tsx','frontend/tests/e2e/forward.spec.ts','frontend/playwright.forward.config.ts']
protected=['research/'+n+'.py' for n in ['models','execution','reconstruction','datasets','design','historical_costs','corporate_actions','registry','training_preflight']]+['market/rules.py','research/reference/reconstruction/sources.json','research/reference/cash-rights/sources.json']
packet=['research/'+n+'.py' for n in ['models','execution','shadow','statistics','validation']]
def sha(raw):return hashlib.sha256(raw).hexdigest()
def record(path):
    raw=(ROOT/path).read_bytes();return {'sha256':sha(raw),'length':len(raw),'normalized_sha256':sha(raw.replace(b'\r\n',b'\n'))}
result={'sources':{p:record(p) for p in paths},'protected_original_model_dependencies':{},'pending23_packet_sources':{}}
for key,names,commit in [('protected_original_model_dependencies',protected,'eabc7a3ae3462821bedc80c2d6c8b2a88d04b19c'),('pending23_packet_sources',packet,'676b5fff2126714c981399ef7d95410de5cd5ffd')]:
    for name in names:
        path='backend/src/roll/'+name
        original=subprocess.run(['git','show',commit+':'+path],cwd=ROOT,capture_output=True,check=True).stdout.replace(b'\r\n',b'\n')
        current=(ROOT/path).read_bytes().replace(b'\r\n',b'\n')
        result[key][path]={'original_sha256':sha(original),'current_sha256':sha(current),'unchanged':original==current}
    assert all(r['unchanged'] for r in result[key].values())
Path(sys.argv[1]).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
