"""Construct cached-only feature patches and verify original dirty bytes untouched."""
import difflib,hashlib,json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[4];out=Path(__file__).parent
def git(name,ref='HEAD'):
    return subprocess.check_output(['git','show',ref+':'+name],cwd=root).decode()
changes={}
app='backend/src/roll/app.py';current=(root/app).read_text();head=git(app)
imp='from roll.market.financial_income import FinancialIncome,IncomeCommand\n'
anchor='from roll.market.evidence import EvidenceStore, DataRequest\n'
block='    financial=FinancialIncome'+current.split('    financial=FinancialIncome',1)[1].split('    dated_daily=DatedDaily',1)[0]
intended=head.replace(anchor,anchor+imp).replace('    prospective=ProspectiveEvidence(evidence,research)\n','    prospective=ProspectiveEvidence(evidence,research)\n'+block)
changes[app]=(head,intended)
sources='backend/src/roll/market/collection_sources.py';source_text=(root/sources).read_text();head=git(sources)
entry=next(line+'\n' for line in source_text.splitlines() if "'id': 'akshare-financial-em'" in line)
policy="                if spec['id']=='akshare-financial-em':"+source_text.split("                if spec['id']=='akshare-financial-em':",1)[1].split("                if spec['id']=='sse-dated-daily-statistic':",1)[0]
intended=head.replace('SOURCES = [\n','SOURCES = [\n'+entry).replace("                if spec['id']=='sse-closing-board':",policy+"                if spec['id']=='sse-closing-board':")
changes[sources]=(head,intended)
patch=''.join(''.join(difflib.unified_diff(a.splitlines(True),b.splitlines(True),fromfile='a/'+p,tofile='b/'+p)) for p,(a,b) in changes.items())
(out/'financial-only.patch').write_text(patch,encoding='utf-8',newline='\n')
status_import='from roll.market.status_evidence import query as status_evidence_query\n'
action_import='from roll.market.action_evidence import query as action_evidence_query\n'
protocol_import='from roll.research.successor_protocol import SuccessorProtocols,ProtocolFreezeCommand,DiagnosticCommand\n'
status_route="\n    @app.get('/api/research/collections/{plan_id}/status-evidence')\n    def status_evidence(plan_id:str,known_by:datetime|None=Query(None)):\n        return status_evidence_query(prospective.post_close,plan_id,known_by)\n"
action_route="\n    @app.get('/api/research/collections/{plan_id}/action-evidence')\n    def action_evidence(plan_id:str,known_by:datetime|None=Query(None)):\n        return action_evidence_query(action_assessments,plan_id,known_by)\n"
start='    app.state.validation=validation\n';end="    @app.post('/api/research/complete-freezes/{freeze_id}/validations',status_code=201)"
original_between=git(app,'fe5d01c7').split(start,1)[1].split(end,1)[0]
current_between=current.split(start,1)[1].split(end,1)[0]
manifest=json.loads((out.parent/'handoff/protected-files.json').read_text(encoding='utf-8-sig'));mismatches=[]
for name,expected in manifest.items():
    raw=(root/name).read_bytes();eol=b'\r\n' if b'\r\n' in raw else b'\n'
    def encoded(s):return s.encode().replace(b'\n',eol)
    if name==app:
        for own in (imp,block,status_import,action_import,protocol_import,status_route,action_route):raw=raw.replace(encoded(own),b'')
        raw=raw.replace(encoded(start+current_between+end),encoded(start+original_between+end))
    elif name==sources:
        raw=raw.replace(encoded(entry),b'').replace(encoded(policy),b'')
    if hashlib.sha256(raw).hexdigest().upper()!=expected:mismatches.append(name)
(out/'preservation.json').write_text(json.dumps({'protected_files':len(manifest),'mismatches':mismatches,'excluded_only_own_feature_app_and_source_insertions':True},indent=2),encoding='utf-8')
assert not mismatches,mismatches
model_paths=json.loads((out.parent/'05-protocol/model-preservation.json').read_text())
comparison={p:subprocess.check_output(['git','show','fe5d01c7:'+p],cwd=root).replace(b'\r\n',b'\n')==(root/p).read_bytes().replace(b'\r\n',b'\n') for p in model_paths}
(out/'model-preservation.json').write_text(json.dumps(comparison,indent=2),encoding='utf-8')
assert all(comparison.values())
