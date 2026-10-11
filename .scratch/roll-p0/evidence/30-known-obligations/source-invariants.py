"""Check protected Git identity and this round's named source bytes; no root DB."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

repo=Path(__file__).resolve().parents[4]
base='479460f73224bc4959112cf45bf98b33addcccee'
protected=[f'backend/src/roll/research/{name}.py' for name in
 ['models','execution','reconstruction','datasets','design','historical_costs','corporate_actions','registry','training_preflight']]+[
 'backend/src/roll/market/rules.py','backend/src/roll/research/reference/reconstruction/sources.json',
 'backend/src/roll/research/reference/cash-rights/sources.json','backend/src/roll/research/shadow.py',
 'backend/src/roll/research/statistics.py','backend/src/roll/research/validation.py']
def git(*args):
 result=subprocess.run(['git',*args],cwd=repo,capture_output=True,text=True,check=True)
 return result.stdout.strip()
git('diff','--exit-code',base,'--',*protected,'backend/src/roll/market/reference')
own=['backend/src/roll/app.py','backend/src/roll/research/prospective.py','backend/src/roll/research/forward.py',
 'backend/src/roll/market/post_close_packet.py','backend/src/roll/market/known_obligations.py',
 'backend/tests/application/test_known_obligation_audit.py','backend/tests/support/known_obligation_method_app.py']
value={'protected_git_blobs':{p:git('rev-parse',base+':'+p) for p in protected},
 'protected_and_market_reference_diff_from_accepted_base':False,
 'own':{p:{'sha256':hashlib.sha256((repo/p).read_bytes()).hexdigest(),'bytes':(repo/p).stat().st_size} for p in own},
 'actual_root_account_or_sqlite_read':False,'previous_preservation_opened':False,'network_calls':0}
target=Path(__file__).with_name('source-'+sys.argv[1]+'.json')
if sys.argv[1].endswith('after'):
 assert value==json.loads(target.with_name(target.name.replace('after','before')).read_bytes())
target.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
print('PROTECTED15_GIT_UNCHANGED_NAMED_SOURCE_STABLE_NO_ROOT_DB_OR_OLD_SAVED_FILES')
