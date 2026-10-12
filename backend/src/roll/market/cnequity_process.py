"""Isolated CNEquity adapters. Only fixed public routes; bounded calls/bytes/time."""
import base64
import contextlib
from datetime import date, datetime, timedelta, timezone
import hashlib
from importlib.metadata import version, distributions
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

COMMIT = 'c118038ea82b5bb78783c0c17a1d9251b36de71d'


def clock():
    return datetime.now(timezone.utc).isoformat()


def verify_runtime(manifest):
    import cnequity
    package = Path(cnequity.__file__).parent
    actual = {p.relative_to(package).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in package.rglob('*.py')}
    dependencies = {d.metadata['Name']: d.version for d in distributions()}
    if manifest['commit'] != COMMIT or actual != manifest['package_hashes'] or version('cnequity') != manifest['version'] or dependencies != manifest['dependencies']:
        raise ValueError('RUNTIME_SOURCE_FINGERPRINT_MISMATCH')
    return {'commit': COMMIT, 'version': version('cnequity'), 'package_manifest_sha256':
            hashlib.sha256(json.dumps(actual, sort_keys=True).encode()).hexdigest(),
            'dependencies': dependencies, 'profile': manifest.get('profile')}


def run(command, state):
    provenance = verify_runtime(command['runtime_manifest'])
    import httpx
    source_id, symbol = command['source_id'], command['symbol']
    if symbol != '600362.SH' or source_id not in {'cnequity-tdx-daily', 'cnequity-eastmoney-daily',
        'cnequity-eastmoney-status', 'cnequity-eastmoney-actions', 'cnequity-cninfo-announcements'}:
        raise ValueError('UNAPPROVED_COLLECTION_SCOPE')
    start, end = date.fromisoformat(command['start_date']), date.fromisoformat(command['end_date'])
    if not 0 <= (end-start).days <= 45:
        raise ValueError('UNAPPROVED_COLLECTION_WINDOW')
    deadline = time.monotonic()+command['timeout_seconds']

    def budget(size=0, call=False):
        if call:
            state['calls'] += 1
        state['bytes'] += size
        if state['calls'] > command['max_calls'] or state['bytes'] > command['max_bytes'] or time.monotonic() > deadline:
            raise ValueError('SOURCE_CALL_BYTE_OR_TIME_LIMIT')

    class CapturingClient:
        # Upstream adapter pagination sees a one-attempt policy. Captures are owned by Roll.
        config = SimpleNamespace(max_retries=1, retry_backoff_seconds=0)
        def __init__(self):
            self.inner = httpx.Client(follow_redirects=False, headers={
                'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.cninfo.com.cn/'})
        def request(self, method, url, *, params=None, data=None, **ignored):
            parsed = httpx.URL(url)
            routes = {
                'cnequity-eastmoney-daily': {('push2his.eastmoney.com', '/api/qt/stock/kline/get')},
                'cnequity-eastmoney-status': {('push2.eastmoney.com', '/api/qt/clist/get'),
                    ('push2delay.eastmoney.com', '/api/qt/clist/get'), ('datapc.eastmoney.com', '/emdatacenter/tfg/list2')},
                'cnequity-eastmoney-actions': {('datacenter-web.eastmoney.com', '/api/data/v1/get')},
                'cnequity-cninfo-announcements': {('www.cninfo.com.cn', '/new/information/topSearch/detailOfQuery'),
                    ('www.cninfo.com.cn', '/new/hisAnnouncement/query')},
            }
            if (parsed.host, parsed.path) not in routes.get(source_id, set()) or parsed.scheme not in {'http', 'https'}:
                raise ValueError('UNAPPROVED_SOURCE_ROUTE')
            if parsed.username or parsed.password:
                raise ValueError('SOURCE_URL_CREDENTIALS_FORBIDDEN')
            # Keep the corporate-action query restricted to the single authorized security.
            if source_id == 'cnequity-eastmoney-actions':
                query = dict(parsed.params)
                query['filter'] = query.get('filter', '')+'(SECURITY_CODE="600362")'
                url = str(parsed.copy_with(query=str(httpx.QueryParams(query)).encode()))
            budget(call=True)
            with self.inner.stream(method, url, params=params, data=data,
                    timeout=max(.1, min(5, deadline-time.monotonic()))) as response:
                body = bytearray()
                for chunk in response.iter_bytes(4096):
                    budget(len(chunk)); body.extend(chunk)
                state['captures'].append({'kind': 'RAW_RESPONSE', 'url': str(response.url),
                    'parameters': params if params is not None else data, 'http_status': response.status_code,
                    'received_at': clock(), 'body_b64': base64.b64encode(body).decode(),
                    'wire_semantics': 'HTTP_ENTITY_BYTES_BEFORE_JSON_OR_DATASET_NORMALIZATION'})
                headers = {k: v for k, v in response.headers.items() if k.lower() not in {'content-encoding', 'content-length'}}
                return httpx.Response(response.status_code, headers=headers, content=bytes(body), request=response.request)
        def get(self, url, **kwargs):
            return self.request('GET', url, **kwargs)
        def post(self, url, **kwargs):
            return self.request('POST', url, **kwargs)
        def close(self):
            self.inner.close()

    if source_id == 'cnequity-tdx-daily':
        import socket
        import zlib
        original_socket = socket.socket
        query_wire = bytearray()
        active = {'capture': False, 'peer': None, 'decoded': 0}
        # Public server allowlist belongs to the pinned upstream, not to request text.
        from cnequity.adapters.tdx_protocol.hosts import VERIFIED_HOSTS
        class BoundedSocket(original_socket):
            def connect(self, address):
                if address not in VERIFIED_HOSTS[:2]:
                    raise ValueError('UNAPPROVED_TDX_SERVER')
                budget(call=True)
                self.settimeout(max(.1, min(2, deadline-time.monotonic())))
                active['peer'] = address
                return super().connect(address)
            def send(self, value, *args, **kwargs):
                budget(call=True)
                return super().send(value, *args, **kwargs)
            def sendall(self, value, *args, **kwargs):
                budget(call=True)
                return super().sendall(value, *args, **kwargs)
            def recv(self, size, *args, **kwargs):
                value = super().recv(size, *args, **kwargs)
                budget(len(value))
                if active['capture']:
                    query_wire.extend(value)
                return value
        socket.socket = BoundedSocket
        def decompress(value, *args, **kwargs):
            remaining = command['max_bytes']-active['decoded']
            decoder = zlib.decompressobj()
            result = decoder.decompress(value, remaining+1)
            active['decoded'] += len(result)
            if len(result) > remaining or decoder.unconsumed_tail:
                raise ValueError('TDX_DECODED_BYTE_LIMIT')
            return result
        zlib.decompress = decompress
        from cnequity.adapters.tdx_protocol.quotes import Quotes
        from cnequity.adapters.tdx_protocol.bars import fetch_bars_paginated
        last_error, rows = None, []
        for peer in VERIFIED_HOSTS[:2]:
            client = None
            try:
                active['capture'] = False
                client = Quotes.factory(server=peer, timeout=2, heartbeat=False)
                if client._client.client is None:
                    raise ValueError('TDX_CONNECT_OR_SETUP_FAILED')
                client._client.raise_exception = True
                active['capture'] = True
                rows = fetch_bars_paginated(client, symbol, start, end, backfill=False)
                break
            except Exception as error:
                last_error = error
            finally:
                if client:
                    client.close()
                if query_wire:
                    state['captures'].append({'kind': 'RAW_SOCKET_RESPONSE', 'url': f'tcp://{peer[0]}:{peer[1]}',
                        'parameters': {'symbol': symbol, 'frequency': 9, 'start_date': str(start), 'end_date': str(end)},
                        'body_b64': base64.b64encode(query_wire).decode(),
                        'wire_semantics': 'TDX_QUERY_RECV_BYTES_SETUP_EXCLUDED'})
                    query_wire.clear()
        if not rows and last_error:
            raise last_error
    else:
        client = CapturingClient()
        try:
            if source_id == 'cnequity-eastmoney-daily':
                from cnequity.adapters.eastmoney.bars import fetch_daily_bars
                diagnostics = {}
                frame = fetch_daily_bars([symbol], start, end, client=client, diagnostics=diagnostics)
                if diagnostics.get('failed_symbols'):
                    raise ValueError('EASTMONEY_DAILY_SOURCE_FAILED')
            elif source_id == 'cnequity-eastmoney-status':
                from cnequity.adapters.eastmoney.trading_status import fetch_trading_status_eastmoney
                frame = fetch_trading_status_eastmoney([symbol], end, client=client)
            elif source_id == 'cnequity-eastmoney-actions':
                from cnequity.adapters.eastmoney.corporate_actions import fetch_corporate_actions_eastmoney
                frame = fetch_corporate_actions_eastmoney(end, dates=[start+timedelta(days=n) for n in range((end-start).days+1)],
                    client=client, config=SimpleNamespace(max_retries=1, retry_backoff_seconds=0))
            else:
                from cnequity.adapters.cninfo.announcements import _announcement_rows_to_frame
                lookup = client.post('https://www.cninfo.com.cn/new/information/topSearch/detailOfQuery',
                    data={'keyWord': '600362', 'maxNum': 10})
                lookup.raise_for_status()
                companies = lookup.json()
                match = next((r for r in companies if r.get('code') == '600362' and r.get('orgId')), None)
                if not match:
                    raise ValueError('CNINFO_ISSUER_ID_NOT_VERIFIED')
                notices = []
                page = 1
                while True:
                    response = client.post('https://www.cninfo.com.cn/new/hisAnnouncement/query', data={
                        'stock': '600362,'+str(match['orgId']), 'tabName': 'fulltext', 'pageSize': 30,
                        'pageNum': page, 'column': 'sse', 'plate': 'sh', 'seDate': f'{start}~{end}',
                        'searchkey': '', 'category': '', 'trade': '', 'sortName': '', 'sortType': '', 'isHLtitle': 'true'})
                    response.raise_for_status()
                    result = response.json()
                    batch = result.get('announcements')
                    if batch is None and result.get('totalAnnouncement') == 0:
                        batch = []
                    if not isinstance(batch, list) or any(r.get('secCode') != '600362' for r in batch):
                        raise ValueError('CNINFO_QUERY_SCOPE_OR_SCHEMA_MISMATCH')
                    notices.extend(batch)
                    if not result.get('hasMore'):
                        break
                    if not batch:
                        raise ValueError('CNINFO_INCOMPLETE_PAGINATION')
                    page += 1
                frame = _announcement_rows_to_frame(notices, start=start, end=end)
            rows = frame.to_dicts()
        finally:
            client.close()
    return {'commit': COMMIT, 'source_id': source_id, 'rows': rows, 'captures': state['captures'],
            'calls': state['calls'], 'received_bytes': state['bytes'], 'runtime_provenance': provenance}


if __name__ == '__main__':
    # This directory contains Roll's cnequity.py bridge; it is not the SDK.
    sys.path = [p for p in sys.path if Path(p or '.').resolve() != Path(__file__).resolve().parent]
    command = json.load(sys.stdin)
    state = {'calls': 0, 'bytes': 0, 'captures': []}
    try:
        with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            result = run(command, state)
    except Exception as error:
        result = {'commit': COMMIT, 'source_id': command.get('source_id'), 'rows': [],
                  'captures': state['captures'], 'calls': state['calls'], 'received_bytes': state['bytes'],
                  'error_code': str(error) if isinstance(error, ValueError) else 'SOURCE_FAILED_'+type(error).__name__}
    rendered = json.dumps(result, ensure_ascii=False, default=str, allow_nan=False).encode('utf-8')
    if len(rendered) > 24*1024*1024:
        rendered = json.dumps({'commit': COMMIT, 'source_id': command.get('source_id'), 'error_code': 'OUTPUT_BYTE_LIMIT'}).encode()
    sys.stdout.buffer.write(rendered)
