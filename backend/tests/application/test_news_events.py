import hashlib,json,sqlite3
from fastapi.testclient import TestClient
from roll.app import create_app

STAMP='2026-10-15T01:00:00+00:00'
SDK_SHA='fbda1c9a6f5b96552bcd61baa80afb6697fae3ab44ddf659a592b7bcbd1c0ca0'


def rows_fixture(rows,output):
    payload={'result':{'cmsArticleWebOld':[{'code':code,'title':title,'content':content,'date':'2026-10-14 12:00:00','mediaName':'METHOD媒体'} for code,title,content in rows]}}
    raw=json.dumps(payload,ensure_ascii=False).encode()
    (output/'01.raw').write_bytes(raw)
    captures=[{'ordinal':1,'role':'LIST','url':'https://search-api-web.eastmoney.com/search/jsonp','received_at':STAMP,'status_code':200,'original_complete':True,'sha256':hashlib.sha256(raw).hexdigest()}]
    items=[]
    for code,title,content in rows:
        items.append({'fields':{'关键词':'600362','新闻标题':title,'新闻内容':content,'发布时间':'2026-10-14 12:00:00','文章来源':'METHOD媒体','新闻链接':'http://finance.eastmoney.com/a/'+code+'.html'},
            'body_status':'NOT_FETCHED_BODY_BUDGET','body_ordinal':None,'text':None,'metadata':None,'errors':['BODY_BUDGET']})
    return {'status':'CAPTURED','sdk_version':'1.19.1','sdk_source_sha256':SDK_SHA,'captures':captures,'items':items,'errors':[]}


def register(client,instrument,name,code):
    version=client.get('/api/market/list').json()['version']
    assert client.post('/api/market/watch',json={'operation':'ADD','instrument':instrument,'expected_list_version':version}).status_code==200
    response=client.post('/api/market/identities',json={'instrument':instrument,'exchange':instrument.split(':')[0],
        'board':'主板','instrument_type':'STOCK','name':name,'basis':'METHOD identity fixture','effective_at':'2026-01-01T00:00:00+08:00'})
    assert response.status_code==200,response.text


def enable_news(client):
    policy=next(p for p in client.get('/api/research/collection-sources').json() if p['id']=='akshare-news-em')
    assert client.post('/api/research/collection-sources/akshare-news-em/policy',json={'enabled':True,'expected_revision':policy['revision'],'basis':'Explicit METHOD event scope'}).status_code==200


def test_news_events_reprints_revisions_alias_and_restart(tmp_path):
    first=[('20261014123451','江西铜业签署重大合同','公司与控股股东签署合同，涉及金额100亿元。'),
           ('20261014123452','江西铜业签署重大合同','公司与控股股东签署合同，涉及金额100亿元。'),
           ('20261014123454','有色金属行业资金流出榜：中钨高新等10股净流出资金超亿元','600362 中钨高新 000657'),
           ('20261014123455','PCB概念上涨，7股主力资金净流入超亿元','600362')]
    second=[('20261014123451','江西铜业签署重大合同','公司与控股股东签署合同，涉及金额120亿元。')]
    with TestClient(create_app(tmp_path)) as client:
        register(client,'SSE:600362','江西铜业股份有限公司','600362')
        register(client,'SZSE:000657','中钨高新','000657')
        enable_news(client)
        async def first_supplier(instrument,output):return rows_fixture(first,output)
        async def second_supplier(instrument,output):return rows_fixture(second,output)
        client.app.state.news.worker=first_supplier
        base='/api/market/news/SSE:600362'
        saved1=client.post(base+'/collect',json={'idempotency_key':'events-one','basis':'METHOD event grouping fixture'}).json()
        assert saved1['status']=='PARTIAL' and len(saved1['facts'])==4
        early=client.get(base).json()
        assert early['unique_event_count']==3 and len(early['facts'])==4 and early['revision_count']==0
        client.app.state.news.worker=second_supplier
        saved2=client.post(base+'/collect',json={'idempotency_key':'events-two','basis':'METHOD revision fixture'}).json()
        assert saved2['status']=='PARTIAL' and len(saved2['facts'])==1
        listing=client.get(base).json()
        assert listing['facts'][0]['association']['classification']=='COMPANY_SUBJECT'
        assert listing['unique_event_count']==3,listing['events']
        assert listing['reprint_count']==1 and listing['revision_count']==1
        event=next(item for item in listing['events'] if len(item['fact_ids'])==3)
        assert event['reprints']==1 and event['revisions']==1
        facts={fact['title']:fact for fact in listing['facts']}
        assert facts['有色金属行业资金流出榜：中钨高新等10股净流出资金超亿元']['association']['classification']=='INDUSTRY_BACKGROUND'
        objects=facts['有色金属行业资金流出榜：中钨高新等10股净流出资金超亿元']['association']['objects']
        assert {item['instrument'] for item in objects}=={'SSE:600362','SZSE:000657'}
        assert facts['PCB概念上涨，7股主力资金净流入超亿元']['association']['classification']=='UNRELATED'
        assert listing['association_counts']=={'COMPANY_SUBJECT':3,'INDUSTRY_BACKGROUND':1,'UNRELATED':1}
        cutoff=client.get(base,params={'known_by':saved1['finished_at']}).json()
        assert cutoff['unique_event_count']==3 and len(cutoff['facts'])==4
        assert cutoff['revision_count']==0 and cutoff['reprint_count']==1
        with sqlite3.connect(tmp_path/'roll.sqlite3') as db:
            assert db.execute('SELECT COUNT(*) FROM news_events').fetchone()[0]==3
            assert db.execute('SELECT COUNT(*) FROM news_event_members').fetchone()[0]==5
            assert db.execute('SELECT COUNT(*) FROM news_association_decisions').fetchone()[0]==5
            assert db.execute('SELECT COUNT(*) FROM news_derivations').fetchone()[0]>=2
            member=db.execute("SELECT relation,parent_fact_id FROM news_event_members JOIN news_events USING(event_id) WHERE primary_fact_id=? AND relation='REVISION'",(event['primary_fact_id'],)).fetchall()
            assert len(member)==1
    with TestClient(create_app(tmp_path)) as client:
        again=client.get(base).json()
        assert again['unique_event_count']==3 and again['reprint_count']==1 and again['revision_count']==1
        assert [event['event_id'] for event in again['events']]==[event['event_id'] for event in listing['events']]
        assert [fact['event'] for fact in again['facts']]==[fact['event'] for fact in listing['facts']]


def test_alias_conflict_keeps_uncertain_and_does_not_pick_a_company(tmp_path):
    rows=[('20261014123461','江西铜业签署重大合同','公司公告签署重大合同。')]
    with TestClient(create_app(tmp_path)) as client:
        register(client,'SSE:600362','江西铜业股份有限公司','600362')
        register(client,'SZSE:000630','江西铜业股份有限公司','000630')
        enable_news(client)
        async def supplier(instrument,output):return rows_fixture(rows,output)
        client.app.state.news.worker=supplier
        base='/api/market/news/SSE:600362'
        client.post(base+'/collect',json={'idempotency_key':'alias-conflict','basis':'METHOD alias conflict fixture'})
        fact=client.get(base).json()['facts'][0]
        assert fact['association']['classification']=='UNCERTAIN'
        assert fact['association']['conflicts']
        assert {item['instrument'] for item in fact['association']['objects']}=={'SSE:600362','SZSE:000630'}
        assert all(item['ambiguous'] for item in fact['association']['objects'])
