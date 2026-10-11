"""Append final browser refusals/audit METHOD profiles without replacing originals."""
import hashlib
import json
import shutil
from pathlib import Path
from roll.decisions.capabilities import source_inventory

here = Path.cwd()
evidence = here / '.scratch/roll-p0/evidence/ticket25'
target = Path('D:/dsh-proj/Roll/.roll-data/implementation-evidence/ticket25')
original = json.loads((evidence / 'runtime-preservation.json').read_text(encoding='utf-8'))
files = list(original['files'])
def digest(path):
    with path.open('rb') as stream: sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'sha256': sha, 'bytes': path.stat().st_size}
profiles = [('browser-stale', '.scratch/t25browser-stale'), ('browser-permission', '.scratch/t25browser-permission'),
            ('browser-sellable', '.scratch/t25browser-sellable2'), ('audit', '.scratch/t25audit')]
for name, relative in profiles:
    source = here / relative
    assert source.exists() and not (target / name).exists()
    for path in sorted(source.rglob('*')):
        if not path.is_file(): continue
        assert not any(word in path.name.lower() for word in ('auth.json', '.env', 'credential', 'token')), path
        destination = target / name / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        before = digest(path)
        shutil.copy2(path, destination)
        assert digest(destination) == before
        files.append({'source': str(path), 'destination': str(destination), **before})
for entry in files: assert digest(Path(entry['destination'])) == {'sha256': entry['sha256'], 'bytes': entry['bytes']}
assert source_inventory() == json.loads((evidence / 'benchmark-results.json').read_text(encoding='utf-8'))['application_sources']
manifest = {**original, 'files': files, 'file_count': len(files), 'additional_profiles': [relative for _, relative in profiles],
            'initial_manifest_sha256': digest(evidence / 'runtime-preservation.json')['sha256'], 'mismatches': 0}
(evidence / 'runtime-preservation-all.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
paths = ['backend/tests/application/test_actions.py', 'backend/tests/support/actions_method_app.py', 'frontend/tests/e2e/actions-restrictions.spec.ts']
(evidence / 'verification-support.json').write_text(json.dumps({'application_sources_equal_final_benchmark': True,
    'files': [{'path': p, **digest(here / p)} for p in paths]}, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'initial_files': original['file_count'], 'additional_files': len(files)-original['file_count'], 'total_files': len(files), 'mismatches': 0}))
