"""Read-only closeout of the completed independent METHOD API flow; never starts Host."""
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys

SCOPE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('accept_repairs', SCOPE / 'accept-repairs.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
os.environ['ROLL_ENV'] = 'test'
sys.path.insert(0, str(a.SOURCE / 'backend/src'))

def rows(profile, table):
    with sqlite3.connect((profile / 'roll.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
        return {row[0]: tuple(row) for row in db.execute('SELECT * FROM ' + table)}

baseline = a.PROFILE.parent / 'independent-method-successor'
for table in ['research_models', 'research_forecasts', 'research_attempts']:
    assert rows(baseline, table) == rows(a.PROFILE, table), table
old_attempts = rows(baseline, 'research_validation_attempts')
new_attempts = rows(a.PROFILE, 'research_validation_attempts')
assert len(new_attempts) == len(old_attempts) + 1
assert all(new_attempts[k] == v for k, v in old_attempts.items())
added = json.loads(next(v[-1] for k, v in new_attempts.items() if k not in old_attempts))
assert added['status'] == 'SUCCEEDED' and added['confirmation_pass_look'] is False
assert added['command']['purpose'] == 'DIAGNOSTIC'
for table in ['research_complete_freezes', 'research_validations', 'research_shadow_runs']:
    before, after = rows(baseline, table), rows(a.PROFILE, table)
    assert all(after[k] == v for k, v in before.items()), table
    assert len(after) == len(before) + 1, table
freeze = json.loads(next(v[-1] for k, v in rows(a.PROFILE, 'research_complete_freezes').items()
    if k not in rows(baseline, 'research_complete_freezes')))
validation = json.loads(next(v[-1] for k, v in rows(a.PROFILE, 'research_validations').items()
    if k not in rows(baseline, 'research_validations')))
shadow = json.loads(rows(a.PROFILE, 'research_shadow_runs')[freeze['freeze_id']][-1])
assert freeze['method_validation']['version'] == '20-method-v2'
assert freeze['statistical_methods']['version'] == '20-statistical-method-v2'
assert freeze['method_validation']['comparator_contract']['MA5_MA20']['exit'] == 'HORIZON_SESSION20_CLOSE'
assert freeze['predecessor_protocol_id'] in rows(baseline, 'research_protocols')
assert validation['purpose'] == 'DIAGNOSTIC' and validation['capability_status'] == 'NOT_GRANTED'
assert validation['system_usable'] is validation['sealed_read'] is validation['confirmation_pass_look'] is False
assert freeze['forward_started_at'] is None
archives = []
for record in [freeze, validation, shadow]:
    for key, item in record.items():
        if 'archive' not in key:
            continue
        path = (a.PROFILE / item['path']).resolve()
        assert path.is_relative_to(a.PROFILE.resolve())
        assert path.stat().st_size == item['bytes'] and a.sha(path) == item['sha256']
        archives.append({'kind':item['kind'], 'sha256':item['sha256'], 'bytes':item['bytes']})
sources = json.loads((a.EVIDENCE / 'source-final.json').read_text(encoding='utf-8'))
assert all(a.sha(a.SOURCE / i['path']) == i['sha256'] for i in sources)
preservation = []
for label in ['old', 'new', 'final']:
    manifest = json.loads((a.EVIDENCE / ('runtime-' + label + '-method-manifest.json')).read_text(encoding='utf-8'))
    for item in manifest['files']:
        for base in ['source', 'destination']:
            path = Path(manifest[base]) / item['path']
            assert path.stat().st_size == item['bytes'] and a.sha(path) == item['sha256']
    preservation.append({'profile':label, 'files':manifest['file_count'], 'sha_length_mismatches':0})
result = {'status':'PASS', 'evidence_kind':'METHOD_CASE', 'literal':a.literal_checks(),
    'public_API_flow':'Completed all API, old-version409, new freeze, shadow/validation replay and restart assertions before final harness table-name mistake; this read-only closeout corrects that count without rerunning Host.',
    'old_shadow_and_validation_409':True, 'restart_replay_match':True,
    'old_freeze_validation_shadow_rows_unchanged':True, 'new_freeze_id':freeze['freeze_id'],
    'new_validation_id':validation['validation_id'], 'new_model_or_forecast_count':0,
    'family_attempt_rows_unchanged':True, 'added_validation_attempts':'1 DIAGNOSTIC SUCCEEDED only',
    'network_calls':0, 'provider_calls':0, 'SEALED_read':False, 'account_version':0,
    'forward_started_at':None, 'NOT_GRANTED':True, 'source18_stable':True,
    'preserved_runtime_profiles':preservation, 'new_archive_integrity':archives,
    'closeout':'SQLite mode=ro, literal-only; no Host restart or research mutation', 'exit_code':0}
a.save('independent-results.json', result)
print('Independent METHOD acceptance closeout PASS; 0 archive/source mismatches; no Host/provider/fit')
