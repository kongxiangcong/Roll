"""Actual HTTP/SQLite engineering registration using a preserved public-source bundle.

No fitting, labels, strategy returns or confirmatory result is computed here.
Requires a host-curated research-inputs/<archive-id> directory; never imports its account.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from datetime import datetime,timezone
import httpx


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--data-root',type=Path,required=True)
    parser.add_argument('--archive-id',default='07-browser');parser.add_argument('--port',type=int,default=8037)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1];directory=args.data_root.resolve();directory.mkdir(parents=True,exist_ok=True)
    report={'evidence_kind':'REAL_PRESERVED_PUBLIC_SOURCE_AND_REAL_HTTP_SQLITE; METHOD_ATTEMPT_ERRORS',
        'started_at':datetime.now(timezone.utc).isoformat(),'data_root':str(directory),'labels_or_candidate_results_computed':False,'steps':[]}
    report['code_sha256']={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
        [root/'backend/src/roll/app.py',*sorted((root/'backend/src/roll/research').glob('*.py')),root/'backend/uv.lock']}
    report['process_ids']=[]
    log=(directory/'process-http.log').open('ab');process=None
    def start():
        p=subprocess.Popen([str(root/'backend/.venv/Scripts/python.exe'),'-X','utf8','-m','uvicorn','roll.app:create_app','--factory','--host','127.0.0.1','--port',str(args.port)],cwd=root/'backend',env={**os.environ,'ROLL_DATA_DIR':str(directory)},stdout=log,stderr=subprocess.STDOUT)
        report['process_ids'].append(p.pid)
        for _ in range(200):
            try:
                if httpx.get(f'http://127.0.0.1:{args.port}/api/health').status_code==200:return p
            except httpx.TransportError:pass
            if p.poll() is not None:raise RuntimeError('service startup failed; see process-http.log')
            time.sleep(.1)
        p.terminate();raise RuntimeError('bounded startup timeout')
    def call(method,path,body=None,expected=200,omit_facts=False):
        response=httpx.request(method,f'http://127.0.0.1:{args.port}/api'+path,json=body,timeout=60)
        assert response.status_code==expected,(path,response.status_code,response.text[:2000])
        value=response.json()
        saved={k:v for k,v in value.items() if k!='facts'} if omit_facts else value
        report['steps'].append({'at':datetime.now(timezone.utc).isoformat(),'method':method,'path':path,'status':response.status_code,'response':saved})
        return value
    try:
        process=start()
        before=call('GET','/account');assert before['version']==0,'Use a fresh isolated account; no user facts or synthetic source account import'
        dataset=call('POST','/research/datasets',{'archive_id':args.archive_id,'basis':'17真实07公开归档SHA核验，基于日期覆盖预登记M0；不读取/计算策略标签结果'},201)
        assert dataset['source_evidence_kind']=='REAL_ACQUISITION' and dataset['coverage']['session_count']==181
        existing=call('GET','/research/protocols');predecessor=existing[0]['protocol_id'] if existing else None
        protocol=call('POST','/research/protocols',{'dataset_id':dataset['dataset_id'],'predecessor_id':predecessor,'basis':'实际181条覆盖登记，封存独立性未证明且不具历史PIT，不授模型/正式使用资格'},201);pid=protocol['protocol_id']
        for name,rows in [('DEVELOPMENT',80),('CALIBRATION',60)]:
            part=call('GET',f'/research/datasets/{dataset["dataset_id"]}/partitions/{name}',omit_facts=True)
            assert len(part['facts'])==rows and all(f['trade_date']<'2026-09-01' for f in part['facts'])
            assert part['all_available_to_this_consumer'] is True
        ids=[]
        for status in ['FAILED','ABORTED',None]:
            attempt=call('POST',f'/research/protocols/{pid}/attempts',{'category':'ENGINEERING_REPLAY','partition':'DEVELOPMENT','configuration':{'method_case':True,'fit_executed':False,'prompt':None,'basis':'fixed error/abort/restart test; no real trained result'},'basis':'公开HTTP失败/中止/重启留痕机制，不冒充实际模型训练'},201);ids.append(attempt['attempt_id'])
            if status:call('POST',f'/research/attempts/{ids[-1]}/finish',{'status':status,'reason':'固定方法错误/主动中止；未进行拟合'})
        call('POST',f'/research/protocols/{pid}/freeze',{'attempt_ids':ids[1:]},409)
        call('POST',f'/research/protocols/{pid}/checkpoints',{'kind':'EARLY_PASS','reason':'METHOD_CASE:未登记可选停止必须拒绝并保留'},409)
        call('POST',f'/research/protocols/{pid}/checkpoints',{'kind':'OPERATIONS','reason':'只记录工程运行检查，不做统计PASS'},201)
        # Engineering sealed input access is explicit; only metadata is written to this report.
        call('POST',f'/research/protocols/{pid}/sealed-input',{'reason':'17公开边界核验实际输入访问；不计算标签或候选策略结果；同窗独立性UNPROVEN'},omit_facts=True)
        sha=dataset['original_archives'][-1]['sha256']
        raw=httpx.get(f'http://127.0.0.1:{args.port}/api/data/archives/{sha}',timeout=60)
        assert raw.status_code==200 and hashlib.sha256(raw.content).hexdigest()==sha
        assert raw.headers['x-content-type-options']=='nosniff' and 'attachment' in raw.headers['content-disposition']
        report['archive_download']={'sha256':sha,'bytes':len(raw.content),'hash_matches':True,'purpose':'ENGINEERING_HASH_CHECK; NOT_CONFIRMATORY_RESULT_LOOK'}
        process.terminate();process.wait(timeout=20);process=start()
        attempts=call('GET',f'/research/protocols/{pid}/attempts');assert [a['status'] for a in attempts]==['FAILED','ABORTED','INTERRUPTED']
        assert call('GET',f'/research/protocols/{pid}')==protocol
        audit=call('GET',f'/research/protocols/{pid}/audit');assert any(a['action']=='ATTEMPT_INTERRUPTED' for a in audit)
        manifest=call('GET',f'/research/protocols/{pid}/attempt-manifest')
        refused=call('POST',f'/research/protocols/{pid}/freeze',{'attempt_ids':manifest['attempt_ids']},409)
        assert 'ATTEMPT_MANIFEST_INCOMPLETE' not in refused['detail']['gaps']
        successor=call('POST','/research/protocols',{'dataset_id':dataset['dataset_id'],'predecessor_id':pid,'basis':'METHOD_CASE关联修正，原结论和区间暴露不重置'},201)
        assert successor['sealed_independence']=='UNPROVEN'
        after=call('GET','/account');assert after==before
        report.update(finished_at=datetime.now(timezone.utc).isoformat(),account_unchanged=True,protocol_id=pid,dataset_id=dataset['dataset_id'],passed=True)
    finally:
        if process and process.poll() is None:process.terminate();process.wait(timeout=20)
        log.close();(directory/'real-registration.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')


if __name__=='__main__':main()
