"""Explicit method SOURCE with real model runtime, never a fixture model endpoint."""
import os
from pathlib import Path

import httpx
from roll.app import create_app


def factory():
    if os.environ.get('ROLL_ENV')!='test' or os.environ.get('ROLL_ADVERSARIAL_SOURCE')!='1':
        raise RuntimeError('ADVERSARIAL_SOURCE_EXPLICIT_TEST_ONLY')
    root=Path(__file__).resolve().parents[3]
    material=(root/'.scratch/roll-p0/evidence/13/attack-materials/webpage.html').read_bytes()
    def source(request):
        if request.url.host=='hq.sinajs.cn':return httpx.Response(200,content=b'var hq_str_sh600519="";')
        return httpx.Response(200,content=material,headers={'content-type':'text/html'})
    return create_app(market_transport=httpx.MockTransport(source))
