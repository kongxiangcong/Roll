"""Opaque consistent acceptance copy; never start or modify the source runtime."""
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3

ROOT = Path('D:/dsh-proj/Roll').resolve()
SOURCE = ROOT / '.roll-data/implementation-evidence/21/actual-current-copy'
TARGET = ROOT / '.roll-data/implementation-evidence/23/actual-current-copy'
REPORT = Path(__file__).resolve().parent / 'actual-copy-manifest.json'

def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()

if TARGET.exists():
    raise SystemExit('Acceptance target already exists; preserve it and use a new explicit target')
if TARGET.parent.resolve() != ROOT / '.roll-data/implementation-evidence/23':
    raise SystemExit('Acceptance target outside the authorized evidence directory')
SOURCE_DB = SOURCE / 'roll.sqlite3'
source_before = digest(SOURCE_DB)
TARGET.mkdir(parents=True)
with sqlite3.connect(SOURCE_DB.as_uri() + '?mode=ro', uri=True) as source:
    with sqlite3.connect(TARGET / 'roll.sqlite3') as destination:
        source.backup(destination)
with sqlite3.connect((TARGET / 'roll.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
    references = [json.loads(row[0]) for row in db.execute('SELECT value FROM evidence_archives')]
files = []
for reference in references:
    original = (SOURCE / reference['path']).resolve()
    copied = (TARGET / reference['path']).resolve()
    if not original.is_relative_to(SOURCE) or not copied.is_relative_to(TARGET):
        raise RuntimeError('Registered archive escaped its runtime directory')
    if original.is_symlink() or not original.is_file():
        raise RuntimeError('Registered archive is missing or not a regular file')
    original_hash = digest(original)
    if original_hash != reference['sha256'] or original.stat().st_size != reference['bytes']:
        raise RuntimeError('Registered archive integrity mismatch')
    copied.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(original, copied)
    copied_hash = digest(copied)
    if copied_hash != original_hash or copied.stat().st_size != original.stat().st_size:
        raise RuntimeError('Opaque archive copy differs')
    files.append({'path': reference['path'], 'sha256': copied_hash, 'bytes': copied.stat().st_size})
source_after = digest(SOURCE_DB)
if source_before != source_after:
    raise RuntimeError('Source database changed during acceptance copy')
record = {'source': str(SOURCE), 'destination': str(TARGET), 'copy_method': 'SQLITE_READONLY_ONLINE_BACKUP',
    'source_db_sha256_before': source_before, 'source_db_sha256_after': source_after,
    'destination_db_sha256': digest(TARGET / 'roll.sqlite3'), 'source_db_unchanged': True,
    'archives': files, 'archive_count': len(files), 'archive_bytes': sum(item['bytes'] for item in files),
    'archive_copy_mismatches': 0, 'semantics_consumed': False, 'credentials_or_unregistered_files_copied': False,
    'original_runtime_started': False, 'fits_or_confirmation_executed': False}
REPORT.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({key: record[key] for key in ['archive_count', 'archive_bytes', 'archive_copy_mismatches', 'source_db_unchanged']}))
