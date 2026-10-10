"""Copy declared isolated engineering fixtures before managed worktree archive."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
CHILD = Path('C:/Users/72449/.codex/worktrees/ticket19-training-preflight/Roll').resolve()
DESTINATION = (ROOT / 'backend/.roll-data/t19-preflight-preserved').resolve()
METADATA = CHILD / '.scratch/roll-p0/evidence/19-completion-2026-10-09/training-preflight-implementation-verification.json'


def verify(content, entry):
    return len(content) == entry['bytes'] and hashlib.sha256(content).hexdigest() == entry['sha256']


def main():
    DESTINATION.relative_to(ROOT.resolve())
    metadata_bytes = METADATA.read_bytes()
    manifest = json.loads(metadata_bytes)['ignored_fixture_preservation']
    if Path(manifest['workspace']).resolve() != CHILD:
        raise ValueError('DECLARED_WORKSPACE_MISMATCH')
    entries = manifest.get('files')
    if entries is None:
        entries = []
        for summary in manifest['directories']:
            directory = (CHILD / summary['path']).resolve()
            directory.relative_to(CHILD)
            if not Path(summary['path']).as_posix().startswith('.scratch/t19-final'):
                raise ValueError('UNEXPECTED_FIXTURE_DIRECTORY')
            files = []
            for source in sorted(directory.rglob('*')):
                if source.is_file():
                    content = source.read_bytes()
                    files.append({'path': source.relative_to(CHILD).as_posix(),
                                  'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()})
            digest = hashlib.sha256(json.dumps(files, ensure_ascii=False, sort_keys=True,
                                               separators=(',', ':')).encode()).hexdigest()
            if (digest != summary['sorted_file_metadata_sha256'] or
                    len(files) != summary['file_count'] or
                    sum(f['bytes'] for f in files) != summary['bytes']):
                raise ValueError('DIRECTORY_MANIFEST_CHANGED: ' + summary['path'])
            entries.extend(files)
    if len(entries) != manifest['file_count']:
        raise ValueError('DECLARED_FILE_COUNT_MISMATCH')
    saved = []
    for entry in entries:
        relative = Path(entry['path'])
        if relative.is_absolute() or not relative.as_posix().startswith('.scratch/t19-final'):
            raise ValueError('UNEXPECTED_FIXTURE_SCOPE')
        original = (CHILD / relative).resolve()
        target = (DESTINATION / relative).resolve()
        original.relative_to(CHILD)
        target.relative_to(DESTINATION)
        content = original.read_bytes()
        if not verify(content, entry):
            raise ValueError('SOURCE_FIXTURE_CHANGED: ' + entry['path'])
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if not verify(target.read_bytes(), entry):
                raise ValueError('EXISTING_DESTINATION_DIFFERS: ' + entry['path'])
        else:
            target.write_bytes(content)
        if not verify(target.read_bytes(), entry):
            raise ValueError('DESTINATION_FIXTURE_MISMATCH: ' + entry['path'])
        saved.append({**entry, 'original': str(original), 'preserved': str(target)})
    total = sum(entry['bytes'] for entry in saved)
    if total != manifest['bytes']:
        raise ValueError('DECLARED_TOTAL_BYTES_MISMATCH')
    receipt = {'verified_at': datetime.now(timezone.utc).isoformat(),
               'source': str(CHILD), 'destination': str(DESTINATION),
               'source_manifest_sha256': hashlib.sha256(metadata_bytes).hexdigest(),
               'file_count': len(saved), 'bytes': total, 'hash_length_mismatches': 0,
               'scope': 'Isolated engineering fixtures; not actual historical market qualification',
               'files': saved, 'worktree_archived': False}
    (Path(__file__).parent / 'worktree-preservation.json').write_bytes(
        (json.dumps(receipt, ensure_ascii=False, indent=2)+'\n').encode('utf-8'))
    print(json.dumps({key: receipt[key] for key in ['file_count', 'bytes', 'hash_length_mismatches']}))


if __name__ == '__main__':
    main()
