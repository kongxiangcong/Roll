"""Explicitly gated local successor preparation; never start a provider review."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess

ROOT = Path(__file__).resolve().parents[5]
SCOPE = Path(__file__).resolve().parent
PROFILE = ROOT / '.roll-data/implementation-evidence/continuation-review-fixes/actual-corrected-copy'
OUT = ROOT / '.roll-data/implementation-evidence/continuation-review-fixes/actual-corrected-results'
APPROVAL = ROOT / '.roll-data/implementation-evidence/continuation-review-fixes/provider-approval-current'
RECEIPT = SCOPE / 'actual-corrected-successor-results.json'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def file_sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def db_history():
    tables = {'research_protocols': 'id', 'research_attempts': 'id', 'research_models': 'id',
        'research_forecasts': 'id', 'research_complete_freezes': 'id', 'research_validations': 'id',
        'research_validation_attempts': 'id', 'research_review_materials': 'id',
        'research_shadow_runs': "freeze_id || ':' || revision"}
    with sqlite3.connect((PROFILE / 'roll.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
        return {table: {row[0]: sha(row[1].encode()) for row in db.execute('SELECT ' + key + ',value FROM ' + table)} for table, key in tables.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-local', action='store_true')
    parser.add_argument('--expected-source-commit', required=True)
    parser.add_argument('--expected-shadow-source-sha256', required=True)
    args = parser.parse_args()
    if not args.execute_local:
        parser.error('Preparation only until explicit local execution authorization; no app started')
    assert PROFILE == ROOT / '.roll-data/implementation-evidence/continuation-review-fixes/actual-corrected-copy'
    assert PROFILE.is_dir() and not any(p.exists() for p in (OUT, APPROVAL, RECEIPT)), 'Preserve prior attempts; do not rerun or overwrite'
    metadata = json.loads((SCOPE / 'successor-preparation-metadata.json').read_text(encoding='utf-8'))
    copied = json.loads((SCOPE / 'actual-corrected-copy-manifest.json').read_text(encoding='utf-8'))
    assert file_sha(PROFILE / 'roll.sqlite3') == metadata['source_db_sha256_after'], 'Prepared copy already changed'
    old_pid, old_freeze, model_id = metadata['old_protocol_id'], metadata['old_freeze_id'], metadata['reused_model']['model_run_id']
    forecast_ids = metadata['old_shadow_forecast_ids']
    source_paths = ['backend/src/roll/research/' + name + '.py' for name in ('models', 'execution', 'shadow', 'statistics', 'validation', 'forward')]
    subprocess.run(['git', 'merge-base', '--is-ancestor', args.expected_source_commit, 'HEAD'], cwd=ROOT, check=True)
    sources = {}
    for path in source_paths:
        raw = (ROOT / path).read_bytes().replace(b'\r\n', b'\n')
        saved = subprocess.run(['git', 'show', args.expected_source_commit + ':' + path], cwd=ROOT, capture_output=True, check=True).stdout.replace(b'\r\n', b'\n')
        assert raw == saved, 'Current product source differs from approved stable commit'
        sources[path] = sha(raw)
    assert sources['backend/src/roll/research/shadow.py'] == args.expected_shadow_source_sha256
    protected_paths = [ROOT / '.roll-data' / name / 'roll.sqlite3' for name in ('reconstructed19-v1',)]
    protected_paths += [ROOT / '.roll-data/implementation-evidence' / name / 'actual-current-copy/roll.sqlite3' for name in ('21', '23')]
    protected_before = {str(p): file_sha(p) for p in protected_paths}
    def verify_old_archives():
        for entry in copied['archives']:
            path = (PROFILE / entry['path']).resolve()
            assert path.is_relative_to(PROFILE)
            assert path.stat().st_size == entry['bytes'] and file_sha(path) == entry['sha256']
    verify_old_archives()
    history_before = db_history()
    os.environ['ROLL_ENV'] = 'test'  # Prevent implicit checkout .env load; actual records keep their original evidence kind.
    for key in ('ROLL_ENV_FILE', 'DEEPSEEK_API_KEY', 'ROLL_DEEPSEEK_API_KEY_FILE', 'ROLL_TEST_CRASH_POINT'):
        os.environ.pop(key, None)
    os.environ['ROLL_CODEX_AUTH_FILE'] = str(OUT / 'no-provider-auth.json')
    from fastapi.testclient import TestClient
    import httpx
    from roll.app import create_app
    from roll.accounts.ledger import encode
    from roll.research.shadow import shadow_code
    from roll.agents.review_runtime import command
    from roll.agents.codex_evidence import MODEL as CODEX_MODEL
    from roll.agents.deepseek_evidence import MODEL as DEEPSEEK_MODEL
    assert shadow_code() != metadata['old_shadow_code_fingerprint'], 'Corrected freeze must bind corrected source'
    network_attempts = []
    def deny_market(request):
        network_attempts.append(str(request.url).split('?')[0])
        raise RuntimeError('Pure local successor preparation forbids market network')
    OUT.mkdir(parents=True, exist_ok=False)
    APPROVAL.mkdir(parents=True, exist_ok=False)
    packet = APPROVAL / 'provider-materials'
    packet.mkdir()
    def get(client, path):
        response = client.get(path); response.raise_for_status(); return response.json()
    def post(client, path, body):
        response = client.post(path, json=body); response.raise_for_status(); return response.json()
    with TestClient(create_app(PROFILE, market_transport=httpx.MockTransport(deny_market))) as client:
        account_before = get(client, '/api/account')
        original_protocol = get(client, '/api/research/protocols/' + old_pid)
        original_attempts = get(client, '/api/research/protocols/' + old_pid + '/attempt-manifest')
        original_audit = get(client, '/api/research/protocols/' + old_pid + '/audit')
        def budget_snapshot(manifest, audit):
            attempts = manifest['attempts']
            fits = sum(a['category'] in {'PRIMARY_FIT', 'G5_NEIGHBOR'} for a in attempts)
            calibration = sum(a['category'] == 'CALIBRATION' for a in attempts)
            return {'all_attempt_ids': manifest['attempt_ids'], 'all_attempt_count': len(attempts),
                'primary_and_neighbor_fit_count': fits, 'fit_limit': 5, 'remaining_fit_slots': max(0, 5 - fits),
                'calibration_attempt_count': calibration, 'calibration_limit': 1, 'remaining_calibration_slots': max(0, 1 - calibration),
                'confirmatory_pass_look_count': sum(bool(e.get('confirmatory_pass_look')) for e in audit)}
        budget_before = budget_snapshot(original_attempts, original_audit)
        model = get(client, '/api/research/models/' + model_id)
        frozen_old = get(client, '/api/research/complete-freezes/' + old_freeze)
        old_shadow = get(client, '/api/research/shadow/' + old_freeze)
        forecasts = [get(client, '/api/research/forecasts/' + identifier) for identifier in forecast_ids]
        assert all(f['model_run_id'] == model_id and f['scope']['namespace'] == 'HISTORICAL' for f in forecasts)
        successor = post(client, '/api/research/protocols', {'dataset_id': metadata['dataset_id'], 'predecessor_id': old_pid,
            'basis': f'Corrected shadow successor of protocol {old_pid}, complete freeze {old_freeze} ({metadata["old_complete_protocol_fingerprint"]}), original model {model_id}; inherited attempts/budgets, no new fit/SEALED/forward'})
        assert successor['design'] == original_protocol['design'] and successor['scope'] == original_protocol['scope']
        successor_id = successor['protocol_id']
        attempt_manifest = get(client, '/api/research/protocols/' + successor_id + '/attempt-manifest')
        assert old_pid in attempt_manifest['lineage'] and set(attempt_manifest['attempt_ids']) == set(original_attempts['attempt_ids'])
        frozen = post(client, '/api/research/protocols/' + successor_id + '/complete-freezes', {
            'model_run_id': model_id, 'attempt_ids': attempt_manifest['attempt_ids'], 'artifact_fingerprints': model['artifact_fingerprints'],
            'baseline': frozen_old['baseline'], 'basis': f'Corrected successor freeze; prior protocol {old_pid}; old freeze {old_freeze} fingerprint {metadata["old_complete_protocol_fingerprint"]}; same model {model_id} and all inherited attempts; historical CAL only'})
        assert frozen['freeze_id'] != old_freeze and frozen['fingerprints']['shadow_code'] == shadow_code()
        current = post(client, '/api/research/shadow/' + frozen['freeze_id'] + '/advance', {
            'through_date': old_shadow['through_date'], 'forecast_ids': forecast_ids, 'expected_revision': 0})
        shadow_replay = post(client, '/api/research/shadow/' + frozen['freeze_id'] + '/replay', {})
        assert shadow_replay['matches_original'] and shadow_replay['network_calls'] == 0
        validation = post(client, '/api/research/complete-freezes/' + frozen['freeze_id'] + '/validations', {
            'purpose': 'DIAGNOSTIC', 'expected_complete_protocol_fingerprint': frozen['complete_protocol_fingerprint'],
            'basis': 'Corrected historical CAL diagnostic; no new fit/forecast/SEALED/confirmation/forward'})
        assert validation['validation_verdict'] != 'PASS' and validation['gates']['G7']['status'] == 'INCONCLUSIVE'
        assert validation['capability_status'] == 'NOT_GRANTED' and validation['sealed_read'] is False
        replay = post(client, '/api/research/validations/' + validation['validation_id'] + '/replay', {})
        assert replay['matches_original'] and replay['network_calls'] == 0
        material = post(client, '/api/research/validations/' + validation['validation_id'] + '/review-materials', {})
        assert get(client, '/api/research/review-materials/' + material['material_id'] + '/reviews') == []
        files = []; provider_body_text = []
        for item in material['inventory']:
            raw = client.get('/api/data/archives/' + item['sha256']); raw.raise_for_status()
            assert sha(raw.content) == item['sha256'] and len(raw.content) == item['bytes']
            provider_body_text.append(raw.content.decode())
            content = encode({'material_id': item['material_id'], 'sha256': item['sha256'], 'content': raw.content.decode()}).encode()
            path = packet / (item['material_id'] + '.json'); path.write_bytes(content)
            files.append({'material_id': item['material_id'], 'material_sha256': item['sha256'], 'content_bytes': item['bytes'],
                'tool_response_bytes': len(content), 'tool_response_sha256': sha(content), 'path': str(path)})
        for backend, selected in (('CODEX', CODEX_MODEL), ('DEEPSEEK', DEEPSEEK_MODEL)):
            content = encode(command({'model': selected}, material)).encode()
            path = packet / (backend.lower() + '-command.json'); path.write_bytes(content)
            files.append({'backend': backend, 'kind': 'INITIAL_COMMAND_WITH_PROMPT_AND_TOOL_SCHEMAS', 'bytes': len(content), 'sha256': sha(content), 'path': str(path)})
        reproduction = encode({'check_id': 'validation-reproduction', 'result_sha256': replay['result_fingerprint'], 'matches_original': True, 'network_calls': 0}).encode()
        (packet / 'reproduction.json').write_bytes(reproduction)
        preview = {'material_id': material['material_id'], 'material_fingerprint': material['material_fingerprint'],
            'validation_id': validation['validation_id'], 'source_commit': args.expected_source_commit,
            'inventory_content_bytes': sum(i['bytes'] for i in material['inventory']),
            'maximum_tool_payload_bytes': sum(f.get('tool_response_bytes', 0) for f in files) + len(reproduction),
            'reproduction_file': {'path': str(packet / 'reproduction.json'), 'bytes': len(reproduction), 'sha256': sha(reproduction)},
            'files': files, 'source_files': source_paths[:5], 'source_sha256': sources,
            'lineage_binding': {'parent_protocol_id': old_pid, 'old_freeze_id': old_freeze,
                'old_complete_protocol_fingerprint': metadata['old_complete_protocol_fingerprint'], 'new_complete_protocol_fingerprint': frozen['complete_protocol_fingerprint'],
                'original_model_run_id': model_id, 'inherited_attempt_ids': original_attempts['attempt_ids'],
                'native_predecessor_freeze_field': False, 'old_freeze_linkage': 'Explicit basis text hashed into complete-freeze archive; local material references archive'},
            'provider_body_context_presence': {key: value in '\n'.join(provider_body_text) for key, value in {
                'parent_protocol_id': old_pid, 'old_freeze_id': old_freeze, 'old_complete_protocol_fingerprint': metadata['old_complete_protocol_fingerprint'],
                'original_model_run_id': model_id, **{'attempt_' + str(index): identifier for index, identifier in enumerate(original_attempts['attempt_ids'])}}.items()},
            'destinations': [{'backend': 'CODEX', 'model': CODEX_MODEL, 'service': 'OpenAI Codex runtime; endpoint selected by SDK'},
                {'backend': 'DEEPSEEK', 'model': DEEPSEEK_MODEL, 'endpoint': 'https://api.deepseek.com/responses'}],
            'external_transmissions': 0, 'approval_status': 'NOT_APPROVED_NEW_PACKAGE', 'actual_review_runs': 0,
            'scope': ['Protocol and all attempt metadata', 'Gates, reasons, incompleteness and G5 summaries', 'Five current model/validation source files', 'Deterministic host reproduction fingerprint'],
            'excluded': ['Personal account amounts/holdings/identity and funding', 'Full input/raw archives and SEALED', 'Credentials/configuration', 'Database and unrelated evidence']}
        save(APPROVAL / 'provider-material-manifest.json', preview)
        save(OUT / 'local-results.json', {'successor': successor, 'full_freeze': frozen, 'shadow': current, 'validation': validation,
            'shadow_replay': shadow_replay, 'validation_replay': replay, 'material': material})
        assert get(client, '/api/account') == account_before
        assert get(client, '/api/research/protocols/' + old_pid) == original_protocol
        attempts_after = get(client, '/api/research/protocols/' + old_pid + '/attempt-manifest')
        assert attempts_after['attempts'] == original_attempts['attempts'] and attempts_after['attempt_ids'] == original_attempts['attempt_ids']
        assert get(client, '/api/research/models/' + model_id) == model
        assert get(client, '/api/research/complete-freezes/' + old_freeze) == frozen_old
        assert get(client, '/api/research/protocols/' + successor_id)['forward_started_at'] is None
        assert get(client, '/api/research/protocols/' + old_pid + '/audit') == original_audit
        budget_after = budget_snapshot(attempts_after, original_audit)
        assert budget_before == budget_after
        successor_attempts = get(client, '/api/research/protocols/' + successor_id + '/attempt-manifest')
        assert set(successor_attempts['attempt_ids']) == set(original_attempts['attempt_ids'])
        assert set(material['basis_manifest']['attempt_manifest']['attempt_ids']) == set(original_attempts['attempt_ids'])
        assert not network_attempts
    verify_old_archives()
    history_after = db_history()
    assert all(history_after[table].get(identifier) == value for table, records in history_before.items() for identifier, value in records.items())
    assert history_after['research_attempts'] == history_before['research_attempts']
    assert history_after['research_models'] == history_before['research_models'] and history_after['research_forecasts'] == history_before['research_forecasts']
    assert {str(p): file_sha(p) for p in protected_paths} == protected_before
    receipt = {'status': 'PASS', 'source_commit': args.expected_source_commit, 'shadow_source_sha256': args.expected_shadow_source_sha256,
        'new_shadow_code_fingerprint': frozen['fingerprints']['shadow_code'], 'profile': str(PROFILE),
        'old_protocol_id': old_pid, 'old_freeze_id': old_freeze, 'successor_protocol_id': successor_id, 'new_freeze_id': frozen['freeze_id'],
        'reused_model_run_id': model_id, 'reused_historical_forecast_ids': forecast_ids,
        'validation_id': validation['validation_id'], 'diagnostic_verdict': validation['validation_verdict'],
        'gate_statuses': {k: v['status'] for k, v in validation['gates'].items()},
        'material_id': material['material_id'], 'material_fingerprint': material['material_fingerprint'],
        'approval_manifest': str(APPROVAL / 'provider-material-manifest.json'), 'approval_manifest_sha256': file_sha(APPROVAL / 'provider-material-manifest.json'),
        'inventory_content_bytes': preview['inventory_content_bytes'], 'maximum_tool_payload_bytes': preview['maximum_tool_payload_bytes'],
        'original_family_budget_before': budget_before, 'original_family_budget_after': budget_after,
        'successor_inherited_lineage': successor_attempts['lineage'], 'successor_inherited_attempt_ids': successor_attempts['attempt_ids'],
        'new_diagnostic_attempts': len(history_after['research_validation_attempts']) - len(history_before['research_validation_attempts']),
        'provider_body_context_presence': preview['provider_body_context_presence'],
        'native_predecessor_freeze_field': False,
        'old_records_and_3841_archives_unchanged': True, 'fit_attempts_models_forecasts_unchanged': True,
        'account_unchanged': True, 'original19_and_21_23_source_db_hashes_unchanged': protected_before,
        'shadow_and_validation_replay_matches': True, 'network_calls': 0, 'sealed_read': False,
        'forward_started': False, 'actual_review_runs': 0, 'external_transmissions': 0, 'capability': 'NOT_GRANTED'}
    save(RECEIPT, receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
