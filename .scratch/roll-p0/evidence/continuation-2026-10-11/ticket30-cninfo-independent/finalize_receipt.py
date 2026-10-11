from pathlib import Path
import hashlib, json, subprocess, sys
root = Path('D:/dsh-proj/Roll')
out = root / '.scratch/roll-p0/evidence/continuation-2026-10-11/ticket30-cninfo-independent'
if '--verify-merge' in sys.argv:
    source_oid = '7c46dc59f09604089fad2096bed2e66118b34334'
    parents = subprocess.check_output(['git', 'show', '-s', '--format=%P', 'HEAD'], cwd=root, text=True).strip().split()
    assert parents == ['c2bf9313ce8937dadea01b68b05396ed57a4f1f5', source_oid]
    ev = root / '.scratch/roll-p0/evidence/30-cninfo-history'
    originals = json.loads((ev / 'staged-originals.json').read_text(encoding='utf-8'))['originals']
    for row in originals:
        content = (root / row['path']).read_bytes()
        blob = subprocess.check_output(['git', 'show', 'HEAD:' + row['path']], cwd=root)
        assert content == blob and len(content) == row['bytes'] and hashlib.sha256(content).hexdigest() == row['sha256']
    for name in ['backend/src/roll/app.py', 'backend/src/roll/market/cninfo_history.py', 'backend/src/roll/market/post_close_packet.py',
                 'backend/src/roll/market/reference/cninfo-history/sources.json', '.scratch/roll-p0/evidence/30-cninfo-history/acceptance.md']:
        assert subprocess.check_output(['git', 'show', 'HEAD:' + name], cwd=root) == subprocess.check_output(['git', 'show', source_oid + ':' + name], cwd=root)
    issue = (root / '.scratch/roll-p0/issues/30-forward-archive-deadline.md').read_text(encoding='utf-8')
    assert '**Completion:** partial' in issue
    result = {'merge_oid': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        'parents': parents, 'raw6_file_git_blob_match_after_merge': True, 'source_parser_routes_and_acceptance_unchanged': True,
        'ticket30_completion': 'partial', 'original_acceptance_remaining_frontier_unchanged': True}
    (out / 'merge-verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
else:
    runtime = root / '.roll-data/r30ci'
    files = []
    for path in sorted(runtime.rglob('*')):
        if path.is_file():
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            files.append({'path': str(path), 'sha256': digest, 'bytes': path.stat().st_size})
    result = {'root': str(runtime), 'file_count': len(files), 'total_bytes': sum(row['bytes'] for row in files), 'files': files,
        'root_preserved_sqlite_connections': 0, 'actual_http_provider_calls': 0, 'training_fits': 0}
    (out / 'owned-runtime-manifest.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k != 'files'}))
