from fastapi.testclient import TestClient
from roll.app import create_app
import hashlib
import json
from datetime import date,timedelta
from io import BytesIO
import pyarrow as pa
import pyarrow.parquet as pq
from concurrent.futures import ThreadPoolExecutor
import httpx
from test_market_directory import establish


def engineering_archive(directory):
    source=directory/'research-inputs'/'method-181';source.mkdir(parents=True)
    dates=[];day=date(2026,1,5)
    while len(dates)<181:
        if day.weekday()<5:dates.append(day.isoformat())
        day+=timedelta(days=1)
    raw=b'explicit fixed research archive method case'
    digest=hashlib.sha256(raw).hexdigest();(source/(digest+'.raw')).write_bytes(raw)
    facts=[{'instrument':'SSE:600519','group':'DAILY','adjustment':'RAW','trade_date':d,'raw_hash':digest,
        'open':'100','close':'100','high':'100','low':'100','volume_shares':'10000','volume_unit':'SHARE','amount_yuan':None,
        'available_at':'2026-10-08T00:00:00+08:00','namespace':'HISTORICAL','evidence_kind':'METHOD_CASE',
        'errors':[],'historical_limitations':['CURRENT_REVISION_NOT_PIT'],'limitations':['HISTORICAL_AMOUNT_NOT_RETURNED']} for d in dates]
    buffer=BytesIO();pq.write_table(pa.Table.from_pylist([{'payload':json.dumps(f)} for f in facts]),buffer)
    parquet=buffer.getvalue();pqhash=hashlib.sha256(parquet).hexdigest();(source/(pqhash+'.parquet')).write_bytes(parquet)
    (source/'browser-live.json').write_text(json.dumps({'request':{'identity_context':{'SSE:600519':{'exchange':'SSE','board':'MAIN','instrument_type':'STOCK'}}},
        'run':{'run_id':'method-source-run','evidence_kind':'METHOD_CASE'},'snapshot':{'snapshot_id':'method-source-snapshot',
        'adapter_version':'METHOD_FIXTURE','evidence_kind':'METHOD_CASE','facts':facts,'coverage':[],
        'archives':[{'sha256':digest,'path':'raw/'+digest+'.raw','kind':'RAW_RESPONSE','bytes':len(raw)}],
        'parquet':{'sha256':pqhash,'path':'parquet/'+pqhash+'.parquet','bytes':len(parquet),'kind':'NORMALIZED_PARQUET'}}}),encoding='utf-8')
    return dates


def test_actual_archive_import_registers_coverage_and_only_exposes_allowed_training_and_calibration_slices(tmp_path):
    dates=engineering_archive(tmp_path)
    with TestClient(create_app(tmp_path)) as client:
        response=client.post('/api/research/datasets',json={'archive_id':'method-181','basis':'固定181条机制验收，不宣称真实历史'})
        assert response.status_code==201,response.text
        dataset=response.json()
        assert dataset['coverage']['session_count']==181 and dataset['coverage']['first_date']=='2026-01-05'
        assert dataset['scope']['namespace']=='HISTORICAL' and not dataset['scope']['historical_point_in_time_proven']
        assert dataset['source_evidence_kind']=='METHOD_CASE' and dataset['prior_seal_independence']=='UNPROVEN'
        assert dataset['partitions']['DEVELOPMENT']['rows']==80
        assert dataset['partitions']['CALIBRATION']['rows']==40
        assert dataset['partitions']['SEALED']['rows']==21
        training=client.get('/api/research/datasets/'+dataset['dataset_id']+'/partitions/DEVELOPMENT').json()
        calibration=client.get('/api/research/datasets/'+dataset['dataset_id']+'/partitions/CALIBRATION').json()
        assert [f['trade_date'] for f in training['facts']]==dates[:80]
        assert [f['trade_date'] for f in calibration['facts']]==dates[80:140]  # prior20 are context, never fitted labels
        assert not any(f['trade_date']>=dates[160] for f in training['facts']+calibration['facts'])
        assert client.get('/api/research/datasets/'+dataset['dataset_id']+'/partitions/SEALED').status_code==403
        assert client.get('/api/account').json()['version']==0  # source engineering account is not imported as a user baseline


def test_protocol_registration_is_durable_draft_with_explicit_freeze_gaps_and_no_forward_start(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        response=client.post('/api/research/protocols',json={'basis':'依据实际覆盖准备M0，未执行最终检验'})
        assert response.status_code==201,response.text
        protocol=response.json()
        assert protocol['status']=='DRAFT' and protocol['validation_verdict'] is None
        assert protocol['forward_started_at'] is None and protocol['forward_deadline'] is None
        assert {'DATA_FINGERPRINT_MISSING','MODEL_ARTIFACT_MISSING','CALIBRATOR_ARTIFACT_MISSING','POLICY_ARTIFACT_MISSING'}<=set(protocol['freeze_gaps'])
        assert protocol['scope']['namespace']=='HISTORICAL' and protocol['capability']=='NOT_GRANTED'
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/research/protocols/'+protocol['protocol_id']).json()==protocol
        assert client.get('/api/research/protocols').json()==[protocol]


def test_metadata_grounded_design_registers_one_candidate_dependencies_costs_support_and_single_final_point(tmp_path):
    engineering_archive(tmp_path)
    with TestClient(create_app(tmp_path)) as client:
        dataset=client.post('/api/research/datasets',json={'archive_id':'method-181','basis':'方法数据'}).json()
        response=client.post('/api/research/protocols',json={'dataset_id':dataset['dataset_id'],'basis':'依据181条覆盖提出M0，不检查结果'})
        assert response.status_code==201,response.text
        protocol=response.json()
        assert protocol['status']=='DESIGN_REGISTERED'
        design=protocol['design']
        assert len(design['candidates'])==1 and design['horizon_sessions']==20
        assert design['primary_objective']['minimum_improvement_nav_return']=='0.0025'
        assert design['statistics']['pass_look_count']==1 and design['statistics']['minimum_effective_time_blocks']==30
        assert design['costs']['broker_actual_commission']=='UNKNOWN'
        assert design['costs']['commission_includes_regulatory_fees'] is True
        assert design['costs']['extra_regulatory_charge']=='0'
        assert design['stopping']['maximum_natural_months']==3
        assert design['support_projection']['sealed_mature_label_upper_bound']==1
        assert design['support_projection']['state']=='INSUFFICIENT_FOR_CONFIRMATORY_PASS'
        assert design['risk_policy_evidence']['owner']=='ticket22' and design['risk_policy_evidence']['inherits_profit_model_pass'] is False
        assert design['g5']['delays']==['NEXT_OPEN','NEXT_CLOSE','ONE_MORE_SESSION_OPEN','OUTSIDE_ALLOWED_PRICE_NO_FILL']
        assert design['formal_monitoring']['unmatured_results_scored'] is False
        assert 'MODEL_ARTIFACT_MISSING' in protocol['freeze_gaps'] and protocol['validation_verdict'] is None


def test_all_attempts_include_failure_abort_restart_and_omitted_manifest_refuses_freeze(tmp_path):
    engineering_archive(tmp_path)
    with TestClient(create_app(tmp_path)) as client:
        dataset=client.post('/api/research/datasets',json={'archive_id':'method-181','basis':'方法数据'}).json()
        protocol=client.post('/api/research/protocols',json={'dataset_id':dataset['dataset_id'],'basis':'全部尝试'}).json()
        pid=protocol['protocol_id'];attempts=[]
        for status in ['FAILED','ABORTED',None]:
            response=client.post('/api/research/protocols/'+pid+'/attempts',json={'category':'PRIMARY_FIT','partition':'DEVELOPMENT',
                'configuration':{'candidate_id':'PRICE_VOLUME_LOGIT_V1','features':['raw_return_20'],'threshold':'0.60','prompt':None},'basis':'固定失败/中止机制'})
            assert response.status_code==201,response.text
            attempt=response.json();attempts.append(attempt['attempt_id'])
            if status:
                finished=client.post('/api/research/attempts/'+attempt['attempt_id']+'/finish',json={'status':status,'reason':'明确失败或停止，无获胜选择'})
                assert finished.status_code==200,finished.text
        freeze=client.post('/api/research/protocols/'+pid+'/freeze',json={'attempt_ids':attempts[1:]})
        assert freeze.status_code==409 and 'ATTEMPT_MANIFEST_INCOMPLETE' in freeze.json()['detail']['gaps']
        assert client.get('/api/research/protocols/'+pid).json()==protocol  # protocol content is immutable
    with TestClient(create_app(tmp_path)) as client:
        items=client.get('/api/research/protocols/'+pid+'/attempts').json()
        assert [a['status'] for a in items]==['FAILED','ABORTED','INTERRUPTED']
        assert [a['attempt_id'] for a in items]==attempts
        audit=client.get('/api/research/protocols/'+pid+'/audit').json()
        assert any(a['action']=='FREEZE_REFUSED' and 'ATTEMPT_MANIFEST_INCOMPLETE' in a['gaps'] for a in audit)
        assert any(a['action']=='ATTEMPT_INTERRUPTED' for a in audit)
        freeze=client.post('/api/research/protocols/'+pid+'/freeze',json={'attempt_ids':attempts})
        assert freeze.status_code==409 and 'MODEL_ARTIFACT_MISSING' in freeze.json()['detail']['gaps']
        assert 'ATTEMPT_MANIFEST_INCOMPLETE' not in freeze.json()['detail']['gaps']
        successor=client.post('/api/research/protocols',json={'dataset_id':dataset['dataset_id'],'predecessor_id':pid,'basis':'关联后继不能隐藏原失败'}).json()
        freeze=client.post('/api/research/protocols/'+successor['protocol_id']+'/freeze',json={'attempt_ids':[]})
        assert 'ATTEMPT_MANIFEST_INCOMPLETE' in freeze.json()['detail']['gaps']
        manifest=client.get('/api/research/protocols/'+successor['protocol_id']+'/attempt-manifest').json()
        assert manifest['attempt_ids']==attempts and manifest['lineage']==[pid,successor['protocol_id']]


def test_sealed_input_download_and_reuse_are_audited_without_creating_a_pass_look(tmp_path):
    dates=engineering_archive(tmp_path)
    with TestClient(create_app(tmp_path)) as client:
        dataset=client.post('/api/research/datasets',json={'archive_id':'method-181','basis':'方法输入'}).json()
        protocol=client.post('/api/research/protocols',json={'dataset_id':dataset['dataset_id'],'basis':'初始协议'}).json();pid=protocol['protocol_id']
        response=client.post('/api/research/protocols/'+pid+'/sealed-input',json={'reason':'工程输入核验，无标签/候选策略结果'})
        assert response.status_code==200,response.text
        assert [f['trade_date'] for f in response.json()['facts']]==dates[140:]
        assert response.json()['confirmatory_pass_look'] is False
        original=dataset['original_archives'][-1]['sha256']
        download=client.get('/api/data/archives/'+original)
        assert download.status_code==200 and hashlib.sha256(download.content).hexdigest()==original
        assert download.headers['x-content-type-options']=='nosniff'
        audit=client.get('/api/research/protocols/'+pid+'/audit').json()
        assert any(e['action']=='SEALED_INPUT_ACCESSED' and not e['confirmatory_pass_look'] for e in audit)
        assert any(e['action']=='ORIGINAL_ARCHIVE_EXPOSED' for e in audit)
        unlinked=client.post('/api/research/protocols',json={'dataset_id':dataset['dataset_id'],'basis':'看过后改参数又取新名称'})
        assert unlinked.status_code==409
        successor=client.post('/api/research/protocols',json={'dataset_id':dataset['dataset_id'],'predecessor_id':pid,'basis':'政策修正须关联原协议'}).json()
        assert successor['predecessor_id']==pid and successor['sealed_independence']=='UNPROVEN'
        assert client.get('/api/research/protocols/'+pid).json()==protocol


def test_optional_stopping_and_result_access_cannot_manufacture_pass_or_forward_start(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        protocol=client.post('/api/research/protocols',json={'basis':'无完整研究，检查可选停止拒绝'}).json();pid=protocol['protocol_id']
        operational=client.post('/api/research/protocols/'+pid+'/checkpoints',json={'kind':'OPERATIONS','reason':'数据获取失败，限制能力'})
        assert operational.status_code==201 and operational.json()['confirmatory_pass_look'] is False
        for kind in ['EARLY_PASS','STATISTICAL_FINAL']:
            response=client.post('/api/research/protocols/'+pid+'/checkpoints',json={'kind':kind,'reason':'不能临时增加可判PASS查看'})
            assert response.status_code==409
        audit=client.get('/api/research/protocols/'+pid+'/audit').json()
        assert any(e['action']=='OPTIONAL_STOPPING_DEVIATION' for e in audit)
        assert any(e['action']=='RESULT_ACCESS_REFUSED' for e in audit)
        assert client.get('/api/research/protocols/'+pid).json()==protocol
        for start,expected in [('2026-01-31T15:30:00+08:00','2026-04-30T15:30:00+08:00'),('2023-11-30T15:30:00+08:00','2024-02-29T15:30:00+08:00')]:
            preview=client.get('/api/research/deadline-preview',params={'start':start})
            assert preview.status_code==200 and preview.json()['deadline']==expected
            assert preview.json()['actual_forward_start'] is False


def test_attempt_budget_and_concurrent_completion_preserve_exactly_one_terminal_record(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        pid=client.post('/api/research/protocols',json={'basis':'有界方法验收'}).json()['protocol_id'];ids=[]
        for _ in range(5):
            response=client.post('/api/research/protocols/'+pid+'/attempts',json={'category':'PRIMARY_FIT','partition':'DEVELOPMENT','configuration':{'threshold':'0.60'},'basis':'固定有界尝试'})
            assert response.status_code==201;ids.append(response.json()['attempt_id'])
        over=client.post('/api/research/protocols/'+pid+'/attempts',json={'category':'PRIMARY_FIT','partition':'DEVELOPMENT','configuration':{'threshold':'0.70'},'basis':'超限不能隐去'})
        assert over.status_code==409
        with ThreadPoolExecutor(2) as pool:
            results=list(pool.map(lambda status:client.post('/api/research/attempts/'+ids[0]+'/finish',json={'status':status,'reason':'并发不能改写终态'}).status_code,['FAILED','SUCCEEDED']))
        assert sorted(results)==[200,409]
        audit=client.get('/api/research/protocols/'+pid+'/audit').json()
        assert sum(e['action']=='ATTEMPT_FINISHED' and e['attempt_id']==ids[0] for e in audit)==1
        assert any(e['action']=='ATTEMPT_BUDGET_REFUSED' and e['configuration']['configuration']['threshold']=='0.70' for e in audit)


def test_corrupt_original_is_refused_without_registering_research_data(tmp_path):
    engineering_archive(tmp_path)
    original=next((tmp_path/'research-inputs'/'method-181').glob('*.raw'));original.write_bytes(b'changed after fingerprint')
    with TestClient(create_app(tmp_path)) as client:
        response=client.post('/api/research/datasets',json={'archive_id':'method-181','basis':'指纹拒绝'})
        assert response.status_code==409 and 'SHA' in response.text
        assert client.get('/api/research/datasets').json()==[]
        assert client.post('/api/research/datasets',json={'archive_id':'../escape','basis':'路径拒绝'}).status_code==422


def test_existing_market_query_and_offline_replay_audit_sealed_inputs_without_a_result_look(tmp_path):
    dates=engineering_archive(tmp_path);calls=[]
    def provider(request):
        calls.append(str(request.url));mode=request.url.params['param'].split(',')[-1]
        return httpx.Response(200,json={'code':0,'data':{'sh600519':{('qfqday' if mode else 'day'):[[dates[160],'100','100','100','100','100'],[dates[161],'80','80','80','80','100']]}}})
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(provider))) as client:
        dataset=client.post('/api/research/datasets',json={'archive_id':'method-181','basis':'方法源日期边界'}).json()
        protocol=client.post('/api/research/protocols',json={'dataset_id':dataset['dataset_id'],'basis':'公开市场路径也须留暴露'}).json();pid=protocol['protocol_id']
        establish(client,['SSE:600519'])
        client.post('/api/market/identities',json={'instrument':'SSE:600519','exchange':'SSE','board':'MAIN','instrument_type':'STOCK','basis':'固定方法明确身份','effective_at':'2026-01-05T00:00:00+08:00'})
        request=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['DAILY'],'purpose':'RESEARCH',
            'start_date':dates[160],'end_date':dates[161],'daily_source':'TENCENT'}).json()
        run=client.post('/api/data/requests/'+request['request_id']+'/retrieve').json()
        assert not any(e['action']=='SEALED_MARKET_INPUT_EXPOSED' for e in client.get('/api/research/protocols/'+pid+'/audit').json())  # run metadata contains no delivered facts
        assert client.get('/api/data/snapshots/'+run['snapshot_id']).status_code==200
        assert client.get('/api/data/snapshots').status_code==200
        assert client.get('/api/data/observations').status_code==200
        before=len(calls);assert client.post('/api/data/runs/'+run['run_id']+'/replay').status_code==200
        assert len(calls)==before
        audit=client.get('/api/research/protocols/'+pid+'/audit').json()
        exposed=[e for e in audit if e['action']=='SEALED_MARKET_INPUT_EXPOSED']
        assert {e['route'] for e in exposed}=={'snapshot-query','snapshots-query','run-replay','observations-query'}
        assert all(e['confirmatory_pass_look'] is False and e['first_date']>=dates[160] for e in exposed)
        assert client.get('/api/research/protocols/'+pid).json()==protocol


def test_codex_actual_tool_input_delivery_is_audited_before_worker_receives_facts(tmp_path,monkeypatch):
    from test_codex_evidence import WORKER,terminal
    directory=tmp_path/'data';dates=engineering_archive(directory)
    monkeypatch.setenv('ROLL_ENV','test')
    credential=tmp_path/'method-chatgpt.json';credential.write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'METHOD_CASE_ONLY'}}))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE',str(credential))
    worker=tmp_path/'method-worker.py';worker.write_text(WORKER,encoding='utf-8')
    def provider(request):
        mode=request.url.params['param'].split(',')[-1]
        return httpx.Response(200,json={'code':0,'data':{'sh600519':{('qfqday' if mode else 'day'):[[dates[160],'100','100','100','100','100']]}}})
    with TestClient(create_app(directory,market_transport=httpx.MockTransport(provider),codex_worker=worker)) as client:
        dataset=client.post('/api/research/datasets',json={'archive_id':'method-181','basis':'固定模型工具边界'}).json()
        pid=client.post('/api/research/protocols',json={'dataset_id':dataset['dataset_id'],'basis':'送模型前审计输入'}).json()['protocol_id']
        establish(client,['SSE:600519'])
        client.post('/api/market/identities',json={'instrument':'SSE:600519','exchange':'SSE','board':'MAIN','instrument_type':'STOCK','basis':'固定身份','effective_at':'2026-01-05T00:00:00+08:00'})
        request=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['DAILY'],'purpose':'RESEARCH','start_date':dates[160],'end_date':dates[160],'daily_source':'TENCENT'}).json()
        run=client.post('/api/data/requests/'+request['request_id']+'/codex',json={'question':'READ DAILY METHOD_CASE; no labels or strategy results'}).json()
        result=terminal(client,run['run_id']);assert result['status']=='COMPLETE' and result['evidence_kind']=='METHOD_CASE_CODEX',result
        exposed=[e for e in client.get('/api/research/protocols/'+pid+'/audit').json() if e['action']=='SEALED_MARKET_INPUT_EXPOSED']
        assert any(e['route']=='codex-tool-input' and e['rows']==2 and e['confirmatory_pass_look'] is False for e in exposed)
