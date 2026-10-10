"""Offline verification of this research batch; does not access model partitions."""
import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def verify(directory: Path):
    raw = directory / '.roll-data'
    inventory = json.loads((raw / 'gap-research-v1/inventory.json').read_text(encoding='utf-8'))
    sources = [{**row, 'path': str(raw / 'gap-research-v1' / row['path'])}
               for row in inventory['originals']]
    sources.append(json.loads((directory / 'annual-report-2022-followup.json').read_text(encoding='utf-8')))
    sources.append(json.loads((directory / 'annual-report-2025-followup.json').read_text(encoding='utf-8')))
    policies = json.loads((directory / 'dividend-tax-research-assessment.json').read_text(encoding='utf-8'))
    sources.extend(row for row in policies['sources'] if row['verified_offline'])
    checks = []
    for row in sources:
        path = Path(row['path']).resolve()
        if not path.is_relative_to(raw.resolve()):
            raise ValueError('Research original outside research archive')
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        checks.append({'url': row['url'], 'path': str(path.relative_to(directory)),
                       'sha256': digest, 'bytes': len(content),
                       'sha256_matches': digest == row['sha256'],
                       'bytes_match': len(content) == row['bytes']})
    for name in ['collect-tax-research.py', 'collect-annual-report-2025.py',
                 'extract-annual-report-2025.py', 'verify-research-originals.py']:
        ast.parse((directory / name).read_text(encoding='utf-8'))
    result = {'verified_at': datetime.now(timezone.utc).isoformat(),
              'verified_originals': len(checks),
              'unique_sha256': len({row['sha256'] for row in checks}),
              'total_bytes': sum(row['bytes'] for row in checks),
              'mismatches': [row for row in checks if not row['sha256_matches'] or not row['bytes_match']],
              'excluded_http_403_responses': 1,
              'checks': checks,
              'collector_and_verifier_ast': 'PASS',
              'network_requests': 0, 'model_fits': 0, 'labels_computed': False,
              'sealed_partitions_read': False,
              'qualification': 'SOURCE_ORIGINAL_VERIFICATION_ONLY'}
    (directory / 'research-originals-verification.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if len(checks) != 29 or result['mismatches']:
        raise ValueError('Unexpected count or archive mismatch')
    return {key: result[key] for key in ['verified_originals', 'unique_sha256', 'total_bytes', 'mismatches']}


if __name__ == '__main__':
    print(json.dumps(verify(Path(__file__).resolve().parent), ensure_ascii=False))
