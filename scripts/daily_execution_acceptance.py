"""Real HTTP execution over preserved17 host partitions and explicitly synthetic methods.

Copies opaque originals/checksums; never parses SEALED or imports user funding.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import sqlite3
import subprocess
import time
from datetime import datetime,timezone
import httpx


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--data-root',type=Path,required=True);parser.add_argument('--port',type=int,default=8038)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1];destination=args.data_root.resolve();source=args.source.resolve()
    destination.mkdir(parents=True,exist_ok=True)
    if (destination/'roll.sqlite3').exists():raise RuntimeError('Use a fresh isolated destination; never overwrite previous results')
    copies=[]
    for folder in ['raw','parquet']:
        for p in sorted((source/folder).glob('*')):
            if not p.is_file():continue
            target=destination/folder/p.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
            digest=hashlib.sha256(p.read_bytes()).hexdigest();assert hashlib.sha256(target.read_bytes()).hexdigest()==digest
            copies.append({'source':str(p),'destination':str(target),'sha256':digest,'bytes':p.stat().st_size,'purpose':'OPAQUE_ENGINEERING_PRESERVATION_NOT_SEALED_MODEL_INPUT'})
    with sqlite3.connect(source.as_uri()+'/roll.sqlite3?mode=ro',uri=True) as original,sqlite3.connect(destination/'roll.sqlite3') as copied:original.backup(copied)
    fixtures=runpy.run_path(str(root/'backend/tests/application/test_execution_labels.py'))
    fixtures['method_archive'](destination,{1:{'low':'97','high':'106'},2:{'low':'97','high':'106','open':'101'},20:{'close':'110','high':'110'}})
    report={'started_at':datetime.now(timezone.utc).isoformat(),'source':str(source),'data_root':str(destination),'source_copies':copies,
        'code_sha256':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [root/'backend/src/roll/app.py',root/'backend/src/roll/research/execution.py',root/'backend/uv.lock']},
        'sealed_price_or_result_consumption':False,'real_user_funding_or_forward_origin':False,'steps':[],'actual_runs':[],'method_runs':[]}
    log=(destination/'process-http.log').open('ab');process=None
    def start():
        p=subprocess.Popen([str(root/'backend/.venv/Scripts/python.exe'),'-X','utf8','-m','uvicorn','roll.app:create_app','--factory','--host','127.0.0.1','--port',str(args.port)],cwd=root/'backend',env={**os.environ,'ROLL_DATA_DIR':str(destination)},stdout=log,stderr=subprocess.STDOUT)
        for _ in range(200):
            try:
                if httpx.get(f'http://127.0.0.1:{args.port}/api/health').status_code==200:return p
            except httpx.TransportError:pass
            if p.poll() is not None:raise RuntimeError('process failed; see process-http.log')
            time.sleep(.1)
        p.terminate();raise RuntimeError('startup timeout')
    client=httpx.Client(base_url=f'http://127.0.0.1:{args.port}/api',timeout=60)
    def call(method,path,body=None,expected=200):
        response=client.request(method,path,json=body);assert response.status_code==expected,(path,response.status_code,response.text[:1000])
        report['steps'].append({'at':datetime.now(timezone.utc).isoformat(),'method':method,'path':path,'status':response.status_code})
        return response.json()
    try:
        process=start();report['process_ids']=[process.pid];account=call('GET','/account');assert account['version']==0 and not account['positions']
        datasets=call('GET','/research/datasets');actual=next(d for d in datasets if d['source_evidence_kind']=='REAL_ACQUISITION')
        protocols=call('GET','/research/protocols');protocol=next(p for p in protocols if p['dataset_id']==actual['dataset_id']);pid=protocol['protocol_id'];report['actual_protocol_id']=pid
        for partition in ['DEVELOPMENT','CALIBRATION']:
            part=call('GET',f'/research/datasets/{actual["dataset_id"]}/partitions/{partition}')
            assert all(f['trade_date']<'2026-09-01' for f in part['facts'])
            dates=[f['trade_date'] for f in part['facts'] if part['metadata']['first_date']<=f['trade_date']<=part['metadata']['last_date']]
            for d in dates:
                run=call('POST',f'/research/protocols/{pid}/executions',{'partition':partition,'observation_date':d,'quantity':'100','basis':'18实际已保全原价+允许分片；历史状态/公司行为/规则不足如实留不可评分，不计算封存收益'},201)
                assert run['result']['label_status']=='UNSCORABLE' and run['result']['label'] is None and run['result']['net_pnl_yuan'] is None
                assert not run['result']['eligible_for_training'];report['actual_runs'].append(run)
        first=report['actual_runs'][0];replay=call('POST',f'/research/executions/{first["execution_id"]}/replay',{})
        assert replay['network_calls']==0 and replay['matches_original']
        support=call('GET',f'/research/protocols/{pid}/execution-support');assert support['record_count']==120 and support['eligible_for_training_count']==0
        report['actual_support']={k:v for k,v in support.items() if k!='records'}
        method=call('POST','/research/datasets',{'archive_id':'method-execution','basis':'明确合成OHLC/rules/state的方法压力；与REAL_ACQUISITION分列，禁止真实训练/G7'},201)
        mp=call('POST','/research/protocols',{'dataset_id':method['dataset_id'],'predecessor_id':pid,'basis':'METHOD_CASE工程事件/价窗/费用/T+1/路径/成熟性验证，保留前序真实未知结论，不赋资格'},201);mpid=mp['protocol_id'];report['method_protocol_id']=mpid
        variants=[{'label_as_of':'2026-01-06T16:00:00+08:00'}, {},{'delay':'NEXT_CLOSE'},{'delay':'ONE_MORE_SESSION_OPEN'},
            {'fill_fraction':'0.50'},{'fill_fraction':'0'},{'delay':'OUTSIDE_ALLOWED_PRICE_NO_FILL'},
            {'method_barriers':{'stop_price_yuan':'98','profit_price_yuan':'104'},'path_policy':'CONSERVATIVE'},
            {'method_barriers':{'stop_price_yuan':'98','profit_price_yuan':'104'},'path_policy':'INTERVAL'},
            {'method_barriers':{'stop_price_yuan':'98','profit_price_yuan':'104'},'path_policy':'UNDETERMINABLE'},
            {'commission_scenario_rate':'0.003','slippage_each_side_rate':'0.002'}]
        for variant in variants:
            run=call('POST',f'/research/protocols/{mpid}/executions',{'partition':'DEVELOPMENT','observation_date':'2026-01-05','quantity':'200','basis':'公开HTTP明确METHOD压力：非真实G7/实际成交/用户财富',**variant},201)
            assert not run['result']['eligible_for_training'];report['method_runs'].append(run)
            assert call('POST',f'/research/executions/{run["execution_id"]}/replay',{})['matches_original']
        original=report['method_runs'][0]
        child=call('POST',f'/research/executions/{original["execution_id"]}/assessments',{'label_as_of':datetime.now(timezone.utc).isoformat(),'basis':'新增成熟复评，不改次日未成熟原记录'},201)
        assert child['result']['label_status']=='MATURE' and call('GET',f'/research/executions/{original["execution_id"]}')==original
        report['assessment']=child
        call('POST',f'/research/protocols/{mpid}/executions',{'partition':'SEALED','observation_date':'2026-09-01','basis':'METHOD封存拒绝边界，不消费封存'},403)
        sha=first['input_archive']['sha256'];download=client.get('/data/archives/'+sha)
        assert download.status_code==200 and hashlib.sha256(download.content).hexdigest()==sha
        assert download.headers['x-content-type-options']=='nosniff' and 'attachment' in download.headers['content-disposition']
        report['input_download']={'sha256':sha,'bytes':len(download.content),'matches':True,'network_used_only_localhost':True}
        process.terminate();process.wait(timeout=20);process=start();report['process_ids'].append(process.pid)
        assert call('GET',f'/research/executions/{first["execution_id"]}')==first and call('GET',f'/research/executions/{original["execution_id"]}')==original
        assert call('GET','/account')==account
        report.update(passed=True,finished_at=datetime.now(timezone.utc).isoformat(),account_unchanged=True)
    finally:
        client.close()
        if process and process.poll() is None:process.terminate();process.wait(timeout=20)
        log.close();(destination/'real-execution.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')


if __name__=='__main__':main()
