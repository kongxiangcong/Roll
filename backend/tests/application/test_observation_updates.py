"""METHOD providers/clocks, exercised through the original worker and public APIs."""
import asyncio
import time
import pytest
import httpx
from datetime import datetime
from fastapi.testclient import TestClient
from roll.app import create_app
from roll.runtime import observation_updates
from test_financial_metrics import prepare
from test_news_events import register, enable_news, rows_fixture
from roll.market import financial_income, news_ingestion, sentiment_series, sentiment

BASE = '/api/observation-updates/SSE:600362'


def configure(client, **extra):
    settings = client.get(BASE).json()['settings']
    response = client.post(BASE+'/settings', json={'enabled': True, 'expected_revision': settings['revision'], 'basis': 'METHOD explicit background observation', **extra})
    assert response.status_code == 200, response.text
    return response.json()


def submit(client, key, kind='NEWS', refresh=False):
    command = {'idempotency_key': key, 'kind': kind, 'basis': 'METHOD bounded observation', 'refresh_sources': refresh}
    response = client.post(BASE+'/requests', json=command)
    assert response.status_code == 201, response.text
    return response.json(), command


def wait(client, job):
    end = time.monotonic()+25
    while time.monotonic() < end:
        value = client.get('/api/observation-update-jobs/'+job['job_id']).json()
        if value['status'] not in ('QUEUED', 'RUNNING'):
            return value
        time.sleep(.05)
    raise AssertionError(client.get(BASE).json())


def start(client):
    client.app.state.reviews.worker_enabled = True
    assert client.app.state.reviews.start()


def seed_news(client):
    register(client, 'SSE:600362', '江西铜业股份有限公司', '600362')
    enable_news(client)
    async def supplier(instrument, output):
        return rows_fixture([('20261014123901', '江西铜业涨3%', '江西铜业涨3%。')], output)
    client.app.state.news.worker = supplier
    assert client.post('/api/market/news/SSE:600362/collect', json={'idempotency_key': 'seed', 'basis': 'METHOD initial source'}).status_code == 201


def test_existing_worker_cache_station_dedup_and_restart(tmp_path):
    with TestClient(create_app(tmp_path, runtime_role='API')) as client:
        assert client.get(BASE).json()['settings']['enabled'] is False
        assert client.post(BASE+'/requests', json={'idempotency_key': 'paused', 'kind': 'NEWS', 'basis': 'METHOD'}).status_code == 409
        prepare(client); seed_news(client); configure(client)
        first, command = submit(client, 'first'); financial, _ = submit(client, 'financial', 'FINANCIAL')
        start(client)
        a, f = wait(client, first), wait(client, financial)
        assert a['status'] == f['status'] == 'COMPLETE', (a, f)
        again, _ = submit(client, 'same-input')
        b = wait(client, again)
        assert b['observation_id'] == a['observation_id'] and b['cache_reused']
        assert client.post(BASE+'/requests', json=command).json() == a
        status = client.get(BASE).json()
        assert len(status['observations']) == 2 and status['worker']['worker_limit'] == 1
        notices = [n for n in client.get('/api/notifications').json()['notifications'] if n['source']['kind'] == 'OBSERVATION_UPDATE']
        assert len(notices) == 2 and all(n['in_app_only'] for n in notices)
        assert all(n['evidence_kind'] == 'METHOD_CASE' for n in notices)
        assert client.get('/api/account').json()['version'] == 0
        saved = client.get('/api/observation-update-jobs/'+a['job_id']).json()
    with TestClient(create_app(tmp_path, runtime_role='API')) as client:
        start(client)
        assert client.get('/api/observation-update-jobs/'+a['job_id']).json() == saved
        assert len(client.get(BASE).json()['observations']) == 2
        assert client.get(BASE).json()['offline_coverage']['gaps']
        assert client.get(BASE).json()['forecast_backfill'] is False


def test_model_failure_keeps_news_and_financial_work_independent(tmp_path, monkeypatch):
    with TestClient(create_app(tmp_path, runtime_role='API')) as client:
        prepare(client); seed_news(client); configure(client, classify=True)
        async def broken(instrument, items):
            raise ValueError('METHOD model unavailable')
        client.app.state.sentiment.worker = broken
        news, _ = submit(client, 'broken-model'); financial, _ = submit(client, 'still-financial', 'FINANCIAL')
        start(client)
        a, b = wait(client, news), wait(client, financial)
        assert a['status'] == 'PARTIAL' and b['status'] == 'COMPLETE', (a, b)
        status = client.get(BASE).json()
        observation = next(o for o in status['observations'] if o['kind'] == 'NEWS')
        assert observation['payload']['saved_fact_count'] == 1 and observation['payload']['classification_run_id'] is None
        assert observation['errors'] and status['worker']['worker_state'] == 'RUNNING'
        assert status['health']['NEWS']['retry_after']
        assert client.get('/api/market/news/SSE:600362').json()['unique_event_count'] == 1
        assert client.get('/api/account').json()['version'] == 0


@pytest.mark.parametrize('failure', ['fingerprint', 'timeout'])
def test_model_fingerprint_failure_still_publishes_saved_news(tmp_path, monkeypatch, failure):
    with TestClient(create_app(tmp_path, runtime_role='API')) as client:
        seed_news(client); configure(client, classify=True)
        def missing(profile):
            raise ValueError('METHOD missing weights')
        if failure == 'fingerprint':
            monkeypatch.setattr(client.app.state.sentiment, 'reference', missing)
        else:
            async def slow(instrument, items):
                await asyncio.sleep(5)
            client.app.state.sentiment.worker = slow
            monkeypatch.setattr(observation_updates, 'MODEL_TIMEOUT', .1)
        job, _ = submit(client, 'missing-model')
        start(client)
        result = wait(client, job)
        assert result['status'] == 'PARTIAL' and result['observation_id']
        observation = client.get(BASE).json()['observations'][0]
        assert observation['payload']['saved_fact_count'] == 1
        assert observation['payload']['classification_run_id'] is None
        assert observation['errors']
        if failure == 'fingerprint':
            assert any('missing weights' in error for error in observation['errors'])


def test_source_pause_cache_and_deadline_cancellation_are_receipted(tmp_path, monkeypatch):
    with TestClient(create_app(tmp_path, runtime_role='API')) as client:
        seed_news(client); configure(client)
        queued, _ = submit(client, 'queued-cancel')
        assert client.post('/api/observation-update-jobs/'+queued['job_id']+'/cancel').json()['status'] == 'CANCELLED'
        # A fresh original source run is reused, without invoking a failed provider.
        async def broken(instrument, output):
            raise ValueError('METHOD source must not be called when fresh')
        client.app.state.news.worker = broken
        cached, _ = submit(client, 'fresh-source', refresh=True)
        start(client)
        result = wait(client, cached)
        assert result['status'] == 'COMPLETE' and result['result'][0]['refresh'] == 'CACHE_FRESH_BY_ACTUAL_SOURCE_RUN'
        policy = next(p for p in client.get('/api/research/collection-sources').json() if p['id'] == 'akshare-news-em')
        assert client.post('/api/research/collection-sources/akshare-news-em/policy', json={'enabled': False, 'expected_revision': policy['revision'], 'basis': 'METHOD pause source'}).status_code == 200
        paused, _ = submit(client, 'source-paused', refresh=True)
        result = wait(client, paused)
        assert result['status'] == 'PARTIAL' and any('SOURCE_DISABLED' in e for e in result['errors'])
        assert client.get('/api/market/news/SSE:600362').json()['facts']
    with TestClient(create_app(tmp_path, runtime_role='API')) as client:
        configure(client)
        # Only the optional module's resource bound is shortened for this METHOD case.
        monkeypatch.setattr(observation_updates, 'TIMEOUT', .1)
        async def slow(job):
            await asyncio.sleep(5)
        client.app.state.observation_updates.prepare = slow
        job, _ = submit(client, 'deadline', 'FINANCIAL')
        start(client)
        result = wait(client, job)
        assert result['status'] == 'CANCELLED' and result['error'] == 'RESOURCE_DEADLINE_EXCEEDED'
        assert client.get(BASE).json()['worker']['worker_state'] == 'RUNNING'


def test_postclose_clock_queues_current_day_once_without_catchup(tmp_path):
    clock = lambda: datetime.fromisoformat('2026-10-19T15:06:00+08:00')
    with TestClient(create_app(tmp_path, runtime_role='API', review_clock=clock)) as client:
        seed_news(client); configure(client, news_postclose=True)
        start(client)
        end = time.monotonic()+10
        while time.monotonic() < end:
            status = client.get(BASE).json()
            if status['jobs'] and status['jobs'][0]['status'] == 'COMPLETE':break
            time.sleep(.05)
        assert len(status['jobs']) == 1 and status['jobs'][0]['status'] == 'COMPLETE', status
        assert status['jobs'][0]['scheduled_checkpoint'] == '2026-10-19T15:05:00+08:00'
        assert status['jobs'][0]['forecast_archive_created'] is False
        configure(client, news_postclose=True, news_refresh=True)
        time.sleep(.2)
        assert len(client.get(BASE).json()['jobs']) == 1
        configure(client, enabled=False)
        assert client.get(BASE).json()['settings']['enabled'] is False


def test_word_revision_does_not_duplicate_notice_or_use_preconfigured_external_channel(tmp_path):
    transmitted = []
    def external(request):
        transmitted.append(request.content)
        return httpx.Response(200, json={'id': 'METHOD-should-not-send', 'event': 'message'})
    with TestClient(create_app(tmp_path, runtime_role='API', notification_transport=httpx.MockTransport(external))) as client:
        seed_news(client); configure(client)
        assert client.post('/api/notification-channel', json={'expected_version': 0, 'enabled': True,
            'server': 'https://ntfy.example.test', 'topic': 'METHOD-observation', 'app_base_url': 'http://127.0.0.1:5173'}).status_code == 200
        first, _ = submit(client, 'original-meaning'); start(client)
        first = wait(client, first)
        async def words(instrument, output):
            return rows_fixture([('20261014123901', '江西铜业股价涨3%', '江西铜业的股价涨3%。')], output)
        client.app.state.news.worker = words
        assert client.post('/api/market/news/SSE:600362/collect', json={'idempotency_key': 'words', 'basis': 'METHOD wording revision, unchanged meaning'}).status_code == 201
        second, _ = submit(client, 'revised-words'); second = wait(client, second)
        assert second['status'] == first['status'] == 'COMPLETE'
        assert second['observation_id'] != first['observation_id']
        end = time.monotonic()+5
        while time.monotonic() < end:
            notices = [n for n in client.get('/api/notifications').json()['notifications'] if n['source']['kind'] == 'OBSERVATION_UPDATE']
            if notices and notices[0]['external_status'] == 'OUTBOUND_CLOSED':break
            time.sleep(.05)
        assert len(notices) == 1 and notices[0]['in_app_only']
        assert notices[0]['external_status'] == 'OUTBOUND_CLOSED' and not transmitted
        assert client.get('/api/notification-channel').json()['enabled'] is True
        assert client.get('/api/account').json()['version'] == 0


def test_expired_original_source_cache_refreshes_through_existing_worker_once(tmp_path, monkeypatch):
    with TestClient(create_app(tmp_path, runtime_role='API')) as client:
        financial_now, news_now = financial_income.now, news_ingestion.now
        monkeypatch.setattr(financial_income, 'now', lambda: '2026-10-16T14:00:00+08:00')
        monkeypatch.setattr(news_ingestion, 'now', lambda: '2026-10-16T14:00:00+08:00')
        prepare(client); seed_news(client)
        monkeypatch.setattr(financial_income, 'now', financial_now)
        monkeypatch.setattr(news_ingestion, 'now', news_now)
        calls = []
        for name in ('financial', 'financial_statements', 'news'):
            service = getattr(client.app.state, name)
            original = service.worker
            async def counted(instrument, output, original=original, name=name):
                calls.append(name)
                return await original(instrument, output)
            service.worker = counted
        configure(client)
        news, _ = submit(client, 'refresh-news', refresh=True)
        financial, _ = submit(client, 'refresh-financial', 'FINANCIAL', refresh=True)
        start(client)
        news, financial = wait(client, news), wait(client, financial)
        assert news['status'] == financial['status'] == 'COMPLETE', (news, financial)
        assert sorted(calls) == ['financial', 'financial_statements', 'news']
        assert all(receipt['status'] in ('COMPLETE', 'PARTIAL') for receipt in news['result']+financial['result'])
        again, _ = submit(client, 'fresh-after-original-refresh', refresh=True)
        again = wait(client, again)
        assert again['status'] == 'COMPLETE' and again['result'][0]['refresh'] == 'CACHE_FRESH_BY_ACTUAL_SOURCE_RUN'
        assert again['observation_id'] == news['observation_id'] and len(calls) == 3


def test_consumer_checkpoint_advances_without_reaging_sources_or_notifying_twice(tmp_path, monkeypatch):
    stamp = {'value': '2026-10-15T15:01:00+08:00'}
    for module in (observation_updates, news_ingestion, sentiment, sentiment_series):
        monkeypatch.setattr(module, 'now', lambda: stamp['value'])
    with TestClient(create_app(tmp_path, runtime_role='API', review_clock=lambda: datetime.fromisoformat(stamp['value']))) as client:
        seed_news(client); configure(client, classify=True)
        calls = []
        async def model(instrument, items):
            calls.append(items)
            return {item['fact_id']: {'prob_positive': .9, 'prob_negative': .1} for item in items}
        client.app.state.sentiment.worker = model
        stamp['value'] = '2026-10-15T15:06:00+08:00'
        job, _ = submit(client, 'first-checkpoint'); start(client)
        first = wait(client, job)
        assert first['status'] == 'COMPLETE', first
        old = client.get(BASE).json()['observations'][0]
        old_series = client.get('/api/market/sentiment-series/runs/'+old['payload']['series_id']).json()
        assert len(old_series['deferred_events']) == 1
        stamp['value'] = '2026-10-16T15:06:00+08:00'
        job, _ = submit(client, 'next-checkpoint'); second = wait(client, job)
        assert second['status'] == 'COMPLETE' and second['observation_id'] != first['observation_id']
        new = client.get(BASE).json()['observations'][0]
        assert new['payload']['source_available_through'] == old['payload']['source_available_through'] == '2026-10-15T15:01:00+08:00'
        current = client.get('/api/market/sentiment-series/runs/'+new['payload']['series_id']).json()
        assert not current['deferred_events']
        assert current['days'][-1]['counts']['POSITIVE'] == 1
        assert client.get('/api/market/sentiment-series/runs/'+old_series['series_id']).json() == old_series
        job, _ = submit(client, 'same-checkpoint'); third = wait(client, job)
        assert third['cache_reused'] and third['observation_id'] == second['observation_id'] and len(calls) == 1
        notices = [n for n in client.get('/api/notifications').json()['notifications'] if n['source']['kind'] == 'OBSERVATION_UPDATE']
        assert len(notices) == 1


def test_persisted_cancel_wins_over_concurrent_prepare_failure(tmp_path):
    with TestClient(create_app(tmp_path, runtime_role='API')) as client:
        configure(client)
        async def cancel_then_fail(job):
            response = client.post('/api/observation-update-jobs/'+job['job_id']+'/cancel')
            assert response.json()['error'] == 'USER_CANCELLED'
            raise ValueError('METHOD concurrent prepare failure')
        client.app.state.observation_updates.prepare = cancel_then_fail
        job, _ = submit(client, 'cancel-failure-order')
        start(client)
        result = wait(client, job)
        time.sleep(.2)  # allow the terminal failure handler to run after cancel
        final = client.get('/api/observation-update-jobs/'+job['job_id']).json()
        assert final == result and final['status'] == 'CANCELLED' and final['error'] == 'USER_CANCELLED'
        assert client.get(BASE).json()['observations'] == []
