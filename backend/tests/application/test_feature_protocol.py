"""METHOD protocol budgets and source versions, no fitting or SEALED inputs."""
import hashlib,json
from datetime import datetime,timedelta
from io import BytesIO
import pyarrow as pa
import pyarrow.parquet as pq
from fastapi.testclient import TestClient
from roll.app import create_app
from roll.accounts.ledger import now
from roll.research.models import code_fingerprint
from test_research_protocol import engineering_archive
from test_financial_metrics import prepare,income
from test_sentiment_series import collect,classify,P,COPY,N,setup

BASE='/api/research'


def parent(client,directory):
    engineering_archive(directory)
    root=directory/'research-inputs/method-181';path=root/'browser-live.json'
    value=json.loads(path.read_bytes())
    value['request']['identity_context']={'SSE:600362':{'exchange':'SSE','board':'MAIN','instrument_type':'STOCK'}}
    facts=value['snapshot']['facts']
    for fact in facts:fact['instrument']='SSE:600362'
    buffer=BytesIO();pq.write_table(pa.Table.from_pylist([{'payload':json.dumps(f)} for f in facts]),buffer)
    raw=buffer.getvalue();sha=hashlib.sha256(raw).hexdigest();(root/(sha+'.parquet')).write_bytes(raw)
    value['snapshot']['parquet'].update(sha256=sha,path='parquet/'+sha+'.parquet',bytes=len(raw))
    path.write_text(json.dumps(value),encoding='utf-8')
    dataset=client.post(BASE+'/datasets',json={'archive_id':'method-181','basis':'METHOD same-issuer metadata, no training'}).json()
    response=client.post(BASE+'/protocols',json={'dataset_id':dataset['dataset_id'],'basis':'METHOD original linked baseline'})
    assert response.status_code==201,response.text
    return response.json()


def plan(client,previous,key='features',variants=None):
    command={'predecessor_id':previous['protocol_id'],'idempotency_key':key,'basis':'METHOD preregistration before outcomes','variants':variants or ['BASELINE','FINANCIAL','SENTIMENT','BOTH']}
    response=client.post(BASE+'/feature-plans',json=command)
    assert response.status_code==201,response.text
    return response.json(),command


def snapshot(client,key='snapshot',**extra):
    command={'idempotency_key':key,'basis':'METHOD available source versions only','instrument':'SSE:600362','known_by':now(),**extra}
    response=client.post(BASE+'/feature-snapshots',json=command)
    assert response.status_code==201,response.text
    return response.json(),command


def test_linked_registration_snapshot_preflight_replay_preserves_original_model_and_seal(tmp_path,monkeypatch):
    original_code=code_fingerprint()
    with TestClient(create_app(tmp_path,runtime_role='API')) as client:
        previous=parent(client,tmp_path);prepare(client);setup(client)
        collect(client,monkeypatch,[P,N],'2026-10-15T14:00:00+08:00','seed')
        run=classify(client,monkeypatch,'2026-10-15T14:01:00+08:00','seed-classification','finbert-adaptation-01')
        series=client.post('/api/market/sentiment-series/SSE:600362',json={'idempotency_key':'seed-series','basis':'METHOD one checkpoint','source_run_id':run['run_id'],'start_date':'2026-10-15','end_date':'2026-10-15'}).json()
        frozen,command=plan(client,previous)
        assert frozen['variants']==['BASELINE','FINANCIAL','SENTIMENT','BOTH']
        child=client.get(BASE+'/protocols/'+frozen['protocol_id']).json()
        assert child['predecessor_id']==previous['protocol_id'] and child['dataset_id']==previous['dataset_id']
        assert frozen['inherited_design']==previous['design']
        assert frozen['calibration_allocation']['primary']=='FINANCIAL'
        assert frozen['inherited_design']['horizon_sessions']==20
        assert frozen['inherited_design']['stopping']['maximum_natural_months']==3
        assert client.get(BASE+'/protocols/'+previous['protocol_id']).json()==previous
        assert client.post(BASE+'/feature-plans',json=command).json()==frozen
        observed,snapshot_command=snapshot(client,series_id=series['series_id'])
        assert observed['financial']['debt_ratio']['value']=='65.475577'
        assert observed['financial']['cash_profit_ratio']['value']=='0.611974'
        assert observed['sentiment']['positive_share']['value']=='0.5'
        assert observed['sentiment']['neutral_share']['value']=='0'
        response=client.post(BASE+'/feature-plans/'+frozen['plan_id']+'/preflights',json={'idempotency_key':'preflight','snapshot_id':observed['snapshot_id']})
        assert response.status_code==201,response.text
        preflight=response.json()
        assert preflight['engineering_ready'] and not preflight['real_fit_admitted']
        assert 'METHOD_SNAPSHOT_NOT_REAL_TRAINING_INPUT' in preflight['fit_gaps']
        assert 'BASE_PRETRAINING_CORPUS_INTERVAL_UNKNOWN' in preflight['fit_gaps']
        assert not preflight['training_started'] and not preflight['sealed_read']
        assert client.post(BASE+'/feature-snapshots',json=snapshot_command).json()==observed
        assert client.get(BASE+'/protocols/'+previous['protocol_id']+'/attempts').json()==[]
        assert not any('SEALED' in event['action'] for event in client.get(BASE+'/protocols/'+previous['protocol_id']+'/audit').json())
        assert code_fingerprint()==original_code and client.get('/api/account').json()['version']==0
        missing,_=snapshot(client,'missing-series')
        refused=client.post(BASE+'/feature-plans/'+frozen['plan_id']+'/preflights',json={'idempotency_key':'missing-contract','snapshot_id':missing['snapshot_id']}).json()
        assert not refused['engineering_ready'] and 'SENTIMENT_MODEL_LABEL_REJECT_OR_CHECKPOINT_CHANGED_OR_MISSING' in refused['engineering_gaps']
        legacy=classify(client,monkeypatch,'2026-10-15T14:02:00+08:00','different-model','legacy')
        legacy_series=client.post('/api/market/sentiment-series/SSE:600362',json={'idempotency_key':'legacy-series','basis':'METHOD wrong model for pinned contract','source_run_id':legacy['run_id'],'start_date':'2026-10-15','end_date':'2026-10-15'}).json()
        wrong,_=snapshot(client,'different-model-snapshot',series_id=legacy_series['series_id'])
        wrong_preflight=client.post(BASE+'/feature-plans/'+frozen['plan_id']+'/preflights',json={'idempotency_key':'wrong-model','snapshot_id':wrong['snapshot_id']}).json()
        assert not wrong_preflight['engineering_ready'] and 'SENTIMENT_MODEL_LABEL_REJECT_OR_CHECKPOINT_CHANGED_OR_MISSING' in wrong_preflight['engineering_gaps']
    with TestClient(create_app(tmp_path,runtime_role='API')) as client:
        assert client.get(BASE+'/feature-plans/'+frozen['plan_id']).json()==frozen
        assert client.get(BASE+'/feature-snapshots/'+observed['snapshot_id']).json()==observed
        assert client.get(BASE+'/feature-preflights/'+preflight['preflight_id']).json()==preflight


def test_shared_budget_counts_failures_and_reservations_across_linked_siblings(tmp_path):
    with TestClient(create_app(tmp_path,runtime_role='API')) as client:
        previous=parent(client,tmp_path)
        for state in ('FAILED','ABORTED'):
            attempt=client.post(BASE+'/protocols/'+previous['protocol_id']+'/attempts',json={'category':'PRIMARY_FIT','partition':'DEVELOPMENT','configuration':{'candidate':'METHOD_NO_COMPUTE'},'basis':'METHOD budget record only'}).json()
            assert client.post(BASE+'/attempts/'+attempt['attempt_id']+'/finish',json={'status':state,'reason':'METHOD no fit executed'}).status_code==200
        response=client.post(BASE+'/feature-plans',json={'predecessor_id':previous['protocol_id'],'idempotency_key':'over','basis':'METHOD shared budget','variants':['BASELINE','FINANCIAL','SENTIMENT','BOTH']})
        assert response.status_code==409 and response.json()['detail']['code']=='FEATURE_FAMILY_BUDGET_INSUFFICIENT'
        frozen,_=plan(client,previous,variants=['BASELINE','FINANCIAL'])
        child=client.get(BASE+'/protocols/'+frozen['protocol_id']).json()
        response=client.post(BASE+'/feature-plans',json={'predecessor_id':child['protocol_id'],'idempotency_key':'sibling-over','basis':'METHOD no reset','variants':['SENTIMENT','BOTH']})
        assert response.status_code==409
        budget=client.get(BASE+'/feature-budget/'+child['protocol_id']).json()
        assert budget['fit_records_including_failed_aborted']==2 and budget['reserved_feature_configurations']==2 and budget['remaining_configurations']==1
        observed,_=snapshot(client)
        # A later original-core attempt consumes remaining unreserved budget;
        # an extra one makes the old registration explicitly unfit to execute.
        for index in range(2):
            assert client.post(BASE+'/protocols/'+child['protocol_id']+'/attempts',json={'category':'G5_NEIGHBOR','partition':'DEVELOPMENT','configuration':{'METHOD_record':index},'basis':'METHOD live budget change, no compute'}).status_code==201
        preflight=client.post(BASE+'/feature-plans/'+frozen['plan_id']+'/preflights',json={'idempotency_key':'after-budget-change','snapshot_id':observed['snapshot_id']}).json()
        assert not preflight['engineering_ready'] and 'FAMILY_BUDGET_CONSUMED_AFTER_REGISTRATION' in preflight['engineering_gaps']
        assert client.get(BASE+'/feature-plans/'+frozen['plan_id']).json()==frozen
        assert client.post(BASE+'/feature-plans',json={'idempotency_key':'new-root','basis':'METHOD prohibited','variants':['BASELINE']}).status_code==422


def test_later_financial_revision_cannot_backfill_old_snapshot_or_cutoff(tmp_path):
    with TestClient(create_app(tmp_path,runtime_role='API')) as client:
        prepare(client)
        old,command=snapshot(client)
        async def revise(instrument,output):
            manifest=await income(instrument,output)
            raw=json.loads((output/'03.raw').read_bytes())
            for row in raw['data']:
                if row['REPORT_DATE'].startswith('2026-06-30'):row['NETPROFIT']=0
            body=json.dumps(raw).encode();(output/'03.raw').write_bytes(body);manifest['captures'][2]['sha256']=hashlib.sha256(body).hexdigest()
            return manifest
        client.app.state.financial.worker=revise
        assert client.post('/api/market/financial/SSE:600362/income/collect',json={'idempotency_key':'revise','basis':'METHOD revision after old cutoff'}).json()['status']=='COMPLETE'
        new,_=snapshot(client,'new')
        assert new['financial']['cash_profit_ratio']['value'] is None
        replay,_=snapshot(client,'historical-reconstruction',known_by=command['known_by'])
        assert replay['financial']==old['financial'] and replay['financial_source_versions']==old['financial_source_versions']
        assert client.get(BASE+'/feature-snapshots/'+old['snapshot_id']).json()==old
        assert client.get('/api/account').json()['version']==0


def test_actual_supported_labels_event_denominator_and_future_series_refusal(tmp_path,monkeypatch):
    with TestClient(create_app(tmp_path,runtime_role='API')) as client:
        setup(client)
        rows=[P,COPY,N,('20261014123009','行业资金流出榜','600362 行业资金流出')]
        collect(client,monkeypatch,rows,'2026-10-15T14:00:00+08:00','news')
        run=classify(client,monkeypatch,'2026-10-15T14:01:00+08:00','classification')
        cutoff='2026-10-15T15:06:00+08:00'
        series=client.post('/api/market/sentiment-series/SSE:600362',json={'idempotency_key':'series','basis':'METHOD one supported checkpoint','source_run_id':run['run_id'],'start_date':'2026-10-15','end_date':'2026-10-15','known_by':cutoff}).json()
        observed,_=snapshot(client,series_id=series['series_id'],known_by=cutoff)
        assert observed['sentiment']['event_support']['value']==3
        assert abs(float(observed['sentiment']['positive_share']['value'])-1/3)<1e-12
        assert observed['sentiment']['positive_share']['value']=='0.3333333333333333333333333333'
        assert observed['sentiment']['neutral_share']=={'value':None,'reason':'LABEL_UNSUPPORTED'}
        assert abs(float(observed['sentiment']['rejection_share']['value'])-1/3)<1e-12
        command={'idempotency_key':'too-early','basis':'METHOD refusal','known_by':'2026-10-15T14:00:00+08:00','series_id':series['series_id']}
        assert client.post(BASE+'/feature-snapshots',json=command).status_code==409
        assert client.post(BASE+'/feature-snapshots',json={**command,'idempotency_key':'future','known_by':(datetime.fromisoformat(now())+timedelta(days=1)).isoformat()}).status_code==422
        assert client.post(BASE+'/feature-snapshots',json={**command,'idempotency_key':'naive','known_by':'2026-10-15T15:06:00'}).status_code==422
