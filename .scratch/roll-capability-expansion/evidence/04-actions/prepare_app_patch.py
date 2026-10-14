"""Preserve preexisting daily integration while staging only new feature routes."""
import difflib,hashlib,json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[4]
path='backend/src/roll/app.py'
original=subprocess.check_output(['git','show','HEAD:'+path],cwd=root).decode()
old='def status_evidence(plan_id:str,known_by:datetime=Query(...)):'
new='def status_evidence(plan_id:str,known_by:datetime|None=Query(None)):'
status_import='from roll.market.status_evidence import query as status_evidence_query\n'
action_import='from roll.market.action_evidence import query as action_evidence_query\n'
anchor='    def sse_action_assessment_query(plan_id:str):return action_assessments.assessments(plan_id)\n'
route="\n    @app.get('/api/research/collections/{plan_id}/action-evidence')\n    def action_evidence(plan_id:str,known_by:datetime|None=Query(None)):\n        return action_evidence_query(action_assessments,plan_id,known_by)\n"
assert original.count(old)==original.count(anchor)==1 and action_import not in original
intended=original.replace(old,new).replace(status_import,status_import+action_import).replace(anchor,anchor+route)
Path(__file__).with_name('app-only.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),intended.splitlines(True),fromfile='a/'+path,tofile='b/'+path)),encoding='utf-8',newline='\n')
protected=json.loads((root/'.scratch/roll-capability-expansion/evidence/handoff/protected-files.json').read_text(encoding='utf-8-sig'))
mismatches=[]
for name,expected in protected.items():
    body=(root/name).read_bytes()
    if name==path:
        eol=b'\r\n' if b'\r\n' in body else b'\n'
        status_route="\n    @app.get('/api/research/collections/{plan_id}/status-evidence')\n    def status_evidence(plan_id:str,known_by:datetime|None=Query(None)):\n        return status_evidence_query(prospective.post_close,plan_id,known_by)\n"
        for own in (status_import,action_import,status_route,route):body=body.replace(own.encode().replace(b'\n',eol),b'')
    if hashlib.sha256(body).hexdigest().upper()!=expected:mismatches.append(name)
Path(__file__).with_name('preservation.json').write_text(json.dumps({'checked':len(protected),'excluded_only_own_status_action_routes_and_imports':True,'mismatches':mismatches},indent=2),encoding='utf-8')
assert not mismatches,mismatches
