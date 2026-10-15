"""Stage this increment's protocol routes without taking earlier daily changes."""
import difflib,hashlib,json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[4];name='backend/src/roll/app.py'
original=subprocess.check_output(['git','show','HEAD:'+name],cwd=root).decode()
working=(root/name).read_bytes();eol=b'\r\n' if b'\r\n' in working else b'\n'
current=working.decode().replace('\r\n','\n')
anchor='    app.state.validation=validation\n'
end="    @app.post('/api/research/complete-freezes/{freeze_id}/validations',status_code=201)"
added=current.split(anchor,1)[1].split(end,1)[0]
old_between=original.split(anchor,1)[1].split(end,1)[0]
added_import='from roll.research.successor_protocol import SuccessorProtocols,ProtocolFreezeCommand,DiagnosticCommand\n'
import_anchor='from roll.research.successor_shadow import SuccessorShadow,SuccessorFreezeCommand,SuccessorAdvanceCommand\n'
assert added_import not in original and added.count('successor_protocols=')==1
intended=original.replace(import_anchor,import_anchor+added_import).replace(anchor+old_between+end,anchor+added+end)
Path(__file__).with_name('app-only.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),intended.splitlines(True),fromfile='a/'+name,tofile='b/'+name)),encoding='utf-8',newline='\n')
status_import='from roll.market.status_evidence import query as status_evidence_query\n'
action_import='from roll.market.action_evidence import query as action_evidence_query\n'
status_route="\n    @app.get('/api/research/collections/{plan_id}/status-evidence')\n    def status_evidence(plan_id:str,known_by:datetime|None=Query(None)):\n        return status_evidence_query(prospective.post_close,plan_id,known_by)\n"
action_route="\n    @app.get('/api/research/collections/{plan_id}/action-evidence')\n    def action_evidence(plan_id:str,known_by:datetime|None=Query(None)):\n        return action_evidence_query(action_assessments,plan_id,known_by)\n"
protected=json.loads((root/'.scratch/roll-capability-expansion/evidence/handoff/protected-files.json').read_text(encoding='utf-8-sig'));mismatches=[]
for path,expected in protected.items():
    body=(root/path).read_bytes()
    if path==name:
        for own in (status_import,action_import,status_route,action_route,added_import):body=body.replace(own.encode().replace(b'\n',eol),b'')
        body=body.replace((anchor+added+end).encode().replace(b'\n',eol),(anchor+old_between+end).encode().replace(b'\n',eol))
    if hashlib.sha256(body).hexdigest().upper()!=expected:mismatches.append(path)
Path(__file__).with_name('preservation.json').write_text(json.dumps({'checked':len(protected),'excluded_only_own_feature_app_hunks':True,'mismatches':mismatches},indent=2),encoding='utf-8')
assert not mismatches,mismatches
