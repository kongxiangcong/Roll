"""METHOD clocks/fixtures prove event counting and immutability, not real coverage."""
from datetime import datetime
from fastapi.testclient import TestClient
from roll.app import create_app
from roll.market import sentiment, news_ingestion
from test_news_events import register, enable_news, rows_fixture

P = ('20261014123601', '江西铜业涨3%', '江西铜业涨3%。')
COPY = ('20261014123602', P[1], P[2])
N = ('20261014123603', '江西铜业跌2%', '江西铜业跌2%。')


def setup(client):
    register(client, 'SSE:600362', '江西铜业股份有限公司', '600362')
    enable_news(client)


def collect(client, monkeypatch, rows, stamp, key):
    monkeypatch.setattr(news_ingestion, 'now', lambda: stamp)
    async def supplier(instrument, output): return rows_fixture(rows, output)
    client.app.state.news.worker = supplier
    response = client.post('/api/market/news/SSE:600362/collect', json={'idempotency_key': key, 'basis': 'METHOD series source'})
    assert response.status_code == 201, response.text


def classify(client, monkeypatch, stamp, key, profile='legacy'):
    monkeypatch.setattr(sentiment, 'now', lambda: stamp)
    async def worker(instrument, items):
        results = {}
        for item in items:
            label = 'POSITIVE' if '涨' in item['text'] else 'NEGATIVE' if '跌' in item['text'] else 'NEUTRAL'
            values = {name: .9 if name == label else .05 for name in ('POSITIVE', 'NEGATIVE', 'NEUTRAL')}
            results[item['fact_id']] = {'prob_positive': .9 if label == 'POSITIVE' else .1,
                'prob_negative': .1 if label == 'POSITIVE' else .9, 'probabilities': values}
        return results
    client.app.state.sentiment.worker = worker
    result = client.post('/api/market/sentiment/SSE:600362/classify', json={'idempotency_key': key, 'basis': 'METHOD series classification', 'profile': profile})
    assert result.status_code == 201 and result.json()['status'] == 'COMPLETE', result.text
    return result.json()


def build(client, run, key, **extra):
    command = {'idempotency_key': key, 'basis': 'METHOD saved observation reconstruction', 'source_run_id': run['run_id'],
        'start_date': '2026-10-15', 'end_date': '2026-10-19', **extra}
    response = client.post('/api/market/sentiment-series/SSE:600362', json=command)
    assert response.status_code == 201, response.text
    return response.json(), command


def test_unique_events_postclose_weekend_replay_and_source_version(tmp_path, monkeypatch):
    with TestClient(create_app(tmp_path, runtime_role='API')) as client:
        setup(client)
        collect(client, monkeypatch, [P, COPY, N], '2026-10-15T14:00:00+08:00', 'initial')
        first = classify(client, monkeypatch, '2026-10-15T14:01:00+08:00', 'first')
        old, _ = build(client, first, 'old')
        collect(client, monkeypatch, [('20261014123604', '江西铜业涨4%', '江西铜业涨4%。')], '2026-10-16T15:01:00+08:00', 'late')
        second = classify(client, monkeypatch, '2026-10-16T15:02:00+08:00', 'second')
        value, command = build(client, second, 'second-series')
        days = {day['trade_date']: day for day in value['days']}
        assert days['2026-10-15']['unique_events'] == 2 and days['2026-10-15']['source_fact_count'] == 3
        assert days['2026-10-15']['counts'] == {'POSITIVE': 1, 'NEGATIVE': 1, 'NEUTRAL': None}
        assert days['2026-10-15']['proportions'] == {'POSITIVE': .5, 'NEGATIVE': .5, 'NEUTRAL': None}
        assert days['2026-10-16']['status'] == 'NO_OBSERVATIONS'
        assert days['2026-10-17']['status'] == 'CLOSED'
        assert days['2026-10-19']['counts']['POSITIVE'] == 1 and days['2026-10-19']['unique_events'] == 1
        assert value['source_coverage']['archived_facts'] == 4 and value['evidence_kind'] == 'METHOD_CASE'
        assert client.get('/api/market/sentiment-series/runs/'+old['series_id']).json() == old
        assert client.post('/api/market/sentiment-series/SSE:600362', json=command).json() == value
        assert client.post('/api/market/sentiment-series/SSE:600362', json={**command, 'basis': 'changed'}).status_code == 409
        assert client.post('/api/market/sentiment-series/SSE:600362', json={**command, 'idempotency_key': 'too-early', 'known_by': '2026-10-15T10:00:00+08:00'}).status_code == 409
        assert client.get('/api/account').json()['version'] == 0
    with TestClient(create_app(tmp_path, runtime_role='API')) as client:
        assert client.get('/api/market/sentiment-series/runs/'+value['series_id']).json() == value


def test_revision_update_does_not_inflate_new_event_denominator(tmp_path, monkeypatch):
    with TestClient(create_app(tmp_path, runtime_role='API')) as client:
        setup(client); collect(client, monkeypatch, [P], '2026-10-15T14:00:00+08:00', 'first')
        first = classify(client, monkeypatch, '2026-10-15T14:01:00+08:00', 'first')
        old, _ = build(client, first, 'old')
        collect(client, monkeypatch, [(P[0], N[1], N[2])], '2026-10-16T14:00:00+08:00', 'revision')
        second = classify(client, monkeypatch, '2026-10-16T14:01:00+08:00', 'second')
        value, _ = build(client, second, 'revision-series')
        days = {day['trade_date']: day for day in value['days']}
        assert days['2026-10-15']['counts']['POSITIVE'] == 1
        assert days['2026-10-16']['unique_events'] == 0 and days['2026-10-16']['revision_event_count'] == 1
        assert days['2026-10-16']['revision_updates'][0]['label'] == 'NEGATIVE'
        assert value['latest_consumed_states'][0]['label'] == 'NEGATIVE'
        assert client.get('/api/market/sentiment-series/runs/'+old['series_id']).json() == old


def test_revision_before_first_consumption_uses_latest_known_event_once(tmp_path, monkeypatch):
    with TestClient(create_app(tmp_path, runtime_role='API')) as client:
        setup(client)
        collect(client, monkeypatch, [P], '2026-10-16T15:01:00+08:00', 'postclose')
        classify(client, monkeypatch, '2026-10-16T15:02:00+08:00', 'postclose')
        collect(client, monkeypatch, [(P[0], N[1], N[2])], '2026-10-16T15:03:00+08:00', 'revision')
        second = classify(client, monkeypatch, '2026-10-16T15:04:00+08:00', 'revised')
        value, _ = build(client, second, 'coalesced')
        monday = next(day for day in value['days'] if day['trade_date'] == '2026-10-19')
        assert monday['unique_events'] == 1 and monday['revision_event_count'] == 0
        assert monday['counts'] == {'POSITIVE': 0, 'NEGATIVE': 1, 'NEUTRAL': None}
        assert monday['proportions']['NEGATIVE'] == 1
        assert monday['events'][0]['source_run_id'] == second['run_id']


def test_later_exact_link_and_model_changes_start_successor_without_old_rewrite(tmp_path, monkeypatch):
    with TestClient(create_app(tmp_path, runtime_role='API')) as client:
        setup(client)
        other = ('20261014123605', '江西铜业涨5%', '江西铜业涨5%。')
        collect(client, monkeypatch, [P, other], '2026-10-15T14:00:00+08:00', 'two')
        first = classify(client, monkeypatch, '2026-10-15T14:01:00+08:00', 'first'); old, _ = build(client, first, 'old')
        collect(client, monkeypatch, [(P[0], other[1], other[2])], '2026-10-16T14:00:00+08:00', 'bridge')
        second = classify(client, monkeypatch, '2026-10-16T14:01:00+08:00', 'bridge-run'); value, _ = build(client, second, 'bridge-series')
        assert value['excluded_predecessor_runs'] == [first['run_id']] and value['source_run_ids'] == [second['run_id']]
        assert sum(day['unique_events'] for day in value['days']) == 1
        assert client.get('/api/market/sentiment-series/runs/'+old['series_id']).json() == old
        third = classify(client, monkeypatch, '2026-10-19T14:01:00+08:00', 'new-model', 'finbert-adaptation-01')
        successor, _ = build(client, third, 'new-model-series')
        assert successor['source_run_ids'] == [third['run_id']] and 'NEUTRAL' in successor['labels_supported']
        assert successor['semantics']['reference_sha256'] != value['semantics']['reference_sha256']


def test_calendar_gaps_and_holiday_mapping_are_explicit(tmp_path):
    with TestClient(create_app(tmp_path, runtime_role='API')) as client:
        service = client.app.state.sentiment_series
        checkpoint, gap = service.consumption('SSE', '2026-09-30T15:01:00+08:00', '2026-09-30T15:02:00+08:00', {})
        assert gap is None and checkpoint.isoformat() == '2026-10-08T15:05:00+08:00'
        assert service.consumption('SSE', '2026-12-31T15:01:00+08:00', '2026-12-31T15:02:00+08:00', {}) == (None, 'CALENDAR_COVERAGE_UNKNOWN')
        assert service.consumption('SSE', '2025-01-02T14:00:00+08:00', '2025-01-02T14:01:00+08:00', {}) == (None, 'INTRADAY_RULE_COVERAGE_UNKNOWN')
