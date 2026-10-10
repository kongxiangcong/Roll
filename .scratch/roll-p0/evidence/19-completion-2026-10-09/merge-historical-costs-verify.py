"""Merger verification: public source bytes and fixed API tests only."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
SOURCE = ROOT / 'backend/src/roll/research/reference'

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8').strip()

items = json.loads((SOURCE / 'historical-cost-sources.json').read_text(encoding='utf-8'))
checks = []
for item in items:
    raw = (SOURCE / item['file']).read_bytes()
    blob = subprocess.check_output(['git', 'show', 'HEAD:backend/src/roll/research/reference/' + item['file']], cwd=ROOT)
    checks.append({'id': item['id'], 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
                   'manifest_matches': hashlib.sha256(raw).hexdigest() == item['sha256'] and len(raw) == item['bytes'],
                   'git_blob_matches': blob == raw})
assert all(i['manifest_matches'] and i['git_blob_matches'] for i in checks)

modules = ['test_execution_labels.py', 'test_transparent_models.py', 'test_research_protocol.py',
           'test_research_lifecycle.py', 'test_research_acquisition_import.py', 'test_historical_execution_costs.py']
command = [sys.executable, '-B', '-X', 'utf8', '-m', 'pytest', '-q',
           *['tests/application/' + item for item in modules], '--basetemp=' + str(ROOT / '.scratch/t19-merge-hfee')]
started = datetime.now(timezone.utc).isoformat()
with (OUT / 'merge-historical-costs-backend.txt').open('wb') as stdout:
    result = subprocess.run(command, cwd=ROOT / 'backend', stdout=stdout, stderr=subprocess.STDOUT,
                            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
metadata = {'head': git('rev-parse', 'HEAD'), 'parents': git('rev-list', '--parents', '-n', '1', 'HEAD'),
            'branch': git('branch', '--show-current'), 'implementation_tip': '4a8223b33c8f7ff5c33be4d41b6f347a4a8dd5e7',
            'sources': checks, 'started_at': started, 'finished_at': datetime.now(timezone.utc).isoformat(),
            'command': command, 'exit_code': result.returncode,
            'stdout_sha256': hashlib.sha256((OUT / 'merge-historical-costs-backend.txt').read_bytes()).hexdigest(),
            'scope': 'SYNTHETIC_API_ENGINEERING_ONLY; no actual DB, sealed samples, real fit, or qualification'}
(OUT / 'merge-historical-costs-receipt.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'head': metadata['head'], 'sources_verified': len(checks), 'exit_code': result.returncode}))
raise SystemExit(result.returncode)
