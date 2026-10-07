"""Bounded localhost acceptance: real18 support refusal and separate synthetic model math."""
import argparse,hashlib,json,os,runpy,shutil,sqlite3,subprocess,time
from pathlib import Path
from datetime import datetime,timezone
import httpx


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--data-root',type=Path,required=True);parser.add_argument('--port',type=int,default=8039)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1];source=args.source.resolve();target=args.data_root.resolve()
    target.mkdir(parents=True,exist_ok=True)
    if (target/'roll.sqlite3').exists():raise RuntimeError('Fresh isolated target required; no overwrite of earlier attempts')
    copies=[]
    for folder in ['raw','parquet']:
        for original in sorted((source/folder).glob('*')):
            if not original.is_file():continue
            destination=target/folder/original.name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,destination)
            digest=hashlib.sha256(original.read_bytes()).hexdigest();assert hashlib.sha256(destination.read_bytes()).hexdigest()==digest
            copies.append({'source':str(original),'destination':str(destination),'bytes':original.stat().st_size,'sha256':digest,'purpose':'OPAQUE_COPY_NOT_SEALED_MODEL_CONSUMPTION'})
    with sqlite3.connect((source/'roll.sqlite3').as_uri()+'?mode=ro',uri=True) as original,sqlite3.connect(target/'roll.sqlite3') as copied:original.backup(copied)
    report={'started_at':datetime.now(timezone.utc).isoformat(),'source':str(source),'data_root':str(target),'copies':copies,'sealed_consumed':False,'steps':[]}
    log=(target/'process-http.log').open('ab');process=None
    def start():
        p=subprocess.Popen([str(root/'backend/.venv/Scripts/python.exe'),'-X','utf8','-m','uvicorn','roll.app:create_app','--factory','--host','127.0.0.1','--port',str(args.port)],cwd=root/'backend',env={**os.environ,'ROLL_DATA_DIR':str(target)},stdout=log,stderr=subprocess.STDOUT)
        for _ in range(200):
            try:
                if httpx.get(f'http://127.0.0.1:{args.port}/api/health').status_code==200:return p
            except httpx.TransportError:pass
            if p.poll() is not None:raise RuntimeError('Startup failed: inspect process-http.log')
            time.sleep(.1)
        p.terminate();raise RuntimeError('Startup timeout')
    client=httpx.Client(base_url=f'http://127.0.0.1:{args.port}',timeout=60)
    def call(method,path,body=None,status=200):
        response=client.request(method,'/api'+path,json=body);assert response.status_code==status,(path,response.status_code,response.text[:1200])
        report['steps'].append({'at':datetime.now(timezone.utc).isoformat(),'method':method,'path':path,'status':response.status_code})
        return response.json()
    try:
        process=start();report['process_ids']=[process.pid];account=call('GET','/account');assert account['version']==0
        datasets=call('GET','/research/datasets');actual=next(d for d in datasets if d['source_evidence_kind']=='REAL_ACQUISITION')
        protocols=call('GET','/research/protocols');protocol=next(p for p in protocols if p['dataset_id']==actual['dataset_id']);pid=protocol['protocol_id']
        support=call('GET',f'/research/protocols/{pid}/execution-support');assert support['record_count']==120 and support['eligible_for_training_count']==0
        report['actual_support']=support
        model=call('POST',f'/research/protocols/{pid}/models',{'purpose':'RESEARCH','basis':'19实际消费18同原输入120不可评分；未知不训练，不产生占位概率'},201)
        assert model['status']=='FAILED' and model['model_artifact'] is None and model['forecast_probability'] is None
        assert model['statistical_support']['development_total']==0 and model['statistical_support']['calibration_total']==0
        report['actual_model']=model
        call('POST',f'/research/models/{model["model_run_id"]}/forecasts',{'observation_date':'2026-06-08','basis':'实际失败无预测'},409)
        helper=runpy.run_path(str(root/'backend/tests/application/test_transparent_models.py'))
        dataset,method,dates=helper['known_method'](client,target,protocols[0]['protocol_id']);mpid=method['protocol_id']
        method_model=call('POST',f'/research/protocols/{mpid}/models',{'purpose':'METHOD_VALIDATION','basis':'固定4量价特征/lambda1/截距校准数学和SHA工件方法；统计不足仍保留'},201)
        assert method_model['status']=='METHOD_ARTIFACT_ONLY';report['method_model']=method_model
        bundle=call('POST',f'/research/models/{method_model["model_run_id"]}/forecasts',{'observation_date':dates[110],'basis':'明确方法时间外原模型预测；校准并非独立验证，无真实起点'},201);report['method_forecast']=bundle
        assert call('POST',f'/research/forecasts/{bundle["forecast_id"]}/replay',{})['matches_original']
        call('POST',f'/research/models/{method_model["model_run_id"]}/forecasts',{'observation_date':dates[170],'basis':'封存不可消费'},403)
        attempts=call('GET',f'/research/protocols/{mpid}/attempt-manifest')
        call('POST',f'/research/protocols/{mpid}/freeze',{'attempt_ids':attempts['attempt_ids']},409)
        for archive in [model['input_archive'],method_model['model_artifact'],method_model['calibrator_artifact'],bundle['archive']]:
            response=client.get('/api/data/archives/'+archive['sha256']);assert hashlib.sha256(response.content).hexdigest()==archive['sha256']
            assert response.headers['x-content-type-options']=='nosniff' and 'attachment' in response.headers['content-disposition']
        process.terminate();process.wait(timeout=20);process=start();report['process_ids'].append(process.pid)
        assert call('GET',f'/research/models/{model["model_run_id"]}')==model
        assert call('GET',f'/research/forecasts/{bundle["forecast_id"]}')==bundle
        replay=call('POST',f'/research/forecasts/{bundle["forecast_id"]}/replay',{});assert replay['network_calls']==0 and replay['matches_original'];report['replay']=replay
        assert call('GET','/account')==account
        assert call('GET',f'/research/protocols/{mpid}')['forward_started_at'] is None
        report.update(passed=True,account_unchanged=True,real_forward_origin=False,finished_at=datetime.now(timezone.utc).isoformat())
    finally:
        client.close()
        if process and process.poll() is None:process.terminate();process.wait(timeout=20)
        log.close();(target/'real-model.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')


if __name__=='__main__':main()
