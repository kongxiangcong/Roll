"""Ninth named byte/Git verification and fresh actual-profile copy, never original DB open."""
import hashlib,json,subprocess,shutil
from pathlib import Path
OWNER=Path('D:/dsh-proj/Roll/.scratch/worktrees/ticket30-producer')
HERE=Path(__file__).resolve().parent
EVIDENCE=OWNER/'.scratch/roll-p0/evidence/30-sse-company-actions'
HANDOFF='14b0082674050d430279c153bac0cdbf7427337c'
def digest(p):
    h=hashlib.sha256();size=0
    with Path(p).open('rb') as stream:
        while chunk:=stream.read(1048576):h.update(chunk);size+=len(chunk)
    return {'sha256':h.hexdigest(),'bytes':size}
def git(*args):return subprocess.check_output(['git',*args],cwd=OWNER).strip()
before=json.loads((EVIDENCE/'source-final-before.json').read_bytes());after=json.loads((EVIDENCE/'source-final-after.json').read_bytes());assert before==after
for path,blob in before['protected15_git_blobs'].items():
    assert git('rev-parse',HANDOFF+':'+path).decode()==blob
    assert git('show',HANDOFF+':'+path).replace(b'\r\n',b'\n')==Path(OWNER/path).read_bytes().replace(b'\r\n',b'\n').strip()
from roll.market.post_close_packet import code
from roll.market.sse_price_quotes import fingerprint as price
from roll.market.sse_company_actions import fingerprint as collector
from roll.market.sse_action_assessments import fingerprint as assessment
assert code()==before['old_producer_fingerprint'] and price()==before['price_fingerprint']
assert collector()==before['collector_fingerprint']=='63505424914969f9e1bd65237df93c886e163d01d0facb8cd2ca6754ce2eeb20'
assert assessment()==before['assessment_fingerprint']
for row in before['official_documents'].values():
    p=OWNER/'backend/src/roll/market/reference/sse-company-contract'/row['path'];raw=subprocess.check_output(['git','show',HANDOFF+':'+p.relative_to(OWNER).as_posix()],cwd=OWNER)
    assert digest(p)=={'sha256':row['sha256'],'bytes':row['bytes']} and hashlib.sha256(raw).hexdigest()==row['sha256']
for row in before['new_observed_sources']['sources']:
    p=OWNER/'backend/src/roll/market/reference/sse-company-action-contract'/row['path'];raw=subprocess.check_output(['git','show',HANDOFF+':'+p.relative_to(OWNER).as_posix()],cwd=OWNER)
    assert digest(p)=={'sha256':row['sha256'],'bytes':row['bytes']} and hashlib.sha256(raw).hexdigest()==row['sha256']
assert digest('D:/dsh-proj/Roll/.roll-data/reconstructed19-v1/roll.sqlite3')==before['original19_bytewise_checksum']
closure=(EVIDENCE/'actual-budget-closure.json').read_bytes();budget=json.loads(closure)
assert budget['actual_attempts']==budget['maximum_attempts']==2 and budget['state']=='CLOSED_NO_MORE_ATTEMPTS'
rows=json.loads((EVIDENCE/'runtime-preservation-manifest.json').read_bytes())
assert len(rows)==1512 and sum(r['bytes'] for r in rows)==162091056
for r in rows:
    expected={'sha256':r['sha256'],'bytes':r['bytes']}
    assert digest(r['source'])==expected and digest(r['destination'])==expected
origin=OWNER/'.scratch/t30a-actual';destination=Path('D:/dsh-proj/Roll/.scratch/t30a9-independent/actual-copy');assert not destination.exists()
copied=[]
for row in rows:
    source=Path(row['source'])
    if not source.is_relative_to(origin):continue
    target=destination/source.relative_to(origin);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    assert digest(target)=={'sha256':row['sha256'],'bytes':row['bytes']}
    copied.append({'source':str(source),'copy':str(target),'sha256':row['sha256'],'bytes':row['bytes']})
assert len(copied)==37
record={'handoff':HANDOFF,'source_guard':before,'preserved1512_both_sides_verified':True,'sha_length_mismatches':0,'original_actual_or_saved_SQLite_opened':False,
    'actual_budget':budget,'closure_sha256':hashlib.sha256(closure).hexdigest(),'fresh_copy':str(destination),'copied_registered_files':copied,
    'actual_HTTP':0,'model_calls':0,'SEALED':0}
(HERE/'integrity-copy.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print('PROTECTED15_19_RAWGIT_COLLECTOR635054_BUDGET2CLOSED_1512BOTHSIDES_37FRESH_COPY_SQLITE_OPEN0')
