"""Bounded supplier MCP client; exact responses are archived by the host callback."""
import json
import os
import time
import tomllib
from pathlib import Path

import httpx

URL = 'https://mxapi.eastmoney.com/mxds/mcp'
TOOLS = {'mx_ashare_finance_data', 'mx_index_block_finance_data', 'mx_finance_search_news',
         'mx_finance_search_notice', 'mx_macro_data', 'mx_comprehensive_finance_data'}


def credential():
    key = os.environ.get('EM_API_KEY')
    if not key and os.environ.get('ROLL_MX_CONFIG_FILE'):
        try:
            config = tomllib.loads(Path(os.environ['ROLL_MX_CONFIG_FILE']).read_text(encoding='utf-8-sig'))
            server = config['mcp_servers']['mx-ds-mcp']
            if server['url'] != URL:
                raise ValueError('MX_ENDPOINT_NOT_ALLOWED')
            key = server.get('http_headers', {}).get('em_api_key')
        except (OSError, KeyError, tomllib.TOMLDecodeError):
            raise ValueError('MX_CONFIG_INVALID') from None
    if not isinstance(key, str) or not key.strip():
        raise ValueError('MX_CREDENTIAL_UNAVAILABLE')
    return key.strip()


def failure(value):
    text = json.dumps(value, ensure_ascii=False).lower()
    if any(word in text for word in ['积分不足', '积分耗尽', '额度不足', '余额不足', 'quota', 'insufficient credit']):
        return 'MX_QUOTA_EXHAUSTED'
    if any(word in text for word in ['限流', '频率', 'rate limit', 'too many requests']):
        return 'MX_RATE_LIMITED'
    return 'MX_REMOTE_ERROR'


def query(tool, question, *, transport=None, deadline=None, cancel_event=None,
          max_calls=3, max_bytes=2*1024*1024, on_response=None, on_bytes=None):
    if tool not in TOOLS:
        raise ValueError('MX_TOOL_NOT_ALLOWED')
    key = credential()
    deadline = deadline if deadline is not None else time.monotonic()+45
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream', 'em_api_key': key}
    calls = size = 0
    with httpx.Client(transport=transport, follow_redirects=False) as client:
        def call(payload):
            nonlocal calls, size
            if calls >= max_calls or time.monotonic() >= deadline or (cancel_event and cancel_event.is_set()):
                raise ValueError('MX_TECHNICAL_LIMIT')
            calls += 1
            try:
                with client.stream('POST', URL, json=payload, headers=headers,
                                   timeout=min(10, max(.1, deadline-time.monotonic()))) as response:
                    if session := response.headers.get('Mcp-Session-Id'):
                        headers['Mcp-Session-Id'] = session
                    raw = bytearray()
                    for chunk in response.iter_bytes(4096):
                        size += len(chunk)
                        if on_bytes:on_bytes(len(chunk))
                        if size > max_bytes or time.monotonic() >= deadline or (cancel_event and cancel_event.is_set()):
                            raise ValueError('MX_TECHNICAL_LIMIT')
                        raw.extend(chunk)
                    text = raw.decode('utf-8')
                    if key in text:
                        raise ValueError('MX_SECRET_REFLECTED_RESPONSE_REJECTED')
                    if text.lstrip().startswith('{'):
                        result = json.loads(text)
                    elif text.strip():
                        messages = [json.loads(line[5:]) for line in text.splitlines() if line.startswith('data:')]
                        result = messages[-1] if messages else {}
                    else:
                        result = {}
                    if not isinstance(result,dict):
                        raise ValueError('MX_RESPONSE_INVALID')
                    if key in json.dumps(result, ensure_ascii=False):
                        raise ValueError('MX_SECRET_REFLECTED_RESPONSE_REJECTED')
                    if on_response:
                        on_response(bytes(raw), response.status_code, payload['method'])
                    if response.status_code in {401, 403}:
                        raise ValueError('MX_AUTH_FAILED')
                    if response.status_code == 429:
                        raise ValueError('MX_RATE_LIMITED')
                    response.raise_for_status()
                    inner=result.get('result')
                    if inner is not None and not isinstance(inner,dict):
                        raise ValueError('MX_RESPONSE_INVALID')
                    if 'error' in result or (inner or {}).get('isError'):
                        raise ValueError(failure(result))
                    return result
            except httpx.HTTPError:
                raise ValueError('MX_REQUEST_FAILED') from None
            except (UnicodeError, json.JSONDecodeError):
                raise ValueError('MX_RESPONSE_INVALID') from None

        init = call({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
            'protocolVersion': '2024-11-05', 'capabilities': {}, 'clientInfo': {'name': 'roll-data', 'version': '1'}}})
        try:
            headers['MCP-Protocol-Version'] = init['result']['protocolVersion']
        except (KeyError, TypeError):
            raise ValueError('MX_INITIALIZE_INVALID') from None
        call({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        result = call({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {
            'name': tool, 'arguments': {'query': question}}}).get('result', {})
        if not isinstance(result,dict) or not isinstance(result.get('content',[]),list):
            raise ValueError('MX_RESPONSE_INVALID')
        has_data = False
        for block in result.get('content', []):
            if not isinstance(block,dict) or block.get('type') != 'text':
                continue
            try:
                value = json.loads(block['text'])
            except (ValueError, TypeError):
                continue
            if isinstance(value, dict) and value.get('message') and not value.get('data'):
                raise ValueError(failure(value))
            if isinstance(value, dict) and value.get('data'):
                has_data = True
        if not has_data:
            code=failure(result)
            raise ValueError(code if code!='MX_REMOTE_ERROR' else 'MX_NO_STRUCTURED_DATA')
        return result
