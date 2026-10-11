"""Named fixed public bytes + protected Git + bytewise original19 checksum, no SQLite open."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

repo=Path(__file__).resolve().parents[4]
base='5b09da42955840c5f948cc4b3a70f6ec69ac8177'
protected=[f'backend/src/roll/research/{name}.py' for name in
 ['models','execution','reconstruction','datasets','design','historical_costs','corporate_actions','registry','training_preflight']]+[
 'backend/src/roll/market/rules.py','backend/src/roll/research/reference/reconstruction/sources.json',
 'backend/src/roll/research/reference/cash-rights/sources.json','backend/src/roll/research/shadow.py',
 'backend/src/roll/research/statistics.py','backend/src/roll/research/validation.py']
def git(*args):
 return subprocess.run(['git',*args],cwd=repo,capture_output=True,text=True,check=True).stdout.strip()
git('diff','--exit-code',base,'--',*protected,'backend/src/roll/market/reference')
def digest(path):
 h=hashlib.sha256();size=0
 with path.open('rb') as stream:
  while chunk:=stream.read(1048576):h.update(chunk);size+=len(chunk)
 return {'sha256':h.hexdigest(),'bytes':size}
reference=repo/'backend/src/roll/market/reference/sse-history'
manifest=json.loads((reference/'sources.json').read_bytes())
named={}
for source in manifest['sources']:
 if source['role'] not in {'suspension_query_js','suspension'}:continue
 found=digest(reference/source['path'])
 assert found=={'sha256':source['sha256'],'bytes':source['bytes']}
 named[source['role']]=found
original=Path('D:/dsh-proj/Roll/.roll-data/reconstructed19-v1/roll.sqlite3')
original_digest=digest(original)
assert original_digest['sha256']=='ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4'
own=['backend/src/roll/app.py','backend/src/roll/research/forward.py','backend/src/roll/market/post_close_packet.py',
 'backend/src/roll/market/sse_suspension.py','backend/src/roll/market/collection_sources.py',
 'backend/tests/application/test_sse_current_suspension.py','backend/tests/application/test_post_close_packet.py']
value={'protected_git_blobs':{p:git('rev-parse',base+':'+p) for p in protected},
 'protected_and_market_reference_diff_from_accepted_base':False,'named_fixed_public_sources':named,
 'original19_bytewise_checksum':original_digest,'original19_sqlite_opened':False,
 'own':{p:digest(repo/p) for p in own},'previous_preservation_opened':False,'network_calls':0}
target=Path(__file__).with_name('source-'+sys.argv[1]+'.json')
if sys.argv[1].endswith('after'):
 assert value==json.loads(target.with_name(target.name.replace('after','before')).read_bytes())
target.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
print('PROTECTED15_FIXED2_ORIGINAL19_BYTE_CHECKSUM_UNCHANGED_NO_SQLITE_OPEN')
