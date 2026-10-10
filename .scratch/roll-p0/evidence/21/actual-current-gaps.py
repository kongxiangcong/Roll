"""Run only on an isolated consistent copy of actual19 runtime, never the original."""
import argparse
import json
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app

parser=argparse.ArgumentParser()
parser.add_argument('--data-dir',required=True)
parser.add_argument('--output',required=True)
args=parser.parse_args()
directory=Path(args.data_dir).resolve()
protected=Path('D:/dsh-proj/Roll/.roll-data/reconstructed19-v1').resolve()
if directory==protected or protected in directory.parents:
    raise SystemExit('Use a separately preserved SQLite-backup/archive copy, never original19 runtime')
pid='f977645b-200a-4c39-a6de-5e122f4e5101'
mid='8be461f3-af8b-4f0f-a707-13e41cf48249'
with TestClient(create_app(directory)) as client:
    account=client.get('/api/account').json()
    manifest=client.get(f'/api/research/protocols/{pid}/attempt-manifest').json()
    model=client.get(f'/api/research/models/{mid}').json()
    assert model['data_use']=='RECONSTRUCTED_RESEARCH' and model['evidence_kind']=='REAL_ACQUISITION'
    response=client.post(f'/api/research/protocols/{pid}/complete-freezes',json={
        'model_run_id':mid,'attempt_ids':manifest['attempt_ids'],'artifact_fingerprints':model['artifact_fingerprints'],
        'baseline':{'cash_yuan':'100000.00','positions':[]},'basis':'Actual reconstructed fixed model, isolated current-gap validation; not actual user funds/strict PIT/qualification'})
    assert response.status_code==201,response.text
    frozen=response.json()
    forecasts=[]
    for item in model['calibration_predictions'][:3]:
        r=client.post(f'/api/research/models/{mid}/forecasts',json={'observation_date':item['observation_date'],'basis':'Actual reconstructed current historical diagnostic only'})
        assert r.status_code==201,r.text
        forecasts.append(r.json())
    last=forecasts[-1]['observation_cutoff'][:10]
    r=client.post(f"/api/research/shadow/{frozen['freeze_id']}/advance",json={'through_date':last,'forecast_ids':[f['forecast_id'] for f in forecasts],'expected_revision':0})
    assert r.status_code==201,r.text
    path=f"/api/research/complete-freezes/{frozen['freeze_id']}/validations"
    command={'purpose':'DIAGNOSTIC','expected_complete_protocol_fingerprint':frozen['complete_protocol_fingerprint'],'basis':'Actual current frozen19 model limitations; noSEALED/no new fits/no actual forward'})
    r=client.post(path,json=command)
    assert r.status_code==201,r.text
    result=r.json()
    assert result['validation_verdict']!='PASS' and result['gates']['G7']['status']=='INCONCLUSIVE'
    replay=client.post(f"/api/research/validations/{result['validation_id']}/replay").json()
    assert replay['matches_original'] and replay['network_calls']==0
    refusal=client.post(path,json={**command,'purpose':'CONFIRMATORY'})
    assert refusal.status_code==409 and refusal.json()['detail']['sealed_read'] is False
    assert client.get('/api/account').json()==account
    assert client.get(f'/api/research/protocols/{pid}/attempt-manifest').json()==manifest
    assert client.get(f'/api/research/protocols/{pid}').json()['forward_started_at'] is None
    record={'runtime_copy':str(directory),'full_freeze':frozen,'validation':result,'replay':replay,'confirmation_refusal':refusal.json(),
        'account_unchanged':True,'original_fit_attempts_unchanged':True,'no_new_fit':True,'sealed_consumed':False,'forward_started':False}
    Path(args.output).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'validation_id':result['validation_id'],'verdict':result['validation_verdict'],'sealed_read':False,'replay_matches':True}))
