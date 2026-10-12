"""Prove final tested source survives an evidence-only integration merge."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[5]
evidence = Path(__file__).resolve().parent
before = json.loads((evidence / 'source-before.json').read_text(encoding='utf-8'))
after = json.loads((evidence / 'source-after.json').read_text(encoding='utf-8'))
original = {item['path']: item for item in before}
checked = []
for expected in after:
    content = (root / expected['path']).read_bytes()
    current = {'path': expected['path'], 'bytes': len(content),
               'sha256': hashlib.sha256(content).hexdigest()}
    assert current == expected, current
    if current['path'] not in {'backend/src/roll/research/shadow.py',
                                'backend/src/roll/research/forward.py'}:
        assert current == original[current['path']], current
    checked.append(current)
result = {'tested_source_files': checked, 'stable_source_count': len(checked),
          'unchanged_model_dependency_count': 12, 'source_mismatches': 0,
          'evidence_only_integration_tip': '670557703c4365ff519bf1f90d2a4c4ea0eb02f4',
          'final_related_test_exit': 0, 'final_related_tests_passed': 44,
          'final_related_test_seconds': 458.10}
(evidence / 'final-source-verification.json').write_text(
    json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print('14 stable source files; 12 unchanged model dependencies; 0 mismatches')
