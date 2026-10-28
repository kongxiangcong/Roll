from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from roll.app import create_app
from roll.runtime.daily_reports import market_metrics
from test_news_events import register
from test_fills import establish


def test_market_metrics_exact_window_and_unknowns():
    start=datetime(2026,9,1)
    bars=[{'trade_date':(start+timedelta(days=i)).date().isoformat(),'close':str(100+i),'amount_yuan':'1000'} for i in range(21)]
    value=market_metrics(bars)
    assert abs(value['trend']['value']-(120/110.5-1)*100)<1e-9
    assert value['activity']['value']==1
    assert value['risk']['max_drawdown_percent']==0
    assert value['risk']['value']>0
    assert market_metrics(bars[:19])['trend']['value'] is None
    bars[-1]['amount_yuan']=None
    assert market_metrics(bars)['activity']['value'] is None


def test_report_freezes_versions_notes_breadth_and_restart(tmp_path):
    with TestClient(create_app(tmp_path,runtime_role='API')) as c:
        establish(c);register(c,'SSE:600362','江西铜业','600362')
        result=c.post('/api/daily-reports',json={})
        assert result.status_code==201,result.text
        first=result.json()
        assert first['revision']==1 and first['edition']=='INITIAL'
        assert first['inputs']['breadth']['status']=='UNKNOWN'
        assert first['inputs']['account']['version']==1
        assert c.post('/api/daily-reports',json={}).json()==first
        command={'idempotency_key':'note1','report_id':first['report_id'],'instrument':'SSE:600362',
                 'thesis':'METHOD commodity demand','invalidation':'Demand weakens','comparator':'ABOVE','threshold':20}
        note=c.post('/api/daily-reports/notes',json=command)
        assert note.status_code==201,note.text
        assert c.post('/api/daily-reports/notes',json=command).json()==note.json()
        assert c.post('/api/daily-reports/notes',json={**command,'thesis':'changed'}).status_code==409
        second=c.post('/api/daily-reports',json={}).json()
        assert second['revision']==2 and second['conditions'][0]['state']=='UNKNOWN'
        assert c.get('/api/daily-reports/'+first['report_id']).json()==first
        assert c.post('/api/daily-reports/notes',json={**command,'idempotency_key':'acted','outcome':'ACTED'}).status_code==422
        day=second['day'];stamp=datetime.now().astimezone().isoformat()
        breadth={'source_url':'https://example.com/market','observed_at':stamp,'trade_date':day,'universe':'SSE_SZSE_A','universe_count':5000,'advancing':2000,'declining':1000,'unchanged':1000,'basis':'METHOD explicitly imported summary'}
        assert c.post('/api/daily-reports/breadth',json={**breadth,'universe_count':100}).status_code==422
        imported=c.post('/api/daily-reports/breadth',json=breadth)
        assert imported.status_code==201,imported.text
        assert imported.json()['coverage_percent']==80
        third=c.post('/api/daily-reports',json={}).json()
        assert third['inputs']['breadth']['advancing_percent']==50
        assert third['inputs']['breadth']['source_kind']=='USER_IMPORTED_UNVERIFIED'
        assert c.post('/api/daily-reports',json={}).json()==third
        assert c.get('/api/account').json()['version']==1
    with TestClient(create_app(tmp_path,runtime_role='API')) as c:
        assert c.get('/api/daily-reports/'+first['report_id']).json()==first
        assert c.get('/api/daily-reports/'+third['report_id']).json()==third


def test_empty_account_and_partial_source_still_report(tmp_path,monkeypatch):
    with TestClient(create_app(tmp_path,runtime_role='API')) as c:
        register(c,'SZSE:000001','平安银行','000001')
        def broken(*args,**kwargs):raise ValueError('METHOD missing archive')
        monkeypatch.setattr(c.app.state.news,'listing',broken)
        result=c.post('/api/daily-reports',json={})
        assert result.status_code==201,result.text
        value=result.json()
        assert value['valuation'] is None and value['status']=='PARTIAL'
        assert value['module_errors'][0]['module']=='NEWS'
        assert c.post('/api/daily-reports',json={}).json()==value


def test_conditions_trigger_and_review_preserves_original(tmp_path,monkeypatch):
    with TestClient(create_app(tmp_path,runtime_role='API')) as c:
        register(c,'SSE:600362','江西铜业','600362')
        stamp=datetime.now().astimezone();day=stamp.astimezone(__import__('roll.market.rules',fromlist=['SHANGHAI']).SHANGHAI).date().isoformat()
        state={'close':'21'}
        def facts(listing,cutoff):
            return ([{'instrument':'SSE:600362','role':'WATCH','last_complete_daily':{'close':state['close'],'trade_date':day,'raw_hash':'METHOD'},'quote':None}],[],[],[])
        monkeypatch.setattr(c.app.state.reviews,'facts_at',facts)
        first=c.post('/api/daily-reports',json={}).json()
        command={'idempotency_key':'price','report_id':first['report_id'],'instrument':'SSE:600362','thesis':'price condition','invalidation':'reverse','comparator':'ABOVE','threshold':20}
        note=c.post('/api/daily-reports/notes',json=command).json()
        second=c.post('/api/daily-reports',json={}).json()
        assert second['conditions'][0]['state']=='TRIGGERED'
        state['close']='19'
        third=c.post('/api/daily-reports',json={}).json()
        assert third['conditions'][0]['state']=='NOT_TRIGGERED'
        assert c.get('/api/daily-reports/'+second['report_id']).json()==second
        reviewed=c.post('/api/daily-reports/notes',json={**command,'idempotency_key':'review','parent_note_id':note['note_id'],'outcome':'REVIEWED','thesis':'review conclusion'})
        assert reviewed.status_code==201
        final=c.post('/api/daily-reports',json={}).json()
        assert len(final['conditions'])==1 and len(final['inputs']['notes'])==2
