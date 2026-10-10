"""Protect metadata without opening runtime databases, inputs or SEALED partitions."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import httpx

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
files = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
tracked = []
for name in files:
    if not name:
        continue
    path = ROOT / name
    if path.is_file():
        body = path.read_bytes()
        tracked.append({'path': name, 'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body)})
pid = 'a9792e33-98e1-464e-85ba-046623fb4bd1'
with httpx.Client(timeout=10) as client:
    response = client.get('http://127.0.0.1:8010/api/research/protocols/' + pid + '/attempt-manifest')
    response.raise_for_status()
    manifest = response.json()
attempts = manifest['attempts']
report = {'captured_at': datetime.now(timezone.utc).isoformat(),
          'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
          'status': subprocess.check_output(['git', 'status', '--short'], cwd=ROOT).decode(),
          'tracked_files': tracked, 'attempt_manifest': manifest,
          'remaining_primary_and_neighbors': 5-sum(a['category'] in {'PRIMARY_FIT', 'G5_NEIGHBOR'} for a in attempts),
          'remaining_calibration': 1-sum(a['category']=='CALIBRATION' for a in attempts),
          'runtime_inputs_opened': False, 'sealed_read': False, 'fits': 0,
          'ignored_data_policy': 'Existing ignored original data retained in place; no cleanup or broad reads.'}
target = OUT / 'initial-state.json'
if target.exists():
    raise RuntimeError('Never overwrite the initial preservation snapshot')
target.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({k: report[k] for k in ['head', 'remaining_primary_and_neighbors', 'remaining_calibration', 'sealed_read']}))
