"""Run every collected backend module once in four isolated pytest processes."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
BACKEND = ROOT / 'backend'
OUT = Path(__file__).resolve().parent


def fingerprint():
    digest = hashlib.sha256()
    for directory in ('src', 'tests'):
        for path in sorted(path for path in (BACKEND / directory).rglob('*')
                           if path.is_file() and path.suffix in {'.py', '.json', '.html', '.pdf'}
                           and '__pycache__' not in path.parts):
            digest.update(path.relative_to(BACKEND).as_posix().encode())
            digest.update(path.read_bytes())
    for name in ('pyproject.toml', 'uv.lock'):
        path = BACKEND / name
        if path.exists():
            digest.update(name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


started = datetime.now(timezone.utc).isoformat()
before = fingerprint()
collection = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-m', 'pytest', 'tests',
                             '--collect-only', '-q'], cwd=BACKEND, capture_output=True, text=True, encoding='utf-8')
(OUT / 'backend-final-collection.txt').write_text(collection.stdout + collection.stderr, encoding='utf-8')
if collection.returncode:
    raise SystemExit(collection.returncode)
nodes = [line for line in collection.stdout.splitlines() if line.startswith('tests/') and '::' in line]
counts = {}
for node in nodes:
    module = node.split('::')[0]
    counts[module] = counts.get(module, 0) + 1
assert len(nodes) == len(set(nodes)) and counts
groups = [[] for _ in range(4)]
weights = [0] * 4
for module, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
    index = min(range(4), key=lambda candidate: weights[candidate])
    groups[index].append(module)
    weights[index] += count
assert sorted(module for group in groups for module in group) == sorted(counts)


def run_group(index):
    log_path = OUT / f'backend-final-group-{index + 1}.txt'
    temporary = (ROOT / f'.scratch/t19-final-real-{index + 1}').resolve()
    assert temporary.parent == (ROOT / '.scratch').resolve()
    assert temporary.name == f't19-final-real-{index + 1}'
    command = [sys.executable, '-B', '-X', 'utf8', '-m', 'pytest', '-q', *groups[index],
               '--basetemp', str(temporary)]
    clock = time.monotonic()
    with log_path.open('wb') as log:
        result = subprocess.run(command, cwd=BACKEND, stdout=log, stderr=subprocess.STDOUT)
    output = log_path.read_text(encoding='utf-8')
    summary = next((line for line in reversed(output.splitlines()) if re.search(r'\d+ passed', line)), '')
    passed = re.search(r'(\d+) passed', summary)
    return {'group': index + 1, 'modules': groups[index], 'expected_tests': weights[index],
            'exit_code': result.returncode, 'passed': int(passed[1]) if passed else 0,
            'summary': summary, 'seconds': round(time.monotonic() - clock, 2), 'log': str(log_path)}


with ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(run_group, range(4)))
after = fingerprint()
report = {'profile': 'FULL_BACKEND_FOUR_ISOLATED_PROCESSES', 'started_at': started,
          'finished_at': datetime.now(timezone.utc).isoformat(), 'code_and_tests_before': before,
          'code_and_tests_after': after, 'unchanged': before == after, 'modules': sorted(counts),
          'collected_tests': len(nodes), 'results': results,
          'passed': before == after and all(result['exit_code'] == 0 and result['passed'] == result['expected_tests'] for result in results)}
(OUT / 'backend-final-manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'passed': report['passed'], 'collected': len(nodes), 'results': results}, ensure_ascii=False))
raise SystemExit(0 if report['passed'] else 1)
