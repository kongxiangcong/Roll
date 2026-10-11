"""Independent literal contracts, public calls on newly owned SQLite only."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json,hashlib,sqlite3
import httpx
from fastapi.testclient import TestClient
from roll.app import create_app
from roll.decisions.capabilities import current_presentation
from capability_method_app import save_package
from test_action_risk_priority import method_clock,setup
from action_order_method import paired_package,grant_command
from test_actions import action_package,prepare
from test_intents import intent_command
from test_account import submit,permission_change
from test_fills import fill
from test_lifecycle_composition import risk_package
from test_reconcile import reconcile,broker_snapshot
from test_funding import funding
from test_capabilities import method_command
from report_method_app import copy_donor,FREEZE

ROOT=Path('D:/dsh-proj/Roll');TREE=ROOT/'.scratch/worktrees/final-review-fix'
OUT=ROOT/'.scratch/roll-p0/evidence/continuation-2026-10-11/final-singlefix-independent'
def capture(name,value):
    (OUT/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def client_for(directory,file=None):
    def forbidden(request):raise AssertionError('Independent acceptance prohibits external HTTP: '+str(request.url))
    return TestClient(create_app(directory,runtime_role='API',capability_method_file=file,market_transport=httpx.MockTransport(forbidden),notification_transport=httpx.MockTransport(forbidden)))
def posted(client,url,body,status=201):
    result=client.post(url,json=body);assert result.status_code==status,result.text
    return result.json()

def test_current_headlines_keep_method_pause_and_restore_separate(tmp_path,monkeypatch):
    method_clock(monkeypatch);package=paired_package();file=save_package(tmp_path/'method.json',package)
    directory=tmp_path/'data'
    with client_for(directory,file) as client:
        initial=client.get('/api/capabilities').json()
        assert initial['headline']=='交易判断未启用' and initial['formal_judgment']=='DISABLED'
        setup(client,package)
        grant=posted(client,'/api/capabilities/grants',grant_command(package,'independent-profit'))
        active=client.get('/api/capabilities').json()
        assert active['headline']=='METHOD 工程能力有效，实际交易判断未启用'
        assert active['formal_judgment']=='DISABLED' and active['formal_capabilities']==[]
        assert active['method_capabilities'][0]['basis_type']=='PROFIT_MODEL'
        assert active['method_capabilities'][0]['system_usable'] is False
        assert client.get('/api/today').json()['technical_capability']['headline']==active['headline']
        posted(client,'/api/capabilities/lifecycle',{'grant_id':grant['grant_id'],'scope':'MODEL','state':'SUSPENDED','reason_code':'USER_PAUSE','reason':'independent METHOD pause','expected_version':0,'idempotency_key':'independent-pause'},200)
        paused=client.get('/api/capabilities').json()
        assert paused['headline']=='能力已暂停，交易判断未启用' and paused['method_capabilities']==[]
        backup=client.post('/api/runtime/backups');assert backup.status_code==201
        archive=client.get('/api/runtime/backups/'+backup.json()['backup_id']+'/export');assert archive.status_code==200
        staged=client.post('/api/runtime/restores',content=archive.content,headers={'content-type':'application/zip'});assert staged.status_code==202,staged.text
    with client_for(directory,file) as client:
        restored=client.get('/api/capabilities').json()
        assert restored['runtime_state']=='RECOVERY_LOCK' and restored['headline']=='恢复锁生效，交易判断未启用'
        assert restored['formal_judgment']=='DISABLED' and restored['formal_capabilities']==restored['method_capabilities']==[]
        assert client.get('/api/today').json()['technical_capability']['headline']==restored['headline']
    capture('public-headlines',{'initial':initial,'active':active,'paused':paused,'restored':restored})

def test_pure_formal_basis_and_default_fold_do_not_create_grants():
    results=[]
    for kinds,label in [(['RISK_POLICY'],'独立降风险能力有效，收益判断未启用'),(['PROFIT_MODEL'],'收益判断能力有效'),(['RISK_POLICY','PROFIT_MODEL'],'收益判断与独立降风险能力有效')]:
        statuses=[{'state':'GRANTED','reasons':[],'allowed_actions':['REDUCE'] if kind=='RISK_POLICY' else ['BUY'],'grant':{'candidate_kind':kind,'grant_id':'PURE-'+kind,'scope':{'instruments':['SSE:600362']},'expires_at':'2027-01-01T00:00:00+08:00','system_usable':True}} for kind in kinds]
        projected=current_presentation({'grant_statuses':statuses,'state':'GRANTED','runtime_state':'NORMAL','lifecycle':{'scopes':{'MODEL':{'state':'ACTIVE'}}}})
        assert projected['headline']==label and projected['formal_judgment']=='ENABLED'
        assert [r['basis_type'] for r in projected['formal_capabilities']]==kinds
        assert projected['method_capabilities']==[]
        results.append(projected)
    settings=(TREE/'frontend/src/pages/settings.tsx').read_text(encoding='utf-8')
    assert '<details><summary>模型维护与资格核验</summary><MaintenancePanel/><CapabilityPanel/></details>' in settings
    panel=(TREE/'frontend/src/components/capability-panel.tsx').read_text(encoding='utf-8')
    assert '<input' not in panel and '已保存的冻结审阅材料<select' in panel and '已保存的 Codex 审阅记录<select' in panel
    assert "'/research/review-materials'" in panel and '/reviews`' in panel
    capture('pure-projection-and-static-ui',{'pure_only_no_admission':True,'projections':results,'default_details_open':False,'existing_material_review_selects':True,'browser_run':False})

def test_risk_sell_missing_frozen_fee_survives_report_and_exports(tmp_path,monkeypatch):
    method_clock(monkeypatch);package=risk_package()
    package['account_version']=package['loss_facts']['baseline_account_version']=3
    package['loss_facts'].update(baseline_assets='130000.10',net_assets='130000.10')
    package['action_packet']['risk_inputs']['quotes']['SSE:600000']['last']='100'
    file=save_package(tmp_path/'method.json',package);directory=copy_donor(tmp_path/'d')
    with client_for(directory,file) as client:
        old=client.get('/api/research/shadow/'+FREEZE).json()
        snapshot=broker_snapshot(cash_balance='100000.10',income='0.00',expenses='0.00')
        snapshot.update(pending_items=[],withdrawable='100000.10',positions=[{'instrument':'SSE:600000','quantity':'300','sellable_quantity':'300'}])
        alignment=reconcile(1,'independent-risk-alignment',snapshot)
        alignment['payload'].update(source='independent METHOD alignment',effective_at=package['required_as_of'])
        assert submit(client,alignment,'align').status_code==200
        assert submit(client,{'kind':'ACCOUNT_DECLARATION','expected_account_version':2,'payload':{'effective_at':package['required_as_of'],'source':'METHOD','record_id':'independent-confirmation','scope':['TRADES','ORDERS','CASH','EQUITY'],'changes':'NONE','basis':'isolated METHOD'}},'declare').status_code==200
        posted(client,'/api/funding/confirm',funding(),200)
        posted(client,'/api/capabilities/grants',{**method_command(),'expected_account_version':3,'allowed_actions':['REDUCE','EXIT'],'deployment_fingerprints':package['deployment_fingerprints']})
        evaluation=posted(client,'/api/actions/evaluate',{})
        assert evaluation['decisions'][0]['action']=='REDUCE' and 'fees_yuan' not in evaluation['decisions'][0]
        receipt=posted(client,'/api/intents/prepare',{**intent_command(evaluation),'price_yuan':'100'})
        actual=fill(3,'independent-risk-sell',direction='SELL');actual['payload'].update(quantity='100',price='100',effective_at=package['required_as_of']);actual['payload']['fee']['amount']='7.00'
        draft=posted(client,'/api/account/drafts',actual)
        posted(client,'/api/account/confirm',{'draft_id':draft['draft_id'],'idempotency_key':'sell','fill_allocations':[{'intent_id':receipt['intent_id'],'fill_record_id':'independent-risk-sell','allocated_quantity':'100','association_status':'USER_CONFIRMED'}]},200)
        params={'decision_id':receipt['decision_id'],'evaluation_id':receipt['evaluation_id'],'intent_id':receipt['intent_id']};url='/api/research/reports/'+FREEZE
        response=client.get(url,params=params);assert response.status_code==200,response.text
        report=response.json();deviation=report['execution_deviations'][0]['allocation_diagnostics'][0]
        assert deviation['proposal_fees_yuan'] is None and deviation['proposal_fee_status']=='UNKNOWN'
        assert deviation['fee_comparison']=='PROPOSAL_FEE_UNKNOWN' and deviation['actual_full_fill_fee']['amount']=='7.00'
        assert client.get(url+'/export',params=params).json()==report
        text=client.get(url+'/export',params={**params,'format':'text'});assert text.status_code==200
        assert 'PROPOSAL_FEE_UNKNOWN' in text.text and '"proposal_fees_yuan":null' in text.text
        assert client.get('/api/research/shadow/'+FREEZE).json()==old
        assert report['prepare_allowed'] is False and report['system_usable'] is False
    capture('risk-sell-fee',report)

def test_concurrent_prepare_receipt_precedes_changed_current_and_pending(tmp_path,monkeypatch):
    method_clock(monkeypatch);package=action_package();file=save_package(tmp_path/'method.json',package)
    with client_for(tmp_path/'data',file) as client:
        prepare(client,package);evaluation=posted(client,'/api/actions/evaluate',{});command=intent_command(evaluation)
        command['idempotency_key']='independent-concurrent'
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses=list(pool.map(lambda _:client.post('/api/intents/prepare',json=command),range(2)))
        assert [r.status_code for r in responses]==[201,201]
        original=responses[0].json();assert original==responses[1].json()
        assert len(client.get('/api/intents').json()['intents'])==1
        posted(client,'/api/intents/'+original['intent_id']+'/declare',{'state':'OPERATION_PENDING','idempotency_key':'pending'},200)
        assert submit(client,permission_change(evaluation['account_version'],'NOT_OPEN'),'changed-permission').status_code==200
        assert client.get('/api/actions/current').json()['decisions']==[]
        before=client.get('/api/intents').json();grants=client.get('/api/capabilities/grants').json()
        assert posted(client,'/api/intents/prepare',command)==original
        conflict=client.post('/api/intents/prepare',json={**command,'price_yuan':'142.00'})
        assert conflict.status_code==409 and conflict.json()['detail']=='INTENT_IDEMPOTENCY_CONTENT_CONFLICT'
        assert client.post('/api/intents/prepare',json={**command,'idempotency_key':'fresh-key'}).status_code==409
        assert client.get('/api/intents').json()==before and client.get('/api/capabilities/grants').json()==grants
        assert before['intents'][0]['status']=='OPERATION_PENDING' and original['status']=='PREPARED'
    capture('concurrent-immutable',{'original':original,'current':before,'changed_content':conflict.json(),'response_statuses':[r.status_code for r in responses]})

def test_partial_facts_remain_current_and_legacy_receipt_is_honest(tmp_path,monkeypatch):
    method_clock(monkeypatch);package=action_package();file=save_package(tmp_path/'method.json',package);directory=tmp_path/'data'
    with client_for(directory,file) as client:
        prepare(client,package);evaluation=posted(client,'/api/actions/evaluate',{});command=intent_command(evaluation)
        original=posted(client,'/api/intents/prepare',command)
        actual=fill(evaluation['account_version'],'independent-partial');actual['payload'].update(quantity='100',price='140.00',effective_at=package['required_as_of'],broker_available_after='76000.10')
        draft=posted(client,'/api/account/drafts',actual)
        posted(client,'/api/account/confirm',{'draft_id':draft['draft_id'],'idempotency_key':'partial','fill_allocations':[{'intent_id':original['intent_id'],'fill_record_id':'independent-partial','allocated_quantity':'100','association_status':'USER_CONFIRMED'}]},200)
        before=client.get('/api/intents').json()
        assert before['intents'][0]['remaining_quantity']=='100' and before['intents'][0]['synced_quantity']=='100'
        assert posted(client,'/api/intents/prepare',command)==original and client.get('/api/intents').json()==before
        # Explicit old-schema fixture only in this test's newly owned database.
        with sqlite3.connect(directory/'roll.sqlite3') as db:
            assert db.execute('DELETE FROM execution_intent_prepare_receipts WHERE idem=?',(command['idempotency_key'],)).rowcount==1
        legacy=client.post('/api/intents/prepare',json=command)
        assert legacy.status_code==409 and legacy.json()['detail']=='LEGACY_PREPARE_RECEIPT_UNAVAILABLE'
        conflict=client.post('/api/intents/prepare',json={**command,'price_yuan':'145.00'})
        assert conflict.status_code==409 and conflict.json()['detail']=='INTENT_IDEMPOTENCY_CONTENT_CONFLICT'
        assert client.get('/api/intents').json()==before
    capture('partial-and-owned-legacy',{'original':original,'current':before,'legacy':legacy.json(),'changed_content':conflict.json(),'legacy_fixture':'OWNED_DB_RECEIPT_REMOVAL_ONLY'})
