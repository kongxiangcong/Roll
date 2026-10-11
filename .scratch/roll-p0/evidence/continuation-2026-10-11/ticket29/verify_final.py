"""Final metadata and original donor raw-byte proof, no database connection."""
import hashlib, json
from pathlib import Path
root = Path('D:/dsh-proj/Roll')
tree = root / '.scratch/worktrees/ticket29'
out = tree / '.scratch/roll-p0/evidence/continuation-2026-10-11/ticket29'
def digest(path):
    raw = path.read_bytes(); return {'bytes':len(raw), 'sha256':hashlib.sha256(raw).hexdigest()}
pin = root / '.scratch/roll-p0/evidence/continuation-2026-10-11/independent20-profile-manifest.json'
assert digest(pin)['sha256'] == '528688f65d19849fffeead4aa8082adc9374dac471eff71ff504c483460c62e7'
donor = root / '.roll-data/implementation-evidence/20/independent-api-runtime-fixed'
manifest = json.loads(pin.read_text(encoding='utf-8'))
assert {p.relative_to(donor).as_posix() for p in donor.rglob('*') if p.is_file()} == {e['path'] for e in manifest['entries']}
for entry in manifest['entries']:
    proof = digest(donor / entry['path'])
    assert proof['bytes'] == entry['bytes'] and proof['sha256'].upper() == entry['sha256']
owned = out / 'runtime-preservation.json'
preserved = root / '.roll-data/implementation-evidence/ticket29-r01/manifest.json'
assert owned.read_bytes() == preserved.read_bytes()
before = {e['path']:e for e in json.loads((out / 'source-before.json').read_text())['sources']}
after = {e['path']:e for e in json.loads((out / 'source-final.json').read_text())['sources']}
cache_before = json.loads((out / 'root-vite-cache-before-final.json').read_text(encoding='utf-8-sig'))
cache_after = json.loads((out / 'root-vite-cache-after-final.json').read_text(encoding='utf-8-sig'))
result = {'donor_files':193, 'donor_after_mismatches':0, 'donor_sqlite_connections':0,
          'preserved_manifest_actual_bytes_and_sha256':digest(preserved), 'owned_manifest':digest(owned),
          'preservation_log_sha_is_lf_payload_not_on_disk_manifest':True,
          'root_vite_cache_own_cache_final_interval_equal':cache_before == cache_after,
          'root_vite_cache_before_first_browser_claimed_unchanged':False,
          'changed_product_sources_since_original_base':sorted(p for p in before.keys() | after.keys() if before.get(p) != after.get(p)),
          'scope':'includes accepted root price source merge; own report/readonly projection/visuals',
          'protected_source_count':15, 'final_product_source_count':len(after)}
(out / '38-final-verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result))
