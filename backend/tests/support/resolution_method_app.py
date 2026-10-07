"""Explicit injected source method case for SQLite/Chrome revision acceptance only."""
import httpx
from fastapi import Body
from roll.app import create_app


def factory():
    price=['1258.620']
    def source(request):
        fields=['贵州茅台','1239.530','1235.580',price[0],'1268.000','1236.050','1258.620','1258.650','3833098','4797246636.000']
        fields+=['0']*20+['2026-09-30','15:34:59','00']
        return httpx.Response(200,content=('var hq_str_sh600519="'+','.join(fields)+'";\n').encode('gbk'))
    app=create_app(market_transport=httpx.MockTransport(source))
    @app.post('/api/__method/price')
    def revise(value:str=Body(embed=True)):
        # This endpoint exists only in the isolated acceptance factory.
        if value!='1259.620':raise ValueError('undeclared method value')
        price[0]=value
        return {'evidence_kind':'METHOD_CASE','price':value}
    return app
