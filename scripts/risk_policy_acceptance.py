"""Read-only real source preservation + distinct deterministic METHOD policy acceptance."""
import argparse,hashlib,json,os,runpy,shutil,sqlite3,subprocess,time
from pathlib import Path
from datetime import datetime,timezone
import httpx


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--data-root',type=Path,required=True);parser.add_argument('--method',action='store_true');parser.add_argument('--port',type=int,default=8042)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1];target=args.data_root.resolve();source=args.source.resolve()
    target.mkdir(parents=True,exist_ok=True)
    if (target/'roll.sqlite3').exists():raise RuntimeError('Fresh target required; original policies/evaluations must not be overwritten')
    report={'started_at':datetime.now(timezone.utc).isoformat(),'data_root':str(target),'method':args.method,'source':str(source),'copies':[],'steps':[],'sealed_consumed':False,'formal_action_published':False}
    if not args.method:
        for folder in ['raw','parquet']:
            for p in sorted((source/folder).glob('*')):
                if not p.is_file():continue
                dest=target/folder/p.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
                digest=hashlib.sha256(p.read_bytes()).hexdigest();assert hashlib.sha256(dest.read_bytes()).hexdigest()==digest
                report['copies'].append({'source':str(p),'destination':str(dest),'bytes':p.stat().st_size,'sha256':digest,'purpose':'OPAQUE_PRESERVATION_NOT_SEALED_RESEARCH_INPUT'})
        with sqlite3.connect((source/'roll.sqlite3').as_uri()+'?mode=ro',uri=True) as original,sqlite3.connect(target/'roll.sqlite3') as copied:original.backup(copied)
    log=(target/'process-http.log').open('ab');process=None
    client=httpx.Client(base_url=f'http://127.0.0.1:{args.port}',timeout=60)
    def start():
        factory='risk_policy_method_app:factory' if args.method else 'roll.app:create_app'
        environment={**os.environ,'ROLL_DATA_DIR':str(target),'PYTHONPATH':str(root/'backend/tests/support')}
        if args.method:environment['ROLL_ENV']='test'
        p=subprocess.Popen([str(root/'backend/.venv/Scripts/python.exe'),'-X','utf8','-m','uvicorn',factory,'--factory','--host','127.0.0.1','--port',str(args.port)],cwd=root/'backend',env=environment,stdout=log,stderr=subprocess.STDOUT)
        for _ in range(200):
            try:
                if client.get('/api/health').status_code==200:return p
            except httpx.TransportError:pass
            if p.poll() is not None:raise RuntimeError('startup failed: process-http.log')
            time.sleep(.1)
        p.terminate();raise RuntimeError('startup timeout')
    def call(method,path,body=None,status=200):
        response=client.request(method,'/api'+path,json=body);assert response.status_code==status,(path,response.status_code,response.text[:1200])
        report['steps'].append({'at':datetime.now(timezone.utc).isoformat(),'method':method,'path':path,'status':status})
        return response.json()
    try:
        process=start();report['process_ids']=[process.pid]
        if args.method:
            helper=runpy.run_path(str(root/'backend/tests/application/test_risk_policy.py'))
            protocol,policy=helper['policy_case'](client,target)
            asof=helper['ASOF'];report['synthetic_funding_not_human_authorization']=True
            command={'kind':'FEE','expected_account_version':2,'payload':{'effective_at':'2026-09-30T15:00:00+08:00','source':'METHOD cash-only未确认费用','record_id':'method-fee','amount':'5','basis':'金额待核','instrument':None,'broker_available_after':None}}
            call('POST','/account/drafts',command,201)
        else:
            account=call('GET','/account');assert account['version']==0
            protocols=call('GET','/research/protocols');datasets=call('GET','/research/datasets');actual=next(d for d in datasets if d['source_evidence_kind']=='REAL_ACQUISITION')
            protocol=next(p for p in protocols if p['dataset_id']==actual['dataset_id']);asof=datetime.now(timezone.utc).isoformat()
            policy=call('POST',f'/research/protocols/{protocol["protocol_id"]}/risk-policies',{'basis':'22独立风险政策原件+当前实际无用户资金授权，记录不足、不继承19失败/收益门槛'},201)
        report['policy']=policy
        result=call('POST',f'/research/risk-policies/{policy["policy_id"]}/evaluations',{'required_as_of':asof,'basis':'独立口径/数量/授权/压力检查；非正式动作'},201);report['evaluation']=result
        if args.method:
            assert result['account_use_check']['state']=='UPDATE_PENDING' and result['account_use_check']['allowed']
            assert result['positions'][0]['executable_quantity']=='400' and result['engineering_verdict']=='PASS'
        else:assert result['executable_quantities'] is None and 'FUNDING_AUTHORIZATION_MISSING' in result['reasons']
        assert result['validation_verdict']=='INCONCLUSIVE' and result['formal_action'] is None
        replay=call('POST',f'/research/risk-evaluations/{result["evaluation_id"]}/replay',{});assert replay['matches_original'] and replay['network_calls']==0;report['replay']=replay
        report['validation']=call('GET',f'/research/risk-policies/{policy["policy_id"]}/validation');assert report['validation']['validation_verdict']=='INCONCLUSIVE'
        call('POST','/formal/evaluate',{'basis_type':'RISK_POLICY','policy_id':policy['policy_id'],'action':'EXIT'},403)
        if args.method:
            shrink=helper['funding'](1,single_exposure='10000.00',effective_at='2026-09-30T10:00:00+08:00')
            call('POST','/funding/confirm',shrink)
            shrunk=call('POST',f'/research/risk-policies/{policy["policy_id"]}/evaluations',{'required_as_of':asof,'basis':'当前缩小授权交集'},201)
            assert shrunk['positions'][0]['executable_quantity']=='800';report['shrunk']=shrunk
            command=helper['fill'](2,'method-qty-pending');command['payload'].update(instrument='SSE:600519',effective_at='2026-09-30T13:00:00+08:00')
            call('POST','/account/drafts',command,201)
            blocked=call('POST',f'/research/risk-policies/{policy["policy_id"]}/evaluations',{'required_as_of':asof,'basis':'未决数量禁止合成可卖量'},201)
            assert blocked['executable_quantities'] is None;report['quantity_blocked']=blocked
        for archive in [policy['material_archive'],result['input_archive']]:
            download=client.get('/api/data/archives/'+archive['sha256']);assert hashlib.sha256(download.content).hexdigest()==archive['sha256']
            assert download.headers['x-content-type-options']=='nosniff' and 'attachment' in download.headers['content-disposition']
        process.terminate();process.wait(timeout=20);process=start();report['process_ids'].append(process.pid)
        assert call('GET',f'/research/risk-policies/{policy["policy_id"]}')==policy
        assert call('GET',f'/research/risk-evaluations/{result["evaluation_id"]}')==result
        assert call('POST',f'/research/risk-evaluations/{result["evaluation_id"]}/replay',{})['matches_original']
        if not args.method:assert call('GET','/account')==account
        assert call('GET','/capabilities')['state']=='UNGRANTED'
        report.update(passed=True,finished_at=datetime.now(timezone.utc).isoformat(),real_user_authorization_created=False)
    finally:
        client.close()
        if process and process.poll() is None:process.terminate();process.wait(timeout=20)
        log.close();(target/'risk-policy-http.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')


if __name__=='__main__':main()
