"""Build a METHOD-only, fresh-store valuation bundle using public service fixtures."""
import argparse
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(root / 'backend/src'), str(root / 'backend/tests/company_research')]
from test_shared_evidence import service
from test_valuation import valuation_request

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--data-directory', required=True, type=Path)
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
if (args.data_directory / 'roll.sqlite3').exists():
    raise SystemExit('Use a fresh directory; existing research is never rewritten')
research = service(args.data_directory)
command, snapshot = valuation_request(research)
saved = research.calculate_valuation(command)
args.output.write_text(json.dumps(research.valuation_bundle(saved['valuation_id']), ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'evidence_kind': 'METHOD_CASE', 'company_id': snapshot['company_id'],
    'snapshot_id': snapshot['snapshot_id'], 'valuation_id': saved['valuation_id'],
    'usable_range': saved['result']['usable_range'], 'replay': research.replay_valuation(saved['valuation_id']),
    'network_calls': 0, 'model_calls': 0}, ensure_ascii=False, indent=2))
