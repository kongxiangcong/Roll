"""Stage only report routes; compare the original dirty baseline after own insertions."""
import difflib,hashlib,json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[4];out=Path(__file__).parent
app='backend/src/roll/app.py';sources='backend/src/roll/market/collection_sources.py'
def git(path,ref='HEAD'):return subprocess.check_output(['git','show',ref+':'+path],cwd=root).decode()
current=(root/app).read_text();head=git(app)
anchor='    successor_protocols=SuccessorProtocols(successor_shadow,validation)\n';end="    @app.get('/api/research/complete-freezes/{predecessor_freeze_id}/policy-successor-freezes')"
between=current.split(anchor,1)[1].split(end,1)[0];previous=head.split(anchor,1)[1].split(end,1)[0]
assert 'successor_input_create' in between and 'successor_input_create' not in previous
intended=head.replace(anchor+previous+end,anchor+between+end)
(out/'app-only.patch').write_text(''.join(difflib.unified_diff(head.splitlines(True),intended.splitlines(True),fromfile='a/'+app,tofile='b/'+app)),encoding='utf-8',newline='\n')
late='    successor_inputs=SuccessorInputConsumers(successor_centers,prospective)\n'
late_anchor='    prospective=ProspectiveEvidence(evidence,research)\n'
intended=intended.replace(late_anchor,late_anchor+late)
(out/'app-only.patch').write_text(''.join(difflib.unified_diff(head.splitlines(True),intended.splitlines(True),fromfile='a/'+app,tofile='b/'+app)),encoding='utf-8',newline='\n')
current=current.replace(anchor+between+end,anchor+previous+end).replace(late,'')
perf_anchor='    reviews.reports = reports\n';perf_end="    @app.get('/api/research/reports/{freeze_id}')"
perf_between=current.split(perf_anchor,1)[1].split(perf_end,1)[0]
perf_old=git(app,'fe5d01c7').split(perf_anchor,1)[1].split(perf_end,1)[0]
current=current.replace(perf_anchor+perf_between+perf_end,perf_anchor+perf_old+perf_end)
financial='    financial=FinancialIncome'+current.split('    financial=FinancialIncome',1)[1].split('    dated_daily=DatedDaily',1)[0]
status_import='from roll.market.status_evidence import query as status_evidence_query\n'
action_import='from roll.market.action_evidence import query as action_evidence_query\n'
protocol_import='from roll.research.successor_protocol import SuccessorProtocols,ProtocolFreezeCommand,DiagnosticCommand\n'
financial_import='from roll.market.financial_income import FinancialIncome,IncomeCommand\n'
status_route="\n    @app.get('/api/research/collections/{plan_id}/status-evidence')\n    def status_evidence(plan_id:str,known_by:datetime|None=Query(None)):\n        return status_evidence_query(prospective.post_close,plan_id,known_by)\n"
action_route="\n    @app.get('/api/research/collections/{plan_id}/action-evidence')\n    def action_evidence(plan_id:str,known_by:datetime|None=Query(None)):\n        return action_evidence_query(action_assessments,plan_id,known_by)\n"
start='    app.state.validation=validation\n';finish="    @app.post('/api/research/complete-freezes/{freeze_id}/validations',status_code=201)"
old_protocol=git(app,'fe5d01c7').split(start,1)[1].split(finish,1)[0]
new_protocol=current.split(start,1)[1].split(finish,1)[0]
for own in (status_import,action_import,protocol_import,financial_import,status_route,action_route,financial):current=current.replace(own,'')
current=current.replace(start+new_protocol+finish,start+old_protocol+finish)
source=(root/sources).read_text();entry=next(line+'\n' for line in source.splitlines() if "'id': 'akshare-financial-em'" in line)
policy="                if spec['id']=='akshare-financial-em':"+source.split("                if spec['id']=='akshare-financial-em':",1)[1].split("                if spec['id']=='sse-dated-daily-statistic':",1)[0]
source=source.replace(entry,'').replace(policy,'')
manifest=json.loads((out.parent/'handoff/protected-files.json').read_text(encoding='utf-8-sig'));mismatches=[]
for path,expected in manifest.items():
    raw=(root/path).read_bytes()
    if path in (app,sources):raw=({app:current,sources:source}[path]).encode().replace(b'\n',b'\r\n' if b'\r\n' in raw else b'\n')
    if hashlib.sha256(raw).hexdigest().upper()!=expected:mismatches.append(path)
(out/'preservation.json').write_text(json.dumps({'protected_files':len(manifest),'mismatches':mismatches,'excluded_only_own_feature_insertions':True},indent=2),encoding='utf-8')
assert not mismatches,mismatches
paths=json.loads((out.parent/'09-financial/model-preservation.json').read_text())
comparison={p:subprocess.check_output(['git','show','fe5d01c7:'+p],cwd=root).replace(b'\r\n',b'\n')==(root/p).read_bytes().replace(b'\r\n',b'\n') for p in paths}
(out/'model-preservation.json').write_text(json.dumps(comparison,indent=2),encoding='utf-8');assert all(comparison.values())
