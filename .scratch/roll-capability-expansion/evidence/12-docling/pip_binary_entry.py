"""Constrain and trace only the isolated dependency bootstrap's anonymous HTTPS."""
import json,runpy,socket,sys,time
from pathlib import Path
from urllib.parse import urlsplit
from pip._vendor.requests.sessions import Session
from pip._vendor.urllib3.util import connection
connection.allowed_gai_family=lambda:socket.AF_INET
original_init=Session.__init__;original_send=Session.send
started=time.monotonic();requests=0;received=0;trace=Path(__file__).with_name('pip-bounded-network.jsonl')
def initialize(self,*args,**kwargs):original_init(self,*args,**kwargs);self.trust_env=False
Session.__init__=initialize
def send(self,request,**kwargs):
 global requests,received
 parsed=urlsplit(request.url)
 if parsed.scheme!='https' or parsed.hostname not in {'pypi.org','files.pythonhosted.org'} or parsed.username or parsed.port not in (None,443) or request.method not in ('GET','HEAD'):raise RuntimeError('DEPENDENCY_TRANSPORT_TARGET_REJECTED')
 requests+=1
 if requests>256 or time.monotonic()-started>600:raise RuntimeError('DEPENDENCY_TRANSPORT_BUDGET')
 before=time.monotonic();kwargs['allow_redirects']=False;response=original_send(self,request,**kwargs)
 with trace.open('a',encoding='utf-8') as file:file.write(json.dumps({'ordinal':requests,'host':parsed.hostname,'path':parsed.path,'status':response.status_code,'header_seconds':time.monotonic()-before})+'\n')
 if isinstance(response._content,bytes):received+=len(response._content)
 else:
  original_stream=response.raw.stream
  def stream(*args,**kwargs):
   global received
   for part in original_stream(*args,**kwargs):
    received+=len(part)
    if received>1536*1024**2 or time.monotonic()-started>600:raise RuntimeError('DEPENDENCY_TRANSPORT_BYTE_OR_TIME_BUDGET')
    yield part
  response.raw.stream=stream
 return response
Session.send=send
sys.argv=['pip',*sys.argv[1:]]
runpy.run_module('pip',run_name='__main__')
