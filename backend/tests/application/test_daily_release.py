from fastapi.testclient import TestClient
from roll.app import create_app


def test_built_web_same_origin_api_and_missing_assets(tmp_path, monkeypatch):
    web=tmp_path/'web';web.mkdir();(web/'index.html').write_text('<h1>Roll build</h1>')
    monkeypatch.setenv('ROLL_WEB_DIST',str(web))
    with TestClient(create_app(tmp_path/'data',runtime_role='API')) as c:
        assert 'Roll build' in c.get('/').text
        assert 'Roll build' in c.get('/daily').text
        assert c.get('/missing.js').status_code==404
        assert c.get('/api/missing').status_code==404
        assert c.get('/api/health').json()['status']=='ok'
        assert len(c.get('/api/runtime/release').json()['source_commit'])==40
