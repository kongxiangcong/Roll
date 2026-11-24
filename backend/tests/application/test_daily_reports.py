from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from roll.app import create_app
from roll.market.rules import SHANGHAI
from roll.runtime.daily_reports import market_metrics
from test_news_events import register
from test_fills import establish
from test_account import baseline, submit
from test_funding import funding


def test_workbench_reviews_the_selected_report_and_preserves_earlier_unknowns(tmp_path):
    with TestClient(create_app(tmp_path, runtime_role='API')) as client:
        command = baseline()
        command['payload']['positions'][0]['instrument'] = 'SSE:600362'
        assert submit(client, command, 'review-baseline').status_code == 200
        register(client, 'SSE:600362', '江西铜业', '600362')
        first = client.post('/api/daily-reports', json={}).json()
        path = f"/api/daily-reports/{first['report_id']}/review"
        response = client.get(path)
        assert response.status_code == 200, response.text
        original = response.json()
        assert original['known_by'] == first['known_by']
        assert original['comparison'] is None
        assert original['account']['cash_weight_pct'] is None
        assert original['account']['constraints_status'] == 'UNKNOWN'
        assert original['holdings'][0]['status'] == 'INSUFFICIENT'
        note = client.post('/api/daily-reports/notes', json={
            'idempotency_key': 'review-due', 'report_id': first['report_id'], 'instrument': 'SSE:600362',
            'thesis': '需求支撑', 'invalidation': '需求减弱', 'due_date': first['day'],
        }).json()
        second = client.post('/api/daily-reports', json={}).json()
        review = client.get(f"/api/daily-reports/{second['report_id']}/review").json()
        assert review['comparison']['report_id'] == first['report_id']
        holding = review['holdings'][0]
        assert holding['status'] == 'REVIEW_REQUIRED'
        assert holding['judgments'][0]['note_id'] == note['note_id']
        assert holding['judgments'][0]['state'] == 'DUE_FOR_REVIEW'
        assert holding['judgments'][0]['due_date'] == first['day']
        assert client.get(path).json() == original


def test_workbench_no_new_review_requires_explicit_scope_and_usable_price(tmp_path, monkeypatch):
    with TestClient(create_app(tmp_path, runtime_role='API')) as client:
        command = baseline()
        command['payload']['positions'][0]['instrument'] = 'SSE:600362'
        assert submit(client, command, 'price-baseline').status_code == 200
        register(client, 'SSE:600362', '江西铜业', '600362')
        state = {'close': '19', 'days_ago': 0, 'document_hash': 'ORIGINAL'}

        def archived_prices(listing, cutoff):
            day = cutoff.astimezone(SHANGHAI).date() - timedelta(days=state['days_ago'])
            bar = {'trade_date': day.isoformat(), 'close': state['close'],
                   'raw_hash': 'ARCHIVED-PRICE', 'available_at': cutoff.replace(microsecond=0).isoformat()}
            announcement = {'group': 'ANNOUNCEMENTS', 'art_code': 'notice-1', 'title': '原件',
                            'raw_hash': 'ARCHIVED-INDEX', 'document_hash': state['document_hash']}
            return [{'instrument': 'SSE:600362', 'last_complete_daily': bar,
                     'company_facts': [announcement]}], [], [], []

        monkeypatch.setattr(client.app.state.reviews, 'facts_at', archived_prices)

        def publish_review():
            report = client.post('/api/daily-reports', json={}).json()
            response = client.get(f"/api/daily-reports/{report['report_id']}/review")
            assert response.status_code == 200, response.text
            return response.json()['holdings'][0]

        first = client.post('/api/daily-reports', json={}).json()
        note = {'report_id': first['report_id'], 'instrument': 'SSE:600362', 'idempotency_key': 'price-general',
                'thesis': '继续观察', 'invalidation': '价格达 20 元', 'comparator': 'ABOVE', 'threshold': 20}
        general = client.post('/api/daily-reports/notes', json=note).json()
        assert publish_review()['status'] == 'INSUFFICIENT'
        scoped = client.post('/api/daily-reports/notes', json={
            **note, 'idempotency_key': 'price-only', 'parent_note_id': general['note_id'], 'price_only': True,
        })
        assert scoped.status_code == 201, scoped.text
        state['close'] = '19.50'
        checked = publish_review()
        assert checked['status'] == 'NO_NEW_REVIEW'
        assert checked['judgments'][0]['price_state'] == 'NOT_TRIGGERED'
        assert any(item['kind'] == 'NEWS' and item['status'] == 'UNKNOWN' for item in checked['changes'])
        state['close'] = '20'
        crossed = publish_review()
        assert crossed['status'] == 'REVIEW_REQUIRED'
        assert crossed['judgments'][0]['price_state'] == 'TRIGGERED'
        state['days_ago'] = 1
        assert publish_review()['status'] == 'INSUFFICIENT'
        state.update(days_ago=0, close='19.50', document_hash='CORRECTED-ORIGINAL')
        correction = publish_review()
        assert correction['status'] == 'REVIEW_REQUIRED'
        assert correction['judgments'][0]['price_state'] == 'NOT_TRIGGERED'
        assert any('CORRECTED-ORIGINAL' in item['references'] for item in correction['changes'])


def test_workbench_funding_checks_keep_the_report_version_and_boundaries(tmp_path):
    with TestClient(create_app(tmp_path, runtime_role='API')) as client:
        establish(client)
        first_funding = funding(cash_reserve='100000.00', total_exposure='0.00', single_exposure='0.00')
        assert client.post('/api/funding/confirm', json=first_funding).status_code == 200
        first = client.post('/api/daily-reports', json={}).json()
        path = f"/api/daily-reports/{first['report_id']}/review"
        original = client.get(path).json()
        summary = original['account']
        assert summary['cash_weight_pct'] == 100 and summary['largest_weight_pct'] == 0
        assert summary['funding_version'] == 1
        assert summary['constraints_status'] == 'UNKNOWN'
        assert {row['kind'] for row in summary['constraints_checks']} == {
            'TOTAL_EXPOSURE', 'SINGLE_EXPOSURE', 'BOOK_CASH_RESERVE',
        }
        assert all(row['status'] == 'WITHIN_BOUNDARY' for row in summary['constraints_checks'])
        assert client.post('/api/funding/confirm', json=funding(1, pause=True)).status_code == 200
        second = client.post('/api/daily-reports', json={}).json()
        next_review = client.get(f"/api/daily-reports/{second['report_id']}/review").json()
        assert next_review['account']['constraints_status'] == 'PAUSED'
        assert client.get(path).json() == original


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
