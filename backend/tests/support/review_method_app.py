"""Only an isolated Chrome method-case factory; no production status override."""
from datetime import datetime
from io import BytesIO
import httpx
from pypdf import PdfWriter
from roll.app import create_app


def factory():
    def source(request):
        host=request.url.host
        if host=='qt.gtimg.cn':return httpx.Response(200,json={'method_case_status':'SUSPENDED','instrument':'SSE:600519',
            'upstream_at':'2026-09-30T16:14:58+08:00','last':'10','volume_reported':'0','amount_yuan':'0',
            'basis':'合成停牌风险原时点案例；不代表实际当前状态'})
        if host=='push2his.eastmoney.com':return httpx.Response(200,json={'rc':0,'data':{'code':'600519','market':1,
            'klines':['2026-09-30,10,10,10,10,100,100000','2026-10-08,10,11,11,10,100,110000']}})
        if host=='web.ifzq.gtimg.cn':
            symbol=request.url.params.get('param','sh000001,').split(',')[0]
            return httpx.Response(200,json={'code':0,'data':{symbol:{'day':[['2026-09-30','3800','3830','3840','3790','400000000']]}}})
        if host=='datacenter-web.eastmoney.com':
            data=[{'SECURITY_CODE':'600519','REPORT_DATE':'2025-12-31','NOTICE_DATE':'2026-06-22',
                'EX_DIVIDEND_DATE':'2026-06-26','EQUITY_RECORD_DATE':'2026-06-25','PRETAX_BONUS_RMB':'28','PLAN_PROGRESS':'实施方案','ASSIGNDSCRPT':'合成权益分派'}]
            if request.url.params.get('reportName')=='RPT_LICO_FN_CPD':data=[{'SECURITY_CODE':'600519','REPORTDATE':'2026-06-30',
                'NOTICE_DATE':'2026-08-15','TOTAL_OPERATE_INCOME':'100000','PARENT_NETPROFIT':'10000','EPS':'1'}]
            return httpx.Response(200,json={'success':True,'code':0,'result':{'pages':1,'count':1,'data':data}})
        if host=='np-anotice-stock.eastmoney.com':
            rows=[{'art_code':code,'title':title,'notice_date':day,'codes':[{'stock_code':'600519'}],'columns':[{'column_code':column}]}
                for code,title,day,column in [('AN_METHOD_NOTICE','合成公告','2026-08-15','001002008'),
                    ('AN_METHOD_REPORT','2026年半年度报告','2026-08-15','001001001002001'),
                    ('AN_METHOD_MAJOR','合成重大事项','2026-07-18','001002008')]]
            return httpx.Response(200,json={'success':1,'data':{'total_hits':3,'list':rows}})
        if host=='np-cnotice-stock.eastmoney.com':
            art=request.url.params['art_code']
            return httpx.Response(200,json={'success':1,'data':{'art_code':art,'notice_title':'合成公开事项','notice_date':'2026-08-15',
                'notice_content':'合成原文；个人实际权益到账尚未确认','attach_list':[{'attach_url':'https://pdf.dfcfw.com/pdf/'+art+'.pdf'}]}})
        if host=='pdf.dfcfw.com':
            stream=BytesIO();writer=PdfWriter();writer.add_blank_page(width=200,height=200);writer.write(stream)
            return httpx.Response(200,content=stream.getvalue(),headers={'content-type':'application/pdf'})
        return httpx.Response(503,content=b'unspecified method source')
    return create_app(market_transport=httpx.MockTransport(source),review_clock=lambda:datetime.fromisoformat('2026-10-08T16:00:00+08:00'))
