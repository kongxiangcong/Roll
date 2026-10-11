"""Capture scoped source and protected-baseline evidence; no runtime mutation."""
import hashlib
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[4]
baseline = '5a7f86e89cf978aa74ba637ce8db677673391aab'
protected = ['research/models.py', 'research/execution.py', 'research/reconstruction.py', 'research/datasets.py',
             'research/design.py', 'research/historical_costs.py', 'research/corporate_actions.py', 'research/registry.py',
             'research/training_preflight.py', 'market/rules.py', 'research/reference/reconstruction/sources.json',
             'research/reference/cash-rights/sources.json']
owned = ['backend/src/roll/app.py', 'backend/src/roll/decisions/capabilities.py', 'backend/tests/application/test_capabilities.py',
         'backend/tests/support/capability_method_app.py', 'frontend/src/api.ts', 'frontend/src/components/capability-panel.tsx',
         'frontend/src/pages/settings.tsx', 'frontend/src/pages/today.tsx', 'frontend/tests/e2e/capabilities.spec.ts']


def digest(raw):
    return hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()


checks = []
for suffix in protected:
    path = 'backend/src/roll/' + suffix
    old = subprocess.check_output(['git', 'show', baseline + ':' + path], cwd=root)
    current = (root / path).read_bytes()
    checks.append({'path': path, 'baseline_sha256': digest(old), 'current_sha256': digest(current), 'unchanged': digest(old) == digest(current)})
sources = [{'path': p, 'normalized_sha256': digest((root / p).read_bytes()), 'bytes': (root / p).stat().st_size} for p in owned]
result = {'baseline': baseline, 'owned_sources': sources, 'protected_sources': checks, 'protected_all_unchanged': all(c['unchanged'] for c in checks)}
assert result['protected_all_unchanged']
(Path(__file__).parent / 'source-receipt.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print('SOURCE_RECEIPT_PASS', len(sources), 'owned;', len(checks), 'protected unchanged')
