"""Two real server processes query/replay the same frozen artifacts, never refit."""
import hashlib,json,os,subprocess,time
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'.scratch/roll-p0/evidence/19-reconstruction-2026-10-10';STATE=json.loads((OUT/'v4/run-state.json').read_text())
def main():
    rounds=[]
    for index in [1,2]:
        guard=OUT/f'http-host-{index}-network.json';log=(OUT/f'http-host-{index}.txt').open('w',encoding='utf-8')
        env={**os.environ,'ROLL_ENV':'test','ROLL_DATA_DIR':str(ROOT/'.roll-data/reconstructed19-v1'),'ROLL_TEST_API_PORT':'8049','ROLL_OFFLINE_GUARD_FILE':str(guard),'PYTHONPATH':str(ROOT/'backend/src')}
        process=subprocess.Popen([str(ROOT/'backend/.venv/Scripts/python.exe'),'-B','-X','utf8',str(ROOT/'scripts/reconstructed19_host.py')],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            with httpx.Client(base_url='http://127.0.0.1:8049/api',trust_env=False,timeout=30) as client:
                deadline=time.monotonic()+180
                while True:
                    if process.poll() is not None:raise RuntimeError(f'Host exited {process.returncode}')
                    try:
                        if client.get('/health').status_code==200:break
                    except httpx.HTTPError:pass
                    if time.monotonic()>deadline:raise RuntimeError('Host health deadline')
                    time.sleep(.5)
                model=client.get('/research/models/'+STATE['model_run_id']);model.raise_for_status()
                forecast=client.get('/research/forecasts/'+STATE['forecast_id']);forecast.raise_for_status()
                assert model.json()==json.loads((OUT/'v4/real-model.json').read_text(encoding='utf-8'))
                assert forecast.json()==json.loads((OUT/'v4/real-forecast.json').read_text(encoding='utf-8'))
                replay=client.post('/research/forecasts/'+STATE['forecast_id']+'/replay');replay.raise_for_status();value=replay.json()
                assert value['network_calls']==0 and value['matches_original']
                assert client.post('/research/models/'+STATE['model_run_id']+'/forecasts',json={'observation_date':'2026-10-10','basis':'Current date must remain outside historical research scope'}).status_code==403
                rounds.append({'pid':process.pid,'persistent_model_equal':True,'persistent_forecast_equal':True,'replay':value,'current_date_prediction_rejected':True,'guard':json.loads(guard.read_text())})
                assert not rounds[-1]['guard']['external_attempts']
        finally:
            process.terminate();process.wait(timeout=30);log.close()
    assert rounds[0]['pid']!=rounds[1]['pid']
    (OUT/'v4/http-restart-replay.json').write_text(json.dumps({'passed':True,'rounds':rounds},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':True,'separate_host_pids':[r['pid'] for r in rounds],'external_attempts':0,'current_date_rejected':True}))
if __name__=='__main__':main()
