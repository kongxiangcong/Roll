"""Bounded, pinned model acquisition. No Hugging Face auto-downloads/retries."""
import hashlib
import json
import time
import sys
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urljoin
import requests

out = Path(__file__).resolve().parent
plan_path = out / (sys.argv[1] if len(sys.argv) > 1 else 'download-plan.json')
plan = json.loads(plan_path.read_bytes())
stem = plan_path.name.removesuffix('-plan.json')
repo = Path(__file__).resolve().parents[5]
destination = repo / plan['destination']
assert (repo / 'backend').is_dir(), repo
destination.mkdir(parents=True, exist_ok=False)
receipt_path = out / f'{stem}-receipt.json'
assert not receipt_path.exists()
started = time.monotonic()
receipt = {'attempt_id': plan['attempt_id'], 'started_at': datetime.now(timezone.utc).isoformat(), 'requests': [], 'artifacts': [], 'bytes': 0, 'status': 'FAILED'}
session = requests.Session()
session.headers['User-Agent'] = 'Roll-model-evaluation/1.0'


def fetch(url, target, offset=0):
    for redirect in range(plan['limits']['maximum_redirects_per_file'] + 1):
        remaining = plan['limits']['maximum_seconds'] - (time.monotonic() - started)
        if remaining <= 0 or len(receipt['requests']) >= plan['limits']['maximum_requests']:
            raise RuntimeError('REQUEST_OR_TIME_BUDGET')
        host = urlsplit(url).hostname
        if (host not in plan['allowed_hosts'] and not any(host.endswith('.'+suffix) for suffix in plan.get('allowed_host_suffixes', []))) or urlsplit(url).scheme != 'https':
            raise RuntimeError('UNAPPROVED_HOST')
        item = {'host': host, 'artifact': target.name, 'bytes': 0}
        receipt['requests'].append(item)
        headers = {'Range': f'bytes={offset}-'} if offset else {}
        with session.get(url, headers=headers, stream=True, timeout=(min(10, remaining), min(15, remaining)), allow_redirects=False) as response:
            item['status'] = response.status_code
            if response.is_redirect:
                if redirect == plan['limits']['maximum_redirects_per_file']:
                    raise RuntimeError('REDIRECT_BUDGET')
                url = urljoin(url, response.headers['Location'])
                continue
            response.raise_for_status()
            if offset and (response.status_code != 206 or not response.headers.get('Content-Range','').startswith(f'bytes {offset}-')):
                raise RuntimeError('RANGE_NOT_HONORED')
            digest = hashlib.sha256()
            if offset:
                with target.open('rb') as prefix:
                    for chunk in iter(lambda:prefix.read(1024*1024),b''):
                        digest.update(chunk)
            with target.open('ab' if offset else 'xb') as stream:
                for chunk in response.iter_content(65536):
                    receipt['bytes'] += len(chunk)
                    item['bytes'] += len(chunk)
                    if receipt['bytes'] > plan['limits']['maximum_bytes'] or time.monotonic() - started > plan['limits']['maximum_seconds']:
                        raise RuntimeError('BYTE_OR_TIME_BUDGET')
                    stream.write(chunk)
                    digest.update(chunk)
            return digest.hexdigest(), offset + item['bytes']
    raise RuntimeError('NO_RESPONSE')


try:
    metadata_path = out / f'{stem}-pinned-model-metadata.raw'
    fetch(f"https://huggingface.co/api/models/{plan['model']}/revision/{plan['revision']}?blobs=true", metadata_path)
    metadata = json.loads(metadata_path.read_bytes())
    if metadata['sha'] != plan['revision']:
        raise RuntimeError('REVISION_MISMATCH')
    siblings = {item['rfilename']: item for item in metadata['siblings']}
    for name in plan['files']:
        target = destination / name
        offset = 0
        if name in plan.get('resume', {}):
            resume = plan['resume'][name]
            prefix = repo / resume['path']
            assert hashlib.sha256(prefix.read_bytes()).hexdigest() == resume['sha256']
            assert prefix.stat().st_size == resume['bytes']
            shutil.copyfile(prefix,target)
            offset = resume['bytes']
        digest, size = fetch(f"https://huggingface.co/{plan['model']}/resolve/{plan['revision']}/{name}?download=true", target, offset)
        expected = siblings[name]
        lfs = expected.get('lfs', {})
        if lfs.get('sha256') and digest != lfs['sha256']:
            raise RuntimeError('WEIGHT_SHA256_MISMATCH')
        if expected.get('size') is not None and size != expected['size']:
            raise RuntimeError('ARTIFACT_SIZE_MISMATCH')
        receipt['artifacts'].append({'path': name, 'bytes': size, 'sha256': digest, 'lfs_sha256_verified': bool(lfs.get('sha256'))})
    receipt['status'] = 'DOWNLOADED_VERIFIED'
except Exception as error:
    receipt['error_type'] = type(error).__name__
    if isinstance(error, RuntimeError):
        receipt['error_code'] = str(error)
finally:
    session.close()
    receipt.update(elapsed_seconds=round(time.monotonic()-started, 3), closed=True, retries=0)
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
