"""Immutable technical-review material and local verification delivery, without grant authority."""
import hashlib
import io
import json
import os
from pathlib import Path
import threading
import time
import zipfile
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict
from roll.accounts.ledger import encode, now
from roll.research.shadow import fingerprint
from roll.agents.settings import HOST_LIMITS, admit_agent_run, require_current_backend
from roll.agents.codex_process import owner_alive, process_creation, recover_directory

LABEL='经自动验证与模型技术审阅，未经人工独立复核'
TOOLS=['roll_read_review_material','roll_reproduce_validation']


class ReviewCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_material_fingerprint:str
    retry_of:str|None=None


class TechnicalReviews:
    def __init__(self,validation,settings,*,worker=None,endpoint=None,risk_policies=None,method_file=None):
        self.validation=validation;self.shadow=validation.shadow;self.registry=validation.registry
        self.ledger=validation.ledger;self.evidence=validation.evidence;self.settings=settings
        self.worker=worker;self.endpoint=endpoint or 'https://api.deepseek.com'
        self.risk_policies=risk_policies
        self.method_file=method_file
        self.method=worker is not None or endpoint is not None
        self.active={};self.lock=threading.Lock()
        if (self.method or method_file is not None) and os.environ.get('ROLL_ENV')!='test':raise ValueError('REVIEW_METHOD_ADAPTER_TEST_ONLY')
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS research_review_materials(id TEXT PRIMARY KEY,basis_id TEXT NOT NULL,value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS technical_review_runs(id TEXT PRIMARY KEY,material_id TEXT NOT NULL,value TEXT NOT NULL)')
            for row in db.execute('SELECT value FROM technical_review_runs').fetchall():
                run=json.loads(row[0])
                if run['status']=='RUNNING' and not owner_alive(run):
                    run.update(status='INTERRUPTED',finished_at=now(),error={'code':'HOST_INTERRUPTED'})
                    if run.get('process'):run['recovery_cleanup']=recover_directory(run)
                    db.execute('UPDATE technical_review_runs SET value=? WHERE id=?',(encode(run),run['run_id']))
        if method_file is not None:self.register_method_file(method_file)

    def get_material(self,identifier):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM research_review_materials WHERE id=?',(identifier,)).fetchone()
        if not row:raise HTTPException(404,'冻结审阅材料不存在')
        value=json.loads(row[0])
        if value.get('method_host_fixture') and (self.method_file is None or os.environ.get('ROLL_ENV')!='test'):
            raise HTTPException(409,'METHOD_REVIEW_MATERIAL_PRODUCTION_LOAD_REFUSED')
        if self.shadow.checked_archive(value['manifest_archive'])!={k:v for k,v in value.items() if k!='manifest_archive'}:
            raise HTTPException(409,'REVIEW_MATERIAL_MANIFEST_MISMATCH')
        for item in value['inventory']:self.evidence.raw(item['sha256'])
        for item in [*value['local_archives'],*value.get('local_code',[])]:self.evidence.raw(item['sha256'])
        return value

    def material(self,validation_id):
        result=self.validation.get(validation_id)
        self.validation.replay(validation_id)
        with self.ledger.connection() as db:row=db.execute('SELECT id FROM research_review_materials WHERE basis_id=?',(validation_id,)).fetchone()
        if row:return self.get_material(row[0])
        original=self.shadow.checked_archive(result['input_archive']);frozen=original['frozen']
        from roll.research.models import code_fingerprint
        if frozen['fingerprints']['model_code']!=code_fingerprint():raise HTTPException(409,'REVIEW_FROZEN_MODEL_CODE_CHANGED')
        protocol={k:result[k] for k in ['protocol_id','complete_protocol_fingerprint','candidate_fingerprints','primary_objective','comparators','windows','statistics','stopping','costs','execution','scope','attempt_manifest','validation_attempt_manifest']}
        # Account amounts and identity are local export inputs, never worker context.
        gates={name:{'status':g['status'],'reasons':g['reasons']} for name,g in result['gates'].items()}
        g5=result['gates']['G5']['details']
        summary={k:result[k] for k in ['validation_id','validation_verdict','preliminary','experiment_status','evidence_kind','evidence_cutoff','incomplete_checks','limitations','unresolved_items','result_fingerprint']}
        summary.update(gates=gates,g5_components={group:[{k:c[k] for k in ['component','status','reason','result_fingerprint'] if k in c} for c in rows] for group,rows in g5.items()},
            independent_calibration_verified=False,strict_historical_pit_verified=False,real_forward_started=False,human_review_label=LABEL,
            input_sha256=result['input_archive']['sha256'],data_use=original['model'].get('data_use'),calibrator_fit_status='FITTED_UNVALIDATED')
        inventory=[]
        def add(identifier,value,kind):
            raw=value.encode() if isinstance(value,str) else encode(value).encode()
            archive=self.evidence.archive(raw,'TECHNICAL_REVIEW_MATERIAL')
            inventory.append({'material_id':identifier,'sha256':archive['sha256'],'bytes':len(raw),'kind':kind,'archive':archive})
        add('protocol-and-attempts',protocol,'PROTOCOL_AND_ALL_ATTEMPTS');add('results-and-limitations',summary,'VALIDATION_RESULTS')
        sources={}
        for name in ['models','execution','shadow','statistics','validation']:
            path=Path(__file__).with_name(name+'.py');raw=path.read_bytes().replace(b'\r\n',b'\n')
            sources['research/'+name+'.py']=hashlib.sha256(raw).hexdigest()
            add('code-'+name,raw.decode(),'CODE')
        code_archive=self.evidence.archive(encode(sources).encode(),'TECHNICAL_REVIEW_CODE_INVENTORY')
        source_root=Path(__file__).parents[1]
        code_paths=['research/'+name+'.py' for name in ['models','execution','reconstruction','datasets','design','historical_costs','corporate_actions','registry','training_preflight','shadow','statistics','validation']]
        code_paths+=['market/rules.py','research/reference/reconstruction/sources.json','research/reference/cash-rights/sources.json']
        local_code=[]
        for relative in code_paths:
            raw=(source_root/relative).read_bytes().replace(b'\r\n',b'\n')
            local_code.append({**self.evidence.archive(raw,'FROZEN_LOCAL_REVIEW_CODE'),'source_path':relative})
        local=[result['manifest_archive'],result['input_archive'],frozen['archive'],original['model']['model_artifact'],original['model']['calibrator_artifact'],original['model']['input_archive'],original['model']['freeze_manifest'],code_archive]
        # The exact frozen code bytes are also available in the local delivery package.
        local.extend(i['archive'] for i in inventory)
        if sum(i['bytes'] for i in inventory)>240000 or len(inventory)+1>HOST_LIMITS['tool_calls']:
            raise HTTPException(409,{'code':'REVIEW_MATERIAL_EXCEEDS_FROZEN_BUDGET','bytes':sum(i['bytes'] for i in inventory)})
        value={'material_id':str(uuid4()),'basis_id':validation_id,'candidate_kind':'PROFIT_MODEL','protocol_id':result['protocol_id'],
            'inventory':inventory,'local_archives':local,'local_code':local_code,'created_at':now(),'evidence_kind':result['evidence_kind'],
            'basis_manifest':result,'review_scope_limitations':['Only the five registered candidate/validation code files are read by the model; upstream dependency fingerprints remain host-bound.','No personal account, authorization, credentials or protected SEALED input is sent.'],
            'human_review_label':LABEL}
        value['material_fingerprint']=fingerprint({k:v for k,v in value.items() if k not in {'created_at','material_id'}})
        value['manifest_archive']=self.evidence.archive(encode(value).encode(),'TECHNICAL_REVIEW_MATERIAL_MANIFEST')
        with self.ledger.connection() as db:db.execute('INSERT INTO research_review_materials VALUES(?,?,?)',(value['material_id'],validation_id,encode(value)))
        return value

    def get(self,identifier):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM technical_review_runs WHERE id=?',(identifier,)).fetchone()
        if not row:raise HTTPException(404,'技术审阅运行不存在')
        run=json.loads(row[0])
        if run.get('review_record_archive') and self.shadow.checked_archive(run['review_record_archive'])!=run['review_record']:
            raise HTTPException(409,'REVIEW_RECORD_ARCHIVE_MISMATCH')
        return run

    def risk_material(self,evaluation_id):
        policies=self.risk_policies;evaluation=policies.get_evaluation(evaluation_id);policy=policies.get(evaluation['policy_id'])
        proof=policies.replay(evaluation_id)
        with self.ledger.connection() as db:row=db.execute('SELECT id FROM research_review_materials WHERE basis_id=?',(evaluation_id,)).fetchone()
        if row:return self.get_material(row[0])
        gates=dict(evaluation['gate_results']);gates['ONLINE_CONSISTENCY']=proof['online_consistency']
        verdict='FAIL' if 'FAIL' in gates.values() else 'PASS' if all(s=='PASS' for s in gates.values()) else 'INCONCLUSIVE'
        basis={'validation_id':evaluation_id,'policy_id':policy['policy_id'],'protocol_id':policy['protocol_id'],
            'validation_verdict':verdict,'preliminary':True,'experiment_status':'POLICY_DIAGNOSTIC',
            'gates':{name:{'status':status,'reasons':evaluation['reasons']} for name,status in gates.items()},
            'incomplete_checks':['ACTUAL_POLICY_QUALIFICATION_PACKAGE_NOT_COMPLETE'],
            'policy_fingerprint':policy['policy_fingerprint'],'code_fingerprint':policy['code_fingerprint'],
            'dependency_fingerprints':policy['dependency_fingerprints'],'input_sha256':evaluation['input_archive']['sha256'],
            'result_fingerprint':fingerprint(proof['result']),'evidence_kind':evaluation['evidence_kind']}
        inventory=[]
        def add(identifier,value,kind):
            raw=value.encode() if isinstance(value,str) else encode(value).encode();archive=self.evidence.archive(raw,'TECHNICAL_REVIEW_MATERIAL')
            inventory.append({'material_id':identifier,'sha256':archive['sha256'],'bytes':len(raw),'kind':kind,'archive':archive})
        public_policy={k:policy[k] for k in ['policy_id','policy_type','scope','required_gates','rule','freshness','sell_scope','stable_priority','loss_branch','recovery','code_fingerprint','dependency_fingerprints','policy_fingerprint']}
        add('protocol-and-attempts',{'policy':public_policy,'attempt_manifest':self.registry.attempt_manifest(policy['protocol_id'])},'POLICY_PROTOCOL_AND_ALL_ATTEMPTS')
        add('results-and-limitations',{**basis,'reasons':evaluation['reasons'],'limitations':['ACCOUNT_CONDITIONAL deterministic risk policy; no profit-model gate exemption.','Complete account, amounts and funding details remain in local export only.']},'POLICY_VALIDATION_RESULTS')
        source_root=Path(__file__).parents[1];local_code=[]
        for relative in ['research/risk_policy.py',*policy['dependency_fingerprints']]:
            raw=(source_root/relative).read_bytes().replace(b'\r\n',b'\n')
            local_code.append({**self.evidence.archive(raw,'FROZEN_LOCAL_REVIEW_CODE'),'source_path':relative})
            add('code-'+relative.replace('/','-'),raw.decode(),'CODE')
        if sum(i['bytes'] for i in inventory)>240000 or len(inventory)+1>HOST_LIMITS['tool_calls']:raise HTTPException(409,'REVIEW_MATERIAL_EXCEEDS_FROZEN_BUDGET')
        evaluation_archive=self.evidence.archive(encode(evaluation).encode(),'FROZEN_POLICY_REVIEW_EVALUATION')
        value={'material_id':str(uuid4()),'basis_id':evaluation_id,'candidate_kind':'RISK_POLICY','protocol_id':policy['protocol_id'],
            'inventory':inventory,'local_archives':[policy['material_archive'],evaluation['input_archive'],evaluation_archive,*[i['archive'] for i in inventory]],
            'local_code':local_code,'created_at':now(),'evidence_kind':evaluation['evidence_kind'],'basis_manifest':basis,
            'review_scope_limitations':['Independent deterministic risk policy uses its five required gates; no profit-model G3/G4/G7 substitution.','Personal account and authorization amounts remain local.'],'human_review_label':LABEL}
        value['material_fingerprint']=fingerprint({k:v for k,v in value.items() if k not in {'created_at','material_id'}})
        value['manifest_archive']=self.evidence.archive(encode(value).encode(),'TECHNICAL_REVIEW_MATERIAL_MANIFEST')
        with self.ledger.connection() as db:db.execute('INSERT INTO research_review_materials VALUES(?,?,?)',(value['material_id'],evaluation_id,encode(value)))
        return value

    def reproduce(self,material):
        if material.get('method_host_fixture'):
            if material['method_code_fingerprint']!=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest():raise HTTPException(409,'METHOD_REVIEW_CODE_CHANGED')
            case=self.shadow.checked_archive(material['method_case_archive'])
            result=self.method_result(case)
            return {'result_fingerprint':fingerprint(result),'matches_original':fingerprint(result)==material['basis_manifest']['result_fingerprint'],'network_calls':0}
        if material['candidate_kind']=='PROFIT_MODEL':
            from roll.research.models import code_fingerprint
            if material['basis_manifest']['candidate_fingerprints']['model_code']!=code_fingerprint():raise HTTPException(409,'REVIEW_FROZEN_MODEL_CODE_CHANGED')
            return self.validation.replay(material['basis_id'])
        proof=self.risk_policies.replay(material['basis_id'])
        return {'result_fingerprint':fingerprint(proof['result']),'matches_original':proof['matches_original'],'network_calls':proof['network_calls']}

    @staticmethod
    def method_result(case):
        """Explicit engineering protocol, never a real G1-G7 evidence supplier."""
        gates=case['gates'];observed=case['observed_value']
        if not gates or any(s not in {'PASS','FAIL','INCONCLUSIVE'} for s in gates.values()):raise ValueError('METHOD_GATE_SCHEMA_INVALID')
        if observed is None and gates.get('G4')!='INCONCLUSIVE':raise ValueError('METHOD_UNKNOWN_SUPPORT_NOT_INCONCLUSIVE')
        if observed is not None and observed<0 and gates.get('G4')!='FAIL':raise ValueError('METHOD_HARD_FAILURE_NOT_FAIL')
        verdict='FAIL' if 'FAIL' in gates.values() else 'INCONCLUSIVE' if 'INCONCLUSIVE' in gates.values() else 'PASS'
        return {'gates':{name:{'status':status,'reasons':['Frozen METHOD completed measurement/support check']} for name,status in gates.items()},'validation_verdict':verdict,'observed_value':observed,'evidence_kind':'METHOD_CASE'}

    def register_method_file(self,path):
        if os.environ.get('ROLL_ENV')!='test':raise ValueError('METHOD_REVIEW_ADAPTER_TEST_ONLY')
        cases=json.loads(Path(path).read_text(encoding='utf-8'))['cases']
        for case in cases:
            basis_id='METHOD:'+case['case_id']
            with self.ledger.connection() as db:
                if db.execute('SELECT id FROM research_review_materials WHERE basis_id=?',(basis_id,)).fetchone():continue
            result=self.method_result(case)
            archive=self.evidence.archive(encode(case).encode(),'HOST_METHOD_REVIEW_INPUT')
            basis={**result,'validation_id':basis_id,'protocol_id':basis_id,'result_fingerprint':fingerprint(result),
                'preliminary':not case['endpoint_reached'],'experiment_status':'ENDED' if case['endpoint_reached'] else 'RUNNING_DIAGNOSTIC',
                'incomplete_checks':[] if case['checks_complete'] else ['METHOD_REQUIRED_CHECK_NOT_COMPLETED']}
            inventory=[]
            for identifier,value in [('protocol-and-attempts',{'protocol':case,'attempts':[{'status':'SUCCEEDED','purpose':'METHOD_ONLY'}]}),('results-and-limitations',basis)]:
                raw=encode(value).encode();item=self.evidence.archive(raw,'TECHNICAL_REVIEW_MATERIAL')
                inventory.append({'material_id':identifier,'sha256':item['sha256'],'bytes':len(raw),'kind':'METHOD_CASE','archive':item})
            code=self.evidence.archive(Path(__file__).read_bytes().replace(b'\r\n',b'\n'),'HOST_METHOD_REVIEW_CODE')
            inventory.append({'material_id':'code-method','sha256':code['sha256'],'bytes':code['bytes'],'kind':'CODE','archive':code})
            value={'material_id':str(uuid4()),'basis_id':basis_id,'protocol_id':basis_id,'candidate_kind':'PROFIT_MODEL','method_host_fixture':True,
                'method_code_fingerprint':code['sha256'],
                'method_case_archive':archive,'basis_manifest':basis,'evidence_kind':'METHOD_CASE','created_at':now(),
                'inventory':inventory,'local_archives':[archive,*[i['archive'] for i in inventory]],'local_code':[{**code,'source_path':'research/technical_review.py'}],
                'human_review_label':LABEL,'review_scope_limitations':['Explicit host engineering protocol/endpoint; not historical PIT, real maturity, real experiment termination or qualification.']}
            value['material_fingerprint']=fingerprint({k:v for k,v in value.items() if k not in {'created_at','material_id'}})
            value['manifest_archive']=self.evidence.archive(encode(value).encode(),'TECHNICAL_REVIEW_MATERIAL_MANIFEST')
            with self.ledger.connection() as db:db.execute('INSERT INTO research_review_materials VALUES(?,?,?)',(value['material_id'],basis_id,encode(value)))

    def method_materials(self):
        if self.method_file is None or os.environ.get('ROLL_ENV')!='test':raise HTTPException(404,'METHOD材料未配置')
        with self.ledger.connection() as db:identifiers=[r[0] for r in db.execute("SELECT id FROM research_review_materials WHERE basis_id LIKE 'METHOD:%' ORDER BY rowid")]
        return [self.get_material(identifier) for identifier in identifiers]

    def runs(self,material_id):
        self.get_material(material_id)
        with self.ledger.connection() as db:return [json.loads(row[0]) for row in db.execute('SELECT value FROM technical_review_runs WHERE material_id=? ORDER BY rowid',(material_id,))]

    def basis_materials(self,basis_id):
        with self.ledger.connection() as db:identifiers=[r[0] for r in db.execute('SELECT id FROM research_review_materials WHERE basis_id=? ORDER BY rowid',(basis_id,))]
        return [self.get_material(identifier) for identifier in identifiers]

    def save(self,run):
        with self.ledger.connection() as db:db.execute('UPDATE technical_review_runs SET value=? WHERE id=?',(encode(run),run['run_id']))

    def start(self,material_id,command):
        selection=self.settings.get();backend=selection['backend']
        require_current_backend(backend)
        material=self.get_material(material_id)
        if command.expected_material_fingerprint!=material['material_fingerprint']:raise HTTPException(409,'REVIEW_MATERIAL_FINGERPRINT_CHANGED')
        if command.retry_of:
            prior=self.get(command.retry_of)
            if prior['material_id']!=material_id or prior['status']=='RUNNING':raise HTTPException(409,'INVALID_REVIEW_RETRY')
        from roll.agents.codex_evidence import CONFIG, MODEL as CODEX_MODEL, SDK_VERSION
        from roll.agents.deepseek_evidence import MODEL as DEEPSEEK_MODEL,LIMITS as DEEPSEEK_LIMITS
        from importlib.metadata import version
        versions={'openai-codex':SDK_VERSION,'openai-codex-cli-bin':SDK_VERSION} if backend=='CODEX' else {name:version(name) for name in ['openai-agents','openai','httpx2']}
        limits={**DEEPSEEK_LIMITS,'runtime_operations':8,'total_calls':22,'model_calls':9,'max_output_tokens':4096,'model_input_bytes':262144}
        timeout=int(os.environ.get('ROLL_TECHNICAL_REVIEW_TIMEOUT_SECONDS',120))
        if not 1<=timeout<=120:raise HTTPException(503,'INVALID_REVIEW_HOST_LIMIT')
        limits['timeout_seconds']=timeout
        code={p.name:hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in [Path(__file__),*Path(__file__).parents[1].joinpath('agents').glob('*.py')]}
        run={'run_id':str(uuid4()),'material_id':material_id,'material_fingerprint':material['material_fingerprint'],'task_kind':'TECHNICAL_REVIEW',
            'backend':backend,'model':os.environ.get('ROLL_CODEX_MODEL',CODEX_MODEL) if backend=='CODEX' else DEEPSEEK_MODEL,
            'resolved_model':None,'limits':limits,'started_at':now(),'finished_at':None,'status':'RUNNING','retry_of':command.retry_of,
            'allowed_tools':TOOLS,'tools':[],'archives':[],'gaps':[],'runtime_audit':{},'host_code_hashes':code,
            'host_owner':{'pid':os.getpid(),'creation_ticks':process_creation(os.getpid())},
            'evidence_kind':'METHOD_CASE_TECHNICAL_REVIEW' if self.method else 'REAL_'+backend+'_TECHNICAL_REVIEW',
            'sdk_runtime_version':versions,'formal_judgment':'DISABLED'}
        run['config_fingerprint']=fingerprint({'backend':backend,'model':run['model'],'config':CONFIG if backend=='CODEX' else self.endpoint,'limits':limits,'tools':TOOLS,'code':code,'sdk_runtime_version':versions})
        with self.lock:
            with self.ledger.connection() as db:
                db.execute('BEGIN IMMEDIATE');admit_agent_run(db,run,selection)
                db.execute('INSERT INTO technical_review_runs VALUES(?,?,?)',(run['run_id'],material_id,encode(run)));db.commit()
            cancel=threading.Event();self.active[run['run_id']]=cancel
        threading.Thread(target=self.execute,args=(run,material,cancel),daemon=True).start()
        return json.loads(encode(run))

    def execute(self,run,material,cancel):
        try:
            if run['backend']=='CODEX':
                configured=os.environ.get('ROLL_CODEX_AUTH_FILE')
                if not configured:run.update(status='UNAVAILABLE',error={'code':'CODEX_AUTH_NOT_CONFIGURED'});return
                content=json.loads(Path(configured).read_text(encoding='utf-8'))
                if content.get('auth_mode')!='chatgpt' or not content.get('tokens'):run.update(status='UNAVAILABLE',error={'code':'CHATGPT_AUTH_REQUIRED'});return
                credential={'auth_mode':'chatgpt','tokens':{k:v for k,v in content['tokens'].items() if k in {'access_token','id_token','refresh_token','account_id'}},'last_refresh':content.get('last_refresh')}
                from roll.agents.codex_process import execute
                execute(self,run,material,cancel,credential)
            else:
                key=os.environ.get('DEEPSEEK_API_KEY')
                if not key and os.environ.get('ROLL_DEEPSEEK_API_KEY_FILE'):key=Path(os.environ['ROLL_DEEPSEEK_API_KEY_FILE']).read_text(encoding='utf-8').strip()
                if not key:run.update(status='UNAVAILABLE',error={'code':'DEEPSEEK_AUTH_NOT_CONFIGURED'});return
                if self.endpoint!='https://api.deepseek.com' and key!='ROLL_METHOD_CASE_ONLY':raise ValueError('METHOD_ENDPOINT_REQUIRES_SYNTHETIC_CREDENTIAL')
                from roll.agents.deepseek_process import execute
                execute(self,run,material,cancel,key)
        except Exception as error:
            run.update(status='FAILED',error={'code':'TECHNICAL_REVIEW_HOST_ERROR','type':type(error).__name__})
        finally:
            if cancel.is_set() and run['status'] not in {'CANCELLED','TIMED_OUT'}:run.update(status='CANCELLED');run.pop('review_record',None)
            run['finished_at']=now()
            if run.get('review_record'):
                run['review_record'].update(finished_at=run['finished_at'],resolved_model=run['resolved_model'],tools=run['tools'])
                run['review_record_archive']=self.evidence.archive(encode(run['review_record']).encode(),'VERIFIED_TECHNICAL_REVIEW_RECORD')
            with self.lock:self.save(run);self.active.pop(run['run_id'],None)

    def cancel(self,identifier):
        run=self.get(identifier)
        with self.lock:
            event=self.active.get(identifier)
            if event:event.set()
        return {'run_id':identifier,'status':run['status'],'cancel_requested':event is not None}

    def close(self):
        with self.lock:
            for event in self.active.values():event.set()
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            with self.lock:
                if not self.active:return
            time.sleep(.05)

    def delivery(self,identifier):
        material=self.get_material(identifier);basis=material['basis_manifest'];runs=self.runs(identifier)
        complete=[self.get(r['run_id']) for r in runs if r['status']=='COMPLETE']
        review=complete[-1] if complete else None
        ended=basis['experiment_status'] in {'ENDED','COMPLETED'} and not basis['preliminary']
        checks_complete=not basis['incomplete_checks']
        gaps=[]
        if not ended:gaps.append('REGISTERED_EXPERIMENT_ENDPOINT_NOT_REACHED')
        if not checks_complete:gaps.extend(basis['incomplete_checks'])
        if not review:gaps.append('TECHNICAL_REVIEW_NOT_COMPLETE')
        return {'material_id':identifier,'material_fingerprint':material['material_fingerprint'],'validation_verdict':basis['validation_verdict'],
            'experiment_status':basis['experiment_status'],'review_status':'COMPLETE' if review else runs[-1]['status'] if runs else 'PENDING_TECHNICAL_REVIEW',
            'review_id':review['run_id'] if review else None,'blocking_issues_resolved':bool(review and review['review_record']['blocking_issues_resolved']),
            'delivery_status':'COMPLETE' if ended and checks_complete and review else 'INCOMPLETE','preliminary':not(ended and checks_complete and review),
            'capability_status':'NOT_GRANTED','human_review_label':LABEL,'gaps':gaps,'evidence_kind':material['evidence_kind']}

    def export(self,identifier):
        material=self.get_material(identifier);delivery=self.delivery(identifier);runs=[self.get(r['run_id']) for r in self.runs(identifier)]
        attachments={a['sha256']:a for a in [*material['local_archives'],*material['local_code'],material['manifest_archive']]}
        for run in runs:
            for archive in run['archives']+[run['review_record_archive']] if run.get('review_record_archive') else run['archives']:attachments[archive['sha256']]=archive
        stream=io.BytesIO()
        manifest={'delivery':delivery,'material':material,'review_attempts':runs,'attachments':list(attachments.values()),'human_review_label':LABEL}
        with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as package:
            package.writestr('manifest.json',encode(manifest))
            for code in material['local_code']:package.writestr('code/'+code['source_path'],self.evidence.raw(code['sha256']).read_bytes())
            for sha,archive in attachments.items():package.writestr('archives/'+sha,self.evidence.raw(sha).read_bytes())
        archive=self.evidence.archive(stream.getvalue(),'VALIDATION_DELIVERY_PACKAGE',extension='zip')
        return {'archive':archive,'delivery':delivery,'manifest_fingerprint':fingerprint(manifest)}
