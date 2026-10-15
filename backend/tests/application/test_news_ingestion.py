import hashlib,json
from fastapi.testclient import TestClient
from roll.app import create_app


def news_fixture(output):
    stamp='2026-10-15T01:00:00+00:00'
    body=b'<html><article><p>METHOD archived full article.</p></article></html>'
    rows=[{'关键词':'600362','新闻标题':'METHOD 江西铜业公告','新闻内容':'列表摘要不是正文','发布时间':'2026-10-14 12:00:00','文章来源':'METHOD媒体','新闻链接':'http://finance.eastmoney.com/a/20261014123456.html'},
          {'关键词':'600362','新闻标题':'METHOD 标题保留','新闻内容':'不可冒充全文','发布时间':'2026-10-14 11:00:00','文章来源':'METHOD媒体','新闻链接':'http://finance.eastmoney.com/a/20261014123457.html'}]
    raw=json.dumps({'result':{'cmsArticleWebOld':[{'code':'20261014123456','title':rows[0]['新闻标题'],'content':rows[0]['新闻内容'],'date':rows[0]['发布时间'],'mediaName':'METHOD媒体'},{'code':'20261014123457','title':rows[1]['新闻标题'],'content':rows[1]['新闻内容'],'date':rows[1]['发布时间'],'mediaName':'METHOD媒体'}]}},ensure_ascii=False).encode()
    captures=[]
    for i,(data,role,url) in enumerate([(raw,'LIST','https://search-api-web.eastmoney.com/search/jsonp'),(body,'BODY','https://finance.eastmoney.com/a/20261014123456.html')],1):
        (output/f'{i:02}.raw').write_bytes(data)
        captures.append({'ordinal':i,'role':role,'url':url,'received_at':stamp,'status_code':200,'original_complete':True,'sha256':hashlib.sha256(data).hexdigest()})
    return {'status':'CAPTURED','sdk_version':'1.19.1','sdk_source_sha256':'fbda1c9a6f5b96552bcd61baa80afb6697fae3ab44ddf659a592b7bcbd1c0ca0','extractor_version':'2.3.1','captures':captures,'items':[
        {'fields':rows[0],'body_status':'EXTRACTED','body_ordinal':2,'text':'METHOD archived full article.','metadata':{'date':'2020-01-01'},'errors':[]},
        {'fields':rows[1],'body_status':'NOT_FETCHED_BODY_BUDGET','body_ordinal':None,'text':None,'metadata':None,'errors':['BODY_BUDGET']}], 'coverage':{'requested_page':1,'requested_page_size':10,'returned':2,'complete_history':False},'errors':[]}


def test_news_original_full_text_headline_gap_idempotency_and_restart(tmp_path):
    calls=[]
    async def supplier(instrument,output):calls.append(instrument);return news_fixture(output)
    with TestClient(create_app(tmp_path)) as client:
        base='/api/market/news/SSE:600362'
        response=client.get(base);assert response.status_code==200,response.text
        assert response.json()['facts']==[]
        version=client.get('/api/market/list').json()['version']
        assert client.post('/api/market/watch',json={'operation':'ADD','instrument':'SSE:600362','expected_list_version':version}).status_code==200
        client.app.state.news.worker=supplier
        command={'idempotency_key':'news-once','basis':'METHOD isolated news transport fixture'}
        assert client.post(base+'/collect',json=command).status_code==409 and not calls
        policy=next(p for p in client.get('/api/research/collection-sources').json() if p['id']=='akshare-news-em')
        assert not policy['enabled']
        assert client.post('/api/research/collection-sources/akshare-news-em/policy',json={'enabled':True,'expected_revision':policy['revision'],'basis':'Explicit isolated METHOD news scope'}).status_code==200
        response=client.post(base+'/collect',json=command);assert response.status_code==201,response.text
        saved=response.json();assert saved['status']=='PARTIAL' and saved['network_calls']==0 and len(saved['facts'])==2
        fact=saved['facts'][0];assert fact['body_text']=='METHOD archived full article.' and fact['excerpt']=='列表摘要不是正文'
        assert fact['reported_published_at']=='2026-10-14 12:00:00'
        assert fact['extracted_metadata']['date']=='2020-01-01' and fact['first_received_at']=='2026-10-15T01:00:00+00:00'
        assert not fact['historical_pit_eligible'] and fact['evidence_kind']=='METHOD_CASE'
        assert client.get('/api/data/archives/'+fact['body_sha256']).content.startswith(b'<html>')
        assert saved['facts'][1]['body_text'] is None and saved['facts'][1]['title']=='METHOD 标题保留'
        assert client.post(base+'/collect',json=command).json()==saved and len(calls)==1
        assert client.get(base,params={'known_by':'2025-01-01T00:00:00Z'}).json()['facts']==[]
        assert client.get('/api/account').json()['version']==0
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/market/news/runs/'+saved['run_id']).json()==saved
        assert len(client.get(base).json()['facts'])==2


def test_news_body_timeout_empty_corruption_and_cancel_keep_originals(tmp_path):
    import asyncio,threading,time
    from concurrent.futures import ThreadPoolExecutor
    with TestClient(create_app(tmp_path)) as client:
        version=client.get('/api/market/list').json()['version'];client.post('/api/market/watch',json={'operation':'ADD','instrument':'SSE:600362','expected_list_version':version})
        policy=next(p for p in client.get('/api/research/collection-sources').json() if p['id']=='akshare-news-em');client.post('/api/research/collection-sources/akshare-news-em/policy',json={'enabled':True,'expected_revision':policy['revision'],'basis':'Explicit METHOD test scope'})
        async def timeout(instrument,output):
            manifest=news_fixture(output);(output/'02.raw').unlink();manifest['captures'][1].update(original_complete=False,status_code=None)
            manifest['items'][0].update(body_status='BODY_FETCH_FAILED',text=None,errors=['TimeoutError']);return manifest
        client.app.state.news.worker=timeout;base='/api/market/news/SSE:600362';command={'idempotency_key':'body-timeout','basis':'METHOD body timeout must preserve headlines'}
        result=client.post(base+'/collect',json=command).json();assert result['status']=='PARTIAL' and len(result['facts'])==2
        assert result['facts'][0]['body_text'] is None and result['facts'][0]['body_sha256'] is None and len(result['originals'])==1
        async def empty(instrument,output):
            manifest=news_fixture(output);raw=b'{"result":{"cmsArticleWebOld":[]}}';(output/'01.raw').write_bytes(raw)
            manifest['captures']=manifest['captures'][:1];manifest['captures'][0]['sha256']=hashlib.sha256(raw).hexdigest();manifest['items']=[];return manifest
        client.app.state.news.worker=empty;result=client.post(base+'/collect',json={**command,'idempotency_key':'empty'}).json();assert result['status']=='EMPTY' and result['facts']==[]
        async def corrupt(instrument,output):
            manifest=news_fixture(output);(output/'02.raw').write_bytes(b'corrupt');return manifest
        client.app.state.news.worker=corrupt;result=client.post(base+'/collect',json={**command,'idempotency_key':'corrupt'}).json()
        assert result['status']=='PARTIAL' and len(result['facts'])==2
        assert result['facts'][0]['body_text'] is None and result['facts'][0]['body_status']=='BODY_INTEGRITY_FAILED'
        assert len(result['originals'])==2 and client.get('/api/data/archives/'+result['facts'][0]['list_sha256']).status_code==200
        started=threading.Event()
        async def slow(instrument,output):
            manifest=news_fixture(output);(output/'capture.json').write_text(json.dumps(manifest),encoding='utf-8');started.set();await asyncio.sleep(60)
        client.app.state.news.worker=slow
        with ThreadPoolExecutor() as pool:
            pending=pool.submit(client.post,base+'/collect',json={**command,'idempotency_key':'cancel'})
            assert started.wait(10)
            active=client.get(base).json()['active_run_ids'];assert len(active)==1
            assert client.post('/api/market/news/runs/'+active[0]+'/cancel',json={}).status_code==200
            result=pending.result(10).json();assert result['status']=='CANCELLED' and len(result['originals'])==2
            assert client.post(base+'/collect',json={**command,'idempotency_key':'cancel'}).json()==result
