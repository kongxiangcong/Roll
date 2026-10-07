"""Curated engineering archive import and host-filtered research partitions."""
import hashlib
import json
from pathlib import Path
from io import BytesIO
from uuid import uuid4
from datetime import datetime,timezone

import pyarrow as pa
import pyarrow.parquet as pq
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field
from roll.accounts.ledger import encode,now


class DatasetCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    archive_id:str=Field(pattern=r'^[a-z0-9][a-z0-9-]{0,39}$')
    basis:str=Field(min_length=1,max_length=2000)


def import_dataset(evidence,command):
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
    if value['state']!='HOST_FILTERED':raise HTTPException(409,'覆盖不足以支持该预定窗口，不临时缩窗')
    facts=[json.loads(r['payload']) for r in pq.read_table(evidence.raw(value['artifact']['sha256'])).to_pylist()]
    return {'dataset_id':dataset['dataset_id'],'namespace':'HISTORICAL','partition':name,'metadata':value,
        'facts':facts,'context_policy':'Leading20 calibration rows are feature context only; never fitted labels',
        'historical_point_in_time_proven':False,'capability':'NOT_GRANTED','consumer_knowledge_cutoff':now(),
        'availability_basis':'Consumers must compare original available_at with their own knowledge cutoff; request flag is not permanent',
        'all_available_to_this_consumer':all(f.get('available_at') and datetime.fromisoformat(f['available_at'])<=datetime.now(timezone.utc) for f in facts)}
