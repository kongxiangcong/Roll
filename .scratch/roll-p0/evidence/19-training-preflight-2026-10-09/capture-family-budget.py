"""Read existing family attempt metadata through the local host; never fit.

Only known protocol IDs from prior acquisition receipts are used. No source,
partition, execution, model, forecast, account or sealed endpoint is called.
The response body is reduced to IDs, categories, terminal status and hashes;
arbitrary attempt configurations and bases are not published.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[4]
RECEIPTS = [
    ROOT / '.scratch/roll-p0/evidence/19/baostock-real-acquisition-partial-utf8.json',
    ROOT / '.scratch/roll-p0/evidence/19/baostock-real-acquisition-repaired.json',
]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--preflight', action='store_true')
    parser.add_argument('--evaluate-metadata', action='store_true',
                        help='Evaluate the new local function using existing host metadata GETs, '
                             'without restarting or updating the live host.')
    args = parser.parse_args()
    if args.preflight and args.evaluate_metadata:
        raise ValueError('CHOOSE_LIVE_ROUTE_OR_LOCAL_METADATA_EVALUATION')
    ids = set()
    for receipt in RECEIPTS:
        for run in json.loads(receipt.read_text(encoding='utf-8'))['runs']:
            if run.get('protocol_id'):
                ids.add(run['protocol_id'])
    if not ids:
        raise ValueError('KNOWN_PROTOCOL_IDS_MISSING')
    result = {'captured_at': datetime.now(timezone.utc).isoformat(),
              'base_url': 'http://127.0.0.1:8010', 'instrument': 'SSE:600362',
              'requests': [], 'families': [], 'source_calls': 0, 'fits': 0,
              'labels_read_or_computed': False, 'sealed_read': False,
              'method': 'GET existing family attempt metadata only'}
    if args.evaluate_metadata:
        from roll.research.training_preflight import training_preflight
        import roll.research.training_preflight as preflight_module
        result['local_function_sha256'] = hashlib.sha256(
            Path(preflight_module.__file__).read_text(encoding='utf-8').replace('\r\n', '\n').encode()
        ).hexdigest()
        result['method'] = 'New local preflight function evaluated against live host metadata GETs; '
        result['method'] += 'this does not assert the live host already serves the new route.'
    with httpx.Client(base_url=result['base_url'], timeout=15, trust_env=False) as client:
        def get(path):
            response = client.get(path)
            response.raise_for_status()
            result['requests'].append({'path': path, 'status': response.status_code,
                                       'body_sha256': hashlib.sha256(response.content).hexdigest(),
                                       'bytes': len(response.content)})
            return response.json()

        roots = set()
        for protocol_id in sorted(ids):
            manifest = get('/api/research/protocols/' + protocol_id + '/attempt-manifest')
            root = manifest['lineage'][0]
            if root in roots:
                continue
            roots.add(root)
            attempts = []
            for attempt in manifest['attempts']:
                attempts.append({key: attempt.get(key) for key in
                                 ['attempt_id', 'protocol_id', 'category', 'partition',
                                  'status', 'started_at']})
                attempts[-1]['configuration_sha256'] = digest(attempt['configuration'])
            primary_used = sum(a['category'] in {'PRIMARY_FIT', 'G5_NEIGHBOR'} for a in attempts)
            calibration_used = sum(a['category'] == 'CALIBRATION' for a in attempts)
            family = {'root_protocol_id': root, 'queried_protocol_id': protocol_id,
                      'lineage': manifest['lineage'],
                      'family_protocol_ids': manifest['family_protocol_ids'],
                      'attempts': attempts, 'fits_limit': 5, 'fits_used': primary_used,
                      'fits_remaining': max(0, 5-primary_used), 'calibration_limit': 1,
                      'calibration_used': calibration_used,
                      'calibration_remaining': max(0, 1-calibration_used),
                      'basis': 'All registered family failures, aborts and interruptions count. '
                               'Host metadata does not prove absence of unreported external work.'}
            if args.preflight or args.evaluate_metadata:
                before = digest(manifest)
                if args.preflight:
                    reports = [get('/api/research/protocols/' + protocol_id + '/training-preflight')
                               for _ in range(2)]
                else:
                    class MetadataRoutes:
                        def get(self, identifier):
                            if identifier != protocol_id:
                                raise ValueError('ONLY_KNOWN_PROTOCOL_METADATA')
                            value = get('/api/research/protocols/' + identifier)
                            self.dataset_id = value['dataset_id']
                            return value

                        def dataset(self, identifier):
                            if identifier != self.dataset_id:
                                raise ValueError('ONLY_REFERENCED_DATASET_METADATA')
                            return get('/api/research/datasets/' + identifier)

                        def attempt_manifest(self, identifier):
                            if identifier != protocol_id:
                                raise ValueError('ONLY_KNOWN_PROTOCOL_METADATA')
                            return get('/api/research/protocols/' + identifier + '/attempt-manifest')

                    reports = [training_preflight(MetadataRoutes(), protocol_id) for _ in range(2)]
                    family['preflight_transport'] = 'LOCAL_FUNCTION_WITH_HTTP_METADATA_ADAPTER'
                after = get('/api/research/protocols/' + protocol_id + '/attempt-manifest')
                family['preflight'] = reports[0]
                family['repeated_preflight_equal'] = reports[0] == reports[1]
                family['manifest_unchanged'] = before == digest(after)
                if not family['repeated_preflight_equal'] or not family['manifest_unchanged']:
                    raise ValueError('READ_ONLY_PREFLIGHT_CHANGED_STATE')
            result['families'].append(family)
    output = Path(args.output).resolve()
    output.relative_to(Path(__file__).resolve().parent)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes((json.dumps(result, ensure_ascii=False, indent=2)+'\n').encode('utf-8'))
    print(json.dumps({'families': len(result['families']),
                      'budgets': [{key: f[key] for key in
                                  ['fits_used', 'fits_remaining', 'calibration_used',
                                   'calibration_remaining']} for f in result['families']],
                      'source_calls': 0, 'fits': 0, 'sealed_read': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
