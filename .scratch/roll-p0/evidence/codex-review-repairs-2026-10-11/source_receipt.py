"""Record own repaired files and protect frozen model-source dependencies."""
import hashlib
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[4]
evidence = Path(__file__).resolve().parent
dependencies = ['models.py', 'execution.py', 'reconstruction.py', 'datasets.py', 'design.py',
                'historical_costs.py', 'corporate_actions.py', 'registry.py', 'training_preflight.py']
paths = ['backend/src/roll/research/' + name for name in dependencies] + [
    'backend/src/roll/market/rules.py',
    'backend/src/roll/research/reference/reconstruction/sources.json',
    'backend/src/roll/research/reference/cash-rights/sources.json',
    'backend/src/roll/research/shadow.py', 'backend/src/roll/research/statistics.py',
    'backend/src/roll/research/validation.py', 'backend/src/roll/research/forward.py',
    'backend/src/roll/agents/codex_process.py', 'backend/src/roll/research/technical_review.py']
receipt = []
for name in paths:
    content = (root / name).read_bytes()
    receipt.append({'path': name, 'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()})
mode = sys.argv[1]
if mode != 'before':
    before = json.loads((evidence / 'source-before.json').read_text(encoding='utf-8'))
    assert before[:12] == receipt[:12], 'Frozen model dependency changed'
    if mode == 'final':
        assert receipt == json.loads((evidence / 'source-after.json').read_text(encoding='utf-8'))
(evidence / ('source-' + mode + '.json')).write_text(json.dumps(receipt, indent=2), encoding='utf-8')
print(mode + ': 18 source files; protected model dependencies unchanged' if mode != 'before' else 'before: 18 source files')
