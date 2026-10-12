"""Install a fixed official CNEquity source tree in an isolated project runtime."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import venv

ROOT = Path(__file__).resolve().parents[1]
COMMIT = 'c118038ea82b5bb78783c0c17a1d9251b36de71d'
RUNTIME = ROOT/'.roll-data/cnequity-runtime'
ADAPTER_REQUIREMENTS = {'httpx': '0.28.1', 'polars': '2.0.0', 'PyYAML': '6.0.3', 'tzdata': '2026.5'}


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'Roll-pinned-data-layer/1.0'})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read(10*1024*1024+1)
        if len(body) > 10*1024*1024:
            raise ValueError('SETUP_DOWNLOAD_SIZE_LIMIT')
        return body


def native_wheel():
    """Resume bounded official binary downloads; validate full PyPI hash before installation."""
    if sys.platform != 'win32':
        return 'polars-runtime-32==2.0.0'
    metadata_path = RUNTIME/'polars-runtime-pypi.json'
    if not metadata_path.exists():
        metadata_path.write_bytes(fetch('https://pypi.org/pypi/polars-runtime-32/2.0.0/json'))
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    item = next(u for u in metadata['urls'] if u['filename'] == 'polars_runtime_32-2.0.0-cp310-abi3-win_amd64.whl')
    target = RUNTIME/'wheels'/item['filename']
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == item['digests']['sha256']:
        return str(target)
    if not item['url'].startswith('https://files.pythonhosted.org/') or not 0 < item['size'] < 100*1024*1024:
        raise ValueError('UNAPPROVED_NATIVE_WHEEL')
    parts = RUNTIME/'wheel-parts'
    parts.mkdir(exist_ok=True)
    chunk_size = 1024*1024
    def part(start):
        end = min(item['size']-1, start+chunk_size-1)
        path = parts/str(start)
        if path.exists() and path.stat().st_size == end-start+1:
            return path
        request = urllib.request.Request(item['url'], headers={
            'Range': f'bytes={start}-{end}', 'Accept-Encoding': 'identity', 'User-Agent': 'Roll-pinned-data-layer/1.0'})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    if response.status != 206 or response.headers.get('Content-Range') != f'bytes {start}-{end}/{item["size"]}':
                        raise ValueError('WHEEL_RANGE_NOT_HONORED')
                    body = response.read(chunk_size+1)
                break
            except (OSError, TimeoutError):
                if attempt == 2:
                    raise
                time.sleep(1)
        if len(body) != end-start+1:
            raise ValueError('INCOMPLETE_WHEEL_PART')
        path.write_bytes(body)
        return path
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        paths = list(pool.map(part, range(0, item['size'], chunk_size)))
    body = b''.join(path.read_bytes() for path in paths)
    if hashlib.sha256(body).hexdigest() != item['digests']['sha256']:
        raise ValueError('NATIVE_WHEEL_HASH_MISMATCH')
    target.write_bytes(body)
    print('Official native wheel SHA256 verified.', flush=True)
    return str(target)


def main():
    RUNTIME.mkdir(parents=True, exist_ok=True)
    marker = RUNTIME/'runtime.json'
    if marker.exists():
        installed = json.loads(marker.read_text(encoding='utf-8'))
        if installed['commit'] != COMMIT:
            raise ValueError('Existing runtime differs; upgrade requires an explicit version change')
        if all(installed.get('dependencies', {}).get(name) == version for name, version in ADAPTER_REQUIREMENTS.items()):
            print('Pinned runtime already installed; run collection integrity/provenance verification.')
            return
        # Preserve the prior runtime provenance while completing this adapter
        # profile. The official source commit is unchanged.
        previous = RUNTIME/f'runtime-before-profile-{time.time_ns()}.json'
        previous.write_bytes(marker.read_bytes())
    source = RUNTIME/'pinned-source'
    tree_path = RUNTIME/'source-tree.json'
    if not tree_path.exists():
        tree_path.write_bytes(fetch(f'https://api.github.com/repos/rootSunc/CNEquity/git/trees/{COMMIT}?recursive=1'))
    tree = json.loads(tree_path.read_text(encoding='utf-8'))
    if tree.get('truncated') or tree.get('sha') != COMMIT:
        raise ValueError('SOURCE_TREE_TRUNCATED')
    selected = [item for item in tree['tree'] if item['type'] == 'blob' and (
        item['path'].startswith('src/') or
        item['path'].startswith('contracts/v') and item['path'].endswith('.json') or
        item['path'] in {'pyproject.toml', 'README.pypi.md', 'LICENSE', 'NOTICE', 'sources/SOURCES.yml'})]
    def download(item):
        target = source/item['path']
        if target.exists():
            body = target.read_bytes()
        elif (RUNTIME/'checkout'/item['path']).exists():
            body = (RUNTIME/'checkout'/item['path']).read_bytes()
        else:
            body = fetch(f'https://raw.githubusercontent.com/rootSunc/CNEquity/{COMMIT}/{item["path"]}')
        git_sha = hashlib.sha1(f'blob {len(body)}\0'.encode()+body).hexdigest()
        if git_sha != item['sha'] and (RUNTIME/'checkout/.git').exists():
            # Windows checkout CRLF conversion is not upstream wire content.
            body = subprocess.check_output(['git', '-C', str(RUNTIME/'checkout'), 'show', COMMIT+':'+item['path']])
            git_sha = hashlib.sha1(f'blob {len(body)}\0'.encode()+body).hexdigest()
        if git_sha != item['sha']:
            raise ValueError('SOURCE_BLOB_MISMATCH:'+item['path'])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        return {'path': item['path'], 'git_blob': git_sha, 'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        files = list(pool.map(download, selected))
    (RUNTIME/'source-manifest.json').write_text(json.dumps({'commit': COMMIT, 'files': files}, indent=2), encoding='utf-8')
    environment = RUNTIME/'.venv'
    python = environment/('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    if not python.exists():
        venv.EnvBuilder(with_pip=True).create(environment)
    # This is an adapter runtime, not the upstream full-market CLI/dashboard.
    # Only the exercised HTTP/Polars/config modules are enabled; do not bring
    # unrelated sentiment, spreadsheets or server dependencies into collection.
    subprocess.run([str(python), '-m', 'pip', 'install', '--disable-pip-version-check', native_wheel()], check=True)
    subprocess.run([str(python), '-m', 'pip', 'install', '--disable-pip-version-check',
                    *[f'{name}=={version}' for name, version in ADAPTER_REQUIREMENTS.items()]], check=True)
    subprocess.run([str(python), '-m', 'pip', 'install', '--no-deps', '--disable-pip-version-check', str(source)], check=True)
    subprocess.run([str(python), '-B', '-X', 'utf8', '-c',
                    'from zoneinfo import ZoneInfo; ZoneInfo("Asia/Shanghai"); '
                    'from cnequity.adapters.eastmoney.bars import fetch_daily_bars; '
                    'from cnequity.adapters.eastmoney.corporate_actions import fetch_corporate_actions_eastmoney; '
                    'from cnequity.adapters.tdx_protocol.quotes import Quotes; '
                    'from cnequity.adapters.cninfo.announcements import _announcement_rows_to_frame'], check=True)
    script = '''import cnequity,hashlib,json;from pathlib import Path;from importlib.metadata import version,distributions
p=Path(cnequity.__file__).parent
print(json.dumps({'version':version('cnequity'),'package_hashes':{f.relative_to(p).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in p.rglob('*.py')},'dependencies':{d.metadata['Name']:d.version for d in distributions()}}))'''
    manifest = json.loads(subprocess.check_output([str(python), '-B', '-X', 'utf8', '-c', script]))
    manifest.update(commit=COMMIT, profile='ROLL_BOUNDED_ADAPTERS_ONLY', source_manifest_sha256=hashlib.sha256((RUNTIME/'source-manifest.json').read_bytes()).hexdigest())
    marker.write_text(json.dumps(manifest, sort_keys=True, indent=2), encoding='utf-8')
    lock = subprocess.check_output([str(python), '-m', 'pip', 'freeze']).decode('utf-8')
    (RUNTIME/'requirements.lock.txt').write_text(lock, encoding='utf-8')
    print(json.dumps({'commit': COMMIT, 'verified_source_files': len(files), 'version': manifest['version'],
                      'runtime': str(RUNTIME)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
