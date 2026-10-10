"""Read-only pre-cleanup integrity/credential checks; prints counts only."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).resolve().parent
MANIFESTS = ['merge-12-runtime.json', 'merge-fuyao-runtime.json',
             'merge-fuyao-background-runtime.json', 'merge-13-runtime.json']
ENV_SHA = 'e959c2e15ad5206edc9b0f690b4dcb3c96f17482ae036e50a51c9f81125ac280'


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def main():
    destination_only = '--destination-only' in sys.argv
    # This explicit authorized file is read only to compare necessary values locally.
    sys.path.insert(0, str(ROOT / 'backend/src'))
    from roll.config import load_runtime_environment
    for name in ['DEEPSEEK_API_KEY', 'FUYAO_API_KEY']:
        os.environ.pop(name, None)
    os.environ['ROLL_ENV_FILE'] = str(ROOT / '.env')
    load_runtime_environment()
    secrets = [os.environ[name].encode() for name in ['DEEPSEEK_API_KEY', 'FUYAO_API_KEY']]
    auth = json.loads(Path(r'C:\Users\72449\.codex\auth.json').read_text(encoding='utf-8'))
    secrets.extend(value.encode() for name in ['id_token', 'access_token', 'refresh_token']
                   if (value := auth.get('tokens', {}).get(name)))
    reports = []
    total = total_bytes = mismatches = secret_matches = 0
    for name in MANIFESTS:
        manifest = json.loads((EVIDENCE / name).read_text(encoding='utf-8'))
        source, target = Path(manifest['source']), Path(manifest['destination'])
        for item in manifest['files']:
            relative = Path(item['relative'])
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('MANIFEST_PATH_OUTSIDE_RUNTIME')
            for base in [target] if destination_only else [source, target]:
                path = base / relative
                if path.stat().st_size != item['bytes'] or digest(path) != item['sha256']:
                    mismatches += 1
                content = path.read_bytes()
                secret_matches += sum(secret in content for secret in secrets)
            total += 1
            total_bytes += item['bytes']
        reports.append({'manifest': name, 'files': len(manifest['files']),
                        'bytes': sum(item['bytes'] for item in manifest['files'])})
    changed = subprocess.check_output(['git', 'diff', '--name-only', 'd1b867e...HEAD'],
                                     cwd=ROOT, text=True).splitlines()
    for path in changed:
        content = subprocess.check_output(['git', 'show', 'HEAD:' + path], cwd=ROOT)
        secret_matches += sum(secret in content for secret in secrets)
    candidates = subprocess.check_output(['git', '-c', 'core.quotePath=false', 'diff', '--name-only', 'HEAD'],
                                         cwd=ROOT, text=True).splitlines()
    candidates += subprocess.check_output(['git', '-c', 'core.quotePath=false', 'ls-files', '--others', '--exclude-standard'],
                                          cwd=ROOT, text=True).splitlines()
    working_files = 0
    for path in set(candidates):
        candidate = ROOT / path
        if candidate.is_file():
            content = candidate.read_bytes()
            secret_matches += sum(secret in content for secret in secrets)
            working_files += 1
    result = {'manifests': reports, 'files': total, 'bytes': total_bytes,
              'verification_scope': 'DESTINATION_ONLY' if destination_only else 'SOURCE_AND_DESTINATION',
              'checked_git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'both_tree_sha_length_mismatches': mismatches,
              'credential_matches': secret_matches, 'changed_git_blobs': len(changed),
              'working_tree_files_scanned': working_files,
              'env_unchanged': digest(ROOT / '.env') == ENV_SHA,
              'env_ignored': subprocess.run(['git', 'check-ignore', '-q', '.env'], cwd=ROOT).returncode == 0,
              'env_tracked': subprocess.run(['git', 'ls-files', '--error-unmatch', '.env'],
                                             cwd=ROOT, stdout=subprocess.DEVNULL,
                                             stderr=subprocess.DEVNULL).returncode == 0}
    output = 'final-preservation-after-cleanup.json' if destination_only else 'final-preservation.json'
    (EVIDENCE / output).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key != 'manifests'}))
    if mismatches or secret_matches or not result['env_unchanged'] or not result['env_ignored'] or result['env_tracked']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
