"""Explicit METHOD_CASE source originals for ticket14 UI; no model or live key."""
import os
import httpx
from fastapi import Body,HTTPException
from roll.app import create_app


def factory():
    if os.environ.get('ROLL_ENV')!='test' or os.environ.get('ROLL_BROWSER_METHOD')!='1':
        raise RuntimeError('Explicit isolated verification METHOD_CASE only')
    source={'origin':'A:first','price':'100.000'}
    def provider(request):
        return httpx.Response(200,json={'instrument':'SSE:600519','method_case_status':'NORMAL',
            'last':source['price'],'upstream_at':'2026-09-30T15:00:00+08:00','basis':'METHOD_CASE independent original generation',
            '_roll14_original_provenance':{'original_record':source['origin'],'producer':source['origin'].split(':')[0],
                'generation_basis':'METHOD_CASE original institutional observation','origin_kind':'DIRECT_ORIGINAL'}})
    app=create_app(market_transport=httpx.MockTransport(provider))
    @app.post('/api/__method/original')
    def original(origin:str=Body(),price:str=Body()):
        if origin not in {'A:first','B:second','B:revised'} or price not in {'100.000','101.000'}:raise HTTPException(422,'Undeclared METHOD_CASE')
        source.update(origin=origin,price=price)
        return {'evidence_kind':'METHOD_CASE',**source}
    return app
