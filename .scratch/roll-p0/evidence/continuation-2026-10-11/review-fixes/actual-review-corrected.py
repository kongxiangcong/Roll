"""Future bounded review handoff. Prepared/compiled only; requires separate user approval.

The old ticket23 packet/helper are historical. This helper must never be used with
that packet. Flags identify the exact separately approved new packet; generating
this file or a local preview does not provide that approval.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[5]
SCOPE = Path(__file__).resolve().parent
PROFILE = ROOT / '.roll-data/implementation-evidence/continuation-review-fixes/actual-corrected-copy'
APPROVAL = ROOT / '.roll-data/implementation-evidence/continuation-review-fixes/provider-approval-current'
OUT = ROOT / '.roll-data/implementation-evidence/continuation-review-fixes/actual-provider-results'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-separately-approved-reviews', action='store_true')
    parser.add_argument('--authorized-material-fingerprint', required=True)
    parser.add_argument('--authorized-manifest-sha256', required=True)
    args = parser.parse_args()
    if not args.execute_separately_approved_reviews:
        parser.error('Compile-only handoff; separate explicit approval for the new packet and destinations is required')
    receipt = json.loads((SCOPE / 'actual-corrected-successor-results.json').read_text(encoding='utf-8'))
    manifest_bytes = (APPROVAL / 'provider-material-manifest.json').read_bytes()
    assert digest(manifest_bytes) == receipt['approval_manifest_sha256'] == args.authorized_manifest_sha256
    manifest = json.loads(manifest_bytes)
    assert manifest['material_fingerprint'] == receipt['material_fingerprint'] == args.authorized_material_fingerprint
    assert manifest['material_id'] == receipt['material_id']
    assert not OUT.exists(), 'Keep prior attempts; no automatic retry or overwrite'
    for item in [*manifest['files'], manifest['reproduction_file']]:
        path = Path(item['path']).resolve()
        assert path.is_relative_to(APPROVAL / 'provider-materials')
        raw = path.read_bytes()
        assert digest(raw) == item.get('tool_response_sha256', item.get('sha256'))
        assert len(raw) == item.get('tool_response_bytes', item.get('bytes'))
    for relative, expected in manifest['source_sha256'].items():
        assert digest((ROOT / relative).read_bytes().replace(b'\r\n', b'\n')) == expected
    # Only after a separately approved invocation may the existing credential pipeline load.
    os.environ['ROLL_ENV'] = 'test'
    os.environ['ROLL_ENV_FILE'] = str(ROOT / '.env')
    os.environ.pop('ROLL_CODEX_AUTH_FILE', None)
    from fastapi.testclient import TestClient
    from roll.app import create_app
    OUT.mkdir(parents=True, exist_ok=False)
    with TestClient(create_app(PROFILE)) as client:
        def get(path):
            response = client.get(path); response.raise_for_status(); return response.json()
        def post(path, body):
            response = client.post(path, json=body); response.raise_for_status(); return response.json()
        validation_id = receipt['validation_id']
        material = get('/api/research/review-materials/' + receipt['material_id'])
        assert material['material_fingerprint'] == receipt['material_fingerprint']
        assert material['basis_id'] == validation_id
        assert not get('/api/research/review-materials/' + material['material_id'] + '/reviews')
        original_validation = get('/api/research/validations/' + validation_id)
        protocol_id = original_validation['protocol_id']
        def boundary():
            return {key: get(path) for key, path in {
                'account': '/api/account', 'protocol': '/api/research/protocols/' + protocol_id,
                'attempts': '/api/research/protocols/' + protocol_id + '/attempt-manifest',
                'audit': '/api/research/protocols/' + protocol_id + '/audit',
            }.items()}
        before = boundary()
        records = []
        for backend in ('CODEX', 'DEEPSEEK'):
            settings = get('/api/agents/settings')
            if settings['backend'] != backend:
                post('/api/agents/settings', {'expected_version': settings['version'], 'backend': backend})
            started = post('/api/research/review-materials/' + material['material_id'] + '/reviews',
                {'expected_material_fingerprint': material['material_fingerprint']})
            deadline = time.monotonic() + 140
            while time.monotonic() < deadline:
                run = get('/api/research/technical-reviews/' + started['run_id'])
                if run['status'] != 'RUNNING':
                    break
                time.sleep(.2)
            else:
                raise RuntimeError('Review exceeded bounded host termination margin; do not retry automatically')
            records.append(run)
            (OUT / ('actual-' + backend.lower() + '.json')).write_text(json.dumps(run, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        delivery = get('/api/research/review-materials/' + material['material_id'] + '/delivery')
        exported = post('/api/research/review-materials/' + material['material_id'] + '/export', {})
        assert before == boundary() and original_validation == get('/api/research/validations/' + validation_id)
        assert len({record['material_fingerprint'] for record in records}) == 1
        assert delivery['preliminary'] and delivery['capability_status'] == 'NOT_GRANTED'
        report = {'validation_id': validation_id, 'material_id': material['material_id'],
            'material_fingerprint': material['material_fingerprint'], 'delivery': delivery, 'export': exported,
            'same_material_both_providers': True, 'account_attempts_sealed_forward_unchanged': True,
            'historical_validation_unchanged': True, 'provider_body_context_presence': manifest['provider_body_context_presence'],
            'context_limit': 'Native predecessor-freeze field and frozen basis are not projected into the provider protocol body; exact successor linkage remains in local complete-freeze archive.'}
        (OUT / 'actual-results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
