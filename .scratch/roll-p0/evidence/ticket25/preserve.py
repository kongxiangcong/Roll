"""Preserve stopped Ticket25 METHOD profiles and verify each byte, no actual DB opening."""
import hashlib
import json
import shutil
from pathlib import Path

here = Path.cwd()
root = Path('D:/dsh-proj/Roll')
evidence = here / '.scratch/roll-p0/evidence/ticket25'
target = root / '.roll-data/implementation-evidence/ticket25'
assert not target.exists(), 'Never replace an existing preservation receipt'

def digest(path):
    data = path.read_bytes()
    return {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}

# Persist the exact already-measured METHOD vector; rebuilding here uses the
# recorded cutoff, not a new clock or a new prediction. No new timed sample.
result = json.loads((evidence / 'benchmark-results.json').read_text(encoding='utf-8'))
package = json.loads((here / '.scratch/t25perf7/qualification.json').read_text(encoding='utf-8'))['package']
from roll.accounts.ledger import encode
facts = [{'instrument': 'SSE:600362', 'trade_date': day, 'close': str(100+i), 'volume_shares': str(1000000+i*10000),
          'adjustment': 'RAW', 'volume_unit': 'SHARE', 'errors': [], 'completion_state': 'COMPLETE_REPORTED_HISTORICAL',
          'method_completion_available_at': day+'T15:05:00+08:00', 'available_at': package['required_as_of'],
          'raw_hash': hashlib.sha256(('METHOD-'+day).encode()).hexdigest(), 'cash_events_effective': [], 'evidence_kind': 'METHOD_CASE'}
         for i, day in enumerate(result['feature_trade_dates'])]
raw = encode(facts).encode()
assert hashlib.sha256(raw).hexdigest() == result['feature_packet_sha256']
(here / '.scratch/t25perf7/feature-packet.json').write_bytes(raw)

profiles = [('api', here / '.scratch/t25accepted'), ('browser', here / '.scratch/t25browser6'), ('benchmark', here / '.scratch/t25perf7')]
excluded = ('test_explicit_codex_', 'test_legacy_deepseek_', 'test_legacy_selection_', 'test_new_deepseek_')
manifest = []
for kind, source in profiles:
    for path in sorted(source.rglob('*')):
        if not path.is_file(): continue
        relative = path.relative_to(source)
        if kind == 'api' and relative.parts[0].startswith(excluded): continue
        assert not any(word in path.name.lower() for word in ('auth.json', '.env', 'credential', 'token')), path
        destination = target / kind / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        before = digest(path)
        shutil.copy2(path, destination)
        assert digest(destination) == before
        manifest.append({'source': str(path), 'destination': str(destination), **before})
(evidence / 'runtime-preservation.json').write_text(json.dumps({'profiles': [str(p) for _, p in profiles], 'target': str(target),
    'excluded_profiles': list(excluded), 'files': manifest, 'file_count': len(manifest), 'mismatches': 0,
    'scope': 'Stopped isolated METHOD only; no actual research/runtime, no credential files'}, ensure_ascii=False, indent=2), encoding='utf-8')

guard = json.loads((here / '.scratch/roll-p0/evidence/continuation-2026-10-11/frontier24-29/root-protected-source-after24.json').read_text(encoding='utf-8'))
for item in guard['source_files']:
    assert digest(here / item['path']) == {'sha256': item['sha256'], 'bytes': item['bytes']}
    assert digest(root / item['path']) == {'sha256': item['sha256'], 'bytes': item['bytes']}
original = guard['original_database']
assert digest(root / original['path']) == {'sha256': original['sha256'], 'bytes': original['bytes']}
reference = json.loads((here / '.scratch/roll-p0/evidence/continuation-2026-10-11/frontier24-29/benchmark-artifact-reference.json').read_text(encoding='utf-8'))
for artifact in reference['artifacts']:
    assert digest(Path(artifact['path'])) == {'sha256': artifact['sha256'], 'bytes': artifact['bytes']}
from roll.decisions.capabilities import source_inventory
sources = source_inventory()
assert sources == result['application_sources']
ui = ['frontend/src/components/action-panel.tsx', 'frontend/src/pages/today.tsx', 'frontend/src/pages/market.tsx', 'frontend/tests/e2e/actions.spec.ts']
(evidence / 'source-guard.json').write_text(json.dumps({'protected_source_count': len(guard['source_files']), 'protected_sources': guard['source_files'],
    'own_and_root_raw_unchanged': True, 'original_database': original, 'original_database_unchanged': True,
    'allowed_model_artifacts_unchanged': reference['artifacts'], 'application_sources': sources,
    'frontend': [{'path': p, **digest(here / p)} for p in ui]}, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'preserved_files': len(manifest), 'mismatches': 0, 'protected_sources': len(guard['source_files']), 'original_database_unchanged': True}))
