"""Read-only MCP discovery using the existing local credential; never log it."""
import json
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

config = tomllib.loads(Path('C:/Users/72449/.codex/config.toml').read_text(encoding='utf-8'))
server = config['mcp_servers']['mx-ds-mcp']
url = server['url']
assert url == 'https://mxapi.eastmoney.com/mxds/mcp'
key = server.get('http_headers', {}).get('em_api_key', '')
if not key or key.startswith(('$', '<', '%')):
    print(json.dumps({'credential_configured': False}))
    raise SystemExit(2)

headers = {'Content-Type':'application/json', 'Accept':'application/json, text/event-stream', 'em_api_key': key}

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

opener = urllib.request.build_opener(NoRedirect)

def call(payload):
    req=urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method='POST')
    try:
        with opener.open(req, timeout=25) as response:
            if response.headers.get('Mcp-Session-Id'):
                headers['Mcp-Session-Id']=response.headers['Mcp-Session-Id']
            raw=response.read(1024*1024).decode()
            if not raw.strip(): return {}
            if raw.lstrip().startswith('{'): return json.loads(raw)
            events=[json.loads(line[5:].strip()) for line in raw.splitlines() if line.startswith('data:') and line[5:].strip()]
            return events[-1] if events else {'unparsed':True}
    except urllib.error.HTTPError as exc:
        return {'http_error':exc.code}
    except Exception as exc:
        return {'transport_error':type(exc).__name__}

init=call({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'roll-readonly-research','version':'1.0'}}})
result={'credential_configured':True,'initialize':init}
if 'result' in init:
    headers['MCP-Protocol-Version']=init['result'].get('protocolVersion','2024-11-05')
    call({'jsonrpc':'2.0','method':'notifications/initialized'})
    listing=call({'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}})
    result['tools_list']=listing
safe=json.dumps(result,ensure_ascii=False,indent=2).replace(key,'<REDACTED>')
Path(__file__).with_name('mx-discovery.json').write_text(safe,encoding='utf-8')
summary={'credential_configured':True,'initialize_ok':'result' in init,'server':init.get('result',{}).get('serverInfo'),'error':init.get('http_error') or init.get('transport_error') or init.get('error')}
if 'tools_list' in result:
    summary['tools']=[{'name':t['name'],'description':t.get('description','')[:180],'inputSchema':t.get('inputSchema')} for t in result['tools_list'].get('result',{}).get('tools',[])]
if '--sample' in sys.argv and 'result' in init:
    query='查询江西铜业（600362.SH）截至2026年10月22日最近5个交易日的日线开盘、最高、最低、收盘价和成交量。请注明日期、单位、复权口径；没有的字段明确缺失，不做投资建议。'
    sample=call({'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'mx_ashare_finance_data','arguments':{'query':query}}})
    safe_sample=json.dumps({'query':query,'response':sample},ensure_ascii=False,indent=2).replace(key,'<REDACTED>')
    Path(__file__).with_name('mx-sample.json').write_text(safe_sample,encoding='utf-8')
    print(safe_sample)
else:
    print(json.dumps(summary,ensure_ascii=False,indent=2).replace(key,'<REDACTED>'))
