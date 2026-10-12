"""No Host: fixed-source, raw-original and own stopped METHOD state closeout."""
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess

SCOPE=Path(__file__).resolve().parent
ROOT=SCOPE.parents[4]
CHILD=ROOT/'.scratch/worktrees/ticket30-producer'
EVIDENCE=CHILD/'.scratch/roll-p0/evidence/30-producer'
RUNTIME=ROOT/'.roll-data/implementation-evidence/ticket30-producer-independent'
OID='c67378800ab35ec791d7d817f66465edab3aaef7'
def info(path):
    body=path.read_bytes();return {'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body)}
sources=json.loads((EVIDENCE/'source-composition-after.json').read_text(encoding='utf-8'))
for item in sources['protected']:
    for base in [ROOT,CHILD]:assert info(base/item['path'])==item['root']
for name,value in sources['own'].items():assert info(CHILD/name)==value
assert info(ROOT/'.roll-data/reconstructed19-v1/roll.sqlite3')==sources['original19_sqlite']
assert subprocess.check_output(['git','-C',str(CHILD),'rev-parse','HEAD'],text=True).strip()==OID
assert not subprocess.check_output(['git','-C',str(CHILD),'status','--porcelain','--untracked-files=no'],text=True).strip()
execution=json.loads((SCOPE/'execution.json').read_text(encoding='utf-8'));assert execution['exit_code']==0
raw_log=RUNTIME/'public-api.raw.txt'
assert '4 passed in 38.98s' in raw_log.read_text(encoding='utf-8-sig')
log=raw_log.read_text(encoding='utf-8-sig').replace('\r\n','\n')
(SCOPE/'public-api.txt').write_text(log,encoding='utf-8',newline='\n')
profiles=[]
for dbfile in sorted((RUNTIME/'pytest-02').glob('*/data/roll.sqlite3')):
    with sqlite3.connect(dbfile.as_uri()+'?mode=ro',uri=True) as db:
        names={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required=['research_models','research_forecasts','research_attempts','research_forward_plans','research_forward_samples']
        assert set(required)<=names
        counts={name:db.execute('SELECT COUNT(*) FROM '+name).fetchone()[0] for name in required}
        assert all(v==0 for v in counts.values()),counts
        runs=[json.loads(r[0]) for r in db.execute('SELECT value FROM retrieval_runs')]
        assert all(r['backend']=='SSE_POST_CLOSE' and r['evidence_kind']=='METHOD_CASE' for r in runs)
        plans=[json.loads(r[0]) for r in db.execute('SELECT value FROM pit_collection_plans')]
        assert all(p['forward_started_at'] is None and p['capability']=='NOT_GRANTED' for p in plans)
        packets=[json.loads(r[0]) for r in db.execute('SELECT value FROM post_close_packets')]
        assert all(not p['forward_admissible'] and p['forward_started_at'] is None for p in packets)
        profiles.append({'profile':dbfile.parent.parent.name,'models_forecasts_attempts_forward_counts':counts,
            'local_fixed_supplier_run_count':len(runs),'packets':len(packets),'all_forward_admissible':False})
assert len(profiles)==4
result={'status':'PASS','source_oid':OID,'independent_tests':4,'pytest_seconds':38.98,'actual_exit_code':0,
    'protected_raw_sources':15,'protected_model_sources':12,'owned_source_raw_mismatches':0,
    'original19_checksum_only':sources['original19_sqlite'],'actual_SQLite_opened':False,
    'raw_stdout':{'path':str(raw_log),'sha256':info(raw_log)['sha256'],'bytes':info(raw_log)['bytes']},
    'committed_stdout_normalization':'CRLF to LF only','METHOD_profiles':profiles,
    'external_HTTP_calls':0,'provider_model_calls':0,'SEALED_read':False,'new_fit_forecast':False,
    'ticket30_completion':'partial','tickets31_32_not_closed':True,
    'actual_forward_clock_started':False,'actual_grant_created':False}
(SCOPE/'closeout-results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print('Closeout PASS: 4 isolated METHOD databases, stable sources and original19 checksum; no actual forward authority')
