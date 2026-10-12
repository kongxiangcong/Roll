import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--release', required=True)
p.add_argument('--executor', required=True)
args = p.parse_args()
v = Path(__file__).parent
root = Path('D:/dsh-proj/Roll')
def read(name):
    return json.loads((v / name).read_text(encoding='utf-8-sig'))
before = read('roll-cleanup-batch-v6-preflight.json')
post = read('roll-cleanup-batch-v6-post.json')
native = read('roll-cleanup-batch-v6-native-result.json')
release = read(args.release)
assert before['status'] == 'PREFLIGHT_PASS' and post['status'] == 'PASS'
assert before['release_id'] == post['release_id'] == native['release_id'] == release['coordinator_release_id']
assert len(native['removed']) == len(before['trees']) == 10
assert post['branches_retained'] and post['all_preserved_targets_unchanged']
assert post['root_dependency_file_set_bytes_unchanged'] and post['root_protected15_allowed3_original19_unchanged']
git = 'C:/Program Files/Git/cmd/git.exe'
def g(*argv):
    return subprocess.check_output([git, '--no-optional-locks', '-c', 'core.longpaths=true', '-C', str(root), *argv], text=True, encoding='utf-8').splitlines()
assert g('rev-parse', 'HEAD')[0] == release['root_head']
for tree in before['trees']:
    assert g('rev-parse', 'refs/heads/'+tree['branch'])[0] == tree['oid']
assert not g('diff', '--cached', '--name-only') and not g('diff', '--name-only')
prior = read('roll-root-untracked-before-final-docs.json')['untracked_entries']
current = g('status', '--porcelain=v1', '--untracked-files=normal')
assert sorted(current) == sorted(prior), (len(current), len(prior))
evidence = root / '.scratch/roll-p0/evidence/continuation-2026-10-11/final-cleanup'
saved = root / '.roll-data/implementation-evidence/final-cleanup-20261012'
assert not evidence.exists() and not saved.exists()
evidence.mkdir(parents=True)
saved.mkdir(parents=True)
names = [
    'roll-cleanup-batch-v6-preflight.json', 'roll-cleanup-batch-v6-native-result.json',
    'roll-cleanup-batch-v6-post.json', args.release, args.executor,
    'roll-cleanup-owner-boundary-v9.ps1', 'roll-cleanup-cwd-reader-v9.cs',
    'roll-cleanup-process-owner-observer-v9.ps1', 'roll-cleanup-release-builder-v9a.ps1',
    'roll-cleanup-v9-root-approved-outside.json', 'roll-cleanup-v9-root-owner-decision.json',
    'roll-cleanup-v8-exact-cwd-memory.json', 'roll-cleanup-v8-public-owner-provenance.json',
    'roll-cleanup-v8-owner-lexical-path-v6.json', 'roll-cleanup-v8-owner-argv-proof-v5.json',
    'roll-cleanup-v8-exact-owner-locators-v3.json',
    'roll-cleanup-v9-process-observation-90787b4d24fe405cad222e3a5ae7a470.json',
    'roll-cleanup-v9-process-owners-90787b4d24fe405cad222e3a5ae7a470.json',
    'roll-cleanup-v8-process-observation-ccc69a3c548040c19b63ab35dfcfd6cc.json',
    'roll-cleanup-v9-first-builder-failure.md', 'roll-cleanup-v9c-diagnostic-lineage.json',
    'roll-cleanup-v9b-io-equivalence.json', 'roll-cleanup-batch-v6-metadata.json',
    'roll-cleanup-batch-v7-final31-normalized.json', 'roll-cleanup-batch-v7-final31-raw-controls.json',
    'roll-cleanup-root-flow-appendix.json', 'roll-root-untracked-before-final-docs.json',
    'roll-cleanup-v9-root-external-source-metadata.json',
    'roll-cleanup-private-file-id-v10.cs',
    'roll-cleanup-batch-v10-private-retention.json', 'roll-cleanup-run-final-phase.ps1',
    'roll-cleanup-run-v11-final-phase.ps1', 'roll-cleanup-run-v12-final-phase.ps1',
    'roll-cleanup-run-v13-final-phase.ps1', 'roll-cleanup-bounded-verifier-v13.ps1',
    'roll-cleanup-run-v14-final-phase.ps1', 'roll-cleanup-batch-v13-root-exact-batch.ps1',
    'roll-cleanup-release-v13-exact3802.json', 'roll-cleanup-v13-first-runtime-preflight-failure.json',
    'roll-cleanup-cache-version-dispositions.py', 'roll-cleanup-cache-version-dispositions.json',
    'roll-cleanup-build-v14.py',
    'roll-cleanup-batch-v12-root-exact-batch.ps1', 'roll-cleanup-release-v12-exact3802.json',
    'roll-cleanup-v12-readonly-concurrency-interruption.json',
    'roll-cleanup-v13-parallel-equivalence.json', 'roll-cleanup-v13-parallel-strict-equivalence.json',
    'roll-cleanup-v13-parallel-first-diagnostic.json',
    'roll-cleanup-batch-v10-root-exact-batch.ps1', 'roll-cleanup-batch-v11-root-exact-batch.ps1',
    'roll-cleanup-release-v10-exact3802.json', 'roll-cleanup-release-v11-exact3802.json',
    'roll-cleanup-v10-readonly-buffer-interruption.json',
    'roll-cleanup-v11-buffer-equivalence.json', 'roll-cleanup-v11-control-equivalence.json',
    'roll-cleanup-v11-first-owner-preflight-failure.json',
    release['final_process_observation'], release['final_process_records'],
    'roll-cleanup-v10-process-refresh.json', 'roll-cleanup-v10-first-owner-preflight-failure.json',
    'roll-cleanup-v10-first-descriptor-preflight-failure.json',
    'roll-cleanup-batch-v10-draft-result.json',
    'roll-cleanup-v9c-private-provenance.json', 'roll-cleanup-v9c-private-provenance.md',
    'roll-cleanup-v9c-private-provenance.py', 'roll-cleanup-v9c-private-provenance-execution.json',
    'roll-cleanup-build-v10-release.py', 'roll-cleanup-preserve-extra-untracked.py',
    'roll-cleanup-publish-receipts.py', 'roll-cleanup-write-final-docs.py',
    'roll-cleanup-verify-staged.py',
    'roll-cleanup-batch-v14-root-exact-batch.ps1',
    'roll-cleanup-v14-original-accepted-preflight.json',
    'roll-cleanup-v14-fileset-diagnostic.py', 'roll-cleanup-v14-fileset-diagnostic.json',
    'roll-cleanup-build-v15-control-continuation.py', 'roll-cleanup-v15-control-continuation.json',
    'roll-cleanup-v14-first-fileset-execute-failure.json', 'roll-cleanup-v14-first-fileset-execute-run.log',
    'roll-cleanup-v15-first-longpath-metadata-failure.md',
    'roll-cleanup-batch-v15-root-exact-batch.ps1',
    'roll-cleanup-build-v16-native-resume.py', 'roll-cleanup-v16-native-resume.json',
    'roll-cleanup-v16-native-progress.json', 'roll-cleanup-v15-before-native-resume.json',
    'roll-cleanup-v15-first-branch-argv-execute-failure.json', 'roll-cleanup-v15-first-branch-argv-execute-run.log',
]
# Include exact supplemental controls registered in the final release, never runtime bodies.
for tree in release['trees']:
    for d in tree['additional_manifests']:
        path = Path(d['path'])
        if path.parent == v:
            names.append(path.name)
for name in ('roll-cleanup-v9c-coverage-only.json', 'roll-cleanup-v9d-coverage-only.json',
             'roll-cleanup-v9a-preflight-run.log', 'roll-cleanup-final-preflight-run.log',
             'roll-cleanup-final-execute-run.log', 'roll-cleanup-final-post-run.log',
             'roll-cleanup-extra-untracked-manifest.json', 'roll-cleanup-extra-untracked-receipt.json',
             'roll-cleanup-private-extra-provenance.json', 'roll-cleanup-private-extra-provenance.md'):
    if (v / name).exists():
        names.append(name)
files = []
for name in dict.fromkeys(names):
    source = v / name
    assert source.is_file() and not source.is_symlink(), name
    target = saved / name
    shutil.copyfile(source, target)
    original_sha = hashlib.file_digest(source.open('rb'), 'sha256').hexdigest()
    target_sha = hashlib.file_digest(target.open('rb'), 'sha256').hexdigest()
    assert original_sha == target_sha
    files.append(dict(source=str(source), preserved=str(target), bytes=target.stat().st_size, sha256=target_sha))
    # Large full machine receipts stay in the portable ignored evidence area.
    if name not in {'roll-cleanup-batch-v6-preflight.json', 'roll-cleanup-batch-v6-post.json', 'roll-cleanup-v14-original-accepted-preflight.json', 'roll-cleanup-v15-before-native-resume.json'}:
        shutil.copyfile(source, evidence / name)

def inside(path, base):
    return str(path).lower().startswith(str(base).lower().rstrip('\\/') + '\\')
tree_paths = [t['path'] for t in before['trees']]
source_paths = {r['source'] for r in before['runtime']}
target_paths = {r['destination'] for r in before['runtime']}
summary = dict(
    status='PASS', generated_utc=datetime.now(timezone.utc).isoformat(),
    actual_executor=args.executor, control_guard_continuation=before.get('control_guard_continuation'),
    native_progress_resume=before.get('native_progress_resume'),
    root_head_during_cleanup=release['root_head'], release_id=post['release_id'],
    removed= native['removed'], branches_retained=True,
    manifest_runtime_rows=len(before['runtime']), unique_runtime_sources=len(source_paths),
    unique_runtime_targets=len(target_paths), preflight_unique_proofs=len(before['proofs']),
    post_retained_proofs=len(post['retained_proofs']), source_inventory_entries=len(before['source_inventory']),
    root_dependency_files=len(before['root_dependency_paths']), junctions_unlinked=len(before['junctions']),
    private_metadata_exclusions=len(before['exact_private_exclusions']),
    root_original_63_retained=True, original_foreign_untracked_entries=len(prior),
    foreign_untracked_set_unchanged=True, protected15_allowed3_original19_unchanged=True,
    preserved_targets_unchanged=True, root_dependency_set_bytes_unchanged=True,
    preflight_accepted_byte_sweeps=1, post_byte_sweeps=1,
    initial_preflight_inventory_failure_retained=True, initial_metadata_coverage_failure_retained=True,
    historical_outside_process_records=40, approved_process_records=len(release['process_owner_records']),
    outside_process_records=len(before['process']['outside']),
    historical_exact_relative_cwd_records=30,
    relative_modules_existing=20, relative_modules_missing=10,
    business_source_process_stops=0, owned_readonly_preflight_process_stops=2,
    bounded_readonly_hash_workers=4,
    process_stops_in_accepted_cleanup_interval=0, private_content_reads=0, sqlite_connections=0,
    public_residuals_preserved=3687, public_residual_bytes=304603079,
    exact_current_public_cache_version_sources=1, original_historical_cache_target_retained=True,
    newly_proven_method_private_exclusions=113,
    unknown_private_files_retained_by_same_volume_rename=2,
    unknown_private_file_content_verified=False,
    retained_private_metadata=post['retained_private_metadata'],
    business_tests=0, actual_provider_reviews=0, external_sends=0,
    completion_states_changed=False, qualification='FITTED_UNVALIDATED / NOT_GRANTED')
(evidence / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
(evidence / 'receipt-files.json').write_text(json.dumps(files, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
(evidence / '.gitattributes').write_text('*.json -text whitespace=cr-at-eol\n*.ps1 -text whitespace=cr-at-eol\n*.cs -text whitespace=cr-at-eol\n*.py -text whitespace=cr-at-eol\n*.md -text whitespace=cr-at-eol\n*.log -text whitespace=cr-at-eol\n', encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False))
