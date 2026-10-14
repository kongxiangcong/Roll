"""Isolated browser source fixture; never reads a real account or calls upstream."""
import json
import httpx
from roll.app import create_app
from roll.market import sse_daily, post_close_packet, evidence
from roll.research import prospective


def app():
    stamp = '2026-10-14T18:00:00+08:00'
    for module in (sse_daily, post_close_packet, evidence, prospective):
        module.now = lambda: stamp
    value = json.loads((sse_daily.HISTORY_REFERENCE / 'a51334316a941c30047614138f201d3dd3d988a453fa754b8673ae1fd74bb113.raw').read_bytes())
    value['result'][0]['TX_DATE'] = '20261014'
    def source(request):
        if request.url.host != 'query.sse.com.cn' or request.url.params.get('sqlId') != sse_daily.HISTORY_DAILY_SQL:
            raise AssertionError('Unexpected browser source request')
        return httpx.Response(200,json=value)
    return create_app(market_transport=httpx.MockTransport(source),runtime_role='API')
