"""Inventory public-data/synthetic-account acceptance artifacts; never copies credentials."""
import hashlib
import json
import os
from pathlib import Path
import shutil

from roll.config import load_runtime_environment

root = Path(__file__).resolve().parents[4]
source = root / 'backend/.roll-data/12-live'
os.environ['ROLL_ENV_FILE'] = 'D:/dsh-proj/Roll/.env'
load_runtime_environment()
secrets = [os.environ[k].encode() for k in ['DEEPSEEK_API_KEY', 'FUYAO_API_KEY'] if os.environ.get(k)]
files = []
for path in source.rglob('*'):
    if path.is_file():
        content = path.read_bytes()
        if any(secret in content for secret in secrets):
            raise RuntimeError('ACCEPTANCE_ARTIFACT_CONTAINS_CREDENTIAL')
        files.append({'source': str(path), 'relative': str(path.relative_to(source)), 'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()})
report = {'source_directory': str(source), 'evidence_kind': 'REAL_DEEPSEEK_TASK_PUBLIC_SOURCES_SYNTHETIC_ACCOUNT', 'file_count': len(files), 'bytes': sum(f['bytes'] for f in files), 'credential_matches': 0, 'files': files}
output = Path(__file__).parent / 'live'
(output / 'runtime-inventory.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
for name in ['deepseek-real-evidence.png', 'deepseek-real-cancel.png', 'deepseek-real-auth-error.png', 'deepseek-real-crash.png', 'results.json']:
    shutil.copy2(root / 'frontend/test-results' / name, output / name)
crash = json.loads((output / 'crash-run.json').read_text(encoding='utf-8'))
import ctypes
kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.OpenProcess.restype = ctypes.c_void_p
dead = []
for pid in crash['process']['observed_pids']:
    handle = kernel.OpenProcess(0x1000, False, pid)
    if handle:
        kernel.CloseHandle(ctypes.c_void_p(handle))
        raise RuntimeError('INTERRUPTED_TASK_PID_STILL_PRESENT')
    dead.append(pid)
(output / 'crash-os-verification.json').write_text(json.dumps({'observed_pids_no_longer_present': dead, 'task_root_removed': not Path(crash['process']['task_root']).exists(), 'recovery_cleanup': crash['recovery_cleanup']}, indent=2), encoding='utf-8')
print(json.dumps({k: v for k, v in report.items() if k != 'files'}))
