"""Public forward archive boundary; synthetic time proves engineering only."""
from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from roll.app import create_app
from test_shadow import setup, freeze


def test_unique_method_sample_and_restart_never_start_actual_clock(tmp_path):
    clock = [datetime.fromisoformat('2026-06-10T16:00:00+08:00')]
    app = create_app(tmp_path, review_clock=lambda: clock[0])
    with TestClient(app) as client:
        _, protocol, model, dates = setup(client, tmp_path)
        day = dates[110]
        clock[0] = datetime.fromisoformat(day+'T16:00:00+08:00')
        frozen = freeze(client, protocol, model).json()
        path = '/api/research/complete-freezes/'+frozen['freeze_id']+'/forward'
        response = client.post(path, json={'purpose':'METHOD_VALIDATION','basis':'Explicit synthetic engineering only'})
        assert response.status_code == 201, response.text
        plan = response.json()
        response = client.post(path+'/check', json={'basis':'Manual trigger'})
        assert response.status_code == 201, response.text
        sample = response.json()['samples'][0]
        assert sample['evidence_kind'] == 'METHOD_CASE'
        assert sample['forecast']['observation_cutoff'][:10] == day
        assert sample['forecast']['probability'] > 0
        assert sample['action']['action'] in {'BUY','REFUSE'}
        assert client.post(path+'/check', json={'basis':'Different snapshot/account/backend trigger'}).json()['samples'] == [sample]
        state = client.get(path).json()
        assert state['forward_started_at'] is None and state['forward_deadline'] is None
        assert state['method_started_at'] == clock[0].isoformat()
        assert state['shadow']['revision'] == 1
        assert client.get('/api/research/protocols/'+protocol['protocol_id']).json()['forward_started_at'] is None
        assert client.post(path+'/replay').json()['matches_original'] is True
    with TestClient(create_app(tmp_path, review_clock=lambda: clock[0])) as client:
        assert client.get(path).json()['samples'] == [sample]
        assert client.post(path+'/replay').json()['network_calls'] == 0


def test_missed_days_no_backfill_and_exact_deadline_closes_with_unmatured_separate(tmp_path):
    clock = [datetime.fromisoformat('2026-06-10T16:00:00+08:00')]
    with TestClient(create_app(tmp_path,review_clock=lambda:clock[0])) as client:
        _, protocol, model, dates = setup(client,tmp_path)
        clock[0] = datetime.fromisoformat(dates[110]+'T16:00:00+08:00')
        frozen = freeze(client,protocol,model).json()
        path = '/api/research/complete-freezes/'+frozen['freeze_id']+'/forward'
        client.post(path,json={'purpose':'METHOD_VALIDATION','basis':'Deadline METHOD'})
        first = client.post(path+'/check',json={'basis':'First live METHOD checkpoint'}).json()
        assert first['samples'][0]['action']['maturity_date'] == dates[130]
        assert first['samples'][0]['action']['reasons'] != ['HORIZON_OUTSIDE_FROZEN_WINDOW']
        clock[0] = datetime.fromisoformat(dates[113]+'T16:00:00+08:00')
        second = client.post(path+'/check',json={'basis':'After two offline sessions'}).json()
        assert len(second['samples']) == 2
        assert {g['trading_date'] for g in second['missing_checkpoints']} == set(dates[111:113])
        assert second['method_deadline'] == first['method_deadline']
        cutoff = datetime.fromisoformat(first['method_deadline'])
        clock[0] = cutoff
        end = client.post(path+'/check',json={'basis':'Inclusive final deadline'}).json()
        assert end['status'] == 'CLOSED'
        assert end['endpoint']['cutoff'] == first['method_deadline']
        assert end['endpoint']['validation_status'] == 'INCOMPLETE'
        assert end['endpoint']['preliminary_verdict'] == 'INCONCLUSIVE'
        assert end['endpoint']['statistical_pass_checks_added'] == 0
        assert len(end['endpoint']['mature']) + len(end['endpoint']['unmatured']) + len(end['endpoint']['unscorable']) == 2
        clock[0] = cutoff.replace(hour=17)
        after = client.post(path+'/check',json={'basis':'No extension after end'}).json()
        assert after['endpoint'] == end['endpoint'] and after['samples'] == end['samples']
        assert after['forward_started_at'] is None


def test_mature_settlement_only_scores_already_archived_opportunities_and_preserves_refusals(tmp_path):
    clock=[datetime.fromisoformat('2026-06-10T16:00:00+08:00')]
    with TestClient(create_app(tmp_path,review_clock=lambda:clock[0])) as client:
        _,protocol,model,dates=setup(client,tmp_path)
        clock[0]=datetime.fromisoformat(dates[110]+'T16:00:00+08:00')
        frozen=freeze(client,protocol,model,baseline={'cash_yuan':'1.00','positions':[]}).json()
        path='/api/research/complete-freezes/'+frozen['freeze_id']+'/forward'
        client.post(path,json={'purpose':'METHOD_VALIDATION','basis':'Refused opportunity METHOD'})
        first=client.post(path+'/check',json={'basis':'Archive before outcome'}).json()
        assert first['samples'][0]['action']['action']=='REFUSE'
        response=client.post(path+'/settle',json={'basis':'Unmatured at observation'})
        assert response.status_code==201,response.text
        early=response.json()
        assert early['unmatured'][0]['label'] is None and early['mature']==[]
        clock[0]=datetime.fromisoformat(dates[130]+'T16:00:00+08:00')
        settled=client.post(path+'/settle',json={'basis':'Known complete METHOD outcome'}).json()
        assert settled['mature'][0]['label']==0
        assert settled['mature'][0]['diagnostic_only'] is True
        assert settled['shadow']['cash_yuan']=='1.00' and settled['shadow']['events']==[]
        assert len(client.get(path).json()['samples'])==1
        assert client.post(path+'/replay').json()['matches_original'] is True
        assert client.get('/api/account').json()['version']==0


def test_registered_user_stop_preserves_history_and_refuses_new_sampling(tmp_path):
    clock=[datetime.fromisoformat('2026-06-10T16:00:00+08:00')]
    with TestClient(create_app(tmp_path,review_clock=lambda:clock[0])) as client:
        _,protocol,model,dates=setup(client,tmp_path)
        clock[0]=datetime.fromisoformat(dates[110]+'T16:00:00+08:00')
        frozen=freeze(client,protocol,model).json();path='/api/research/complete-freezes/'+frozen['freeze_id']+'/forward'
        client.post(path,json={'purpose':'METHOD_VALIDATION','basis':'Pre-registered stop METHOD'})
        first=client.post(path+'/check',json={'basis':'First sample'}).json()
        stop=client.post(path+'/stop',json={'kind':'USER_STOP','basis':'User stops ability, statistical verdict separately preserved'})
        assert stop.status_code==200,stop.text
        stopped=stop.json()
        assert stopped['endpoint']['stop_reason']=='USER_STOP'
        assert stopped['endpoint']['cutoff']==clock[0].isoformat()
        assert stopped['method_deadline']==first['method_deadline']
        assert stopped['endpoint']['unmatured'][0]['label'] is None
        clock[0]=datetime.fromisoformat(dates[111]+'T16:00:00+08:00')
        assert client.post(path+'/check',json={'basis':'No post-stop sample'}).json()['samples']==first['samples']
        assert client.post(path+'/stop',json={'kind':'EARLY_PASS','basis':'Invalid optional PASS look'}).status_code==422


@pytest.mark.parametrize('start,deadline',[
    ('2026-01-31T16:00:00+08:00','2026-04-30T16:00:00+08:00'),
    ('2025-11-30T16:00:00+08:00','2026-02-28T16:00:00+08:00'),
    ('2023-11-30T16:00:00+08:00','2024-02-29T16:00:00+08:00'),
    ('2024-02-29T16:00:00+08:00','2024-05-29T16:00:00+08:00'),
])
def test_public_natural_month_algorithm_does_not_use_ninety_days(tmp_path,start,deadline):
    with TestClient(create_app(tmp_path)) as client:
        response=client.get('/api/research/deadline-preview',params={'start':start})
        assert response.status_code==200,response.text
        assert response.json()['deadline']==deadline and response.json()['actual_forward_start'] is False


def test_actual_backup_restore_lock_does_not_archive_or_start_from_saved_plan(tmp_path):
    source=tmp_path/'source';target=tmp_path/'restored';clock=[datetime.fromisoformat('2026-06-10T14:00:00+08:00')]
    with TestClient(create_app(source,review_clock=lambda:clock[0])) as client:
        _,protocol,model,dates=setup(client,source)
        clock[0]=datetime.fromisoformat(dates[110]+'T14:00:00+08:00')
        frozen=freeze(client,protocol,model).json();path='/api/research/complete-freezes/'+frozen['freeze_id']+'/forward'
        client.post(path,json={'purpose':'METHOD_VALIDATION','basis':'Restore-only saved plan'})
        backup=client.post('/api/runtime/backups').json()
        package=client.get('/api/runtime/backups/'+backup['backup_id']+'/export').content
    with TestClient(create_app(target,review_clock=lambda:clock[0])) as client:
        restored=client.post('/api/runtime/restores',content=package)
        assert restored.status_code==202,restored.text
    clock[0]=datetime.fromisoformat(dates[110]+'T16:00:00+08:00')
    with TestClient(create_app(target,review_clock=lambda:clock[0])) as client:
        assert client.get('/api/runtime/backups/status').json()['recovery']['state']=='RECOVERY_LOCK'
        response=client.post(path+'/check',json={'basis':'Restored plan cannot start before current reconciliation'})
        assert response.status_code==409,response.text
        assert response.json()['detail']['code']=='FORWARD_RECOVERY_LOCK'
        state=client.get(path).json()
        assert state['samples']==[] and state['method_started_at'] is None and state['forward_started_at'] is None
        assert client.get('/api/research/protocols/'+protocol['protocol_id']).json()['forward_started_at'] is None
