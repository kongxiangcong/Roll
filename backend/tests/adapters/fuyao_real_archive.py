"""Opt-in actual Fuyao FastAPI/archive acceptance. Requires host environment key."""
import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime,timezone
from fastapi.testclient import TestClient
from roll.app import create_app


def run(directory, report):
    result={'kind':'REAL_ACQUISITION','started_at':datetime.now(timezone.utc).isoformat(),'runs':[],
        'credential_source':'HOST_ENVIRONMENT_ONLY','account_written':False,'historical_pit_proven':False}
    with TestClient(create_app(directory)) as client:
        before=client.get('/api/account').json()
        listing=client.get('/api/market/list').json()
        response=client.post('/api/market/watch',json={'operation':'ADD','instrument':'SSE:600519','expected_list_version':listing['version']})
        assert response.status_code==200,response.text
        commands=[{'instruments':['SSE:600519'],'groups':['DAILY','QUOTE','STATUS','ADJUSTMENTS'],'purpose':'RESEARCH',
            'start_date':'2023-01-01','end_date':'2026-09-30','daily_source':'FUYAO','quote_source':'FUYAO','adjustment_source':'FUYAO'},
            {'instruments':['SSE:000001','SZSE:399001','SZSE:399997'],'groups':['DAILY'],'purpose':'BACKGROUND',
            'start_date':'2026-01-01','end_date':'2026-09-30','daily_source':'FUYAO'}]
        for command in commands:
            request=client.post('/api/data/requests',json={**command,'timeout_seconds':60,'max_calls':8})
            assert request.status_code==201,request.text
            value=client.post('/api/data/requests/'+request.json()['request_id']+'/retrieve').json()
            snapshot=client.get('/api/data/snapshots/'+value['snapshot_id']).json()
            actual=[]
            for archive in snapshot['archives']+[snapshot['parquet']]:
                data=client.get('/api/data/archives/'+archive['sha256']).content
                assert hashlib.sha256(data).hexdigest()==archive['sha256']
                actual.append({'sha256':archive['sha256'],'bytes':len(data),'kind':archive['kind']})
            replay=client.post('/api/data/runs/'+value['run_id']+'/replay').json()
            assert replay['network_calls']==0 and replay['facts']==snapshot['facts']
            result['runs'].append({'run':value,'snapshot_id':snapshot['snapshot_id'],'coverage':snapshot['coverage'],
                'archive_checks':actual,'offline_replay_equal':True,'network_calls_replay':0,
                'daily_rows':sum(f['group']=='DAILY' for f in snapshot['facts']),
                'daily_allowed':sum(f['group']=='DAILY' and f['model_daily_input_allowed'] for f in snapshot['facts']),
                'history_unknown_calendar_rows':sum('CALENDAR_COVERAGE_UNKNOWN' in f.get('limitations',[]) for f in snapshot['facts']),
                'quote_times':[{'instrument':f['instrument'],'upstream_at':f['upstream_at'],'trade_date':f['trade_date'],
                    'source_snapshot_ready_at':f.get('source_snapshot_ready_at')} for f in snapshot['facts'] if f['group']=='QUOTE'],
                'actions':[{'ex_date':f['ex_date'],'cash_per_share':f['cash_per_share'],'disclosure_date':f['disclosure_date'],
                    'historical_complete_actions_verified':f['historical_complete_actions_verified']} for f in snapshot['facts'] if f['group']=='ADJUSTMENTS']})
        assert before==client.get('/api/account').json()
        result['account_unchanged']=True
    with TestClient(create_app(directory)) as client:
        for item in result['runs']:
            original=client.get('/api/data/runs/'+item['run']['run_id']).json()
            assert original==item['run']
            assert client.post('/api/data/runs/'+original['run_id']+'/replay').json()['network_calls']==0
        result['restart_original_runs_equal']=True
    result['finished_at']=datetime.now(timezone.utc).isoformat()
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'report':str(report),'runs':[{k:r[k] for k in ['snapshot_id','daily_rows','daily_allowed','history_unknown_calendar_rows']} for r in result['runs']],'account_unchanged':True},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,required=True);parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();run(args.directory,args.report)
