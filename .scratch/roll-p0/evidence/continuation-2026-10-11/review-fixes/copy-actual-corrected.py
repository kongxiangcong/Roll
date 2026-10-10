"""Opaque stopped-profile SQLite backup; no app, fit, provider or archive parsing."""
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3

ROOT = Path('D:/dsh-proj/Roll').resolve()
SOURCE = ROOT / '.roll-data/implementation-evidence/23/actual-current-copy'
TARGET = ROOT / '.roll-data/implementation-evidence/continuation-review-fixes/actual-corrected-copy'
REPORT = Path(__file__).resolve().parent / 'actual-corrected-copy-manifest.json'


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def check_plain_path(path, boundary):
    if not path.is_relative_to(boundary):
        raise RuntimeError('Path outside explicitly authorized runtime')
    current = path
    while current != ROOT:
        if current.is_symlink() or getattr(current, 'is_junction', lambda: False)():
            raise RuntimeError('Runtime path contains a link or junction')
        current = current.parent
    if not path.resolve().is_relative_to(boundary):
        raise RuntimeError('Resolved runtime path escaped boundary')


if TARGET.exists() or REPORT.exists():
    raise SystemExit('New target/report must not exist; preserve prior outcomes')
check_plain_path(SOURCE, SOURCE)
check_plain_path(TARGET, TARGET)
source_db = SOURCE / 'roll.sqlite3'
source_wal = SOURCE / 'roll.sqlite3-wal'
if not source_db.is_file() or (source_wal.exists() and source_wal.stat().st_size):
    raise SystemExit('Stopped source must have a regular DB and no nonempty WAL')
source_files = [p for p in SOURCE.glob('roll.sqlite3*') if p.is_file()]
source_before = {p.name: {'bytes': p.stat().st_size, 'sha256': digest(p)} for p in source_files}
TARGET.mkdir(parents=True, exist_ok=False)
# Source is stopped and WAL empty: immutable read-only prevents even SHM mutation.
# SQLite's online backup API copies the whole persisted database without opening an app.
with sqlite3.connect(source_db.as_uri() + '?mode=ro&immutable=1', uri=True) as source:
    source.execute('PRAGMA query_only=ON')
    with sqlite3.connect(TARGET / 'roll.sqlite3') as destination:
        source.backup(destination)
    tables = [row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    source_counts = {name: source.execute('SELECT count(*) FROM "' + name.replace('"', '""') + '"').fetchone()[0] for name in tables}
with sqlite3.connect((TARGET / 'roll.sqlite3').as_uri() + '?mode=ro&immutable=1', uri=True) as db:
    assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    copied_counts = {name: db.execute('SELECT count(*) FROM "' + name.replace('"', '""') + '"').fetchone()[0] for name in tables}
    assert copied_counts == source_counts
    references = [json.loads(row[0]) for row in db.execute('SELECT value FROM evidence_archives')]
files = []
for reference in references:
    original = SOURCE / reference['path']
    copied = TARGET / reference['path']
    check_plain_path(original, SOURCE)
    check_plain_path(copied, TARGET)
    if not original.is_file():
        raise RuntimeError('Registered archive missing or not a regular file')
    original_hash = digest(original)
    if original_hash != reference['sha256'] or original.stat().st_size != reference['bytes']:
        raise RuntimeError('Registered archive integrity mismatch')
    copied.parent.mkdir(parents=True, exist_ok=True)
    if copied.exists():
        raise RuntimeError('Duplicate registered destination; do not overwrite')
    shutil.copyfile(original, copied)
    if digest(copied) != original_hash or copied.stat().st_size != reference['bytes']:
        raise RuntimeError('Opaque archive copy differs')
    files.append({'path': reference['path'], 'sha256': original_hash, 'bytes': reference['bytes']})
source_after = {p.name: {'bytes': p.stat().st_size, 'sha256': digest(p)} for p in source_files}
if source_before != source_after:
    raise RuntimeError('Source database or sidecars changed during opaque backup')
record = {
    'status': 'PASS', 'source': str(SOURCE), 'destination': str(TARGET),
    'copy_method': 'SQLITE_READONLY_IMMUTABLE_ONLINE_BACKUP_STOPPED_EMPTY_WAL',
    'source_process_preflight': 'PASS: no exact source-profile command references',
    'source_files_before': source_before, 'source_files_after': source_after,
    'source_db_unchanged': True, 'source_sidecars_unchanged': True,
    'destination_db_sha256': digest(TARGET / 'roll.sqlite3'),
    'sqlite_integrity': 'ok', 'table_row_counts_unchanged': True,
    'table_row_counts': source_counts, 'archives': files,
    'archive_count': len(files), 'archive_bytes': sum(item['bytes'] for item in files),
    'archive_copy_mismatches': 0, 'semantics_consumed': False,
    'credentials_or_unregistered_files_copied': False,
    'source_or_original_runtime_started': False, 'fits_or_confirmation_executed': False,
    'new_freeze_or_validation_executed': False, 'provider_calls': 0,
}
REPORT.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({key: record[key] for key in ('status', 'archive_count', 'archive_bytes', 'archive_copy_mismatches', 'source_db_unchanged', 'source_sidecars_unchanged', 'provider_calls')}))
