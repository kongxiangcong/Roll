"""Eighth exact named public originals and protected sources; bytewise DB checksum only."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
folder = Path(__file__).resolve().parent
repo = folder.parents[3]
base = '870b451ec1330e01a343b6928b7ef2544b57fda8'
protected = [f'backend/src/roll/research/{name}.py' for name in
 ['models', 'execution', 'reconstruction', 'datasets', 'design', 'historical_costs', 'corporate_actions', 'registry', 'training_preflight']] + [
 'backend/src/roll/market/rules.py', 'backend/src/roll/research/reference/reconstruction/sources.json',
 'backend/src/roll/research/reference/cash-rights/sources.json', 'backend/src/roll/research/shadow.py',
 'backend/src/roll/research/statistics.py', 'backend/src/roll/research/validation.py']
unchanged = protected + ['backend/src/roll/market/post_close_packet.py', 'backend/src/roll/market/sse_company_contract.py',
 'backend/src/roll/market/reference', 'backend/src/roll/research/reference']
def git(*args):
 return subprocess.run(['git', *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
git('diff', '--exit-code', base, '--', *unchanged)
def digest(path):
 h=hashlib.sha256();size=0
 with path.open('rb') as stream:
  while chunk:=stream.read(1048576):h.update(chunk);size+=len(chunk)
 return {'sha256':h.hexdigest(),'bytes':size}
reference=repo/'backend/src/roll/market/reference/sse-company-contract'
named={}
for source in json.loads((reference/'sources.json').read_bytes())['sources']:
 actual=digest(reference/source['path']);assert actual=={'sha256':source['sha256'],'bytes':source['bytes']}
 named[source['role']]=actual
snap_sha='bc0971238819277c2b9d6773e341c6d12496adb7991fc897000974cbb2942403'
snap=digest(repo/'.scratch/roll-p0/evidence/30-sse-company-contract/runtime/source-assessment'/(snap_sha+'.raw'))
assert snap=={'sha256':snap_sha,'bytes':409}
original=digest(Path('D:/dsh-proj/Roll/.roll-data/reconstructed19-v1/roll.sqlite3'))
assert original['sha256']=='ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4'
from roll.market.post_close_packet import code
from roll.market.sse_price_quotes import fingerprint
assert code()=='cae8f942a6f95b138743c54fb24348987bf288b8d960658120acf3a28083a0fc'
value={'protected_git_blobs':{p:git('rev-parse',base+':'+p) for p in protected},
 'old_producer_and_reference_diff':False,'named_documents':named,'named_snap':snap,
 'original19_bytewise_checksum':original,'original19_sqlite_opened':False,
 'previous_preservation_opened':False,'actual_network_calls':0,'old_parser_fingerprint':code(),
 'price_parser_fingerprint':fingerprint(),'own':{p:digest(repo/p) for p in
 ['backend/src/roll/app.py','backend/src/roll/market/sse_price_quotes.py','backend/tests/application/test_sse_price_quotes.py']}}
target=folder/('source-'+sys.argv[1]+'.json')
if sys.argv[1].endswith('after'):
 assert value==json.loads(target.with_name(target.name.replace('after','before')).read_bytes())
target.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
print('PROTECTED15_OLD_PARSER_NAMED_PUBLIC_ORIGINALS_ORIGINAL19_BYTEWISE_UNCHANGED')
