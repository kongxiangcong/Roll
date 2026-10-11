"""Scope exact originals and protected source identity; never connect to preserved SQLite."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
folder = Path(__file__).resolve().parent
repo = folder.parents[3]
base = '0cb1aab8068d2260cc9e9aaf46d3ae788855dd76'
protected = [f'backend/src/roll/research/{name}.py' for name in
 ['models', 'execution', 'reconstruction', 'datasets', 'design', 'historical_costs', 'corporate_actions', 'registry', 'training_preflight']] + [
 'backend/src/roll/market/rules.py', 'backend/src/roll/research/reference/reconstruction/sources.json',
 'backend/src/roll/research/reference/cash-rights/sources.json', 'backend/src/roll/research/shadow.py',
 'backend/src/roll/research/statistics.py', 'backend/src/roll/research/validation.py']
def git(*args):
    return subprocess.run(['git', *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
git('diff', '--exit-code', base, '--', *protected, 'backend/src/roll/market/reference/sse-history', 'backend/src/roll/research/reference')
def digest(path):
    h = hashlib.sha256(); size = 0
    with path.open('rb') as stream:
        while chunk := stream.read(1048576): h.update(chunk); size += len(chunk)
    return {'sha256': h.hexdigest(), 'bytes': size}
reference = repo / 'backend/src/roll/market/reference/sse-company-contract'
named = {}
for source in json.loads((reference / 'sources.json').read_bytes())['sources']:
    actual = digest(reference / source['path'])
    assert actual == {'sha256': source['sha256'], 'bytes': source['bytes']}
    named[source['role']] = actual
original = digest(Path('D:/dsh-proj/Roll/.roll-data/reconstructed19-v1/roll.sqlite3'))
assert original['sha256'] == 'ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4'
own = ['backend/src/roll/app.py', 'backend/src/roll/research/forward.py', 'backend/src/roll/market/post_close_packet.py',
       'backend/src/roll/market/sse_company_contract.py', 'backend/src/roll/market/collection_sources.py',
       'backend/src/roll/market/reference/sse-company-contract/sources.json']
value = {'protected_git_blobs': {p: git('rev-parse', base + ':' + p) for p in protected},
         'protected_and_old_reference_diff': False, 'two_named_document_originals': named,
         'original19_bytewise_checksum': original, 'original19_sqlite_opened': False,
         'previous_preservation_opened': False, 'own': {p: digest(repo / p) for p in own}, 'network_calls': 0}
target = folder / ('source-' + sys.argv[1] + '.json')
if sys.argv[1].endswith('after'):
    assert value == json.loads(target.with_name(target.name.replace('after', 'before')).read_bytes())
target.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8', newline='\n')
print('PROTECTED15_OLD_REFERENCES_NEW_FIXED2_ORIGINAL19_BYTEWISE_ONLY_UNCHANGED')
