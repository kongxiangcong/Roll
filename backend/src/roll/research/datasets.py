"""Verified host acquisitions and curated engineering research partitions."""
import hashlib
import json
from pathlib import Path
from io import BytesIO
from uuid import uuid4
from datetime import datetime,timezone

import pyarrow as pa
import pyarrow.parquet as pq
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field,model_validator
from roll.accounts.ledger import encode,now


class DatasetCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    archive_id:str|None=Field(default=None,pattern=r'^[a-z0-9][a-z0-9-]{0,39}$')
    source_run_id:str|None=Field(default=None,min_length=1,max_length=100)
    basis:str=Field(min_length=1,max_length=2000)

    @model_validator(mode='after')
    def source_is_unambiguous(self):
        if (self.archive_id is None)==(self.source_run_id is None):
            raise ValueError('Exactly one archive_id or source_run_id is required')
        return self


def import_dataset(evidence,command):
    if command.source_run_id is not None:return import_acquisition(evidence,command)
    source=evidence.directory/'research-inputs'/command.archive_id
    path=source/'browser-live.json'
    if not path.is_file():raise HTTPException(404,'宿主隔离目录中尚无该公开工程归档包')
    bundle=json.loads(path.read_text(encoding='utf-8'));snapshot=bundle['snapshot']
    originals=[]
    for archive in snapshot['archives']+[snapshot['parquet']]:
        original=source/(archive['sha256']+('.parquet' if archive is snapshot['parquet'] else '.raw'))
        if not original.is_file():raise HTTPException(409,'源归档缺失')
        content=original.read_bytes()
        if hashlib.sha256(content).hexdigest()!=archive['sha256']:raise HTTPException(409,'源归档SHA不一致')
        copied=evidence.archive(content,archive['kind'],extension='parquet' if archive is snapshot['parquet'] else 'raw',
            **{k:v for k,v in archive.items() if k not in {'sha256','path','kind','bytes'}})
        originals.append(copied)
    rows=[json.loads(r['payload']) for r in pq.read_table(evidence.raw(snapshot['parquet']['sha256'])).to_pylist()]
    if rows!=snapshot['facts']:raise HTTPException(409,'源Parquet与源快照事实不一致')
    daily=[f for f in rows if f['group']=='DAILY' and f.get('adjustment')=='RAW']
    instruments=sorted({f['instrument'] for f in daily})
    if len(instruments)!=1:raise HTTPException(422,'首轮仅登记一个有实际覆盖的明确证券，背景指数不作为个股候选')
    identity=bundle['request'].get('identity_context',{}).get(instruments[0],{})
    if identity.get('instrument_type')!='STOCK':raise HTTPException(422,'来源明确股票身份不足，不能将背景或未知类型作为个股研究')
    daily.sort(key=lambda f:f['trade_date']);dates=[f['trade_date'] for f in daily]
    if len(set(dates))!=len(dates):raise HTTPException(409,'同版原价日线重复，不能静默挑选')
    partitions={};supported=len(daily)>=181
    intervals={'DEVELOPMENT':(0,min(80,len(daily)),0),'CALIBRATION':(100,140,80),'SEALED':(160,len(daily),140)}
    for name,(start,end,context_start) in intervals.items():
        if name!='DEVELOPMENT' and not supported:
            partitions[name]={'state':'INSUFFICIENT_COVERAGE','rows':0};continue
        payload=daily[context_start:end]
        buffer=BytesIO();pq.write_table(pa.Table.from_pylist([{'payload':encode(f)} for f in payload]),buffer)
        artifact=evidence.archive(buffer.getvalue(),'RESEARCH_PARTITION',extension='parquet',partition=name,
            research_namespace='HISTORICAL',original_snapshot_id=snapshot['snapshot_id'])
        partitions[name]={'state':'HOST_FILTERED','rows':end-start,'context_rows':start-context_start,
            'first_date':dates[start],'last_date':dates[end-1],'context_first_date':dates[context_start],
            'artifact':artifact,'access':'EXPLICIT_AUDITED_SEALED_INPUT' if name=='SEALED' else 'DEVELOPMENT_OR_CALIBRATION_ONLY'}
    fingerprint=hashlib.sha256(encode({'original_sha':[r['sha256'] for r in originals],'source_version':snapshot['adapter_version'],
        'bundle_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'identity_context':identity,
        'partition_code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'partitions':{k:v.get('artifact',{}).get('sha256') for k,v in partitions.items()},'namespace':'HISTORICAL'}).encode()).hexdigest()
    return {'dataset_id':str(uuid4()),'registered_at':now(),'basis':command.basis,'archive_id':command.archive_id,
        'data_fingerprint':fingerprint,'source_run_id':bundle['run']['run_id'],'source_snapshot_id':snapshot['snapshot_id'],
        'source_bundle_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'source_adapter_version':snapshot['adapter_version'],'source_evidence_kind':snapshot['evidence_kind'],
        'scope':{'namespace':'HISTORICAL','instruments':instruments,'identity_context':{instruments[0]:identity},
            'selection':'TODAY_LIST_CONDITIONAL','historical_point_in_time_proven':False,'historical_membership_reconstructed':False,
            'source_account_authority':'ENGINEERING_SYNTHETIC; NO_REAL_USER_BASELINE_OR_FUNDING'},
        'coverage':{'session_count':len(dates),'first_date':dates[0],'last_date':dates[-1],
            'missing_amount_rows':sum(f.get('amount_yuan') is None for f in daily),
            'unknown_volume_unit_rows':sum(f.get('volume_unit')!='SHARE' for f in daily),
            'basic_error_rows':sum(bool(f.get('errors')) for f in daily)},
        'partitions':partitions,'original_archives':originals,
        'prior_seal_independence':'UNPROVEN','prior_exposure':'PUBLIC_ENGINEERING_ARCHIVE_ALREADY_AVAILABLE; NOT_PROVEN_UNSEEN',
        'engineering_exposure':json.loads((source/'engineering-exposure.json').read_text(encoding='utf-8')) if (source/'engineering-exposure.json').is_file() else None,
        'limitations':['CURRENT_PROVIDER_REVISION_NOT_HISTORICAL_PIT','HISTORICAL_SPECIAL_STATUS_UNKNOWN',
            'ENGINEERING_PRICE_INPUT_EXPOSURE_NOT_A_CONFIRMATORY_PASS_LOOK','UNKNOWN_ACTUAL_BROKER_COMMISSION',
            'HISTORICAL_AMOUNT_MISSING','HISTORICAL_SEAL_INDEPENDENCE_UNPROVEN'],
        'partition_basis':'181 available sessions:80 development,20 label embargo,40 calibration,20 label embargo,21 sealed; only metadata used to allocate',
        'label_results_computed':False,'validation_verdict':None,'capability':'NOT_GRANTED'}


def partition(evidence,dataset,name,allow_sealed=False):
    if name not in {'DEVELOPMENT','CALIBRATION'} and not (allow_sealed and name=='SEALED'):raise HTTPException(403,'封存输入须经记录理由的专用访问入口；不能获取整档后自行过滤')
    value=dataset['partitions'][name]
    if value['state']!='HOST_FILTERED':raise HTTPException(409,{'code':'RESEARCH_WINDOWS_NOT_PREREGISTERED' if value['state']=='NOT_PREREGISTERED' else 'INSUFFICIENT_PARTITION_COVERAGE','reason':'仅登记采集覆盖不授权训练窗口；不临时缩窗'})
    facts=[json.loads(r['payload']) for r in pq.read_table(evidence.raw(value['artifact']['sha256'])).to_pylist()]
    return {'dataset_id':dataset['dataset_id'],'namespace':'HISTORICAL','partition':name,'metadata':value,
        'facts':facts,'context_policy':'Leading20 calibration rows are feature context only; never fitted labels',
        'historical_point_in_time_proven':False,'capability':'NOT_GRANTED','consumer_knowledge_cutoff':now(),
        'availability_basis':'Consumers must compare original available_at with their own knowledge cutoff; request flag is not permanent',
        'all_available_to_this_consumer':all(f.get('available_at') and datetime.fromisoformat(f['available_at'])<=datetime.now(timezone.utc) for f in facts)}


def import_acquisition(evidence,command):
    """Register the exact committed acquisition; metadata coverage is not as-of proof."""
    run=evidence.get('retrieval_runs',command.source_run_id)
    if run['status'] not in {'COMPLETE','PARTIAL'} or not run.get('snapshot_id'):
        raise HTTPException(409,'来源运行尚无可登记的完成快照')
    request=evidence.get('data_requests',run['request_id'])
    snapshot=evidence.get('market_evidence_snapshots',run['snapshot_id'])
    if request['purpose']!='RESEARCH':raise HTTPException(422,'仅明确研究用途的宿主请求可登记为研究数据')
    if snapshot['run_id']!=run['run_id'] or snapshot['request_id']!=request['request_id']:
        raise HTTPException(409,'来源请求/运行/快照关联不一致')
    originals=snapshot['archives']+[snapshot['parquet']]
    for archive in originals:evidence.raw(archive['sha256'])
    # SDK-decoded responses remain linked to their captured socket originals.
    for archive in snapshot['archives']:
        if archive.get('decoded_hash'):evidence.raw(archive['decoded_hash'])
    rows=[json.loads(r['payload']) for r in pq.read_table(evidence.raw(snapshot['parquet']['sha256'])).to_pylist()]
    if rows!=snapshot['facts']:raise HTTPException(409,'源Parquet与源快照事实不一致')
    raw_hashes={a['sha256'] for a in snapshot['archives']}
    if any(r.get('raw_hash') not in raw_hashes for r in rows):raise HTTPException(409,'规范事实未绑定该快照原件')
    daily=sorted([r for r in rows if r['group']=='DAILY' and r.get('adjustment')=='RAW'],key=lambda r:r['trade_date'])
    instruments=sorted({r['instrument'] for r in daily})
    if len(instruments)!=1 or request['instruments']!=instruments:
        raise HTTPException(422,'首轮必须是一个有实际原价覆盖的明确证券，不混入背景或其他个股')
    instrument=instruments[0];identity=request.get('identity_context',{}).get(instrument,{})
    if identity.get('instrument_type')!='STOCK':raise HTTPException(422,'来源明确股票身份不足')
    dates=[r['trade_date'] for r in daily]
    if len(set(dates))!=len(dates):raise HTTPException(409,'同版原价日线重复，不能静默挑选')
    if any(not request['start_date']<=d<=request['end_date'] for d in dates):raise HTTPException(409,'日线日期超出来源请求范围')
    statuses=[r for r in rows if r['group']=='STATUS' and r['instrument']==instrument]
    calendars=[r for r in rows if r['group']=='CALENDAR']
    actions=[r for r in rows if r['group']=='ADJUSTMENTS' and r['instrument']==instrument]
    limitations=sorted({v for r in rows for key in ['limitations','historical_limitations'] for v in r.get(key,[])})
    blockers=['HISTORICAL_POINT_IN_TIME_NOT_PROVEN','COMPLETE_CORPORATE_ACTION_TREATMENT_NOT_PROVEN',
        'COMPLETE_HISTORICAL_EXECUTION_STATUS_NOT_PROVEN','HISTORICAL_RULE_COVERAGE_REQUIRES_VALIDATION',
        'RESEARCH_WINDOWS_NOT_PREREGISTERED','HISTORICAL_SEAL_INDEPENDENCE_UNPROVEN']
    if any(r.get('errors') or r.get('volume_unit')!='SHARE' or r.get('completion_state')!='COMPLETE_REPORTED_HISTORICAL' for r in daily):
        blockers.append('COMPLETE_DAILY_RAW_SHARE_INPUT_REQUIRED')
    if len(daily)<21:blockers.append('FEATURE_LOOKBACK_INSUFFICIENT')
    source_bundle={'request':request,'run':run,'snapshot':snapshot}
    source_sha=hashlib.sha256(encode(source_bundle).encode()).hexdigest()
    fingerprint=hashlib.sha256(encode({'source_bundle_sha256':source_sha,'original_sha256':[a['sha256'] for a in originals],
        'registration_code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}).encode()).hexdigest()
    return {'dataset_id':str(uuid4()),'registered_at':now(),'basis':command.basis,'archive_id':None,
        'source_origin':'HOST_DATA_REQUEST','source_run_id':run['run_id'],'source_snapshot_id':snapshot['snapshot_id'],
        'source_bundle_sha256':source_sha,'source_adapter_version':snapshot['adapter_version'],
        'source_evidence_kind':snapshot['evidence_kind'],'data_fingerprint':fingerprint,
        'scope':{'namespace':'HISTORICAL','instruments':instruments,'identity_context':{instrument:identity},
            'selection':'CURRENT_FINITE_LIST_CONDITIONAL_RESEARCH','historical_point_in_time_proven':False,
            'historical_membership_reconstructed':False,'source_account_authority':'NONE; MARKET_DATA_ONLY'},
        'coverage':{'session_count':len(dates),'first_date':dates[0],'last_date':dates[-1],
            'requested_start':request['start_date'],'requested_end':request['end_date'],
            'missing_amount_rows':sum(r.get('amount_yuan') is None for r in daily),
            'unknown_volume_unit_rows':sum(r.get('volume_unit')!='SHARE' for r in daily),
            'basic_error_rows':sum(bool(r.get('errors')) for r in daily),
            'incomplete_daily_rows':sum(r.get('completion_state')!='COMPLETE_REPORTED_HISTORICAL' for r in daily),
            'daily_sources':sorted({r['source_id'] for r in daily}),
            'status_rows':len(statuses),'status_reported_dates':len({r.get('trade_date') for r in statuses if r.get('trade_date')}),
            'calendar_rows':len(calendars),'company_action_rows':len(actions),
            'source_coverage':snapshot['coverage'],'source_gaps':snapshot['gaps'],
            'historical_as_of_versions_verified':False,'complete_status_verified':False,'complete_actions_verified':False},
        'partitions':{name:{'state':'NOT_PREREGISTERED','rows':0} for name in ['DEVELOPMENT','CALIBRATION','SEALED']},
        'original_archives':originals,'training_readiness':{'state':'BLOCKED','blockers':blockers,
            'basis':'Host verifies immutable acquisition bytes, not historical observation-time availability. Reported status/calendar/dividend dates are not complete execution or as-of proof.'},
        'prior_seal_independence':'UNPROVEN','prior_exposure':'SOURCE_ACQUISITION_VISIBLE; NO_UNUSED_FINAL_WINDOW_REGISTERED',
        'engineering_exposure':None,'limitations':sorted(set(limitations+blockers)),
        'partition_basis':'Coverage registration only. Old engineering80/40/21 layout is not silently reused for this actual acquisition.',
        'label_results_computed':False,'validation_verdict':None,'capability':'NOT_GRANTED'}
