"""No-network browser transport fixture, distinct from actual SDK acceptance."""
import sys
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app


def app():
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'application'))
    from test_news_ingestion import news_fixture
    application=create_app()
    async def supplier(instrument,output):return news_fixture(output)
    application.state.news.worker=supplier
    with TestClient(application) as client:
        version=client.get('/api/market/list').json()['version'];client.post('/api/market/watch',json={'operation':'ADD','instrument':'SSE:600362','expected_list_version':version})
        policy=next(p for p in client.get('/api/research/collection-sources').json() if p['id']=='akshare-news-em')
        client.post('/api/research/collection-sources/akshare-news-em/policy',json={'enabled':True,'expected_revision':policy['revision'],'basis':'Explicit METHOD browser source scope'})
    return application
