"""Basic daily use is independent of research qualification."""
from datetime import datetime
from fastapi.testclient import TestClient
from roll.app import create_app
from test_observation_updates import BASE, configure
from test_fills import establish, fill
from test_observation_updates import submit, start, wait
import httpx
import json
import asyncio
from roll.runtime import observation_updates


def test_daily_schedule_survives_restart_and_does_not_replay_missed_days(tmp_path):
    clock = datetime.fromisoformat('2026-10-20T15:10:00+08:00')
    with TestClient(create_app(tmp_path, runtime_role='API')) as client:
        configure(client, news_postclose=True, financial_postclose=True, market_postclose=True, news_refresh=True)
        service = client.app.state.observation_updates
        service.schedule(clock)
        service.schedule(clock)
        jobs = client.get(BASE).json()['jobs']
        assert len(jobs) == 3
        assert {job['command']['kind'] for job in jobs} == {'NEWS', 'FINANCIAL', 'MARKET'}
        assert all(job['command']['refresh_sources'] for job in jobs)
        assert all(not job['forecast_archive_created'] for job in jobs)
    with TestClient(create_app(tmp_path, runtime_role='API')) as client:
        assert client.get(BASE).json()['settings']['financial_postclose']
        client.app.state.observation_updates.schedule(clock)
        assert len(client.get(BASE).json()['jobs']) == 3
        configure(client, enabled=False)
        client.app.state.observation_updates.schedule(datetime.fromisoformat('2026-10-21T15:10:00+08:00'))
        assert len(client.get(BASE).json()['jobs']) == 3


def test_jiangxi_buy_sell_without_grant_and_restart(tmp_path):
    with TestClient(create_app(tmp_path, runtime_role='API')) as client:
        establish(client)
        for version, direction, price, day in [(1, 'BUY', '10.00', '08'), (2, 'SELL', '11.00', '09')]:
            command = fill(version, 'daily-'+direction, direction)
            command['payload'].update(instrument='SSE:600362', price=price,
                effective_at=f'2026-10-{day}T10:00:00+08:00')
            before = client.get('/api/account').json()
            response = client.post('/api/account/drafts', json=command)
            assert response.status_code == 201, response.text
            assert client.get('/api/account').json()['version'] == before['version']
            response = client.post('/api/account/confirm', json={
                'draft_id': response.json()['draft_id'], 'idempotency_key': 'daily-'+direction})
            assert response.status_code == 200, response.text
        account = client.get('/api/account').json()
        assert account['cash_balance'] == '100290.00'
        assert len(account['fills']) == 2
        assert client.get('/api/today').json()['technical_capability']['state'] == 'UNGRANTED'
    with TestClient(create_app(tmp_path, runtime_role='API')) as client:
        assert client.get('/api/account').json() == account


def test_market_refresh_source_failure_is_local_and_does_not_block_account(tmp_path):
    calls = []
    def unavailable(request):
        calls.append(str(request.url))
        return httpx.Response(503)
    with TestClient(create_app(tmp_path, runtime_role='API',
                              market_transport=httpx.MockTransport(unavailable))) as client:
        listing = client.get('/api/market/list').json()
        assert client.post('/api/market/watch', json={'operation':'ADD', 'instrument':'SSE:600362',
            'expected_list_version':listing['version']}).status_code == 200
        configure(client)
        job, _ = submit(client, 'market-failure', 'MARKET', True)
        start(client)
        result = wait(client, job)
        assert result['status'] == 'PARTIAL', result
        assert result['errors'] and len(calls) <= 2
        assert client.get('/api/account').json()['version'] == 0
        assert client.get(BASE).json()['worker']['worker_state'] == 'RUNNING'
        establish(client)
        assert client.get('/api/account').json()['version'] == 1


def test_repeated_market_receipts_do_not_duplicate_unchanged_price_notice(tmp_path):
    def provider(request):
        if request.url.host == 'q.stock.sohu.com':
            return httpx.Response(200, content=json.dumps([{'status':0,'code':'cn_600362','hq':[
                ['2026-10-19','10','11','1','10%','9','12','100','11','1%']], 'stat':[]}]).encode())
        fields = ['']*33
        for index, value in {0:'METHOD',1:'10',2:'10',3:'11',4:'12',5:'9',8:'10000',9:'110000',
                             30:'2026-10-19',31:'15:00:00',32:'00'}.items():
            fields[index] = value
        return httpx.Response(200, content=('var hq_str_sh600362="'+','.join(fields)+'";').encode())
    with TestClient(create_app(tmp_path, runtime_role='API', market_transport=httpx.MockTransport(provider))) as client:
        listing = client.get('/api/market/list').json()
        client.post('/api/market/watch', json={'operation':'ADD', 'instrument':'SSE:600362',
            'expected_list_version':listing['version']})
        configure(client)
        start(client)
        for key in ('market-first', 'market-again'):
            job, _ = submit(client, key, 'MARKET', True)
            result = wait(client, job)
            assert result['status'] == 'COMPLETE', result
        notices = [n for n in client.get('/api/notifications').json()['notifications']
                   if n['source']['kind'] == 'OBSERVATION_UPDATE']
        assert len(notices) == 1
        assert notices[0]['title'] == '行情观察已更新'


def test_next_trading_day_financial_update_does_not_wait_full_24_hours(tmp_path, monkeypatch):
    calls = []
    class SavedSource:
        run_table = 'daily_cache_test_runs'
        async def collect(self, instrument, command):
            calls.append(instrument)
            return {'run_id':'new','status':'COMPLETE','evidence_kind':'METHOD_CASE'}
    with TestClient(create_app(tmp_path, runtime_role='API')) as client:
        service = client.app.state.observation_updates
        monkeypatch.setattr(service.sources, 'access', lambda *_: None)
        with service.ledger.connection() as db:
            db.execute('CREATE TABLE daily_cache_test_runs(instrument TEXT,value TEXT)')
            db.execute('INSERT INTO daily_cache_test_runs VALUES(?,?)', ('SSE:600362', json.dumps({
                'run_id':'previous', 'status':'PARTIAL', 'finished_at':'2026-10-19T15:06:00+08:00'})))
        job = {'job_id':'cache-policy','instrument':'SSE:600362','command':{'refresh_sources':True,'basis':'METHOD cache policy'}}
        monkeypatch.setattr(observation_updates, 'now', lambda: '2026-10-19T18:00:00+08:00')
        receipts = []
        asyncio.run(service.refresh(SavedSource(), job, 'akshare-financial-em', receipts, []))
        assert not calls and receipts[0]['status'] == 'PARTIAL'
        monkeypatch.setattr(observation_updates, 'now', lambda: '2026-10-20T15:05:00+08:00')
        asyncio.run(service.refresh(SavedSource(), job, 'akshare-financial-em', [], []))
        assert calls == ['SSE:600362']
