"""Bounded official MCP client. Credentials never enter receipts or error messages."""
import json
import os
import tomllib
import urllib.request
from pathlib import Path

URL = 'https://mxapi.eastmoney.com/mxds/mcp'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def query(tool, question):
    if tool not in {'mx_ashare_finance_data', 'mx_index_block_finance_data'}:
        raise ValueError('MX_TOOL_NOT_ALLOWED')
    key = os.environ.get('EM_API_KEY')
    if not key and os.environ.get('ROLL_MX_CONFIG_FILE'):
        config = tomllib.loads(Path(os.environ['ROLL_MX_CONFIG_FILE']).read_text(encoding='utf-8'))
        server = config['mcp_servers']['mx-ds-mcp']
        if server['url'] != URL:
            raise ValueError('MX_ENDPOINT_NOT_ALLOWED')
        key = server.get('http_headers', {}).get('em_api_key')
    if not key:
        raise ValueError('MX_CREDENTIAL_UNAVAILABLE')
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream', 'em_api_key': key}
    opener = urllib.request.build_opener(NoRedirect)

    def call(payload):
        try:
            req = urllib.request.Request(URL, data=json.dumps(payload).encode(), headers=headers)
            with opener.open(req, timeout=45) as response:
                if session := response.headers.get('Mcp-Session-Id'):
                    headers['Mcp-Session-Id'] = session
                raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise ValueError('MX_RESPONSE_TOO_LARGE')
            raw = raw.decode().replace(key, '<REDACTED>')
            if not raw.strip():
                return {}
            if raw.lstrip().startswith('{'):
                result = json.loads(raw)
            else:
                result = [json.loads(line[5:]) for line in raw.splitlines() if line.startswith('data:')][-1]
            if 'error' in result or result.get('result', {}).get('isError'):
                raise ValueError('MX_REMOTE_ERROR')
            return result
        except Exception as exc:
            raise ValueError('MX_REQUEST_FAILED') from None

    init = call({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
        'protocolVersion': '2024-11-05', 'capabilities': {}, 'clientInfo': {'name': 'roll-assistance', 'version': '1'}}})
    headers['MCP-Protocol-Version'] = init['result']['protocolVersion']
    call({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
    result = call({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {
        'name': tool, 'arguments': {'query': question}}})['result']
    for block in result.get('content', []):
        if block.get('type') == 'text':
            try:
                value = json.loads(block['text'])
            except ValueError:
                continue
            if isinstance(value, dict) and value.get('message') and not value.get('data'):
                raise ValueError('MX_BUSINESS_MESSAGE_NO_DATA')
    return result
