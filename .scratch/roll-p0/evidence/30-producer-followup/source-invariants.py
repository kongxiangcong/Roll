"""Read only the 15 named protected sources and this finite implementation; no SQLite."""
import hashlib
import json
import sys
from pathlib import Path

repo=Path(__file__).resolve().parents[4]
root=Path('D:/dsh-proj/Roll')
names=['models','execution','reconstruction','datasets','design','historical_costs','corporate_actions','registry','training_preflight']
protected=[f'backend/src/roll/research/{n}.py' for n in names]+[
 'backend/src/roll/market/rules.py','backend/src/roll/research/reference/reconstruction/sources.json',
 'backend/src/roll/research/reference/cash-rights/sources.json','backend/src/roll/research/shadow.py',
 'backend/src/roll/research/statistics.py','backend/src/roll/research/validation.py']
def info(path):
 body=path.read_bytes()
 return {'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body)}
manifest=json.loads((repo/'backend/src/roll/market/reference/sse-history/sources.json').read_bytes())
value={'protected':[{'path':p,'root':info(root/p),'worktree':info(repo/p)} for p in protected],
 'own':{p:info(repo/p) for p in ['backend/src/roll/app.py','backend/src/roll/market/post_close_packet.py',
 'backend/tests/application/test_sse_history_assessment.py','backend/src/roll/market/reference/sse-history/sources.json']},
 'originals':[{**s,'actual':info(repo/'backend/src/roll/market/reference/sse-history'/s['path'])} for s in manifest['sources']],
 'original19_sqlite_read':False,'network_calls':0}
assert all(v['root']==v['worktree'] for v in value['protected'])
assert all(s['actual']=={'sha256':s['sha256'],'bytes':s['bytes']} for s in value['originals'])
target=Path(__file__).with_name('source-'+sys.argv[1]+'.json')
if sys.argv[1].endswith('after'):
 before=target.with_name(target.name.replace('after','before'))
 assert value==json.loads(before.read_bytes())
target.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print('PROTECTED15_FIXED6_AND_CURRENT_SOURCE_PASS_NO_SQLITE_READ')
