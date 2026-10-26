"""Public offline replay rejection checks; never modifies the frozen bundle."""
import base64
import copy
import json
import sys
from pathlib import Path
from fastapi import HTTPException
root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(root / 'backend/src'))
from roll.research.company.valuation import replay_bundle
bundle = json.loads((Path(__file__).parent / 'synthetic-replay-bundle.json').read_text(encoding='utf-8'))
results = []
for damage, expected in [('source', 'ARTIFACT_CORRUPT'), ('original', 'ARTIFACT_CORRUPT'), ('result', 'RESEARCH_RECORD_CORRUPT')]:
    candidate = copy.deepcopy(bundle)
    if damage == 'source': candidate['sources']['calculator.py'] = base64.b64encode(b'altered calculator').decode()
    elif damage == 'original': candidate['originals'][next(iter(candidate['originals']))] = base64.b64encode(b'altered material').decode()
    else: candidate['valuation']['result']['scenarios'][0]['per_share'] = 99
    try:
        replay_bundle(candidate)
    except HTTPException as error:
        assert error.detail['code'] == expected, error.detail
        results.append({'damage': damage, 'rejected': True, 'code': expected})
    else:
        raise AssertionError('Damaged bundle was accepted')
print(json.dumps({'status': 'PASS', 'network_calls': 0, 'model_calls': 0, 'checks': results}, indent=2))
