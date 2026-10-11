"""Read-only source/original profile checksum receipt; does not open SQLite."""
import hashlib
import json
import sys
from pathlib import Path

repo=Path(__file__).resolve().parents[4]
root=Path('D:/dsh-proj/Roll')
names=['models','execution','reconstruction','datasets','design','historical_costs','corporate_actions','registry','training_preflight']
protected=[f'backend/src/roll/research/{n}.py' for n in names]+[
    'backend/src/roll/market/rules.py','backend/src/roll/research/reference/reconstruction/sources.json',
    'backend/src/roll/research/reference/cash-rights/sources.json',
    'backend/src/roll/research/shadow.py','backend/src/roll/research/statistics.py','backend/src/roll/research/validation.py']
own=['backend/src/roll/app.py','backend/src/roll/market/collection_sources.py','backend/src/roll/market/evidence.py',
    'backend/src/roll/market/post_close_packet.py','backend/src/roll/research/forward.py','backend/src/roll/research/prospective.py']
def info(path):
    body=path.read_bytes()
    return {'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body)}
value={'protected':[{'path':p,'root':info(root/p),'worktree':info(repo/p)} for p in protected],
    'own':{p:info(repo/p) for p in own},'original19_sqlite':info(root/'.roll-data/reconstructed19-v1/roll.sqlite3')}
assert all(p['root']==p['worktree'] for p in value['protected'])
assert value['original19_sqlite']['sha256']=='ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4'
target=Path(__file__).parent/('source-'+sys.argv[1]+'.json')
if sys.argv[1]=='after':assert value==json.loads(target.with_name('source-before.json').read_text(encoding='utf-8'))
target.write_text(json.dumps(value,indent=2),encoding='utf-8')
print('SOURCE_AND_ORIGINAL19_INVARIANTS_PASS')
