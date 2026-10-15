"""Actual pinned AKShare component with explicit synthetic transport, never real HTTP."""
import hashlib,json,os,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]


def test_actual_sdk_raw_first_body_allowlist_redirect_and_no_cookie_forwarding(tmp_path):
    rows=[{'code':code,'title':'METHOD 江西铜业'+str(i),'content':'METHOD 摘要','date':'2026-10-14 12:00:00','mediaName':'METHOD媒体'} for i,code in enumerate(['20261014123456','20261014123457','127.0.0.1'])]
    raw='jQuery35101792940631092459_1764599530165('+json.dumps({'result':{'cmsArticleWebOld':rows}},ensure_ascii=False)+')'
    entries=[{'role':'LIST','url':'https://search-api-web.eastmoney.com/search/jsonp','body':raw},
             {'role':'BODY','url':'https://finance.eastmoney.com/a/20261014123456.html','body':'<html><article>METHOD full body.</article></html>'},
             {'role':'BODY','url':'https://finance.eastmoney.com/a/20261014123457.html','status_code':302,'body':'METHOD redirect to private address must not be followed'}]
    fixture=tmp_path/'fixture.json';fixture.write_text(json.dumps(entries),encoding='utf-8');output=tmp_path/'capture'
    env={k:v for k,v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','TEMP','TMP'}};env['ROLL_ENV']='test'
    result=subprocess.run([str(ROOT/'.scratch/rce-runtime/akshare/Scripts/python.exe'),'-B',str(ROOT/'backend/src/roll/market/akshare_news_process.py')],input=json.dumps({'instrument':'SSE:600362','output_directory':str(output),'fixture':str(fixture)}).encode(),env=env,capture_output=True,timeout=25)
    assert result.returncode==0,result.stderr.decode(errors='replace')
    manifest=json.loads((output/'capture.json').read_text(encoding='utf-8'))
    assert manifest['status']=='CAPTURED',manifest
    assert manifest['transport_kind']=='METHOD_FIXTURE_ZERO_HTTP' and not manifest['sdk_hardcoded_cookie_forwarded']
    assert all(c.get('request_cookie_sent') is False for c in manifest['captures'])
    assert len(manifest['captures'])==3 and len(manifest['items'])==3
    assert (output/'01.raw').read_text(encoding='utf-8')==raw
    assert manifest['items'][0]['body_status']=='ARCHIVED_PENDING_EXTRACTION'
    assert manifest['items'][1]['body_status']=='BODY_FETCH_FAILED' and manifest['items'][1]['errors']==['NEWS_HTTP_302']
    assert manifest['items'][2]['body_status']=='BODY_FETCH_FAILED' and manifest['items'][2]['errors']==['NEWS_BODY_TARGET_NOT_ALLOWED']
    for i,c in enumerate(manifest['captures'],1):assert hashlib.sha256((output/f'{i:02}.raw').read_bytes()).hexdigest()==c['sha256']


def test_news_dead_owner_restores_received_entities_and_headlines_without_retry(tmp_path):
    from fastapi.testclient import TestClient
    from roll.app import create_app
    profile=tmp_path/'profile'
    script='''
import json,os
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app
from test_news_ingestion import news_fixture
with TestClient(create_app(Path(os.environ['METHOD_PROFILE']))) as c:
 v=c.get('/api/market/list').json()['version'];c.post('/api/market/watch',json={'operation':'ADD','instrument':'SSE:600362','expected_list_version':v})
 p=next(p for p in c.get('/api/research/collection-sources').json() if p['id']=='akshare-news-em');c.post('/api/research/collection-sources/akshare-news-em/policy',json={'enabled':True,'expected_revision':p['revision'],'basis':'METHOD dead-owner proof'})
 async def die(instrument,output):
  m=news_fixture(output);(output/'capture.json').write_text(json.dumps(m),encoding='utf-8');os._exit(7)
 c.app.state.news.worker=die
 c.post('/api/market/news/SSE:600362/collect',json={'idempotency_key':'interrupted','basis':'METHOD interrupted capture, zero network'})
'''
    env=os.environ.copy();env.update(METHOD_PROFILE=str(profile),PYTHONPATH=os.pathsep.join([str(ROOT/'backend/src'),str(ROOT/'backend/tests/application')]))
    result=subprocess.run([str(ROOT/'backend/.venv/Scripts/python.exe'),'-X','utf8','-B','-c',script],env=env,capture_output=True,timeout=30)
    assert result.returncode==7,result.stderr.decode(errors='replace')
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    barrier=Barrier(2)
    def initialize():
        barrier.wait(10)
        with TestClient(create_app(profile)) as c:return c.get('/api/market/news/SSE:600362').json()
    with ThreadPoolExecutor(2) as pool:
        futures=[pool.submit(initialize) for _ in range(2)];recovered=[f.result(30) for f in futures]
    assert all(len(v['facts'])==2 and len(v['runs'][0]['facts'])==2 for v in recovered)
    assert recovered[0]['runs'][0]==recovered[1]['runs'][0]
    with TestClient(create_app(profile)) as c:
        listing=c.get('/api/market/news/SSE:600362').json();assert not listing['active_run_ids']
        run=listing['runs'][0];assert run['status']=='INTERRUPTED' and len(run['originals'])==2
        assert len(run['facts'])==2 and len(listing['facts'])==2 and run['network_calls']==0
        assert c.post('/api/market/news/SSE:600362/collect',json={'idempotency_key':'interrupted','basis':'METHOD interrupted capture, zero network'}).json()==run
