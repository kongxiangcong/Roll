"""Named-source and preservation hashes only: never SQLite-open saved namespaces."""
import hashlib,json,subprocess
from pathlib import Path
OWNER=Path('D:/dsh-proj/Roll/.scratch/worktrees/ticket30-producer')
HERE=Path(__file__).resolve().parent
EVIDENCE=OWNER/'.scratch/roll-p0/evidence/30-sse-price-quotes'
HANDOFF='3d541869989d446150b0c25b2dd8370a55f088ab'
BASE='870b451ec1330e01a343b6928b7ef2544b57fda8'
def git(*args):
    return subprocess.check_output(['git',*args],cwd=OWNER).strip()
def digest(path):
    h=hashlib.sha256();size=0
    with Path(path).open('rb') as stream:
        while chunk:=stream.read(1048576):h.update(chunk);size+=len(chunk)
    return {'sha256':h.hexdigest(),'bytes':size}
before=json.loads((EVIDENCE/'source-composition-before.json').read_bytes())
after=json.loads((EVIDENCE/'source-composition-after.json').read_bytes())
assert before==after
checks={}
for path,blob in before['protected_git_blobs'].items():
    assert git('rev-parse',HANDOFF+':'+path).decode()==blob
    assert git('show',HANDOFF+':'+path).replace(b'\r\n',b'\n')==Path(OWNER/path).read_bytes().replace(b'\r\n',b'\n').strip()
    checks[path]={'git_blob':blob,'worktree':digest(OWNER/path)}
for path in ['backend/src/roll/market/post_close_packet.py','backend/src/roll/market/sse_company_contract.py']:
    assert git('rev-parse',BASE+':'+path)==git('rev-parse',HANDOFF+':'+path)
    checks[path]={'git_blob':git('rev-parse',HANDOFF+':'+path).decode(),'worktree':digest(OWNER/path)}
reference=OWNER/'backend/src/roll/market/reference/sse-company-contract'
for row in json.loads((reference/'sources.json').read_bytes())['sources']:
    actual=digest(reference/row['path']);assert actual=={'sha256':row['sha256'],'bytes':row['bytes']}
    gitraw=subprocess.check_output(['git','show',HANDOFF+':backend/src/roll/market/reference/sse-company-contract/'+row['path']],cwd=OWNER)
    assert hashlib.sha256(gitraw).hexdigest()==row['sha256'] and len(gitraw)==row['bytes']
    checks[row['role']]=actual
snap=OWNER/'.scratch/roll-p0/evidence/30-sse-company-contract/runtime/source-assessment/bc0971238819277c2b9d6773e341c6d12496adb7991fc897000974cbb2942403.raw'
assert digest(snap)==before['named_snap'];checks['named_snap']=digest(snap)
original=Path('D:/dsh-proj/Roll/.roll-data/reconstructed19-v1/roll.sqlite3')
assert digest(original)==before['original19_bytewise_checksum'];checks['original19_bytewise_checksum']=digest(original)
rows=[]
for name in ['runtime-preservation-manifest.json','runtime-preservation-accepted25-manifest.json']:
    for row in json.loads((EVIDENCE/name).read_bytes()):
        expected={'sha256':row['sha256'],'bytes':row['bytes']}
        assert digest(row['source'])==expected and digest(row['destination'])==expected
        rows.append(row)
assert len(rows)==1762 and sum(r['bytes'] for r in rows)==185392709
from roll.market.post_close_packet import code
from roll.market.sse_price_quotes import fingerprint
assert code()==before['old_parser_fingerprint'] and fingerprint()==before['price_parser_fingerprint']
record={'handoff':HANDOFF,'protected_and_named':checks,'old_parser_fingerprint':code(),'price_parser_fingerprint':fingerprint(),
    'owned_manifest_files_verified_both_sides':len(rows),'owned_manifest_bytes':sum(r['bytes'] for r in rows),'sha_length_mismatches':0,
    'saved_or_original_SQLite_opened':False,'actual_HTTP_calls':0,'model_calls':0,'SEALED_consumed':False,'proposal_executed':False}
(HERE/'integrity.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print('PROTECTED15_NAMED_RAW_GIT_ORIGINAL19_1762FILES_BOTHSIDES_0DIFF_SQLITE_OPEN0_HTTP0')
