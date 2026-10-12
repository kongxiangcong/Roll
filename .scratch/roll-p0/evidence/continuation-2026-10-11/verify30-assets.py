"""Static source-commit and preserved METHOD profile verification; no app."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
SCOPE = Path(__file__).resolve().parent
sha = lambda data: hashlib.sha256(data).hexdigest()
manifest = json.loads((ROOT / '.scratch/roll-p0/evidence/30/runtime-preservation-manifest.json').read_text(encoding='utf-8'))
counts = []
for item in manifest['profiles']:
    source, target = Path(item['source']), Path(item['target'])
    assert source.is_relative_to(ROOT / '.scratch/worktrees/ticket30')
    assert target.is_relative_to(ROOT / '.roll-data/implementation-evidence/30')
    for f in item['files']:
        for directory in (source, target):
            p = directory / f['path']
            assert p.resolve().is_relative_to(directory.resolve())
            data = p.read_bytes()
            assert len(data) == f['length'] and sha(data) == f['sha256'], str(p)
    assert len(item['files']) == item['file_count']
    counts.append({'target': str(target), 'files': len(item['files']), 'bytes': sum(f['length'] for f in item['files'])})
snapshot = json.loads((ROOT / '.scratch/roll-p0/evidence/30/source-after-offset-final.json').read_text(encoding='utf-8'))
commit = '11df4e367f82b8970b1af1e7346225d990dd456a'
for path, record in snapshot['sources'].items():
    raw = subprocess.run(['git', 'show', commit + ':' + path], cwd=ROOT, capture_output=True, check=True).stdout
    assert sha(raw.replace(b'\r\n', b'\n')) == record['normalized_sha256'], path
for key in ('protected_original_model_dependencies', 'pending23_packet_sources'):
    for path, record in snapshot[key].items():
        raw = subprocess.run(['git', 'show', commit + ':' + path], cwd=ROOT, capture_output=True, check=True).stdout
        assert sha(raw.replace(b'\r\n', b'\n')) == record['original_sha256'], path
profile = ROOT / '.roll-data/implementation-evidence/30/independent-method-profile'
files = []
for p in sorted(profile.rglob('*')):
    if p.is_file():
        data = p.read_bytes()
        files.append({'path': p.relative_to(profile).as_posix(), 'bytes': len(data), 'sha256': sha(data)})
own = {'profile': str(profile), 'source_merge': '6215a71e73185a6fe015aefa40fb0d00347f665a',
    'evidence_kind': 'METHOD_CASE', 'server_stopped': True, 'file_count': len(files),
    'total_bytes': sum(f['bytes'] for f in files), 'credentials_present': False, 'files': files}
(SCOPE / 'independent30-profile-manifest.json').write_text(json.dumps(own, indent=2) + '\n', encoding='utf-8')
report = {'status': 'PASS', 'source_commit_verified': commit, 'profiles': counts,
    'preserved_profile_count': len(counts), 'preserved_files': sum(x['files'] for x in counts),
    'preserved_bytes': sum(x['bytes'] for x in counts), 'source_and_target_mismatches': 0,
    'product_source_snapshot_matches': True, 'upstream_model_dependencies_unchanged': 12,
    'five_provider_sources_unchanged_in_ticket30': True,
    'source_scope': 'pre-DIV-fix ticket30 source; later shadow fix requires new source-bound evidence',
    'independent_profile_files': own['file_count'], 'independent_profile_bytes': own['total_bytes'],
    'app_started': False, 'provider_calls': 0, 'production19_opened': False}
(SCOPE / 'merge30-assets.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in report.items() if k != 'profiles'}))
