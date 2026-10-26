from fastapi.testclient import TestClient
from roll.app import create_app
from test_news_events import rows_fixture,register,enable_news

ROWS=[('20261014123471','江西铜业涨停，业绩增长','公司发布业绩，股价涨停。'),
      ('20261014123472','江西铜业下跌，风险提示','公司提示风险，股价下跌。'),
      ('20261014123473','江西铜业召开说明会','公司召开说明会。'),
      ('20261014123474','有色金属行业资金流出榜：云南锗业等10股','600362 云南锗业')]


def test_limited_sentiment_persists_rejects_and_replays(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        register(client,'SSE:600362','江西铜业股份有限公司','600362')
        enable_news(client)
        async def supplier(instrument,output):return rows_fixture(ROWS,output)
        client.app.state.news.worker=supplier
        base='/api/market/news/SSE:600362'
        assert client.post(base+'/collect',json={'idempotency_key':'sentiment-news','basis':'METHOD sentiment facts'}).status_code==201
        calls=[]
        async def worker(instrument,items):
            calls.append([item['fact_id'] for item in items])
            return {items[0]['fact_id']:{'prob_positive':0.9,'prob_negative':0.1},
                    items[1]['fact_id']:{'prob_positive':0.2,'prob_negative':0.8}}
        client.app.state.sentiment.worker=worker
        response=client.post('/api/market/sentiment/SSE:600362/classify',json={'idempotency_key':'sentiment-once','basis':'METHOD limited sentiment'})
        assert response.status_code==201,response.text
        value=response.json();assert value['status']=='COMPLETE' and value['capability']=='RESEARCH_LIMITED'
        facts={row['title']:row for row in value['facts']}
        assert facts['江西铜业涨停，业绩增长']['label']=='POSITIVE'
        assert facts['江西铜业下跌，风险提示']['label']=='NEGATIVE'
        assert facts['江西铜业召开说明会']['reject_reason']=='ABSTAIN_NO_DIRECTIONAL_CUE'
        assert facts['有色金属行业资金流出榜：云南锗业等10股']['reject_reason']=='ABSTAIN_FUND_FLOW'
        assert len(calls)==1 and len(calls[0])==2
        assert value['coverage']==0.5 and value['counts']=={'POSITIVE':1,'NEGATIVE':1,'ABSTAIN_NO_DIRECTIONAL_CUE':1,'ABSTAIN_FUND_FLOW':1}
        listing=client.get('/api/market/sentiment/SSE:600362').json()
        assert listing['run']['run_id']==value['run_id'] and listing['evaluation']['passed_frozen_gates'] is False
        assert listing['evaluation']['combined']['negative_recall']==0.2 and listing['network_calls']==0
        assert listing['evaluation']['combined']['per_class']['NEGATIVE']['support']==30
        assert listing['evaluation']['metric_scope']=='ALL_LABELED_ROWS_ABSTENTION_IS_FALSE_NEGATIVE'
        assert client.post('/api/market/sentiment/SSE:600362/classify',json={'idempotency_key':'sentiment-once','basis':'METHOD limited sentiment'}).json()==value
        assert client.post('/api/market/sentiment/SSE:600362/classify',json={'idempotency_key':'sentiment-once','basis':'different'}).status_code==409
        cutoff=client.get('/api/market/sentiment/SSE:600362',params={'known_by':'2025-01-01T00:00:00Z'})
        assert cutoff.status_code==404
        assert client.get('/api/account').json()['version']==0
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/market/sentiment/runs/'+value['run_id']).json()==value
        assert client.get('/api/market/sentiment/SSE:600362').json()['counts']==value['counts']
