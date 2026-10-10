"""Isolated METHOD HTTP factory; no production override endpoint or real provider call."""
import httpx
from roll.app import create_app


def factory():
    source=httpx.MockTransport(lambda request:httpx.Response(200,json={'instrument':'SSE:600519','last':'30','upstream_at':'2026-09-30T15:00:00+08:00',
        'method_case_status':'NORMAL','basis':'Explicit synthetic METHOD09/30 close/state, actually archived now; not past available proof','reported_limit_up':'33','reported_limit_down':'27'}))
    return create_app(market_transport=source)
