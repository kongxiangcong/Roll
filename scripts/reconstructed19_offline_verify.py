"""Fresh host: external sockets/DNS denied; Windows asyncio loopback IPC allowed."""
import ipaddress,json,runpy,socket,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'.scratch/roll-p0/evidence/19-reconstruction-2026-10-10'
attempts=[]
def local(host):
    if host=='localhost':return True
    try:return ipaddress.ip_address(host).is_loopback
    except ValueError:return False
def denied():
    attempts.append('EXTERNAL_SOCKET_OR_DNS_ATTEMPT');raise RuntimeError('Offline verification forbids external network')
connect=socket.socket.connect;connect_ex=socket.socket.connect_ex;lookup=socket.getaddrinfo
def guarded_connect(sock,address):
    if not isinstance(address,tuple) or not local(address[0]):denied()
    return connect(sock,address)
def guarded_connect_ex(sock,address):
    if not isinstance(address,tuple) or not local(address[0]):denied()
    return connect_ex(sock,address)
def guarded_lookup(host,*args,**kwargs):
    if not local(host):denied()
    return lookup(host,*args,**kwargs)
socket.socket.connect=guarded_connect;socket.socket.connect_ex=guarded_connect_ex;socket.getaddrinfo=guarded_lookup
sys.argv=['reconstructed19_acceptance.py','verify','--final-version']
runpy.run_path(str(ROOT/'scripts/reconstructed19_acceptance.py'),run_name='__main__')
assert not attempts
(OUT/'v4/offline-network-guard.json').write_text(json.dumps({'fresh_process':True,'external_socket_and_dns_blocked_before_app_import':True,'loopback_allowed_for_windows_asyncio_self_pipe':True,'external_attempts':attempts,'network_calls':0,'result':'PASSED'},indent=2)+'\n',encoding='utf-8')
