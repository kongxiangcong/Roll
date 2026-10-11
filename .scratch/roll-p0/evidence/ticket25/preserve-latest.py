"""Append stopped final-composition profiles without replacing 2922 originals."""
import hashlib
import json
import shutil
from pathlib import Path
from roll.decisions.capabilities import source_inventory

here = Path.cwd()
root = Path('D:/dsh-proj/Roll')
evidence = here / '.scratch/roll-p0/evidence/ticket25'
target = root / '.roll-data/implementation-evidence/ticket25'
prior = json.loads((evidence / 'runtime-preservation-states.json').read_text(encoding='utf-8'))
files = list(prior['files'])

def digest(path):
    with path.open('rb') as stream:
        sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'sha256': sha, 'bytes': path.stat().st_size}

profiles = [('composition-latest', '.scratch/t25latest-compose'), ('benchmark-latest', '.scratch/t25perf10')]
excluded = ('test_explicit_codex_', 'test_legacy_deepseek_', 'test_legacy_selection_', 'test_new_deepseek_')
for kind, relative in profiles:
    source = here / relative
    assert source.exists() and not (target / kind).exists()
    for path in sorted(source.rglob('*')):
        if not path.is_file(): continue
        suffix = path.relative_to(source)
        if kind == 'composition-latest' and suffix.parts[0].startswith(excluded): continue
        assert not any(word in path.name.lower() for word in ('auth.json', '.env', 'credential', 'token')), path
        destination = target / kind / suffix
        destination.parent.mkdir(parents=True, exist_ok=True)
        before = digest(path)
        shutil.copy2(path, destination)
        assert digest(destination) == before
        files.append({'source': str(path), 'destination': str(destination), **before})
for item in files:
    expected = {'sha256': item['sha256'], 'bytes': item['bytes']}
    assert digest(Path(item['source'])) == expected
    assert digest(Path(item['destination'])) == expected
manifest = {**prior, 'files': files, 'file_count': len(files), 'latest_profiles': profiles,
            'previous_manifest_sha256': digest(evidence / 'runtime-preservation-states.json')['sha256'],
            'previous_count': prior['file_count'], 'additional_count': len(files)-prior['file_count'],
            'mismatches': 0, 'sources_reverified': True}
(evidence / 'runtime-preservation-latest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
guard = json.loads((evidence / 'source-guard-states.json').read_text(encoding='utf-8'))
for item in guard['protected_sources']:
    expected = {'sha256': item['sha256'], 'bytes': item['bytes']}
    assert digest(here / item['path']) == expected
    assert digest(root / item['path']) == expected
original = guard['original_database']
assert digest(root / original['path']) == {'sha256': original['sha256'], 'bytes': original['bytes']}
for item in guard['allowed_model_artifacts_unchanged']:
    assert digest(Path(item['path'])) == {'sha256': item['sha256'], 'bytes': item['bytes']}
result = json.loads((evidence / 'benchmark-results.json').read_text(encoding='utf-8'))
sources = source_inventory()
assert sources == result['application_sources']
for item in guard['frontend']:
    assert digest(here / item['path']) == {'sha256': item['sha256'], 'bytes': item['bytes']}
support = ['backend/tests/application/test_actions.py', 'backend/tests/support/actions_method_app.py',
           'frontend/tests/e2e/actions-restrictions.spec.ts']
(evidence / 'source-guard-latest.json').write_text(json.dumps({**guard, 'application_sources': sources,
    'integration_base': 'c3fe7d8d83d05b8579979be3c6b62a5af03103ce', 'source_projection_commit': 'e3a4a56',
    'application_sources_equal_handoff_benchmark': False, 'application_sources_equal_states_benchmark': False,
    'application_sources_equal_latest_benchmark': True, 'prior_browser_frontend_identical': True,
    'support': [{'path': p, **digest(here / p)} for p in support]}, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'previous_files': prior['file_count'], 'additional_files': len(files)-prior['file_count'],
    'total_files': len(files), 'mismatches': 0, 'protected_sources': len(guard['protected_sources']),
    'original_database_unchanged': True, 'current_sources_equal_benchmark': True}))

