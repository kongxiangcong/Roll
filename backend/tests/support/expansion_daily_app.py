"""Isolated browser source fixture; never reads a real account or calls upstream."""
import json
import httpx
from roll.app import create_app
from roll.market import sse_daily, post_close_packet, evidence, sse_company_contract, sse_company_actions, sse_action_assessments
from roll.research import prospective


def app():
    stamp = '2026-10-14T18:00:00+08:00'
    for module in (sse_daily, post_close_packet, evidence, prospective, sse_company_contract, sse_company_actions, sse_action_assessments):
        module.now = lambda: stamp
    value = json.loads((sse_daily.HISTORY_REFERENCE / 'a51334316a941c30047614138f201d3dd3d988a453fa754b8673ae1fd74bb113.raw').read_bytes())
    value['result'][0]['TX_DATE'] = '20261014'
    def source(request):
        actions={'COMMON_SSE_CP_GPJCTPZ_GPLB_LRFP_FH_L':'20243b376bad269c47fffb63cd38034caa0c619eadaf85e9532741ec9a0aa91e',
                 'COMMON_SSE_CP_GPJCTPZ_GPLB_LRFP_SG_L':'b498844359a5f0bd6b2dbddaa1b02b1a9d55e04f708cdb93b14cfb776d553f52'}
        if request.url.params.get('sqlId') in actions:
            return httpx.Response(200,content=(sse_action_assessments.REFERENCE/(actions[request.url.params['sqlId']]+'.raw')).read_bytes())
        if request.url.host=='yunhq.sse.com.cn':
            return httpx.Response(200,json={'code':'600362','date':20261009,'time':150004,'snap':['江西铜业',44.01,1,.44,1234567.89,12345,43,43.57,[],[],45,42,' E1 ',125,0,3,0,48,39,None,0,'opaque-status','opaque-limit','']})
        if request.url.params.get('sqlId')==sse_company_contract.SQL:
            return httpx.Response(200,json={'sqlId':sse_company_contract.SQL,'isPagination':'false','result':[{'COMPANY_CODE':'600362','A_STOCK_CODE':'600362','SEC_TYPE':'主板A','STATE_CODE_A_DESC':'上市','A_LIST_DATE':'2002-01-11','STATUS_A':'opaque'}]})
        if request.url.host != 'query.sse.com.cn' or request.url.params.get('sqlId') != sse_daily.HISTORY_DAILY_SQL:
            raise AssertionError('Unexpected browser source request')
        return httpx.Response(200,json=value)
    return create_app(market_transport=httpx.MockTransport(source),runtime_role='API')
