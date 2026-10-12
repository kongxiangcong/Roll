"""One explicitly authorized continuation of the sole pre-bootstrap failure; no automatic retry or DS."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time

ROOT = Path(__file__).resolve().parents[5]
SCOPE = Path(__file__).resolve().parent
PROFILE = ROOT / '.roll-data/implementation-evidence/continuation-review-fixes/actual-corrected-copy'
APPROVAL = ROOT / '.roll-data/implementation-evidence/continuation-review-fixes/provider-approval-current'
OUT = ROOT / '.roll-data/implementation-evidence/continuation-review-fixes/actual-codex-results-continuation-01'
FINGERPRINT = '95ddbd52fa7f4e2df78b97556f36c6c675da75603eb290ec5ecab260abfbfba1'
MANIFEST_SHA = '206d2ec53d85af4b28423017da24b5a6030d5078ec5237ee939233245ef84984'
PREDECESSOR = '88f44e5c-33fd-4e27-a36a-66b9d33c853c'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def research_history():
    with sqlite3.connect((PROFILE / 'roll.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
        tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'research_%' ORDER BY name")]
        return {table: sorted(digest(repr(tuple(row)).encode()) for row in db.execute('SELECT * FROM ' + table)) for table in tables}


def review_count():
    with sqlite3.connect((PROFILE / 'roll.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
        return db.execute('SELECT count(*) FROM technical_review_runs').fetchone()[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', choices=['CODEX'], required=True)
    parser.add_argument('--execute-user-approved-codex', action='store_true')
    parser.add_argument('--authorized-material-fingerprint', required=True)
    parser.add_argument('--authorized-manifest-sha256', required=True)
    parser.add_argument('--codex-auth-file', required=True)
    args = parser.parse_args()
    if not args.execute_user_approved_codex:
        parser.error('Execution requires the specific human-approved CODEX-only invocation')
    assert args.authorized_material_fingerprint == FINGERPRINT and args.authorized_manifest_sha256 == MANIFEST_SHA
    auth_path = Path(args.codex_auth_file).resolve()
    assert auth_path == Path('C:/Users/72449/.codex/auth.json').resolve() and auth_path.is_file()
    assert not OUT.exists(), 'Preserve all attempts; never repeat or overwrite automatically'
    receipt = json.loads((SCOPE / 'actual-corrected-successor-results.json').read_text(encoding='utf-8'))
    manifest_bytes = (APPROVAL / 'provider-material-manifest.json').read_bytes()
    assert digest(manifest_bytes) == receipt['approval_manifest_sha256'] == MANIFEST_SHA
    manifest = json.loads(manifest_bytes)
    assert manifest['material_fingerprint'] == receipt['material_fingerprint'] == FINGERPRINT
    assert manifest['material_id'] == receipt['material_id']
    body_files = [item for item in manifest['files'] if 'material_id' in item]
    assert len(body_files) == 7 and len({item['material_id'] for item in body_files}) == 7
    assert sum(item['content_bytes'] for item in body_files) == manifest['inventory_content_bytes'] == 179889
    for item in [*manifest['files'], manifest['reproduction_file']]:
        path = Path(item['path']).resolve()
        assert path.is_relative_to(APPROVAL / 'provider-materials')
        raw = path.read_bytes()
        assert digest(raw) == item.get('tool_response_sha256', item.get('sha256'))
        assert len(raw) == item.get('tool_response_bytes', item.get('bytes'))
        if 'material_id' in item:
            body = json.loads(raw)['content'].encode()
            assert digest(body) == item['material_sha256'] and len(body) == item['content_bytes']
    for relative, expected in manifest['source_sha256'].items():
        assert digest((ROOT / relative).read_bytes().replace(b'\r\n', b'\n')) == expected
    assert review_count() == 1, 'Only the explicitly authorized sole failed predecessor is allowed'
    prior_path = ROOT / '.roll-data/implementation-evidence/continuation-review-fixes/actual-codex-results-authorized-auth/actual-codex.json'
    assert file_sha(prior_path) == 'c602ed3478bd0b9feea23167d2250f45ef30dfe693fc1bbcfafa77a0418e27cf'
    prior_saved = json.loads(prior_path.read_text(encoding='utf-8'))
    with sqlite3.connect((PROFILE / 'roll.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
        prior_rows = db.execute('SELECT id, value FROM technical_review_runs').fetchall()
    assert len(prior_rows) == 1 and prior_rows[0][0] == PREDECESSOR
    prior_before = json.loads(prior_rows[0][1])
    assert prior_before == prior_saved
    assert prior_before['status'] == 'FAILED' and prior_before['backend'] == 'CODEX'
    assert prior_before['material_id'] == receipt['material_id'] and prior_before['material_fingerprint'] == FINGERPRINT
    assert prior_before['error'] == {'code': 'SDK_RUNTIME_ERROR', 'type': 'InternalRpcError'}
    assert not prior_before.get('bootstrap_audit') and not prior_before.get('runtime_audit')
    assert not prior_before.get('runtime_thread_id') and not prior_before.get('runtime_turn_id')
    assert not prior_before.get('runtime_completion') and not prior_before['tools'] and not prior_before['archives']
    assert all(prior_before['call_usage'].get(k, 0) == 0 for k in ['model_requests', 'host_tool_calls', 'http_calls', 'runtime_operations'])
    probe = json.loads((SCOPE / 'codex-startup-probe-results.json').read_text(encoding='utf-8'))
    assert probe['verdict'] == 'PASS' and probe['initialize_succeeded'] and probe['account_read_succeeded']
    assert probe['model_calls'] == probe['review_runs_created'] == probe['material_reads'] == 0

    history_before = research_history()
    protected = [ROOT / '.roll-data/reconstructed19-v1/roll.sqlite3']
    protected += [ROOT / '.roll-data/implementation-evidence' / name / 'actual-current-copy/roll.sqlite3' for name in ('21', '23')]
    protected += [ROOT / '.scratch/roll-p0/evidence/23/actual-review.py', SCOPE / 'actual-review-corrected.py']
    protected += list((ROOT / '.roll-data/implementation-evidence/23/provider-approval').rglob('*'))
    protected = [path for path in protected if path.is_file()]
    protected_before = {str(path): {'bytes': path.stat().st_size, 'sha256': file_sha(path)} for path in protected}
    OUT.mkdir(parents=True, exist_ok=False)
    save(OUT / 'authorized-preflight.json', {'status': 'PASS', 'backend': 'CODEX', 'model': 'gpt-6.1-sol',
        'material_id': receipt['material_id'], 'material_fingerprint': FINGERPRINT, 'manifest_sha256': MANIFEST_SHA,
        'seven_body_files': 7, 'inventory_content_bytes': 179889, 'prior_review_runs': 1, 'retry_of': PREDECESSOR,
        'prior_root_cause': 'UNKNOWN', 'continuation_authorization': 'Explicit root continuation after healthy account-only probe; completes original approved model review',
        'permitted_provider': 'OpenAI Codex runtime endpoint selected by existing SDK',
        'deepseek_authorized': False, 'automatic_retry': False})
    print('PREFLIGHT_PASS: exact approved7 bodies/source/manifest; CODEX-only; sole pre-bootstrap FAILED predecessor verified', flush=True)
    os.environ['ROLL_ENV'] = 'test'
    os.environ['ROLL_ENV_FILE'] = str(ROOT / '.env')
    os.environ['ROLL_CODEX_MODEL'] = 'gpt-6.1-sol'
    os.environ['ROLL_CODEX_AUTH_FILE'] = str(auth_path)  # Previously human-authorized13 path; host pipeline alone reads its contents.
    for key in ('ROLL_TEST_CRASH_POINT', 'ROLL_TEST_BOOTSTRAP_FAULT', 'ROLL_TECHNICAL_REVIEW_TIMEOUT_SECONDS'):
        os.environ.pop(key, None)
    from roll.config import load_runtime_environment
    load_runtime_environment()  # Existing explicitly approved host credential pipeline; never print/read secrets ourselves.
    os.environ['DEEPSEEK_API_KEY'] = ''
    os.environ['ROLL_DEEPSEEK_API_KEY_FILE'] = ''
    assert os.environ.get('ROLL_CODEX_AUTH_FILE'), 'Existing approved CODEX credential path not configured'
    from fastapi.testclient import TestClient
    import httpx
    from roll.app import create_app
    from roll.agents.review_runtime import command
    market_network_attempts = []
    def deny_market(request):
        market_network_attempts.append(str(request.url).split('?')[0])
        raise RuntimeError('Review has no market acquisition authorization')
    run = None
    with TestClient(create_app(PROFILE, market_transport=httpx.MockTransport(deny_market))) as client:
        def get(path):
            response = client.get(path); response.raise_for_status(); return response.json()
        def post(path, body):
            response = client.post(path, json=body); response.raise_for_status(); return response.json()
        material = get('/api/research/review-materials/' + receipt['material_id'])
        assert material['material_fingerprint'] == FINGERPRINT and material['basis_id'] == receipt['validation_id']
        expected_inventory = {item['material_id']: item['material_sha256'] for item in body_files}
        assert {item['material_id']: item['sha256'] for item in material['inventory']} == expected_inventory
        codex_command = next(item for item in manifest['files'] if item.get('backend') == 'CODEX')
        assert json.loads(Path(codex_command['path']).read_text()) == command({'model': 'gpt-6.1-sol'}, material)
        assert get('/api/research/review-materials/' + material['material_id'] + '/reviews') == [prior_before]
        original_validation = get('/api/research/validations/' + receipt['validation_id'])
        protocol_id = original_validation['protocol_id']
        assert original_validation['validation_verdict'] == 'FAIL' and original_validation['gates']['G7']['status'] == 'INCONCLUSIVE'
        def boundary():
            return {key: get(path) for key, path in {
                'account': '/api/account', 'protocol': '/api/research/protocols/' + protocol_id,
                'old_protocol': '/api/research/protocols/' + receipt['old_protocol_id'],
                'attempts': '/api/research/protocols/' + protocol_id + '/attempt-manifest',
                'audit': '/api/research/protocols/' + protocol_id + '/audit',
                'old_audit': '/api/research/protocols/' + receipt['old_protocol_id'] + '/audit',
                'model': '/api/research/models/' + receipt['reused_model_run_id'],
                'freeze': '/api/research/complete-freezes/' + receipt['new_freeze_id'],
            }.items()}
        before = boundary()
        settings = get('/api/agents/settings')
        if settings['backend'] != 'CODEX':
            post('/api/agents/settings', {'expected_version': settings['version'], 'backend': 'CODEX'})
        assert get('/api/agents/settings')['backend'] == 'CODEX'
        started = post('/api/research/review-materials/' + material['material_id'] + '/reviews',
            {'expected_material_fingerprint': FINGERPRINT, 'retry_of': PREDECESSOR})
        assert started['backend'] == 'CODEX' and started['model'] == 'gpt-6.1-sol' and started['retry_of'] == PREDECESSOR
        assert started['evidence_kind'] == 'REAL_CODEX_TECHNICAL_REVIEW'
        save(OUT / 'started-run.json', started)
        print(json.dumps({'phase': 'ONE_AUTHORIZED_CODEX_CONTINUATION_STARTED', 'run_id': started['run_id'], 'material_fingerprint': FINGERPRINT}), flush=True)
        deadline = time.monotonic() + 140
        while time.monotonic() < deadline:
            run = get('/api/research/technical-reviews/' + started['run_id'])
            if run['status'] != 'RUNNING':
                break
            time.sleep(.25)
        else:
            post('/api/research/technical-reviews/' + started['run_id'] + '/cancel', {})
            raise RuntimeError('Review host exceeded bounded terminal margin; attempt retained, never retry automatically')
        save(OUT / 'actual-codex.json', run)
        delivery = get('/api/research/review-materials/' + material['material_id'] + '/delivery')
        exported = post('/api/research/review-materials/' + material['material_id'] + '/export', {})
        assert before == boundary() and original_validation == get('/api/research/validations/' + receipt['validation_id'])
        runs = get('/api/research/review-materials/' + material['material_id'] + '/reviews')
        assert len(runs) == 2 and all(r['backend'] == 'CODEX' for r in runs) and review_count() == 2
        assert get('/api/research/technical-reviews/' + PREDECESSOR) == prior_before
        assert file_sha(prior_path) == 'c602ed3478bd0b9feea23167d2250f45ef30dfe693fc1bbcfafa77a0418e27cf'
        assert delivery['preliminary'] and delivery['capability_status'] == 'NOT_GRANTED'
        assert not market_network_attempts
        save(OUT / 'actual-results.json', {'run': run, 'delivery': delivery, 'export': exported,
            'same_frozen_approved_material': True, 'account_attempts_model_freeze_forward_sealed_unchanged': True,
            'historical_validation_unchanged': True, 'deepseek_calls': 0, 'automatic_retries': 0})
        print(json.dumps({'phase': 'CODEX_TERMINAL', 'run_id': run['run_id'], 'status': run['status'],
            'resolved_model': run['resolved_model'], 'error_code': run.get('error', {}).get('code'),
            'review_status': delivery['review_status'], 'delivery_status': delivery['delivery_status']}), flush=True)
    history_after = research_history()
    assert history_before == history_after, 'Review altered research rows or attempt budget'
    assert protected_before == {str(path): {'bytes': path.stat().st_size, 'sha256': file_sha(path)} for path in protected}
    assert file_sha(APPROVAL / 'provider-material-manifest.json') == MANIFEST_SHA
    public_fields = ['run_id', 'material_id', 'material_fingerprint', 'backend', 'model', 'resolved_model', 'model_provider',
        'status', 'retry_of', 'started_at', 'finished_at', 'evidence_kind', 'sdk_runtime_version', 'config_fingerprint',
        'effective_config_fingerprint', 'runtime_executable_sha256', 'bridge', 'runtime_thread_id', 'runtime_turn_id',
        'runtime_completion', 'limits', 'tools', 'gaps', 'review_record', 'review_record_archive', 'call_usage',
        'token_usage', 'acquisition_usage', 'elapsed_seconds', 'process']
    safe_run = {key: run[key] for key in public_fields if key in run}
    if run.get('error'):
        safe_run['error'] = {key: run['error'][key] for key in ('code', 'type') if key in run['error']}
    result = {'status': 'PASS_REAL_CODEX_REVIEW' if run['status'] == 'COMPLETE' else 'RECORDED_NONCOMPLETE_REAL_CODEX_ATTEMPT',
        'backend_scope': 'CODEX_ONLY_USER_APPROVED', 'run': safe_run, 'delivery': delivery, 'local_export': exported,
        'same_frozen_approved_material': True, 'approved_manifest_sha256': MANIFEST_SHA,
        'actual_review_run_count': 2, 'authorized_continuation_count': 1, 'retry_of': PREDECESSOR,
        'initial_prebootstrap_failure_preserved': True, 'initial_failure_root_cause': 'UNKNOWN', 'deepseek_calls': 0, 'automatic_retry_count': 0,
        'account_model_freeze_attempts_budget_audits_forward_unchanged': True, 'all_research_tables_unchanged': True,
        'protected_files_before_after_unchanged': protected_before, 'sealed_read': False, 'real_forward_started': False,
        'market_network_calls': 0, 'capability_status': 'NOT_GRANTED', 'historical_diagnostic_verdict': 'FAIL',
        'G7': 'INCONCLUSIVE', 'provider_body_context_limit': 'Old freeze UUID/fingerprint and original model UUID omitted by existing projection; exact linkage remains in local archive'}
    if run['status'] == 'COMPLETE':
        assert run['review_record']['review_status'] == 'COMPLETE' and run['review_record']['reproduction_verified']
        assert run['resolved_model'] == 'gpt-6.1-sol' and run['model_provider'] == 'openai'
        assert len([tool for tool in run['tools'] if tool['status'] == 'VERIFIED_READ']) == 7
        assert len([tool for tool in run['tools'] if tool['status'] == 'VERIFIED_REPRODUCTION']) == 1
    save(SCOPE / 'actual-codex-continuation-results.json', result)
    print(json.dumps({'phase': 'FINAL_INVARIANCE_PASS', 'status': result['status'], 'run_id': run['run_id'],
        'deepseek_calls': 0, 'research_protected_state_unchanged': True}), flush=True)


if __name__ == '__main__':
    main()
