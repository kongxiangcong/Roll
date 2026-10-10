"""Verify final code/metadata and preserved engineering bytes, not real samples."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    final = json.loads((HERE / 'actual-preflight-final.json').read_text(encoding='utf-8'))
    before = json.loads((HERE / 'actual-family-before.json').read_text(encoding='utf-8'))
    family = final['families'][0]
    assert family['repeated_preflight_equal'] and family['manifest_unchanged']
    assert family['attempts'] == before['families'][0]['attempts']
    assert family['fits_used'] == 2 and family['fits_remaining'] == 3
    assert family['calibration_used'] == 0 and family['calibration_remaining'] == 1
    assert family['preflight']['source']['evidence_kind'] == 'REAL_ACQUISITION'
    assert not family['preflight']['ready_to_fit']
    allowed = {'/api/research/protocols/' + family['queried_protocol_id'],
               '/api/research/protocols/' + family['queried_protocol_id'] + '/attempt-manifest',
               '/api/research/datasets/' + family['preflight']['dataset_id']}
    # The capture also checks the other known predecessor receipt before deduplicating its family.
    allowed.update('/api/research/protocols/' + pid + '/attempt-manifest'
                   for pid in family['family_protocol_ids'])
    assert all(r['path'] in allowed and r['status'] == 200 for r in final['requests'])
    assert final['source_calls'] == final['fits'] == 0
    assert not final['labels_read_or_computed'] and not final['sealed_read']
    module = ROOT / 'backend/src/roll/research/training_preflight.py'
    assert sha(module.read_text(encoding='utf-8').replace('\r\n', '\n').encode()) == final['local_function_sha256']
    expected = {
        'backend/src/roll/research/models.py': 'a4672de83a34bebc2013604266fd721ab2c3bf87acc0fbbd1bc9e13d9287fa49',
        'backend/src/roll/research/registry.py': '112616135ac1efc1c0ebbc674114a7a31cf5f68c96938cf5f86318c583166bcf',
        'backend/src/roll/research/execution.py': '45f09eb8585f65a00b9860f526778d743a2dd6afbe3c140dc88e97e03d718e4a',
    }
    for path, value in expected.items():
        assert sha((ROOT / path).read_bytes()) == value, path
    implementation = json.loads((ROOT / '.scratch/roll-p0/evidence/19-completion-2026-10-09/training-preflight-implementation-verification.json').read_text(encoding='utf-8'))
    for row in implementation['tracked_stdout']:
        raw = (ROOT / row['path']).read_bytes()
        assert len(raw) == row['bytes'] and sha(raw) == row['sha256'], row['path']
    merge = json.loads((HERE / 'merge-test-receipt.json').read_text(encoding='utf-8'))
    assert merge['exit_code'] == 0 and merge['watched_bytes_unchanged']
    assert sha((HERE / 'merge-backend.txt').read_bytes()) == merge['stdout_sha256']
    for path, value in merge['after'].items():
        assert sha((ROOT / path).read_bytes()) == value, path
    preservation = json.loads((HERE / 'worktree-preservation.json').read_text(encoding='utf-8'))
    target_root = (ROOT / 'backend/.roll-data/t19-preflight-preserved').resolve()
    assert Path(preservation['destination']).resolve() == target_root
    assert len(preservation['files']) == 1228
    for row in preservation['files']:
        target = Path(row['preserved']).resolve()
        target.relative_to(target_root)
        raw = target.read_bytes()
        assert len(raw) == row['bytes'] and sha(raw) == row['sha256'], row['path']
    cleanup = json.loads((HERE / 'worktree-cleanup.json').read_text(encoding='utf-8'))
    assert cleanup['confirmed_artifact']['attachmentType'] == 'archived_worktree'
    assert not Path(preservation['source']).exists()
    for script in ['capture-family-budget.py', 'preserve-worktree.py', 'verify-final-evidence.py']:
        ast.parse((HERE / script).read_text(encoding='utf-8'))
    result = {'verified_at': datetime.now(timezone.utc).isoformat(),
              'implementation_regression_passed': 21, 'merged_critical_passed': 5,
              'counts_are_separate_runs_not_summed': True, 'full_backend_rerun': False,
              'original_algorithm_files_unchanged': expected,
              'actual_registered_family_attempts_unchanged': True,
              'actual_source_calls': 0, 'actual_fits': 0, 'actual_labels_or_sealed_read': False,
              'preserved_fixture_files': len(preservation['files']),
              'preserved_fixture_bytes': sum(r['bytes'] for r in preservation['files']),
              'destination_only_post_archive_hash_length_mismatches': 0,
              'managed_worktree_archive_confirmed': True, 'ticket19_complete': False,
              'scope': 'Code/metadata/engineering byte evidence; no real model or calibration qualification'}
    (HERE / 'final-verification.json').write_bytes((json.dumps(result, ensure_ascii=False, indent=2)+'\n').encode())
    print(json.dumps({'verified': True, 'preserved_files': 1228, 'mismatches': 0,
                      'worktree_archived': True, 'ticket19_complete': False}))


if __name__ == '__main__':
    main()
