from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from roll.app import create_app
from roll.market.observation_symbols import symbols
from test_news_events import register, rows_fixture, enable_news
from test_observation_updates import start, wait


def test_symbols_are_exchange_bound():
    assert symbols('SSE:600000')==('600000','SH600000','600000.SH')
    assert symbols('SZSE:000001')==('000001','SZ000001','000001.SZ')
    for invalid in ['SSE:000001','SZSE:600362','BSE:830001','600362','SSE:600362/../../']:
        with pytest.raises(ValueError):symbols(invalid)


def test_two_holdings_watch_and_local_failure_restart(tmp_path):
    with TestClient(create_app(tmp_path,runtime_role='API')) as c:
        draft=c.post('/api/account/drafts',json={'kind':'BASELINE','expected_account_version':0,'payload':{
            'effective_at':'2026-10-07T10:00:00+08:00','source':'METHOD finite daily',
            'cash_balance':'100000','broker_available':None,'broker_frozen':None,'withdrawable':None,
            'positions':[{'instrument':i,'quantity':'100','sellable_quantity':None,'reference_cost':'10'} for i in ['SSE:600362','SZSE:000001']], 'permission_profile':[]}})
        assert draft.status_code==201,draft.text
        assert c.post('/api/account/confirm',json={'draft_id':draft.json()['draft_id'],'idempotency_key':'baseline'}).status_code==200
        register(c,'SSE:600000','浦发银行','600000');enable_news(c)
        async def supplier(instrument,output):
            if instrument=='SZSE:000001':raise ValueError('METHOD one issuer failed')
            result=rows_fixture([('20261014123451',instrument+'新闻',instrument+'公开事实')],output)
            for item in result['items']:item['fields']['关键词']=instrument.split(':')[1]
            return result
        c.app.state.news.worker=supplier
        jobs=[]
        for instrument in ['SSE:600362','SZSE:000001','SSE:600000']:
            base='/api/observation-updates/'+instrument
            assert c.post(base+'/settings',json={'enabled':True,'expected_revision':1,'basis':'METHOD','news_postclose':True}).status_code==200
            response=c.post(base+'/requests',json={'idempotency_key':'same-key','kind':'NEWS','basis':'METHOD','refresh_sources':True})
            assert response.status_code==201,response.text
            jobs.append(response.json())
        start(c)
        results=[wait(c,j) for j in jobs]
        assert [j['status'] for j in results]==['COMPLETE','PARTIAL','COMPLETE'],results
        assert len({j['job_id'] for j in results})==3
        assert c.get('/api/account').json()['version']==1
        assert c.post('/api/observation-updates/SSE:600999/requests',json={'idempotency_key':'outside','kind':'NEWS','basis':'METHOD'}).status_code==403
        listing=c.get('/api/market/list').json()
        c.post('/api/market/watch',json={'operation':'REMOVE','instrument':'SSE:600000','expected_list_version':listing['version']})
        c.app.state.observation_updates.schedule(datetime.fromisoformat('2026-10-20T15:10:00+08:00'))
        assert len(c.get('/api/observation-updates/SSE:600000').json()['jobs'])==1
    with TestClient(create_app(tmp_path,runtime_role='API')) as c:
        for j in results:assert c.get('/api/observation-update-jobs/'+j['job_id']).json()==j
