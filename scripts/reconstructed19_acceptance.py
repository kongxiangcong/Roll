"""Actual archived-source ticket19 acceptance, resumable stages without refit/search."""
import argparse,hashlib,json,os,sqlite3
from pathlib import Path
from uuid import uuid4
from datetime import date
from collections import Counter
from io import BytesIO

import pyarrow as pa
import pyarrow.parquet as pq
from fastapi.testclient import TestClient
from roll.accounts.ledger import encode,now
from roll.app import create_app
from roll.market.baostock import daily
from roll.market.evidence import decimal_value
from roll.research.models import features,code_fingerprint
from roll.research import reconstruction

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'.scratch/roll-p0/evidence/19-reconstruction-2026-10-10';OUT=BASE
DATA=ROOT/'.roll-data/reconstructed19-v1'
STATE=OUT/'run-state.json'

def save(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def call(client,method,path,body=None,status=200):
    r=client.request(method,'/api'+path,json=body)
    if r.status_code!=status:raise RuntimeError(f'{method} {path}: {r.status_code} {r.text[:1800]}')
    return r.json()

def register_captures(app):
    evidence=app.state.evidence;directory=OUT/'status-collection';receipt=json.loads((directory/'receipt.json').read_text())
    wire=(directory/'daily.wire').read_bytes();body=(directory/'decoded.json').read_bytes();payload=json.loads(body)
    assert hashlib.sha256(wire).hexdigest()==receipt['wire_sha256'] and hashlib.sha256(body).hexdigest()==receipt['decoded_sha256']
    decoded=evidence.archive(body,'BAOSTOCK_DECODED_RESPONSE',research_namespace='HISTORICAL')
    raw=evidence.archive(wire,'BAOSTOCK_ORIGINAL_SOCKET_RESPONSE',source_id='baostock-daily',source_url='https://www.baostock.com/mainContent?file=stockKData.md',
        received_at=payload['received_at'],published_at=None,evidence_kind='REAL_ACQUISITION',decoded_hash=decoded['sha256'],research_namespace='HISTORICAL')
    request={'request_id':str(uuid4()),'purpose':'RESEARCH','instruments':['SSE:600362'],'groups':['DAILY','STATUS'],
        'start_date':'2016-12-01','end_date':'2023-12-31','created_at':receipt['started_at'],'cutoff':payload['received_at']}
    facts,coverage=daily(payload,raw,'SSE:600362',request,decimal_value,include_status=True)
    buffer=BytesIO();pq.write_table(pa.Table.from_pylist([{'payload':encode(f)} for f in facts]),buffer)
    parquet=evidence.archive(buffer.getvalue(),'NORMALIZED_PARQUET',extension='parquet')
    run={'run_id':str(uuid4()),'request_id':request['request_id'],'status':'COMPLETE','snapshot_id':str(uuid4()),'evidence_kind':'REAL_ACQUISITION',
        'started_at':receipt['started_at'],'finished_at':receipt['finished_at'],'network_calls':receipt['calls']}
    snapshot={'snapshot_id':run['snapshot_id'],'run_id':run['run_id'],'request_id':request['request_id'],'facts':facts,'archives':[raw,decoded],
        'parquet':parquet,'coverage':coverage,'gaps':[],'evidence_kind':'REAL_ACQUISITION','adapter_version':'baostock-sdk-v1','created_at':payload['received_at']}
    with app.state.ledger.connection() as db:
        db.execute('BEGIN IMMEDIATE');db.execute('INSERT INTO data_requests VALUES(?,?)',(request['request_id'],encode(request)))
        db.execute('INSERT INTO retrieval_runs VALUES(?,?,?)',(run['run_id'],request['request_id'],encode(run)))
        db.execute('INSERT INTO market_evidence_snapshots VALUES(?,?,?)',(snapshot['snapshot_id'],run['run_id'],encode(snapshot)));db.commit()
    imports=json.loads((OUT/'reference-imports.json').read_text(encoding='utf-8'))
    for item in imports:
        body=Path(item['path']).read_bytes();assert hashlib.sha256(body).hexdigest()==item['metadata']['sha256']
        evidence.archive(body,item['kind'],extension='pdf',**item['metadata'])
    return run['run_id']

def main():
    global OUT,STATE
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['clean','labels','fit','verify']);parser.add_argument('--final-version',action='store_true');args=parser.parse_args()
    if args.final_version:
        OUT=BASE/'v4';OUT.mkdir(exist_ok=True);STATE=OUT/'run-state.json'
    os.environ['ROLL_ENV']='test'
    if args.stage=='clean' and not (BASE/'isolated-runtime-detachment.json').exists():
        # An opaque database backup copies the source's ephemeral review-worker lock.
        # No queued work exists. Rebind only this lock in the isolated copy; history stays.
        with sqlite3.connect(DATA/'roll.sqlite3') as db:
            pending=[json.loads(r[0])['status'] for r in db.execute('SELECT value FROM review_tasks')]
            assert not any(s in {'QUEUED','RUNNING'} for s in pending)
            worker_rows=list(db.execute('SELECT * FROM review_worker'))
            save('isolated-runtime-detachment.json',{'purpose':'Detach source host ephemeral lock in opaque isolated copy only',
                'original_worker_rows_sha256':hashlib.sha256(encode(worker_rows).encode()).hexdigest(),'history_or_budget_modified':False,'original_database_modified':False})
            db.execute('DELETE FROM review_worker')
    app=create_app(DATA)
    with TestClient(app) as client:
        state=json.loads(STATE.read_text()) if STATE.exists() else {}
        if args.stage=='clean':
            if state:raise RuntimeError('Existing admission preserved; use subsequent stage rather than overwrite')
            before=call(client,'GET','/research/protocols/a9792e33-98e1-464e-85ba-046623fb4bd1/attempt-manifest')
            assert sum(a['category']=='PRIMARY_FIT' for a in before['attempts'])==2 and not any(a['category']=='CALIBRATION' for a in before['attempts'])
            previous=json.loads((BASE/'v3/run-state.json').read_text()) if args.final_version else None
            status_id=previous['status_run_id'] if previous else register_captures(app);state['status_run_id']=status_id;save('capture-state.json',state)
            strict=client.post('/api/research/datasets/b34112c8-7eea-4367-acbd-73dba0b8f296/reconstruct',json={'status_run_id':status_id,'data_use':'STRICT_HISTORICAL_AS_OF','basis':'Actual current history cannot obtain strict PIT'})
            assert strict.status_code==409
            dataset=call(client,'POST','/research/datasets/b34112c8-7eea-4367-acbd-73dba0b8f296/reconstruct',
                {'status_run_id':status_id,'basis':'ADR0004 actual Wind primary + public BaoStock statuses + issuer cash/annual audit; finite coverage windows, no strictPIT/qualification'},201)
            save('dataset.json',dataset)
            protocol=call(client,'POST','/research/protocols',{'dataset_id':dataset['dataset_id'],'predecessor_id':previous['protocol_id'] if previous else 'a9792e33-98e1-464e-85ba-046623fb4bd1',
                'basis':'ADR0004 approved reconstruction; v4 checks protected ranges over whole source containers and preserves null-price suspension semantics, HALF_UP tax/dependent engine hashes before any real fit. Identical sources/windows/candidate; retain v2/v3 preflight records and all shared failed fits/exposure/budget; no outcome-based selection, SEALED or formal/forward use'},201)
            state.update(dataset_id=dataset['dataset_id'],protocol_id=protocol['protocol_id'],source_dataset_id=dataset['parent_dataset_id'],
                code_fingerprint=code_fingerprint(),reconstruction_fingerprint=reconstruction.fingerprint(),strict_pit_rejected=True,budget_before=before)
            save('protocol.json',protocol);save('run-state.json',state)
            report=json.loads(app.state.evidence.raw(dataset['quality_report_archive']['sha256']).read_text(encoding='utf-8'));save('quality-report.json',report)
            print(json.dumps({k:v for k,v in report.items() if k not in {'per_date_fields','windows'}},ensure_ascii=False))
        elif args.stage=='labels':
            dataset=call(client,'GET','/research/datasets/'+state['dataset_id']);pid=state['protocol_id']
            summaries={};feature_dates={}
            for name in ['DEVELOPMENT','CALIBRATION']:
                part=call(client,'GET',f'/research/datasets/{state["dataset_id"]}/partitions/{name}')
                feature_dates[name]=[]
                prior=call(client,'GET',f'/research/protocols/{pid}/execution-support?partition={name}')
                old_dates={r['observation_date'] for r in prior['records']}
                for row in part['facts']:
                    day=row['trade_date']
                    if not part['metadata']['first_date']<=day<=part['metadata']['last_date']:continue
                    try:
                        snapshot=features(part['facts'],day,False,part['consumer_knowledge_cutoff']);app.state.models.check_feature_calendar(snapshot,call(client,'GET','/research/protocols/'+pid))
                        feature_dates[name].append(day)
                    except ValueError:pass
                    if day in old_dates:continue
                    call(client,'POST',f'/research/protocols/{pid}/executions',{'partition':name,'observation_date':day,'basis':'Actual20-session RAW single-opportunity economic label, keep unresolved/boundary/missed cases; no portfolio policy'},201)
                support=call(client,'GET',f'/research/protocols/{pid}/execution-support?partition={name}')
                summaries[name]={k:v for k,v in support.items() if k!='records'}
                save(name.lower()+'-label-index.json',[{'execution_id':r['execution_id'],'date':r['observation_date'],'maturity':r['result']['maturity_date'],
                    'status':r['result']['label_status'],'label':r['result']['label'],'eligible':r['result']['eligible_for_training'],'reasons':r['result']['reasons'],'input_sha256':r['input_sha256']} for r in support['records']])
                print(name,json.dumps(summaries[name],ensure_ascii=False),flush=True)
            save('label-support.json',summaries);save('feature-dates.json',feature_dates)
            preflight=call(client,'GET',f'/research/protocols/{pid}/training-preflight');save('actual-preflight.json',preflight)
            print(json.dumps({'ready_to_fit':preflight['ready_to_fit'],'blockers':preflight['blockers'],'support':preflight.get('support'),'budget':preflight['budget']},ensure_ascii=False),flush=True)
            assert preflight['ready_to_fit'],preflight['blockers']
        elif args.stage=='fit':
            if state.get('model_run_id'):raise RuntimeError('Already fitted; never repeat a CAL fit')
            pid=state['protocol_id'];preflight=call(client,'GET',f'/research/protocols/{pid}/training-preflight');assert preflight['ready_to_fit']
            save('fit-admission.json',preflight)
            model=call(client,'POST',f'/research/protocols/{pid}/models',{'purpose':'RESEARCH','basis':'Single preregistered real reconstructed-price-volume fit lambda1 /20-session NEXT_OPEN; fixed intercept CAL, old family failures/budget retained'},201)
            save('real-model.json',model);state['model_run_id']=model['model_run_id'];state['fitted_code_fingerprint']=model['code_fingerprint'];save('run-state.json',state)
            assert model['status']=='RESEARCH_ARTIFACT_FROZEN',model['reasons']
            day=model['calibration_predictions'][0]['observation_date']
            forecast=call(client,'POST',f'/research/models/{model["model_run_id"]}/forecasts',{'observation_date':day,'basis':'Actual historical CAL research prediction; reconstruction not contemporaneous publication or forward start'},201)
            save('real-forecast.json',forecast);state['forecast_id']=forecast['forecast_id'];save('run-state.json',state)
            print(json.dumps({'model_run_id':model['model_run_id'],'status':model['status'],'support':model['statistical_support'],'fingerprints':model['artifact_fingerprints'],'freeze':model['freeze_manifest']},ensure_ascii=False))
        else:
            model=call(client,'GET','/research/models/'+state['model_run_id']);forecast=call(client,'GET','/research/forecasts/'+state['forecast_id'])
            assert model==json.loads((OUT/'real-model.json').read_text(encoding='utf-8'));assert forecast==json.loads((OUT/'real-forecast.json').read_text(encoding='utf-8'))
            replay=call(client,'POST','/research/forecasts/'+state['forecast_id']+'/replay');assert replay['network_calls']==0 and replay['matches_original']
            protocol=call(client,'GET','/research/protocols/'+state['protocol_id']);assert protocol['forward_started_at'] is None and protocol['capability']=='NOT_GRANTED'
            events=call(client,'GET','/research/protocols/'+state['protocol_id']+'/audit');actions=[e['action'] for e in events]
            pre=actions.index('MODEL_PRECALIBRATION_PREDICTIONS_ARCHIVED');cal=next(i for i,e in enumerate(events) if e['action']=='ATTEMPT_STARTED' and e['configuration']['category']=='CALIBRATION');assert pre<cal
            assert not any('SEALED_INPUT_ACCESSED'==e['action'] for e in events)
            manifest=call(client,'GET','/research/protocols/'+state['protocol_id']+'/attempt-manifest')
            assert len(manifest['attempts'])==4 and [a['category'] for a in manifest['attempts']].count('CALIBRATION')==1
            for archive in [model['input_archive'],model['model_artifact'],model['calibrator_artifact'],model['calibration_prediction_archive'],model['calibrated_prediction_archive'],model['freeze_manifest'],forecast['archive']]:
                app.state.evidence.raw(archive['sha256'])
            save('restart-replay.json',{'passed':True,'replay':replay,'precalibration_archive_event_index':pre,'cal_attempt_event_index':cal,'attempt_manifest':manifest,
                'real_non_method_model':model['evidence_kind']=='REAL_ACQUISITION','calibrator_fit_status':model['calibrator_fit_status'],'full_experiment_frozen':False,
                'formal_capability':protocol['capability'],'forward_started_at':None,'protected_sealed_consumed':False,'verified_at':now()})
            print(json.dumps(replay,ensure_ascii=False))

if __name__=='__main__':main()
