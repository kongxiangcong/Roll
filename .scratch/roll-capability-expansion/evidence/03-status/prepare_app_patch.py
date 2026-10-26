"""Stage only this ticket's route; leave earlier uncommitted SSE integration out."""
import difflib, hashlib, json, subprocess
from pathlib import Path

root=Path(__file__).resolve().parents[4]
path='backend/src/roll/app.py'
original=subprocess.check_output(['git','show','HEAD:'+path],cwd=root).decode()
added_import='from roll.market.status_evidence import query as status_evidence_query\n'
anchor='from roll.market.directory import MarketDirectory, WatchCommand, IdentityCommand, ScopeCommand\n'
added_route="\n    @app.get('/api/research/collections/{plan_id}/status-evidence')\n    def status_evidence(plan_id:str,known_by:datetime=Query(...)):\n        return status_evidence_query(prospective.post_close,plan_id,known_by)\n"
route_anchor="    def sse_company_contract_receipts(plan_id:str):\n        return prospective.post_close.company_contracts.receipts(plan_id)\n"
assert original.count(anchor)==original.count(route_anchor)==1
intended=original.replace(anchor,anchor+added_import).replace(route_anchor,route_anchor+added_route)
patch=''.join(difflib.unified_diff(original.splitlines(True),intended.splitlines(True),fromfile='a/'+path,tofile='b/'+path))
Path(__file__).with_name('app-only.patch').write_text(patch,encoding='utf-8',newline='\n')
protected=json.loads((root/'.scratch/roll-capability-expansion/evidence/handoff/protected-files.json').read_text(encoding='utf-8-sig'))
result=[]
for name,expected in protected.items():
    body=(root/name).read_bytes()
    if name==path:
        eol=b'\r\n' if b'\r\n' in body else b'\n'
        body=body.replace(added_import.encode().replace(b'\n',eol),b'').replace(added_route.encode().replace(b'\n',eol),b'')
    if hashlib.sha256(body).hexdigest().upper()!=expected: result.append(name)
receipt={'checked':len(protected),'excluded_only_own_status_route_and_import':True,'mismatches':result}
Path(__file__).with_name('preservation.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
assert not result,receipt
