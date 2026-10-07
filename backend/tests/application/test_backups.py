"""Public backup/export/restore with real SQLite and original attachments."""
import hashlib
import io
import json
import zipfile
import csv
import time
from datetime import datetime,timedelta,timezone

import pytest

import httpx
from fastapi.testclient import TestClient
from roll.app import create_app
from test_account import baseline
from test_market_directory import establish


def confirm(client):
    draft = client.post('/api/account/drafts', json=baseline()).json()
    return client.post('/api/account/confirm', json={'draft_id':draft['draft_id'],'idempotency_key':'backup-baseline'}).json()


def test_complete_backup_export_and_restart_restoration_preserve_originals(tmp_path):
    directory=tmp_path/'source'
    raw=b'{"rc":0,"data":{"code":"600519","klines":["2026-09-30,10,10,10,10,100,100000"]}}'
    transport=httpx.MockTransport(lambda r:httpx.Response(200,content=raw))
    with TestClient(create_app(directory,market_transport=transport)) as client:
        establish(client,['SSE:600519'])
        request=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['DAILY'],'purpose':'OBSERVATION','start_date':'2026-09-30','end_date':'2026-09-30'}).json()
        run=client.post('/api/data/requests/'+request['request_id']+'/retrieve').json()
        original=client.get('/api/account').json()
        events=client.get('/api/account/events').json()
        snapshot=client.get('/api/data/snapshots/'+run['snapshot_id']).json()
        (directory/'tasks').mkdir(exist_ok=True)
        (directory/'tasks'/'auth.json').write_text('{"token":"SECRET_MUST_NOT_EXPORT"}')
        response=client.post('/api/runtime/backups')
        assert response.status_code==201,response.text
        backup=response.json()
        assert backup['status']=='COMPLETE' and backup['restore_point']['account_version']==1
        exported=client.get('/api/runtime/backups/'+backup['backup_id']+'/export')
        assert exported.status_code==200
        with zipfile.ZipFile(io.BytesIO(exported.content)) as bundle:
            assert not any('tasks' in name or 'auth' in name for name in bundle.namelist())
            manifest=json.loads(bundle.read('manifest.json'))
            assert manifest['event_count']==len(events)
            assert manifest['attachments']
            for item in manifest['attachments']:
                assert hashlib.sha256(bundle.read(item['path'])).hexdigest()==item['sha256']
        assert client.get('/api/runtime/backups/status').json()['uncovered_changes'] is False
    target=tmp_path/'target'
    with TestClient(create_app(target)) as client:
        staged=client.post('/api/runtime/restores',content=exported.content,headers={'content-type':'application/zip'})
        assert staged.status_code==202,staged.text
        assert staged.json()['state']=='PENDING_RESTART'
        assert client.get('/api/account').json()['version']==0
    with TestClient(create_app(target)) as client:
        assert client.get('/api/account').json()==original
        assert client.get('/api/account/events').json()==events
        assert client.get('/api/data/snapshots/'+run['snapshot_id']).json()==snapshot
        assert client.post('/api/data/runs/'+run['run_id']+'/replay').json()['network_calls']==0
        state=client.get('/api/runtime/backups/status').json()
        assert state['recovery']['state']=='RECOVERY_LOCK'
        assert client.post('/api/formal/evaluate').json()['detail']['code']=='RECOVERY_LOCK'
        assert client.get('/api/reviews/summary').status_code==200


def zip_edit(raw,edit):
    buffer=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as original,zipfile.ZipFile(buffer,'w') as changed:
        for name in original.namelist():
            value=edit(name,original.read(name))
            if value is not None:changed.writestr(name,value)
    return buffer.getvalue()


@pytest.mark.parametrize('damage',['missing','corrupt','database_only','projection'])
def test_invalid_bundle_never_stages_or_changes_live_account(tmp_path,damage):
    with TestClient(create_app(tmp_path)) as client:
        confirm(client)
        columns=next(csv.reader(io.StringIO(client.get('/api/account/csv/template').text.lstrip('\ufeff'))))
        output=io.StringIO();writer=csv.DictWriter(output,columns);writer.writeheader()
        writer.writerow({'template_version':'ROLL-CSV-3','kind':'CASH_IN','effective_at':'2026-10-07T12:00:00+08:00','source':'原私人现金凭证内容需原值恢复','record_id':'deposit','amount':'10'})
        uploaded=client.post('/api/account/csv/drafts',params={'filename':'private-account.csv','encoding':'utf-8','expected_account_version':1},content=output.getvalue().encode()).json()
        backup=client.post('/api/runtime/backups').json()
        raw=client.get('/api/runtime/backups/'+backup['backup_id']+'/export').content
        def edit(name,value):
            if name.startswith('raw/'):
                return None if damage in {'missing','database_only'} else b'corrupt' if damage=='corrupt' else value
            if name=='manifest.json' and damage=='projection':
                manifest=json.loads(value);manifest['event_count']+=1;return json.dumps(manifest).encode()
            return value
        before=client.get('/api/account').json()
        denied=client.post('/api/runtime/restores',content=zip_edit(raw,edit))
        assert denied.status_code==409,denied.text
        assert client.get('/api/runtime/backups/status').json()['pending_restore'] is None
        assert client.get('/api/account').json()==before
        assert client.get('/api/account/csv/files/'+uploaded['file']['sha256']).content==output.getvalue().encode()


def test_missing_registered_original_prevents_success_and_export(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        confirm(client)
        client.post('/api/account/csv/drafts',params={'filename':'material.csv','encoding':'utf-8','expected_account_version':1},content=b'bad-original')
        backup=client.post('/api/runtime/backups').json()
        # Native file damage is the setup; all product assertions use public routes.
        next((tmp_path/'raw'/'account-csv').iterdir()).unlink()
        denied=client.post('/api/runtime/backups')
        assert denied.status_code==409
        assert client.get('/api/runtime/backups/status').json()['last_check']['error']['code']=='ATTACHMENT_MISSING_OR_CORRUPT'
        assert client.get('/api/runtime/backups/status').json()['latest_success']['backup_id']==backup['backup_id']
        export=client.get('/api/runtime/backups/'+backup['backup_id']+'/export')
        assert export.status_code==200  # Earlier complete copy remains independently recoverable.
        path=tmp_path/'backups'/backup['backup_id']
        original=next((path/'raw'/'account-csv').iterdir());original.write_bytes(b'damaged-backup')
        assert client.get('/api/runtime/backups/'+backup['backup_id']+'/export').status_code==409
        assert client.get('/api/runtime/backups/status').json()['latest_backup_known_corrupt'] is True


def test_running_days_24h_and_restart_catchup_only_cover_actual_changes(tmp_path):
    clock=[datetime.now(timezone.utc)]
    with TestClient(create_app(tmp_path,backup_clock=lambda:clock[0])) as client:
        confirm(client)
        for _ in range(100):
            if client.get('/api/reviews/audits').json():break
            time.sleep(.03)
        first=client.post('/api/runtime/backups').json()
        assert client.post('/api/runtime/backups/check').json()['state']=='UNCHANGED_OR_NOT_DUE'
        clock[0]+=timedelta(hours=25)
        # No persistent change: even a new date does not manufacture another backup.
        assert client.post('/api/runtime/backups/check').json()['state']=='UNCHANGED_OR_NOT_DUE'
        client.post('/api/account/equity-hints',json={'source':'原凭证','declared_at':None,'instrument':None,'content':'未核个人权益线索'})
        assert client.get('/api/runtime/backups/status').json()['uncovered_changes'] is True
        second=client.post('/api/runtime/backups/check').json()
        assert second['reason']=='RUNNING_DAY_CHANGED' and second['backup_id']!=first['backup_id']
        client.post('/api/account/equity-hints',json={'source':'原凭证2','declared_at':None,'instrument':None,'content':'运行日后半段新材料'})
        assert client.get('/api/runtime/backups/status').json()['uncovered_changes'] is True
    with TestClient(create_app(tmp_path,backup_clock=lambda:clock[0])) as client:
        for _ in range(100):
            state=client.get('/api/runtime/backups/status').json()
            if not state['uncovered_changes']:break
            time.sleep(.03)
        assert state['uncovered_changes'] is False
        assert state['latest_success']['reason']=='RESTART_CATCHUP'
        assert state['offline_backup_promised'] is False


def test_restored_user_funding_remains_immutable_history_and_current_recovery_guard(tmp_path):
    from test_funding import funding
    with TestClient(create_app(tmp_path)) as client:
        confirm(client)
        active=client.post('/api/funding/confirm',json=funding()).json()
        assert active['enabled'] is True and active['state']=='CONFIRMED'
        backup=client.post('/api/runtime/backups').json()
        raw=client.get('/api/runtime/backups/'+backup['backup_id']+'/export').content
        revoked=client.post('/api/funding/confirm',json=funding(1,enabled=False)).json()
        assert revoked['state']=='REVOKED'
        assert client.post('/api/runtime/restores',content=raw).status_code==202
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/funding/versions/1').json()==active
        guard=client.get('/api/capabilities').json()
        assert guard['state']=='RECOVERY_LOCK'
        assert guard['recovery']['old_active_records']=='HISTORY_ONLY'
        assert guard['recovery']['possibly_missing_revocations']=='UNVERIFIED'
        assert guard['recovery']['formal_actions_allowed'] is False
        assert guard['recovery']['old_notifications_allowed'] is False
        assert guard['recovery']['permission_consumer_27']=='NOT_CONNECTED'
        assert client.post('/api/formal/evaluate').json()['detail']['code']=='RECOVERY_LOCK'
        assert client.get('/api/today').json()['recovery']['state']=='RECOVERY_LOCK'
        assert client.get('/api/account').json()['version']==1
        assert client.get('/api/data/sources').status_code==200


def test_local_access_and_native_owner_acl_protect_reconstructive_originals(tmp_path):
    import os
    app=create_app(tmp_path)
    with TestClient(app,client=('203.0.113.9',50000)) as remote:
        assert remote.get('/api/runtime/backups/status').status_code==403
    with TestClient(create_app(tmp_path)) as client:
        assert client.post('/api/runtime/restores',content=b'bad',headers={'Origin':'https://outside.invalid'}).status_code==403
        assert client.get('/api/runtime/backups/status').status_code==200
    if os.name=='nt':
        import win32security,win32api,win32con
        token=win32security.OpenProcessToken(win32api.GetCurrentProcess(),win32con.TOKEN_QUERY)
        owner=win32security.GetTokenInformation(token,win32security.TokenUser)[0]
        security=win32security.GetFileSecurity(str(tmp_path/'backups'),win32security.DACL_SECURITY_INFORMATION)
        acl=security.GetSecurityDescriptorDacl()
        principals={win32security.ConvertSidToStringSid(acl.GetAce(i)[2]) for i in range(acl.GetAceCount())}
        assert principals=={win32security.ConvertSidToStringSid(owner),'S-1-5-18'}
        assert security.GetSecurityDescriptorControl()[0]&win32security.SE_DACL_PROTECTED


def test_hash_valid_database_with_wrong_persisted_projection_is_rejected_by_event_replay(tmp_path):
    import sqlite3
    with TestClient(create_app(tmp_path/'data')) as client:
        confirm(client)
        backup=client.post('/api/runtime/backups').json()
        raw=client.get('/api/runtime/backups/'+backup['backup_id']+'/export').content
        with zipfile.ZipFile(io.BytesIO(raw)) as bundle:files={name:bundle.read(name) for name in bundle.namelist()}
        database=tmp_path/'altered.sqlite3';database.write_bytes(files['roll.sqlite3'])
        # Actual storage tampering deliberately repairs checksums: replay must
        # catch the mismatch between retained account facts and original events.
        db=sqlite3.connect(database)
        row=db.execute('SELECT snapshot FROM account_versions WHERE version=1').fetchone()
        snapshot=json.loads(row[0]);snapshot['cash_balance']='999999.00'
        encoded=json.dumps(snapshot,ensure_ascii=False,sort_keys=True,separators=(',',':'))
        db.execute('UPDATE account_versions SET snapshot=? WHERE version=1',(encoded,));db.commit();db.close()
        files['roll.sqlite3']=database.read_bytes();manifest=json.loads(files['manifest.json'])
        manifest['database_sha256']=hashlib.sha256(files['roll.sqlite3']).hexdigest()
        manifest['account_projection_sha256']=hashlib.sha256(encoded.encode()).hexdigest()
        files['manifest.json']=json.dumps(manifest).encode()
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as bundle:
            for name,value in files.items():bundle.writestr(name,value)
        denied=client.post('/api/runtime/restores',content=buffer.getvalue())
        assert denied.status_code==409 and denied.json()['detail']['code']=='ACCOUNT_EVENT_REPLAY_MISMATCH'
        assert client.get('/api/account').json()['cash_balance']=='100000.10'


def test_pending_restore_identity_and_concurrent_confirmation_snapshot(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    with TestClient(create_app(tmp_path/'source')) as client:
        confirm(client)
        draft=client.post('/api/account/drafts',json={'kind':'CASH_IN','expected_account_version':1,'payload':{
            'effective_at':'2026-10-07T12:00:00+08:00','source':'有据外部转入','record_id':'deposit','amount':'20'}}).json()
        with ThreadPoolExecutor(2) as pool:
            created=pool.submit(client.post,'/api/runtime/backups')
            accepted=pool.submit(client.post,'/api/account/confirm',json={'draft_id':draft['draft_id'],'idempotency_key':'deposit'})
            backup=created.result().json();receipt=accepted.result()
        assert receipt.status_code==200
        assert backup['restore_point']['account_version'] in {1,2}
        raw=client.get('/api/runtime/backups/'+backup['backup_id']+'/export').content
        latest=client.post('/api/runtime/backups').json();raw2=client.get('/api/runtime/backups/'+latest['backup_id']+'/export').content
    with TestClient(create_app(tmp_path/'target')) as client:
        first=client.post('/api/runtime/restores',content=raw)
        assert first.status_code==202
        assert client.post('/api/runtime/restores',content=raw).json()['backup_id']==backup['backup_id']
        changed=client.post('/api/runtime/restores',content=raw2)
        assert changed.status_code==409 and changed.json()['detail']['code']=='RESTORE_ALREADY_PENDING'
    with TestClient(create_app(tmp_path/'target')) as client:
        restored=client.get('/api/account').json()
        assert restored['version']==backup['restore_point']['account_version']
        assert restored['cash_balance']==('100020.10' if restored['version']==2 else '100000.10')
        assert len(client.get('/api/account/events').json())==backup['restore_point']['event_count']


def test_registered_research_feature_model_forecast_and_source_files_restore_as_method_only(tmp_path):
    from test_transparent_models import known_method
    source=tmp_path/'source'
    with TestClient(create_app(source)) as client:
        dataset,protocol,dates=known_method(client,source)
        model=client.post('/api/research/protocols/'+protocol['protocol_id']+'/models',json={'purpose':'METHOD_VALIDATION','basis':'16完整原件恢复联验，仅数学工程METHOD'}).json()
        forecast=client.post('/api/research/models/'+model['model_run_id']+'/forecasts',json={'observation_date':dates[110],'basis':'16数学METHOD回放，不是正式预测'}).json()
        assert model['status']=='METHOD_ARTIFACT_ONLY' and forecast['capability']=='NOT_GRANTED'
        backup=client.post('/api/runtime/backups').json()
        bundle=client.get('/api/runtime/backups/'+backup['backup_id']+'/export').content
        with zipfile.ZipFile(io.BytesIO(bundle)) as archived:
            manifest=json.loads(archived.read('manifest.json'))
            hashes={item['sha256'] for item in manifest['attachments']}
            assert {model[key]['sha256'] for key in ['input_archive','model_artifact','calibrator_artifact','calibration_prediction_archive']}<=hashes
            assert forecast['archive']['sha256'] in hashes
    target=tmp_path/'target'
    with TestClient(create_app(target)) as client:assert client.post('/api/runtime/restores',content=bundle).status_code==202
    with TestClient(create_app(target)) as client:
        assert client.get('/api/research/models/'+model['model_run_id']).json()==model
        assert client.get('/api/research/forecasts/'+forecast['forecast_id']).json()==forecast
        replay=client.post('/api/research/forecasts/'+forecast['forecast_id']+'/replay').json()
        assert replay['matches_original'] is True and replay['network_calls']==0
        assert client.get('/api/research/datasets/'+dataset['dataset_id']).json()==dataset
        # The registered original source bundle still supports the same real
        # local importer, including its original source raw/Parquet dependencies.
        repeated=client.post('/api/research/datasets',json={'archive_id':'method-execution','basis':'恢复原件本机复验，不创造前向样本'})
        assert repeated.status_code==201,repeated.text
        assert client.get('/api/capabilities').json()['state']=='RECOVERY_LOCK'

