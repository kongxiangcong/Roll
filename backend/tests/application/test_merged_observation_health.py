"""Synthetic persisted pre-merge records; no providers or model execution."""
from roll.app import create_app
from test_news_events import register
from fastapi.testclient import TestClient


def test_legacy_cooldown_remains_visible_without_leaking_to_another_issuer(tmp_path):
    with TestClient(create_app(tmp_path, runtime_role='API')) as client:
        register(client, 'SZSE:000848', '承德露露', '000848')
        updates = client.app.state.observation_updates
        legacy = dict(error='METHOD historical failure', retry_after='2099-01-01T00:00:00+00:00')
        updates.health_write('RESEARCH:SSE:600362', legacy)
        updates.health_write('NEWS', legacy)
        jcc = client.get('/api/observation-updates/SSE:600362').json()['health']
        other = client.get('/api/observation-updates/SZSE:000848').json()['health']
        assert jcc['RESEARCH'] == jcc['NEWS'] == legacy
        assert 'RESEARCH' not in other and 'NEWS' not in other
        current = dict(error='METHOD current issuer state', retry_after='2098-01-01T00:00:00+00:00')
        updates.health_write('SSE:600362:RESEARCH', current)
        assert client.get('/api/observation-updates/SSE:600362').json()['health']['RESEARCH'] == current
