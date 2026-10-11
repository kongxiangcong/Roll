"""Pinned historical METHOD donor. Byte-copy only before opening a disposable copy."""
import hashlib
import json
from pathlib import Path
import shutil
import os

ROOT = Path('D:/dsh-proj/Roll')
DONOR = ROOT / '.roll-data/implementation-evidence/20/independent-api-runtime-fixed'
MANIFEST = ROOT / '.scratch/roll-p0/evidence/continuation-2026-10-11/independent20-profile-manifest.json'
MANIFEST_SHA = '528688f65d19849fffeead4aa8082adc9374dac471eff71ff504c483460c62e7'
FREEZE = '76286d80-4c5d-4262-b97d-ecb856f181f4'

def copy_donor(target):
    target = Path(target)
    assert not target.exists(), 'Use a new disposable profile'
    raw = MANIFEST.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == MANIFEST_SHA
    manifest = json.loads(raw)
    assert manifest['files'] == len(manifest['entries']) == 193
    actual = {p.relative_to(DONOR).as_posix() for p in DONOR.rglob('*') if p.is_file()}
    assert actual == {e['path'] for e in manifest['entries']}
    assert not any(p.lower().endswith(('auth.json', 'channel.json', 'credentials.json', '.env')) for p in actual)
    for entry in manifest['entries']:
        source = DONOR / entry['path']
        original = source.read_bytes()
        assert len(original) == entry['bytes']
        assert hashlib.sha256(original).hexdigest().upper() == entry['sha256']
        destination = target / entry['path']
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        assert destination.read_bytes() == original
        assert source.read_bytes() == original
    (target.parent / (target.name + '-donor-copy.json')).write_text(json.dumps({
        'donor': str(DONOR), 'manifest_sha256': MANIFEST_SHA, 'files': 193,
        'original_sqlite_connections': 0, 'copy_mismatches': 0,
        'original_before_after_mismatches': 0, 'evidence_kind': 'METHOD_CASE'}, indent=2), encoding='utf-8')
    return target


def factory():
    from roll.app import create_app
    from test_valuation import quote_transport
    directory = Path(os.environ['ROLL_DATA_DIR'])
    copy_donor(directory)
    return create_app(directory, runtime_role='API', market_transport=quote_transport())
