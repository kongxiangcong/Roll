"""Trace and cap the third isolated Trafilatura dependency attempt (explicit machine proxy)."""
import json, os, socket, sys, time
from pathlib import Path
from urllib.parse import urlsplit
from pip._vendor.requests.sessions import Session

trace_path = Path(__file__).with_name('dependency-attempt03-network.jsonl')
started = time.monotonic()
requests = 0
received = 0
proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('HTTP_PROXY') or ''
if proxy != 'http://127.0.0.1:7890':
    raise SystemExit('EXPECTED_MACHINE_PROXY_NOT_PRESENT')

original_send = Session.send

def send(self, request, **kwargs):
    global requests, received
    parsed = urlsplit(request.url)
    if parsed.scheme != 'https' or parsed.hostname not in {'pypi.org', 'files.pythonhosted.org'} \
            or parsed.username or parsed.port not in (None, 443) or request.method not in ('GET', 'HEAD'):
        raise RuntimeError('DEPENDENCY_TRANSPORT_TARGET_REJECTED')
    requests += 1
    if requests > 128 or time.monotonic() - started > 600:
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
            'bytes': len(response.content) if request.method == 'GET' else 0,
            'proxy': bool(self.proxies.get('https')),
        }) + '\n')
    if response.status_code >= 300:
        raise RuntimeError('DEPENDENCY_TRANSPORT_REDIRECT_OR_ERROR')
    if request.method == 'GET':
        received += len(response.content)
        if received > 104857600:
            raise RuntimeError('DEPENDENCY_TRANSPORT_BYTE_BUDGET')
    return response

Session.send = send
sys.argv = ['pip', *sys.argv[1:]]
import runpy
runpy.run_module('pip', run_name='__main__')
