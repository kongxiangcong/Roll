"""METHOD API tests: immutable research profile, real neutral label, failure isolation and legacy replay."""
import hashlib,json
import pytest
from fastapi.testclient import TestClient
from roll.app import create_app
from roll.market import sentiment as module
from test_news_events import register,enable_news,rows_fixture

ROWS=[('20261014123501','江西铜业涨3%','江西铜业上涨3%。'),('20261014123502','江西铜业跌3%','江西铜业下跌3%。'),('20261014123503','江西铜业召开董事会','江西铜业召开董事会。'),('20261014123504','其他基金净值上涨','600362 成分名单。'),('20261014123505','江西铜业发布季度业绩','江西铜业发布季度业绩。')]
COMMAND={'idempotency_key':'research-once','basis':'METHOD three-class public API','profile':'finbert-adaptation-01'}

def prepare(client):
    register(client,'SSE:600362','江西铜业股份有限公司','600362');enable_news(client)
    async def supplier(instrument,output):return rows_fixture(ROWS,output)
    client.app.state.news.worker=supplier
    response=client.post('/api/market/news/SSE:600362/collect',json={'idempotency_key':'research-news','basis':'METHOD saved facts'})
    assert response.status_code==201,response.text

async def worker(instrument,items):
    output={}
    for item in items:
        if '涨' in item['text']:values={'POSITIVE':.9,'NEGATIVE':.05,'NEUTRAL':.05}
        elif '跌' in item['text']:values={'POSITIVE':.05,'NEGATIVE':.9,'NEUTRAL':.05}
        elif '董事会' in item['text']:values={'POSITIVE':.05,'NEGATIVE':.05,'NEUTRAL':.9}
        else:values={'POSITIVE':.34,'NEGATIVE':.33,'NEUTRAL':.33}
        output[item['fact_id']]={'probabilities':values}
    return output

def test_three_class_append_replay_restart_and_source_input(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        prepare(client);client.app.state.sentiment.worker=worker
        response=client.post('/api/market/sentiment/SSE:600362/classify',json=COMMAND)
        assert response.status_code==201,response.text
        run=response.json();assert run['status']=='COMPLETE' and run['evidence_kind']=='METHOD_CASE'
        assert run['counts']=={'POSITIVE':1,'NEGATIVE':1,'NEUTRAL':1,'ABSTAIN_NO_COMPANY_OBJECT':1,'ABSTAIN_LOW_CONFIDENCE':1}
        neutral=next(r for r in run['facts'] if r['label']=='NEUTRAL')
        assert neutral['prob_neutral']==.9 and neutral['model_input_text']
        assert hashlib.sha256(neutral['model_input_text'].encode()).hexdigest()==neutral['text_sha256']
        assert neutral['source_input_sha256'] and neutral['model_input_version']=='sentiment-object-v2.1-shared-predicate'
        assert client.get('/api/market/sentiment/SSE:600362').json()['labels_supported']==['NEUTRAL','POSITIVE','NEGATIVE']
        assert client.post('/api/market/sentiment/SSE:600362/classify',json=COMMAND).json()==run
        assert client.post('/api/market/sentiment/SSE:600362/classify',json={**COMMAND,'profile':'legacy'}).status_code==409
        assert client.get('/api/market/sentiment/SSE:600362',params={'known_by':'2020-01-01T00:00:00Z'}).status_code==404
        assert client.get('/api/account').json()['version']==0
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/market/sentiment/runs/'+run['run_id']).json()==run
        assert client.get('/api/market/sentiment/SSE:600362').json()['run']==run

def test_invalid_output_is_failed_and_never_overwrites_prior_run(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        prepare(client);client.app.state.sentiment.worker=worker
        old=client.post('/api/market/sentiment/SSE:600362/classify',json=COMMAND).json();assert old['status']=='COMPLETE'
        async def malformed(instrument,items):return {r['fact_id']:{'probabilities':{'POSITIVE':float('nan'),'NEGATIVE':.5,'NEUTRAL':.5}} for r in items}
        client.app.state.sentiment.worker=malformed
        failed=client.post('/api/market/sentiment/SSE:600362/classify',json={**COMMAND,'idempotency_key':'invalid-output'}).json()
        assert failed['status']=='FAILED' and failed['errors']==['SENTIMENT_INVALID_PROBABILITIES']
        assert client.get('/api/market/sentiment/SSE:600362').json()['run']==old
        assert client.get('/api/account').json()['version']==0

def test_missing_configuration_scope_and_unknown_profile(tmp_path,monkeypatch):
    monkeypatch.delenv('ROLL_SENTIMENT_PYTHON',raising=False)
    with TestClient(create_app(tmp_path)) as client:
        prepare(client)
        response=client.post('/api/market/sentiment/SSE:600362/classify',json=COMMAND)
        assert response.status_code==409 and response.json()['detail']=='SENTIMENT_ISOLATED_PYTHON_NOT_CONFIGURED'
        assert client.post('/api/market/sentiment/SZSE:000657/classify',json=COMMAND).status_code==422
        assert client.post('/api/market/sentiment/SSE:600362/classify',json={**COMMAND,'profile':'invented'}).status_code==422
        client.app.state.sentiment.worker=worker
        reference=json.loads(module.RESEARCH_REFERENCE.read_bytes());reference['object_sha256']='0'*64
        path=tmp_path/'bad-reference.json';path.write_text(json.dumps(reference),encoding='utf-8');monkeypatch.setattr(module,'RESEARCH_REFERENCE',path)
        response=client.post('/api/market/sentiment/SSE:600362/classify',json=COMMAND)
        assert response.status_code==409 and response.json()['detail']=='SENTIMENT_OBJECT_FINGERPRINT_MISMATCH'

def test_registered_alias_conflict_refuses_without_worker_call(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        prepare(client);register(client,'SZSE:000657','江西铜业股份有限公司','000657')
        async def never(instrument,items):raise AssertionError('ambiguous registered alias must not reach model')
        client.app.state.sentiment.worker=never
        run=client.post('/api/market/sentiment/SSE:600362/classify',json=COMMAND).json()
        assert run['status']=='COMPLETE' and run['counts']=={'ABSTAIN_IDENTITY_CONFLICT':5}
        assert all(r['label'] is None and r['prob_neutral'] is None for r in run['facts'])
