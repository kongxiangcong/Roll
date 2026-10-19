"""Actual isolated worker via public API over hash-verified real archived snippets; no METHOD hooks."""
import hashlib,json,os,uuid
from pathlib import Path
from datetime import datetime,timezone
from fastapi.testclient import TestClient
from roll.app import create_app
from roll.accounts.ledger import encode,now
p=Path(__file__).resolve().parent;b=p.parent;repo=p.parents[4]
f=json.loads((p/'runtime-freeze.json').read_bytes())
for name,h in f['files'].items():assert hashlib.sha256((repo/name).read_bytes()).hexdigest()==h,name
inputs=json.loads((p/'runtime-inputs.json').read_bytes())['rows']
destination=repo/'.scratch/r16-candidate-runtime01';assert not destination.exists();destination.mkdir()
os.environ['ROLL_SENTIMENT_PYTHON']=str(repo/'.scratch/rce-runtime/docling/Scripts/python.exe')
command={'idempotency_key':'real-research-runtime01','basis':'User-authorized actual local classification of12 hash-verified archived source snippets; no training/primary rows or METHOD worker','profile':'finbert-adaptation-01'}
with TestClient(create_app(destination,runtime_role='API')) as client:
 before=client.get('/api/account').json()['version']
 version=client.get('/api/market/list').json()['version']
 r=client.post('/api/market/watch',json={'operation':'ADD','instrument':'SSE:600362','expected_list_version':version});assert r.status_code==200,r.text
 r=client.post('/api/market/identities',json={'instrument':'SSE:600362','exchange':'SSE','board':'主板','instrument_type':'STOCK','name':'江西铜业股份有限公司','basis':'Existing authorized issuer identity confirmed by CNINFO secCode600362/orgIdgssh0600362; isolated research copy','effective_at':'2026-01-01T00:00:00+08:00'});assert r.status_code==200,r.text
 news=client.app.state.news;evidence=news.evidence;facts=[];stamp=now()
 for source in inputs:
  raw=(b/source['raw_path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==source['raw_sha256']
  archive=evidence.archive(raw,'ARCHIVED_NEWS_INDEX',source_id='RESEARCH_ARCHIVED_INDEX',source_url=None,source_record_url=source['url'],received_at=stamp,upstream_capture_path=source['raw_path'],evidence_kind='REAL_ARCHIVE_IMPORT',original_complete=True)
  fact={'fact_id':str(uuid.uuid5(uuid.NAMESPACE_URL,source['url']+'|'+source['source_input_sha256'])),'instrument':'SSE:600362','run_id':'REAL-ARCHIVE-MATERIALIZATION-01','source_id':'RESEARCH_ARCHIVED_INDEX','title':source['title'],'excerpt':source['summary'],'url':source['url'],'media':source.get('media'),'reported_published_at':source['date'],'publication_timezone':'UPSTREAM_REPORTED_NOT_HISTORICAL_PIT','first_received_at':stamp,'available_at':stamp,'list_sha256':archive['sha256'],'body_sha256':None,'body_status':'NOT_FETCHED_ARCHIVED_TITLE_SUMMARY_ONLY','body_text':None,'body_received_at':None,'extracted_metadata':None,'extractor_version':None,'original_fields':source,'evidence_kind':'REAL_ARCHIVE_IMPORT','errors':[],'historical_pit_eligible':False,'system_usable':False}
  with news.ledger.connection() as db:db.execute('INSERT INTO news_facts VALUES(?,?,?)',(fact['fact_id'],'SSE:600362',encode(fact)))
  facts.append(fact)
 assert news.worker is None and client.app.state.sentiment.worker is None
 response=client.post('/api/market/sentiment/SSE:600362/classify',json=command);assert response.status_code==201,response.text
 run=response.json();(p/'real-api-run.json').write_bytes(json.dumps(run,ensure_ascii=False,indent=2).encode())
 assert run['status']=='COMPLETE',run['errors']
 assert run['evidence_kind']=='REAL_LOCAL_CLASSIFICATION' and run['profile']=='finbert-adaptation-01'
 listing=client.get('/api/market/sentiment/SSE:600362');assert listing.status_code==200,listing.text
 assert listing.json()['run']==run
 assert client.post('/api/market/sentiment/SSE:600362/classify',json=command).json()==run
 assert client.get('/api/market/sentiment/runs/'+run['run_id']).json()==run
 after=client.get('/api/account').json()['version'];assert before==after==0
 summary={'status':'COMPLETE','evidence_kind':'REAL_LOCAL_CLASSIFICATION','source_kind':'REAL_ARCHIVE_IMPORT_NOT_PRODUCTION_SOURCE_ADMISSION','source_rows':12,'directory':str(destination),'run_id':run['run_id'],'counts':run['counts'],'coverage':run['coverage'],'network_calls':run['network_calls'],'account_before':before,'account_after':after,'worker_override':False,'training_or_primary_rows_loaded':False,'new_quality_claim':False,'object_features':['real other-issuer correction titles refused as no company object, not company-revision sentiment generalization','new current-price assertions and neutral board/share-count procedure','original source text and raw SHA retained']}
with TestClient(create_app(destination,runtime_role='API')) as client:
 assert client.get('/api/market/sentiment/runs/'+summary['run_id']).json()==run
 assert client.get('/api/market/sentiment/SSE:600362').json()['run']==run
 summary['restart_replay_identical']=True
(p/'real-api-summary.json').write_bytes(json.dumps(summary,ensure_ascii=False,indent=2).encode());print(json.dumps(summary,ensure_ascii=False,indent=2))
