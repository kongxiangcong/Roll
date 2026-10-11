"""Only newly owned METHOD databases are opened; old archives remain byte-only."""
from pathlib import Path
import sqlite3,json,hashlib
from contextlib import closing
SCOPE=Path(__file__).resolve().parent;ROOT=SCOPE.parents[4]
runtime=ROOT/'.roll-data/implementation-evidence/ticket31-independent/pytest-01'
profiles=[]
for p in runtime.rglob('roll.sqlite3'):
    if 'backups' in p.parts:continue
    assert p.resolve().is_relative_to(runtime.resolve())
    with closing(sqlite3.connect(p)) as db:
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        counts={t:db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ['research_models','research_forecasts','research_attempts','research_forward_plans','research_forward_samples']}
        assert all(v==0 for v in counts.values()),counts
        profiles.append({'profile':str(p.relative_to(runtime)),'rows':counts})
assert len(profiles)==2
base=ROOT/'.roll-data/implementation-evidence/31/worker-delivery'
browser=json.loads((base/'managed-runtime/acceptance-31-browser/run-KSkC0e/receipt.json').read_text())
assert browser['status']=='PASS' and all(browser['checks'].values())
assert browser['observation']['result']['forecast'] is None and not browser['observation']['result']['forward_sample_created']
result={'status':'PASS','own_profiles':profiles,'saved_profile_SQL_connections':0,'browser_existing_receipt':'run-KSkC0e','browser_checks':browser['checks'],'existing_screenshot_inspected':True,'provider_calls':0,'external_HTTP':0,'METHOD_training_runs_this_acceptance':0,'actual_profile_opened':False,'real_qualification':False,'ticket31_completion':'partial'}
(SCOPE/'closeout-results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
(SCOPE/'execution.json').write_text(json.dumps({'command':'root backend/.venv/Scripts/python.exe -B -X utf8 -m pytest ticket31-independent/test_public.py -q -p no:cacheprovider --basetemp=owned pytest-01','source_oid':'a19ce9b592aa0ae207255c40691cb6d76f1e6554','actual_exit_code':0,'single_run':'2 passed in 14.65s','exec_session':73717,'final_output_chunk':'359063','actual_worker_exit_code':0,'source_supplier':'MockTransport exactly one local supplied original; no external HTTP'},indent=2)+'\n',encoding='utf-8',newline='\n')
print('Own METHOD databases, old browser metadata and execution closeout PASS')
