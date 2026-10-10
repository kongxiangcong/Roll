"""Opt-in fixed provider HTTP replies; the production Agents SDK and Job worker run unchanged."""
from contextlib import asynccontextmanager
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import time

import httpx
from roll.app import create_app


def factory():
    if os.environ.get('ROLL_ENV')!='test':raise RuntimeError('METHOD_FACTORY_TEST_ONLY')
    if os.environ.get('DEEPSEEK_API_KEY') not in {None,'ROLL_METHOD_CASE_ONLY'}:
        raise RuntimeError('METHOD_FACTORY_REFUSES_REAL_CREDENTIAL')
    os.environ['DEEPSEEK_API_KEY']='ROLL_METHOD_CASE_ONLY'
    os.environ.pop('ROLL_DEEPSEEK_API_KEY_FILE',None)
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['content-length'])))
            inputs=body['input'];results=[json.loads(v['output']) for v in inputs if v.get('type')=='function_call_output']
            if 'WAIT_METHOD' in str(inputs):time.sleep(60)
            if not results:
                items=[{'type':'function_call','id':'fc_quote','call_id':'call_quote','name':'roll_read_evidence',
                    'arguments':json.dumps({'instrument':'SSE:600519','group':'QUOTE'}),'status':'completed'}]
            elif len(results)==1:
                items=[{'type':'function_call','id':'fc_source','call_id':'call_source','name':'roll_read_source',
                    'arguments':json.dumps({'instrument':'SSE:600519','source_id':'MOUTAI_OFFICIAL'}),'status':'completed'}]
            else:
                candidate={'instrument':'SSE:600519','group':'QUOTE','raw_hash':results[-1]['archive']['sha256'],
                    'assertion':'方法案例官网材料','evidence_quote':'贵州茅台公开材料 METHOD_CASE','time_basis':'UNKNOWN'}
                items=[{'type':'message','id':'msg_method','role':'assistant','status':'completed','content':[
                    {'type':'output_text','text':json.dumps({'candidates':[candidate],'gaps':['来源事项时间未知']}),'annotations':[]}]}]
            response={'id':'resp_method_'+str(time.time_ns()),'object':'response','created_at':1791398400,
                'model':'deepseek-flash','status':'completed','output':items,'parallel_tool_calls':True,
                'tool_choice':'auto','tools':[],'usage':{'input_tokens':200,'output_tokens':50,'total_tokens':250},
                'error':None,'incomplete_details':None}
            raw=json.dumps(response).encode()
            try:
                self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)))
                self.end_headers();self.wfile.write(raw)
            except (BrokenPipeError,ConnectionResetError):pass
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    server.daemon_threads=True
    threading.Thread(target=server.serve_forever,daemon=True).start()
    def source(request):
        if request.url.host=='hq.sinajs.cn':return httpx.Response(200,content=b'var hq_str_sh600519="";')
        return httpx.Response(200,text='<p>贵州茅台公开材料 METHOD_CASE</p>',headers={'content-type':'text/html'})
    app=create_app(market_transport=httpx.MockTransport(source),deepseek_endpoint='http://127.0.0.1:'+str(server.server_port))
    location=os.environ.get('ROLL_DEEPSEEK_METHOD_LOCATION_FILE')
    if location:
        Path(location).write_text(json.dumps({'data_dir':str(app.state.evidence.directory),
            'evidence_kind':'METHOD_CASE_DEEPSEEK','created_at_utc':datetime.now(timezone.utc).isoformat()}),encoding='utf-8')
    lifespan=app.router.lifespan_context
    @asynccontextmanager
    async def managed(application):
        try:
            async with lifespan(application):yield
        finally:server.shutdown();server.server_close()
    app.router.lifespan_context=managed
    return app
