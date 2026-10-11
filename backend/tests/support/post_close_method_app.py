"""Explicit test-only raw supplier/clock. Cannot be loaded as a production factory."""
import os
from pathlib import Path
import httpx


def factory():
    if os.environ.get('ROLL_ENV')!='test':raise RuntimeError('METHOD factory requires test environment')
    from roll.app import create_app
    from roll.market import evidence,post_close_packet
    from roll.research import prospective
    clock=os.environ['ROLL_POST_CLOSE_METHOD_CLOCK']
    for module in [evidence,post_close_packet,prospective]:module.now=lambda:clock
    raw=b'{"date":20261012,"time":150005,"list":[["600362","METHOD",100,101,99,100,1234,123400,100]]}'
    return create_app(Path(os.environ['ROLL_DATA_DIR']),
        market_transport=httpx.MockTransport(lambda _:httpx.Response(200,content=raw)))
