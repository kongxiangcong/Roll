"""Offline public read/backup verification. Never invokes a model."""
import hashlib
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'backend' / 'src'))
from roll.accounts.ledger import Ledger
from roll.market.directory import MarketDirectory
from roll.market.evidence import EvidenceStore
from roll.research.company import CompanyResearch
from roll.runtime.backups import Backups
base = Path(__file__).parent
receipt = json.loads((base / 'real-receipt.json').read_text(encoding='utf-8'))
ledger = Ledger(Path(receipt['data_directory']))
research = CompanyResearch(EvidenceStore(ledger, MarketDirectory(ledger)))
checks = []
for folder in [base / 'attempt01', base]:
    expected = json.loads((folder / 'real-snapshot.json').read_text(encoding='utf-8'))
    packet = json.loads((folder / 'real-input.json').read_text(encoding='utf-8'))
    run = json.loads((folder / 'real-run.json').read_text(encoding='utf-8'))
    assert research.analysis_snapshot(expected['snapshot_id'], purpose='DAILY') == expected
    assert research.analysis_snapshot(expected['snapshot_id'], purpose='REPORT') == expected
    assert research.analysis_input(packet['input_id']) == packet
    assert research.analysis_run(run['run_id']) == run
    raw = (folder / 'real-output.raw').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == run['candidate_output_sha256']
    assert research.evidence.raw(run['candidate_output_sha256']).read_bytes() == raw
    for h in expected['core']['hypotheses']:
        assert research.operating_hypothesis(h['version_id']) == h
    checks.append({'snapshot_id':expected['snapshot_id'], 'raw_output_sha256':run['candidate_output_sha256'],
                   'hypotheses':len(expected['core']['hypotheses']), 'core_sha256':expected['core_sha256']})
backups = Backups(Path(receipt['data_directory']))
backup = backups.create()
backups.export(backup['backup_id'])
result = {'status':'PASS', 'snapshots':checks, 'final_code_backup_export_verified':True, 'model_calls':0}
(base / 'offline-replay.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')
print(json.dumps(result, ensure_ascii=False))
