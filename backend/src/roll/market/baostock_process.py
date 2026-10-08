"""Single bounded SDK process. Credentials/login frames never enter output authority."""
import base64
import contextlib
from datetime import datetime, timezone
import json
from importlib.metadata import version
import os
import socket
import sys
import time
import zlib


def main(command):
    import baostock as bs
    import baostock.common.context as context
    from baostock.common import contants as constants
    auth_mode=command['auth_mode']
    key=os.environ.get('BAOSTOCK_API_KEY') if auth_mode=='API_KEY' else None
    host='vip-api.baostock.com' if auth_mode=='API_KEY' else 'public-api.baostock.com'
    deadline=time.monotonic()+command['timeout_seconds']
    state={'calls':0,'received_bytes':0,'query_wire':bytearray(),'capture':False,'failure':None}
    original=socket.socket
    class BoundedSocket(original):
        def connect(self,address):
            if address!=(host,10030):raise ValueError('BAOSTOCK_UNAPPROVED_HOST')
            self.settimeout(max(.1,min(5,deadline-time.monotonic())))
            return super().connect(address)
        def send(self,value,*args,**kwargs):
            if time.monotonic()>=deadline or state['calls']>=command['max_calls']:
                state['failure']='CALL_OR_TIME_LIMIT';raise ValueError('BAOSTOCK_CALL_OR_TIME_LIMIT')
            state['calls']+=1
            # SDK sends small protocol commands; require all bytes actually sent.
            super().sendall(value,*args,**kwargs)
            return len(value)
        def recv(self,size,*args,**kwargs):
            if time.monotonic()>=deadline:raise ValueError('BAOSTOCK_DEADLINE')
            value=super().recv(size,*args,**kwargs)
            if not value:raise ValueError('BAOSTOCK_EOF')
            state['received_bytes']+=len(value)
            if state['received_bytes']>command['max_bytes']:
                state['failure']='BYTE_LIMIT';raise ValueError('BAOSTOCK_BYTE_LIMIT')
            if state['capture']:state['query_wire'].extend(value)
            return value
    def bounded_decompress(value,*args,**kwargs):
        decoder=zlib.decompressobj()
        output=decoder.decompress(value,command['max_bytes']+1)
        if len(output)>command['max_bytes'] or decoder.unconsumed_tail:
            state['failure']='DECODED_BYTE_LIMIT';raise ValueError('BAOSTOCK_DECODED_BYTE_LIMIT')
        if key and key.encode() in output:
            state['failure']='SECRET_REFLECTED';raise ValueError('BAOSTOCK_SECRET_REFLECTED_RESPONSE_REJECTED')
        return output
    zlib.decompress=bounded_decompress
    socket.socket=BoundedSocket
    if key:bs.set_API_key(key)
    login=bs.login()
    if login.error_code!='0':return {'error_code':login.error_code}
    state['capture']=True
    group=command['group']
    if group=='DAILY':
        result=bs.query_history_k_data_plus(command['symbol'],command['fields'],start_date=command['start_date'],end_date=command['end_date'],frequency='d',adjustflag='3')
    elif group=='CALENDAR':result=bs.query_trade_dates(start_date=command['start_date'],end_date=command['end_date'])
    elif group=='ADJUSTMENTS':result=bs.query_dividend_data(command['symbol'],year=str(command['year']),yearType='operate')
    else:raise ValueError('BAOSTOCK_GROUP_INVALID')
    collected=[]
    while result.error_code=='0' and result.next():collected.append(result.get_row_data())
    if state['failure']:return {'error_code':state['failure']}
    if result.error_code!='0':return {'error_code':result.error_code}
    state['capture']=False
    received_at=datetime.now(timezone.utc).isoformat()
    # Close transport directly: logout is not needed for authority and must not exceed budget.
    context.default_socket.close()
    return {'error_code':'0','fields':result.fields,'rows':collected,'wire_b64':base64.b64encode(state['query_wire']).decode(),
        'received_at':received_at,'calls':state['calls'],'received_bytes':state['received_bytes'],'sdk_version':constants.BAOSTOCK_CLIENT_VERSION,'sdk_distribution_version':version('baostock'),'pandas_distribution_version':version('pandas')}


if __name__=='__main__':
    # Avoid shadowing the official top-level SDK with this directory's baostock.py adapter.
    sys.path=[p for p in sys.path if os.path.abspath(p)!=os.path.dirname(os.path.abspath(__file__))]
    command=json.load(sys.stdin)
    try:
        with open(os.devnull,'w') as sink,contextlib.redirect_stdout(sink),contextlib.redirect_stderr(sink):
            result=main(command)
    except Exception:
        result={'error_code':'PROCESS_OR_TRANSPORT_FAILURE'}
    # Check decrypted/decoded SDK values too, since compressed wire can hide credential echoes.
    rendered=json.dumps(result,ensure_ascii=False)
    if os.environ.get('BAOSTOCK_API_KEY') and os.environ['BAOSTOCK_API_KEY'] in rendered:rendered=json.dumps({'error_code':'SECRET_REFLECTED'})
    sys.stdout.write(rendered)
