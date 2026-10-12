"""Actual uvicorn acceptance host with outbound non-loopback socket/DNS denial."""
import ipaddress,json,os,socket
from pathlib import Path
guard=Path(os.environ['ROLL_OFFLINE_GUARD_FILE']);attempts=[]
def write_guard():guard.write_text(json.dumps({'non_loopback_connections_and_dns_blocked':True,'external_attempts':attempts},indent=2),encoding='utf-8')
def local(host):
    if host in {'localhost','127.0.0.1','::1'}:return True
    try:return ipaddress.ip_address(host).is_loopback
    except ValueError:return False
def deny(host):
    attempts.append('NON_LOOPBACK_ATTEMPT');write_guard();raise RuntimeError('Offline acceptance host forbids external network')
connect=socket.socket.connect;connect_ex=socket.socket.connect_ex;lookup=socket.getaddrinfo
def guarded_connect(sock,address):
    if not isinstance(address,tuple) or not local(address[0]):deny('redacted')
    return connect(sock,address)
def guarded_connect_ex(sock,address):
    if not isinstance(address,tuple) or not local(address[0]):deny('redacted')
    return connect_ex(sock,address)
def guarded_lookup(host,*args,**kwargs):
    if not local(host):deny('redacted')
    return lookup(host,*args,**kwargs)
socket.socket.connect=guarded_connect;socket.socket.connect_ex=guarded_connect_ex;socket.getaddrinfo=guarded_lookup;write_guard()
import uvicorn
from roll.app import create_app
uvicorn.run(create_app(),host='127.0.0.1',port=int(os.environ['ROLL_TEST_API_PORT']),log_level='warning')
