"""Host-clocked finite plan only: no database, no HTTP."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from roll.market import sse_company_contract as source
from roll.market.rules import SHANGHAI
folder = Path(__file__).resolve().parent
repo = folder.parents[3]
contract = source.schema()
value = {'created_at': datetime.now(timezone.utc).isoformat(),
         'host_date': datetime.now(SHANGHAI).date().isoformat(),
         'source_commit': subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=repo, capture_output=True, text=True, check=True).stdout.strip(),
         'parser_fingerprint': source.fingerprint(), 'source_files': json.loads((folder / 'source-live-before.json').read_bytes())['own'],
         'documents': contract['sources'], 'document_mapping_hash': contract['mapping_hash'],
         'requests': [{'role': role, 'url': source.URLS[role], 'parameters': source.PARAMS[role]} for role in ['snap', 'company']],
         'total_actual_http_attempt_limit': 2, 'per_role_attempt_limit': 1,
         'namespace': str(repo / '.scratch/t30u-live'), 'method': 'GET', 'response_variant': 'JSON_WITHOUT_CALLBACK',
         'declared_client_variant': 'POST_JSONP_CALLBACK', 'frontend_equivalence_claim': False,
         'timeout_seconds': 15, 'max_decoded_bytes_per_response': 8 * 1024 * 1024,
         'redirects': False, 'retries': 0, 'fallbacks': 0, 'source_document_calls': 0,
         'expected_refusals': ['WRONG_OR_MISSING_SECURITY', 'MISSING_FUTURE_OR_UNSUPPORTED_DATE',
                               'SELECT_ALIGNMENT', 'INVALID_NUMERIC_VALUE', 'COMPANY_SQL_OR_A_BRANCH',
                               'AMBIGUOUS_EMPTY_COMPANY', 'HTTP_ERROR_OR_INCOMPLETE_PREFIX'],
         'unknown_dimensions': source.GAPS, 'evidence_kind': 'REAL_SOURCE_ASSESSMENT',
         'system_usable': False, 'actual_forward_start': False, 'capability': 'NOT_GRANTED'}
content = (json.dumps(value, indent=2) + '\n').encode()
target = folder / 'finite-execution-plan.json'
assert not target.exists()
target.write_bytes(content)
print(json.dumps({'plan': str(target), 'sha256': hashlib.sha256(content).hexdigest(),
                  'parser_fingerprint': value['parser_fingerprint'], 'max_calls': 2}))
