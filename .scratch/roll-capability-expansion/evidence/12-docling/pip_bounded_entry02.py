"""Trace and cap the second isolated Docling dependency attempt (explicit machine proxy)."""
import atexit, json, os, sys, time
from pathlib import Path
from urllib.parse import urlsplit
from pip._vendor.requests.sessions import Session

trace_path = Path(__file__).with_name('dependency-attempt02-network.jsonl')
summary_path = Path(__file__).with_name('dependency-attempt02-receipt.json')
started = time.monotonic()
requests = 0
received = 0
MAX_REQUESTS = 512
MAX_BYTES = 1610612736
MAX_SECONDS = 1800

original_send = Session.send

def send(self, request, **kwargs):
    global requests, received
    parsed = urlsplit(request.url)
    if parsed.scheme != 'https' or parsed.hostname not in {'pypi.org', 'files.pythonhosted.org'} \
            or parsed.username or parsed.port not in (None, 443) or request.method not in ('GET', 'HEAD'):
        raise RuntimeError('DEPENDENCY_TRANSPORT_TARGET_REJECTED')
    requests += 1
    if requests > MAX_REQUESTS or time.monotonic() - started > MAX_SECONDS:
        raise RuntimeError('DEPENDENCY_TRANSPORT_BUDGET')
    before = time.monotonic()
    kwargs['allow_redirects'] = False
    response = original_send(self, request, **kwargs)
    with trace_path.open('a', encoding='utf-8') as file:
        file.write(json.dumps({
            'ordinal': requests,
            'host': parsed.hostname,
            'path': parsed.path,
            'status': response.status_code,
            'header_seconds': round(time.monotonic() - before, 3),
        }) + '\n')
    if response.status_code >= 300:
        raise RuntimeError('DEPENDENCY_TRANSPORT_REDIRECT_OR_ERROR')
    if request.method == 'GET':
        content = response.__dict__.get('_content', False)
        if isinstance(content, bytes):
            received += len(content)
        elif hasattr(response.raw, 'stream'):
            original_stream = response.raw.stream
            def stream(*args, **kwargs2):
                global received
                for part in original_stream(*args, **kwargs2):
                    received += len(part)
                    if received > MAX_BYTES or time.monotonic() - started > MAX_SECONDS:
                        raise RuntimeError('DEPENDENCY_TRANSPORT_BYTE_OR_TIME_BUDGET')
                    yield part
            response.raw.stream = stream
    return response

Session.send = send
sys.argv = ['pip', *sys.argv[1:]]
import runpy

def finish():
    summary_path.write_text(json.dumps({
        'attempt_id': 'DOCLING-DEP-ATTEMPT-02',
        'status': 'FINISHED',
        'requests': requests,
        'bytes': received,
        'elapsed_seconds': round(time.monotonic() - started, 3),
        'proxy_env': os.environ.get('HTTPS_PROXY'),
    }, indent=2), encoding='utf-8')

atexit.register(finish)
runpy.run_module('pip', run_name='__main__')
