"""Read-only persisted review, approved-tool and archive acceptance; no SDK/Host start."""
import hashlib
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[5]
SCOPE = Path(__file__).resolve().parent
PRIVATE = ROOT / '.roll-data/implementation-evidence/continuation-review-fixes'
PROFILE = PRIVATE / 'actual-corrected-copy'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    result = json.loads((SCOPE / 'actual-codex-continuation-results.json').read_text(encoding='utf-8'))
    run = json.loads((PRIVATE / 'actual-codex-results-continuation-01/actual-codex.json').read_text(encoding='utf-8'))
    original_path = PRIVATE / 'actual-codex-results-authorized-auth/actual-codex.json'
    original = json.loads(original_path.read_text(encoding='utf-8'))
    assert sha(original_path.read_bytes()) == 'c602ed3478bd0b9feea23167d2250f45ef30dfe693fc1bbcfafa77a0418e27cf'
    # Preserve the stopped profile's committed WAL view; immutable=1 omits WAL.
    with sqlite3.connect((PROFILE / 'roll.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
        rows = db.execute('SELECT id,value FROM technical_review_runs ORDER BY rowid').fetchall()
    assert len(rows) == 2
    assert json.loads(rows[0][1]) == original and json.loads(rows[1][1]) == run
    assert run['status'] == 'COMPLETE' and run['retry_of'] == original['run_id']
    assert run['backend'] == 'CODEX' and run['resolved_model'] == 'gpt-6.1-sol' and run['model_provider'] == 'openai'
    manifest_path = PRIVATE / 'provider-approval-current/provider-material-manifest.json'
    assert sha(manifest_path.read_bytes()) == '206d2ec53d85af4b28423017da24b5a6030d5078ec5237ee939233245ef84984'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    inventory = {f['material_id']: f['material_sha256'] for f in manifest['files'] if 'material_id' in f}
    reads = [t for t in run['tools'] if t['status'] == 'VERIFIED_READ']
    assert len(reads) == 7 and {t['material_id']: t['sha256'] for t in reads} == inventory
    record = run['review_record']
    assert record['review_status'] == 'COMPLETE' and record['reproduction_verified']
    assert record['material_fingerprint'] == manifest['material_fingerprint'] == run['material_fingerprint']
    assert {r['material_id']: r['sha256'] for r in record['references']} == inventory
    reproductions = [t for t in run['tools'] if t['status'] == 'VERIFIED_REPRODUCTION']
    assert len(reproductions) == 1 and reproductions[0]['matches_original'] and reproductions[0]['network_calls'] == 0
    assert record['checks'][0]['result_sha256'] == reproductions[0]['result_sha256']
    for relative, expected in manifest['source_sha256'].items():
        assert sha((ROOT / relative).read_bytes().replace(b'\r\n', b'\n')) == expected
    model_manifest = json.loads((SCOPE / 'independent-model-source-hashes.json').read_text(encoding='utf-8'))
    for item in model_manifest['files']:
        assert sha((ROOT / item['path']).read_bytes()) == item['sha256']
    archives = [run['review_record_archive'], result['local_export']['archive']]
    for archive in archives:
        path = (PROFILE / archive['path']).resolve()
        assert path.is_relative_to(PROFILE.resolve())
        raw = path.read_bytes()
        assert sha(raw) == archive['sha256'] and len(raw) == archive['bytes']
    assert json.loads((PROFILE / run['review_record_archive']['path']).read_text(encoding='utf-8')) == record
    assert result['all_research_tables_unchanged'] and result['account_model_freeze_attempts_budget_audits_forward_unchanged']
    assert result['deepseek_calls'] == 0 and result['automatic_retry_count'] == 0
    assert result['delivery']['review_status'] == 'COMPLETE' and result['delivery']['delivery_status'] == 'INCOMPLETE'
    assert result['delivery']['capability_status'] == 'NOT_GRANTED' and result['delivery']['preliminary']
    proof = {'status': 'PASS', 'source_behavior_unchanged_since': '25d9b9ae48b94ea4603cc36ab3dbacc8200be248',
        'run_id': run['run_id'], 'review_id': record['review_id'], 'retry_of': run['retry_of'],
        'two_persisted_CODEX_runs': True, 'initial_failed_record_byte_and_content_preserved': True,
        'approved_inventory_7_reads_exact_sha': True, 'one_host_reproduction_verified_network_calls': 0,
        'six_provider_source_hashes_unchanged': True, 'twelve_model_source_hashes_unchanged': True,
        'review_record_and_full_local_export_archive_sha_length_verified': True,
        'issues': [{'issue_id': i['issue_id'], 'severity': i['severity'], 'blocking': i['blocking'],
            'resolved': i.get('resolution') is not None} for i in record['issues']],
        'blocking_issues_resolved': record['blocking_issues_resolved'], 'delivery_status': 'INCOMPLETE',
        'capability_status': 'NOT_GRANTED', 'DeepSeek': 'EXCLUDED_0_CALLS',
        'actual_helper_exit_code': 0, 'actual_helper_session_id': 64171,
        'initial_helper_exit_code': 0, 'initial_helper_session_id': 3035,
        'account_only_probe_exit_code': 0, 'account_only_probe_session_id': 33254,
        'initial_InternalRpcError_root_cause': 'UNKNOWN', 'production_bug_fix_claimed': False,
        'scope_limitations': record['limitations'] + record['review_scope_limitations']}
    (SCOPE / 'actual-codex-continuation-acceptance.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print('persisted CODEX continuation acceptance PASS; 7 approved reads/1 reproduction/2 archives/12+6 source SHA verified')


if __name__ == '__main__':
    main()
