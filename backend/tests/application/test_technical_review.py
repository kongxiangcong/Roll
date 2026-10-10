import json
import time
import io
import zipfile
from fastapi.testclient import TestClient
from roll.app import create_app
from test_validation import prepared


WORKER = '''import json,sys
command=json.loads(sys.stdin.readline())
prompt=json.loads(command['prompt'])
def emit(**value):print(json.dumps(value),flush=True)
refs=[]
for item in prompt['inventory']:
 emit(kind='tool',id=item['material_id'],name='roll_read_review_material',arguments={'material_id':item['material_id']})
 value=json.loads(json.loads(sys.stdin.readline())['result']['contentItems'][0]['text'])
 refs.append({'material_id':item['material_id'],'sha256':value['sha256']})
emit(kind='tool',id='reproduce',name='roll_reproduce_validation',arguments={})
proof=json.loads(json.loads(sys.stdin.readline())['result']['contentItems'][0]['text'])
output={'method':'Read immutable protocol, results, attempts and code; reproduce host calculation',
 'material_fingerprint':prompt['material_fingerprint'],'references':refs,
 'checks':[{'check_id':proof['check_id'],'result_sha256':proof['result_sha256'],'matches_original':proof['matches_original']}],
 'issues':[{'issue_id':'missing-real-evidence','severity':'BLOCKING','blocking':True,'description':'Required real evidence unavailable',
 'references':refs[:1],'resolution':None}],
 'limitations':['METHOD_CASE is engineering only; no human independent review; incomplete real experiment']}
emit(kind='completed',status='completed',output=json.dumps(output),error_info=None)
'''


def terminal(client, identifier):
    for _ in range(1200):
        value=client.get('/api/research/technical-reviews/'+identifier).json()
        if value['status']!='RUNNING':return value
        time.sleep(.025)
    raise AssertionError('Review exceeded bounded test deadline')


def validated(client,directory):
    frozen,protocol,model=prepared(client,directory)
    response=client.post('/api/research/complete-freezes/'+frozen['freeze_id']+'/validations',json={
        'purpose':'DIAGNOSTIC','expected_complete_protocol_fingerprint':frozen['complete_protocol_fingerprint'],
        'basis':'Technical review METHOD evidence, not formal qualification'})
    assert response.status_code==201,response.text
    return response.json()


def test_frozen_review_is_checked_persistent_and_does_not_complete_an_unfinished_experiment(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test')
    credential=tmp_path/'auth.json';credential.write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'METHOD_CASE_ONLY'}}))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE',str(credential))
    worker=tmp_path/'review_worker.py';worker.write_text(WORKER)
    directory=tmp_path/'runtime'
    with TestClient(create_app(directory,codex_worker=worker)) as client:
        validation=validated(client,directory)
        response=client.post('/api/research/validations/'+validation['validation_id']+'/review-materials',json={})
        assert response.status_code==201,response.text
        material=response.json()
        started=client.post('/api/research/review-materials/'+material['material_id']+'/reviews',json={
            'expected_material_fingerprint':material['material_fingerprint']})
        assert started.status_code==202,started.text
        review=terminal(client,started.json()['run_id'])
        assert review['status']=='COMPLETE',review
        assert review['review_record']['blocking_issues_resolved'] is False
        assert review['review_record']['reproduction_verified'] is True
        assert review['review_record']['backend']=='CODEX'
        assert review['material_fingerprint']==material['material_fingerprint']
        delivery=client.get('/api/research/review-materials/'+material['material_id']+'/delivery').json()
        assert delivery['preliminary'] is True and delivery['delivery_status']=='INCOMPLETE'
        assert delivery['review_status']=='COMPLETE'
        assert delivery['capability_status']=='NOT_GRANTED'
        assert delivery['human_review_label']=='经自动验证与模型技术审阅，未经人工独立复核'
        export=client.post('/api/research/review-materials/'+material['material_id']+'/export',json={})
        assert export.status_code==201,export.text
        package=client.get('/api/data/archives/'+export.json()['archive']['sha256'])
        assert package.status_code==200
        assert client.get('/api/account').json()['version']==0
        assert client.get('/api/research/protocols/'+validation['protocol_id']).json()['forward_started_at'] is None
    with TestClient(create_app(directory)) as client:
        assert client.get('/api/research/technical-reviews/'+review['run_id']).json()==review


def test_model_agreement_cannot_clear_host_registered_validation_deficits(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test')
    credential=tmp_path/'auth.json';credential.write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'METHOD_CASE_ONLY'}}))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE',str(credential))
    worker=tmp_path/'agree.py';worker.write_text(WORKER.replace("emit(kind='completed',status='completed',output=json.dumps(output),error_info=None)","output['issues']=[]\noutput['limitations']=['I agree this can be used']\nemit(kind='completed',status='completed',output=json.dumps(output),error_info=None)"))
    directory=tmp_path/'runtime'
    with TestClient(create_app(directory,codex_worker=worker)) as client:
        validation=validated(client,directory)
        material=client.post('/api/research/validations/'+validation['validation_id']+'/review-materials',json={}).json()
        started=client.post('/api/research/review-materials/'+material['material_id']+'/reviews',json={'expected_material_fingerprint':material['material_fingerprint']})
        review=terminal(client,started.json()['run_id'])
        assert review['status']=='COMPLETE',review
        record=review['review_record']
        assert record['blocking_issues_resolved'] is False
        assert 'G7' in record['host_unresolved_gate_evidence']
        assert client.get('/api/research/review-materials/'+material['material_id']+'/delivery').json()['capability_status']=='NOT_GRANTED'


def test_local_delivery_contains_frozen_upstream_code_and_full_inputs_without_reading_sealed(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        validation=validated(client,tmp_path)
        material=client.post('/api/research/validations/'+validation['validation_id']+'/review-materials',json={}).json()
        exported=client.post('/api/research/review-materials/'+material['material_id']+'/export',json={}).json()
        raw=client.get('/api/data/archives/'+exported['archive']['sha256']).content
        with zipfile.ZipFile(io.BytesIO(raw)) as package:
            assert 'code/research/registry.py' in package.namelist()
            assert 'code/research/training_preflight.py' in package.namelist()
            assert 'code/market/rules.py' in package.namelist()
            assert 'code/research/reference/cash-rights/sources.json' in package.namelist()
            assert json.loads(package.read('archives/'+validation['input_archive']['sha256']))['replay']['forecasts']
            assert 'forward_started_at' in package.read('code/research/registry.py').decode()
        assert not any(event['action']=='SEALED_INPUT_ACCESSED' for event in client.get('/api/research/protocols/'+validation['protocol_id']+'/audit').json())


def test_risk_policy_review_uses_its_own_five_gates_and_read_only_reproduction(tmp_path,monkeypatch,method_market_timeline):
    from test_risk_policy import policy_case,transport,ASOF
    consume=method_market_timeline(ASOF)
    monkeypatch.setenv('ROLL_ENV','test')
    credential=tmp_path/'auth.json';credential.write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'METHOD_CASE_ONLY'}}))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE',str(credential))
    worker=tmp_path/'review.py';worker.write_text(WORKER)
    directory=tmp_path/'runtime'
    with TestClient(create_app(directory,market_transport=transport(),codex_worker=worker)) as client:
        _,policy=policy_case(client,directory);consume()
        evaluation=client.post('/api/research/risk-policies/'+policy['policy_id']+'/evaluations',json={'required_as_of':ASOF,'basis':'Frozen risk-policy review engineering'}).json()
        before=client.get('/api/account').json()
        response=client.post('/api/research/risk-evaluations/'+evaluation['evaluation_id']+'/review-materials',json={})
        assert response.status_code==201,response.text
        material=response.json()
        assert material['candidate_kind']=='RISK_POLICY'
        assert set(material['basis_manifest']['gates'])=={'DATA','RULE_QUANTITY','AUTHORIZATION','STRESS_EXECUTION','ONLINE_CONSISTENCY'}
        run=client.post('/api/research/review-materials/'+material['material_id']+'/reviews',json={'expected_material_fingerprint':material['material_fingerprint']}).json()
        review=terminal(client,run['run_id'])
        assert review['status']=='COMPLETE',review
        assert review['review_record']['reproduction_verified'] is True
        assert client.get('/api/account').json()==before


def test_host_method_endpoint_can_deliver_completed_fail_or_inconclusive_without_grant(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test')
    credential=tmp_path/'auth.json';credential.write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'METHOD_CASE_ONLY'}}))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE',str(credential))
    worker=tmp_path/'review.py';worker.write_text(WORKER)
    fixture=tmp_path/'completed.json'
    fixture.write_text(json.dumps({'cases':[
        {'case_id':'completed-hard-failure','gates':{'G1':'PASS','G4':'FAIL','G7':'INCONCLUSIVE'},'checks_complete':True,'endpoint_reached':True,'observed_value':-1},
        {'case_id':'completed-insufficient-support','gates':{'G1':'PASS','G4':'INCONCLUSIVE','G7':'INCONCLUSIVE'},'checks_complete':True,'endpoint_reached':True,'observed_value':None}]}))
    with TestClient(create_app(tmp_path/'runtime',codex_worker=worker,technical_review_method_file=fixture)) as client:
        materials=client.get('/api/research/method-review-materials').json()
        assert len(materials)==2
        for material in materials:
            started=client.post('/api/research/review-materials/'+material['material_id']+'/reviews',json={'expected_material_fingerprint':material['material_fingerprint']}).json()
            assert terminal(client,started['run_id'])['status']=='COMPLETE'
            delivery=client.get('/api/research/review-materials/'+material['material_id']+'/delivery').json()
            assert delivery['delivery_status']=='COMPLETE' and delivery['preliminary'] is False
            assert delivery['validation_verdict'] in {'FAIL','INCONCLUSIVE'}
            assert delivery['evidence_kind']=='METHOD_CASE'
            assert delivery['capability_status']=='NOT_GRANTED'
    monkeypatch.setenv('ROLL_ENV','production')
    import pytest
    with pytest.raises(ValueError,match='METHOD'):
        create_app(tmp_path/'refused',technical_review_method_file=fixture)


def test_deepseek_sdk_review_uses_the_same_material_contract_and_freezes_runtime_versions(tmp_path,monkeypatch):
    from test_deepseek_evidence import model_server,response,call,message
    monkeypatch.setenv('ROLL_ENV','test');monkeypatch.setenv('DEEPSEEK_API_KEY','ROLL_METHOD_CASE_ONLY')
    fixture=tmp_path/'case.json';fixture.write_text(json.dumps({'cases':[{'case_id':'deepseek','gates':{'G4':'INCONCLUSIVE'},'checks_complete':True,'endpoint_reached':True,'observed_value':None}]}))
    def provider(body,number):
        content=next(v['content'] for v in body['input'] if v.get('role')=='user')
        prompt=json.loads(content if isinstance(content,str) else next(c['text'] for c in content if c.get('type')=='input_text'))
        results=[json.loads(v['output']) for v in body['input'] if v.get('type')=='function_call_output']
        if len(results)<len(prompt['inventory']):
            item=prompt['inventory'][len(results)]
            return 200,response([call('roll_read_review_material',{'material_id':item['material_id']},number)])
        if len(results)==len(prompt['inventory']):return 200,response([call('roll_reproduce_validation',{},number)])
        proof=results[-1]
        candidate={'method':'Same host-frozen review contract over SDK tools','material_fingerprint':prompt['material_fingerprint'],
            'references':[{'material_id':i['material_id'],'sha256':i['sha256']} for i in prompt['inventory']],
            'checks':[{k:proof[k] for k in ['check_id','result_sha256','matches_original']}],'issues':[],
            'limitations':['METHOD_CASE does not confer actual qualification or human independent review']}
        return 200,response([message(json.dumps(candidate))])
    with model_server(provider) as (endpoint,bodies),TestClient(create_app(tmp_path/'runtime',deepseek_endpoint=endpoint,technical_review_method_file=fixture)) as client:
        client.post('/api/agents/settings',json={'expected_version':0,'backend':'DEEPSEEK'}).raise_for_status()
        material=client.get('/api/research/method-review-materials').json()[0]
        started=client.post('/api/research/review-materials/'+material['material_id']+'/reviews',json={'expected_material_fingerprint':material['material_fingerprint']}).json()
        review=terminal(client,started['run_id'])
        assert review['status']=='COMPLETE',review
        assert review['sdk_runtime_version']['openai-agents']=='0.23.1'
        assert review['review_record']['backend']=='DEEPSEEK'
        assert review['material_fingerprint']==material['material_fingerprint']
        assert len(bodies)==5
        assert review['process']['credential_persisted'] is False


def test_invalid_review_output_keeps_attempts_and_cannot_publish_or_self_grant(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test')
    credential=tmp_path/'auth.json';credential.write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'METHOD_CASE_ONLY'}}))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE',str(credential))
    fixture=tmp_path/'case.json';fixture.write_text(json.dumps({'cases':[{'case_id':'bad','gates':{'G4':'INCONCLUSIVE'},'checks_complete':False,'endpoint_reached':False,'observed_value':None}]}))
    mutations=[("output['references'][0]['sha256']='forged'",'REVIEW_REFERENCE_NOT_VERIFIED'),
        ("output['checks'][0]['matches_original']=False",'REVIEW_REPRODUCTION_CLAIM_MISMATCH'),
        ("output['issues'][0]['resolution']={'basis':'Already fixed because model agrees','references':refs[:1]}",'REVIEW_BLOCKING_RESOLUTION_NOT_EVIDENCED'),
        ("del output['method']",'REVIEW_OUTPUT_SCHEMA_INVALID')]
    worker=tmp_path/'bad.py'
    for index,(mutation,code) in enumerate(mutations):
        worker.write_text(WORKER.replace("emit(kind='completed',status='completed',output=json.dumps(output),error_info=None)",mutation+"\nemit(kind='completed',status='completed',output=json.dumps(output),error_info=None)"))
        with TestClient(create_app(tmp_path/'runtime',codex_worker=worker,technical_review_method_file=fixture)) as client:
            material=client.get('/api/research/method-review-materials').json()[0]
            command={'expected_material_fingerprint':material['material_fingerprint']}
            if index:command['retry_of']=prior['run_id']
            started=client.post('/api/research/review-materials/'+material['material_id']+'/reviews',json=command).json()
            result=terminal(client,started['run_id'])
            assert result['status']=='INVALID_OUTPUT' and result['error']['code']==code,result
            assert 'review_record' not in result
            if index:assert result['retry_of']==prior['run_id']
            prior=result
            assert client.post('/api/research/technical-reviews/'+result['run_id']+'/grant',json={}).status_code==404
            assert client.get('/api/account').json()['version']==0
            assert len(client.get('/api/research/review-materials/'+material['material_id']+'/reviews').json())==index+1
            assert client.get('/api/research/review-materials/'+material['material_id']+'/delivery').json()['review_status']=='INVALID_OUTPUT'


def test_cancel_timeout_retry_and_acquisition_share_the_same_frozen_execution_slot(tmp_path,monkeypatch):
    from test_codex_evidence import request_data
    from test_market_directory import establish
    monkeypatch.setenv('ROLL_ENV','test');monkeypatch.delenv('DEEPSEEK_API_KEY',raising=False);monkeypatch.delenv('ROLL_DEEPSEEK_API_KEY_FILE',raising=False)
    credential=tmp_path/'auth.json';credential.write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'METHOD_CASE_ONLY'}}))
    monkeypatch.setenv('ROLL_CODEX_AUTH_FILE',str(credential))
    fixture=tmp_path/'case.json';fixture.write_text(json.dumps({'cases':[{'case_id':'bounded','gates':{'G4':'INCONCLUSIVE'},'checks_complete':False,'endpoint_reached':False,'observed_value':None}]}))
    worker=tmp_path/'waiting.py';worker.write_text("import json,sys,time\njson.loads(sys.stdin.readline())\nprint(json.dumps({'kind':'turn','turn_id':'waiting'}),flush=True)\ntime.sleep(120)\n")
    with TestClient(create_app(tmp_path/'runtime',codex_worker=worker,technical_review_method_file=fixture)) as client:
        establish(client,['SSE:600519']);request_id=request_data(client)
        material=client.get('/api/research/method-review-materials').json()[0]
        path='/api/research/review-materials/'+material['material_id']+'/reviews'
        assert client.post(path,json={'expected_material_fingerprint':'forged'}).status_code==409
        started=client.post(path,json={'expected_material_fingerprint':material['material_fingerprint']}).json()
        client.post('/api/agents/settings',json={'expected_version':0,'backend':'DEEPSEEK'}).raise_for_status()
        assert client.post('/api/data/requests/'+request_id+'/agent',json={'question':'Retrieve fixed fact'}).status_code==409
        assert client.post(path,json={'expected_material_fingerprint':material['material_fingerprint']}).status_code==409
        current=client.get('/api/research/technical-reviews/'+started['run_id']).json()
        assert current['backend']=='CODEX' and current['backend_settings']['version']==0
        assert current['config_fingerprint']==started['config_fingerprint']
        client.post('/api/research/technical-reviews/'+started['run_id']+'/cancel',json={}).raise_for_status()
        cancelled=terminal(client,started['run_id']);assert cancelled['status']=='CANCELLED'
        assert 'review_record' not in cancelled and cancelled['process']['remaining_pids']==[]
        retry=client.post(path,json={'expected_material_fingerprint':material['material_fingerprint'],'retry_of':cancelled['run_id']}).json()
        unavailable=terminal(client,retry['run_id'])
        assert unavailable['backend']=='DEEPSEEK' and unavailable['retry_of']==cancelled['run_id'] and unavailable['status']=='UNAVAILABLE'
        client.post('/api/agents/settings',json={'expected_version':1,'backend':'CODEX'}).raise_for_status()
        monkeypatch.setenv('ROLL_TECHNICAL_REVIEW_TIMEOUT_SECONDS','1')
        bounded=client.post(path,json={'expected_material_fingerprint':material['material_fingerprint'],'retry_of':unavailable['run_id']}).json()
        expired=terminal(client,bounded['run_id'])
        assert expired['status']=='TIMED_OUT' and expired['process']['remaining_pids']==[]
        assert len(client.get(path).json())==3
        assert client.get('/api/research/technical-reviews/'+cancelled['run_id']).json()==cancelled


def test_corrupt_frozen_material_blocks_review_and_export_before_new_attempt(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test')
    fixture=tmp_path/'case.json';fixture.write_text(json.dumps({'cases':[{'case_id':'corrupt','gates':{'G4':'INCONCLUSIVE'},'checks_complete':False,'endpoint_reached':False,'observed_value':None}]}))
    directory=tmp_path/'runtime'
    with TestClient(create_app(directory,technical_review_method_file=fixture)) as client:
        material=client.get('/api/research/method-review-materials').json()[0]
        (directory/material['inventory'][0]['archive']['path']).write_bytes(b'corrupt frozen protocol')
        path='/api/research/review-materials/'+material['material_id']
        assert client.get(path).status_code==409
        assert client.post(path+'/reviews',json={'expected_material_fingerprint':material['material_fingerprint']}).status_code==409
        assert client.post(path+'/export',json={}).status_code==409
        assert client.get('/api/account').json()['version']==0
