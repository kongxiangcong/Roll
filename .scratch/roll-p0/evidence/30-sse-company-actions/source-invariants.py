"""Exact source guards; original19 checksum only, no SQLite or old runtime reads."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from roll.market.post_close_packet import code
from roll.market.sse_price_quotes import fingerprint as price_fingerprint
from roll.market.sse_company_actions import fingerprint as collector_fingerprint,contract,PREPARED_SHA
from roll.market.sse_action_assessments import fingerprint as assessment_fingerprint,observed_schema

folder=Path(__file__).resolve().parent;repo=folder.parents[3];base='9b6e00732721a6a549723006d494f57a485a0d9f'
protected=[f'backend/src/roll/research/{name}.py' for name in ['models','execution','reconstruction','datasets',
    'design','historical_costs','corporate_actions','registry','training_preflight']]+[
    'backend/src/roll/market/rules.py','backend/src/roll/research/reference/reconstruction/sources.json',
    'backend/src/roll/research/reference/cash-rights/sources.json','backend/src/roll/research/shadow.py',
    'backend/src/roll/research/statistics.py','backend/src/roll/research/validation.py']
def git(*args):return subprocess.check_output(['git',*args],cwd=repo,text=True).strip()
git('diff','--exit-code',base,'--',*protected,'backend/src/roll/market/post_close_packet.py',
    'backend/src/roll/market/sse_company_contract.py','backend/src/roll/market/sse_price_quotes.py',
    'backend/src/roll/market/reference','backend/src/roll/research/reference',
    ':(exclude)backend/src/roll/market/reference/sse-company-action-contract')
def digest(path):
    sha=hashlib.sha256();size=0
    with path.open('rb') as stream:
        while block:=stream.read(1048576):sha.update(block);size+=len(block)
    return {'sha256':sha.hexdigest(),'bytes':size}
original=digest(Path('D:/dsh-proj/Roll/.roll-data/reconstructed19-v1/roll.sqlite3'))
assert original=={'sha256':'ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4','bytes':165814272}
assert code()=='cae8f942a6f95b138743c54fb24348987bf288b8d960658120acf3a28083a0fc'
assert price_fingerprint()=='11a8063025fe548fb1c996923be6c9f818d5e1dd74f47382ed145ecf73019de1'
assert collector_fingerprint()=='63505424914969f9e1bd65237df93c886e163d01d0facb8cd2ca6754ce2eeb20'
docs=contract();schema,body=observed_schema()
own=['backend/src/roll/app.py','backend/src/roll/market/collection_sources.py',
     'backend/src/roll/market/sse_company_actions.py','backend/src/roll/market/sse_action_assessments.py',
     'backend/tests/application/test_sse_company_actions.py']
inventory={path:{'sha256_lf':hashlib.sha256((repo/path).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
    'bytes_lf':len((repo/path).read_bytes().replace(b'\r\n',b'\n'))} for path in own}
value={'protected15_git_blobs':{path:git('rev-parse',base+':'+path) for path in protected},
    'old_producer_price_and_old_reference_diff':False,'old_producer_fingerprint':code(),
    'price_fingerprint':price_fingerprint(),'collector_fingerprint':collector_fingerprint(),
    'assessment_fingerprint':assessment_fingerprint(),'own_inventory':inventory,
    'official_documents':docs['sources'],'prepared_plan_id':docs['prepared']['preparation_id'],'prepared_plan_hash':PREPARED_SHA,
    'new_observed_sources':schema,'original19_bytewise_checksum':original,
    'original19_sqlite_opened':False,'private_or_prior_preserved_sqlite_opened':False,
    'real_http_budget_closed':True,'real_http_attempts':2,'guard_http_calls':0}
stage=sys.argv[1];target=folder/('source-'+stage+'.json')
if stage.endswith('after'):assert value==json.loads((folder/('source-'+stage.removesuffix('after')+'before.json')).read_bytes())
assert not target.exists(),'Guard stage immutable: select a new stage name.'
target.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print('PROTECTED15_OLD_REF_CAE_PRICE_COLLECTOR_SCHEMA_ORIGINAL19_CHECKSUM_SOURCE_UNCHANGED')
