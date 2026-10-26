"""Preserve every owned untracked/ignored file before requesting worktree removal."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path('D:/dsh-proj/Roll')
EVIDENCE = ROOT / '.scratch/roll-p0/evidence/continuation-2026-10-14'
TARGET = ROOT / '.roll-data/implementation-evidence/worktree-cleanup-20261014'
NAMES = ['t25-production-inputs', 't30-action-window', 't25-input-settings', 't20-policy-successor']
LINKS = {'frontend/node_modules': ROOT / 'frontend/node_modules', 'backend/.venv': ROOT / 'backend/.venv'}

def digest(path):
    path = Path('\\\\?\\' + str(path.absolute())) if os.name == 'nt' and not str(path).startswith('\\\\?\\') else path
    checksum = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(chunk)
    return {'bytes': path.stat().st_size, 'sha256': checksum.hexdigest()}

def git_files(tree, ignored):
    arguments = ['git', '-c', 'core.quotepath=false', '-C', str(tree), 'ls-files', '--others', '--exclude-standard', '-z']
    if ignored:
        arguments.insert(-1, '--ignored')
    return set(filter(None, subprocess.check_output(arguments).decode('utf-8').split('\0')))

receipt = {'authorization': {'skill': 'C:/Users/72449/.agents/skills/implement-spec/SKILL.md',
    'instruction': '9. Clean up all implementer subagent worktrees.', 'user_invoked': True},
    'workspace': str(ROOT), 'target': str(TARGET), 'worktrees': [], 'mismatches': 0}
for name in NAMES:
    tree = ROOT / '.scratch/worktrees' / name
    if tree.resolve().parent != (ROOT / '.scratch/worktrees').resolve():
        raise RuntimeError('Unexpected worktree root')
    if subprocess.check_output(['git', '-C', str(tree), 'status', '--porcelain', '--untracked-files=no']).strip():
        raise RuntimeError('Tracked changes remain')
    excluded = []
    for relative, expected in LINKS.items():
        link = tree / relative
        if link.exists():
            if not link.is_junction() or link.resolve() != expected.resolve():
                raise RuntimeError('Unexpected dependency link')
            excluded.append({'path': relative, 'kind': 'JUNCTION', 'target': str(expected), 'action': 'unlink only; preserve shared target'})
    rows = []
    for relative in sorted(git_files(tree, False) | git_files(tree, True)):
        if any(relative == link or relative.startswith(link + '/') for link in LINKS):
            continue
        source = tree / relative
        physical_source = Path('\\\\?\\' + str(source.absolute())) if os.name == 'nt' else source
        if source.is_symlink() or source.is_junction():
            resolved = source.resolve()
            if not resolved.is_relative_to(tree.resolve()):
                raise RuntimeError('Untracked link escapes owned tree: ' + relative)
            excluded.append({'path': relative, 'kind': 'GENERATED_INTERNAL_LINK', 'target': str(resolved),
                'action': 'metadata retained; target files independently preserved'})
            continue
        if not physical_source.is_file():
            raise RuntimeError('Unexpected non-file untracked content: ' + relative)
        if not source.resolve().is_relative_to(tree.resolve()):
            raise RuntimeError('Source escaped owned tree')
        if any(part == '.env' or part.startswith('.roll-private') or 'auth' in part.lower() or 'credential' in part.lower() for part in source.relative_to(tree).parts):
            raise RuntimeError('Private-looking file requires separate provenance check')
        destination = TARGET / name / relative
        physical_destination = Path('\\\\?\\' + str(destination.absolute())) if os.name == 'nt' else destination
        before = digest(source)
        physical_destination.parent.mkdir(parents=True, exist_ok=True)
        if physical_destination.exists():
            if digest(destination) != before:
                raise RuntimeError('Existing preservation destination differs')
        else:
            shutil.copyfile(physical_source, physical_destination)
        if digest(source) != before or digest(destination) != before:
            raise RuntimeError('Preservation mismatch')
        rows.append({'path': relative, 'destination': str(destination), **before})
    receipt['worktrees'].append({'name': name, 'path': str(tree), 'head': subprocess.check_output(['git', '-C', str(tree), 'rev-parse', 'HEAD']).decode().strip(),
        'excluded_dependency_junctions': excluded, 'untracked_and_ignored_files': rows,
        'file_count': len(rows), 'bytes': sum(row['bytes'] for row in rows)})
EVIDENCE.mkdir(parents=True, exist_ok=True)
(EVIDENCE / 'cleanup-content-audit.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'worktrees': len(receipt['worktrees']), 'files': sum(row['file_count'] for row in receipt['worktrees']),
    'bytes': sum(row['bytes'] for row in receipt['worktrees']), 'mismatches': 0}))
