"""Opt-in bounded background acceptance; host supplies Fuyao credentials."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app


def run(directory, report):
    result={'kind':'REAL_BACKGROUND_ACQUISITION','started_at':datetime.now(timezone.utc).isoformat(),
        'scope':['SSE:000300','SSE:000905'],'purpose':'BACKGROUND','start_date':'2026-09-01',
        'end_date':'2026-09-30','credential_source':'HOST_ENVIRONMENT_ONLY',
        'model_training':False,'sealed_outcomes_read':False,'historical_pit_proven':False}
    with TestClient(create_app(directory)) as client:
        before=client.get('/api/account').json()
        listing=client.get('/api/market/list').json()
        assert len(listing['background_indices'])==5
        command={k:result[k] for k in ['purpose','start_date','end_date']}
        response=client.post('/api/data/requests',json={**command,'instruments':result['scope'],
            'groups':['DAILY'],'daily_source':'FUYAO','timeout_seconds':60,'max_calls':2})
        assert response.status_code==201,response.text
        value=client.post('/api/data/requests/'+response.json()['request_id']+'/retrieve').json()
        result['run']=value
        snapshot=client.get('/api/data/snapshots/'+value['snapshot_id']).json()
        result['daily_rows']={instrument:sum(f['instrument']==instrument for f in snapshot['facts'])
            for instrument in result['scope']}
        result['coverage']=snapshot['coverage']
        result['archive_checks']=[]
        for archive in snapshot['archives']+[snapshot['parquet']]:
            raw=client.get('/api/data/archives/'+archive['sha256']).content
            assert hashlib.sha256(raw).hexdigest()==archive['sha256']
            result['archive_checks'].append({'sha256':archive['sha256'],'bytes':len(raw),'kind':archive['kind']})
        replay=client.post('/api/data/runs/'+value['run_id']+'/replay').json()
        assert replay['network_calls']==0 and replay['facts']==snapshot['facts']
        result['offline_replay_equal']=True
        result['network_calls_replay']=0
        assert client.get('/api/account').json()==before
        assert all(not f['model_daily_input_allowed'] for f in snapshot['facts'])
        result['account_unchanged']=True
        result['individual_stock_model_input_allowed']=False
    with TestClient(create_app(directory)) as client:
        assert client.get('/api/data/runs/'+value['run_id']).json()==value
        assert client.post('/api/data/runs/'+value['run_id']+'/replay').json()['network_calls']==0
        result['restart_original_run_equal']=True
    result['finished_at']=datetime.now(timezone.utc).isoformat()
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    assert value['status']=='COMPLETE' and all(count>0 for count in result['daily_rows'].values()),value
    print(json.dumps({'status':value['status'],
        'daily_rows':result['daily_rows'],'report':str(report)},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();run(args.directory,args.report)
