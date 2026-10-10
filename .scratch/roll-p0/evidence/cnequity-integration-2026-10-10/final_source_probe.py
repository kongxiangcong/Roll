"""One bounded live source check of the final collector fingerprint, plus recovery inventory."""
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'backend/src'))
from roll.app import create_app
from roll.market.cnequity import CNEquityCollection
from roll.accounts.ledger import now
from datetime import datetime

app = create_app(ROOT/'.roll-data/pit')
pit = app.state.prospective
plan = pit.plans()[0]
run = CNEquityCollection(app.state.evidence, pit.sources).one(
    plan, pit.sources.policy('cnequity-tdx-daily'), time.monotonic()+20)
batch = pit.record(plan['plan_id'], run['run_id'])
replay = app.state.evidence.replay(run['run_id'])
comparison = pit.sources.compare_daily(plan['plan_id'], pit.as_of(plan['plan_id'], datetime.fromisoformat(now()))['versions'])
integrity = pit.sources.integrity()
result = {'run': run, 'batch': batch, 'replay': {'network_calls': replay['network_calls'], 'fact_count': len(replay['facts'])},
          'comparison': comparison, 'integrity': integrity, 'readiness': pit.readiness(plan['plan_id'])}
if integrity['consistent']:
    result['backup'] = app.state.backups.create(reason='CNEQUITY_FINAL_SOURCE_VERIFICATION')
Path(__file__).with_name('final-source-probe.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'status': run['status'], 'facts': batch['fact_count'], 'network_calls': run['network_calls'],
                  'integrity': integrity['consistent'], 'capability': result['readiness']['capability']}))
assert integrity['consistent'] and run['status'] == 'COMPLETE' and batch['fact_count'] > 0
