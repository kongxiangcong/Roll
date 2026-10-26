"""Actual ancestor creates schema1; OS failure and current HTTP prove recovery."""
import io
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
import httpx
from test_account_process import Server
from test_fill_process import BASELINE


def ancestral_source(tmp_path):
    source=tmp_path/'old-source'
    repo=Path(__file__).resolve().parents[3]
    for name in ['__init__.py','config.py','app.py','accounts/__init__.py','accounts/ledger.py']:
        raw=subprocess.run(['git','show','17ca07d:backend/src/roll/'+name],cwd=repo,capture_output=True,check=True).stdout
        path=source/'roll'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    return source


@pytest.mark.parametrize('fault',['before_ddl','after_ddl','migration_failure'])
def test_pre_ddl_snapshot_and_interrupted_or_failed_migration_restore_real_old_files(tmp_path,fault):
    source=ancestral_source(tmp_path);directory=tmp_path/'data'
    old=Server(directory,source_directory=source)
    try:
        draft=old.client.post('/api/account/drafts',json=BASELINE).json()
        receipt=old.client.post('/api/account/confirm',json={'draft_id':draft['draft_id'],'idempotency_key':'old-receipt'}).json()
        original=old.client.get('/api/account').json();events=old.client.get('/api/account/events').json()
        pending=old.client.post('/api/account/drafts',json={'kind':'PERMISSIONS','expected_account_version':1,'payload':{
            'effective_at':'2026-10-07T11:00:00+08:00','source':'真实旧服务待确认权限','permission_profile':[]}}).json()
    finally:old.stop()
    env={**os.environ,'ROLL_DATA_DIR':str(directory),'ROLL_ENV':'test','ROLL_TEST_BOOTSTRAP_FAULT':fault}
    env.pop('PYTHONPATH',None)
    failed=subprocess.run([sys.executable,'-m','uvicorn','roll.app:create_app','--factory','--host','127.0.0.1','--port','0'],
        env=env,cwd=Path(__file__).resolve().parents[2],capture_output=True,timeout=30)
    assert failed.returncode== (1 if fault=='migration_failure' else 87)
    # The recovery bundle actually predates ALTER/any current module construction.
    manifests=[json.loads(p.read_text(encoding='utf-8')) for p in (directory/'backups').glob('*/manifest.json')]
    assert len(manifests)==1 and manifests[0]['reason']=='PRE_UPGRADE'
    assert manifests[0]['schema_version']==1 and manifests[0]['event_count']==len(events)
    restored_old=tmp_path/'restore-old';restored_old.mkdir()
    (restored_old/'roll.sqlite3').write_bytes((directory/'backups'/manifests[0]['backup_id']/'roll.sqlite3').read_bytes())
    ancestor=Server(restored_old,source_directory=source)
    try:
        assert ancestor.client.get('/api/account').json()==original
        assert ancestor.client.get('/api/account/events').json()==events
        assert ancestor.client.get('/api/account/receipts/'+receipt['receipt_id']).json()==receipt
        assert ancestor.client.get('/api/account/drafts/'+pending['draft_id']).json()==pending
    finally:ancestor.stop()
    new=Server(directory)
    try:
        assert new.client.get('/api/account').json()==original
        assert new.client.get('/api/account/events').json()==events
        assert new.client.get('/api/account/receipts/'+receipt['receipt_id']).json()==receipt
        state=new.client.get('/api/runtime/backups/status').json()
        assert state['migration_failure']['state']=='ROLLED_BACK'
        command={'draft_id':pending['draft_id'],'idempotency_key':'post-migration'}
        accepted=new.client.post('/api/account/confirm',json=command)
        assert accepted.status_code==200,accepted.text
        assert new.client.post('/api/account/confirm',json=command).json()==accepted.json()
        assert new.client.get('/api/account').json()['version']==2
    finally:new.stop()


def test_process_exit_before_backup_publication_never_reports_staging_as_success(tmp_path,monkeypatch):
    directory=tmp_path/'data'
    monkeypatch.setenv('ROLL_TEST_BACKUP_FAULT','before_publication')
    server=Server(directory)
    try:
        draft=server.client.post('/api/account/drafts',json=BASELINE).json()
        command={'draft_id':draft['draft_id'],'idempotency_key':'baseline'}
        receipt=server.client.post('/api/account/confirm',json=command).json()
        with pytest.raises(httpx.TransportError):server.client.post('/api/runtime/backups')
        assert server.process.wait(timeout=10)==88
    finally:server.stop()
    monkeypatch.delenv('ROLL_TEST_BACKUP_FAULT')
    new=Server(directory)
    try:
        assert all(item['reason']!='MANUAL' for item in new.client.get('/api/runtime/backups').json())
        assert new.client.post('/api/account/confirm',json=command).json()==receipt
        assert new.client.get('/api/account').json()['version']==1
    finally:new.stop()


def launch_failure(directory,**settings):
    env={**os.environ,'ROLL_DATA_DIR':str(directory),'ROLL_ENV':'test',**settings}
    env.pop('PYTHONPATH',None)
    return subprocess.run([sys.executable,'-m','uvicorn','roll.app:create_app','--factory','--host','127.0.0.1','--port','0'],
        env=env,cwd=Path(__file__).resolve().parents[2],capture_output=True,timeout=30)


def test_live_peer_prevents_any_restore_replacement_until_all_hosts_stopped(tmp_path):
    directory=tmp_path/'data';first=Server(directory);peer=None
    try:
        draft=first.client.post('/api/account/drafts',json=BASELINE).json()
        first.client.post('/api/account/confirm',json={'draft_id':draft['draft_id'],'idempotency_key':'baseline'}).raise_for_status()
        original=first.client.get('/api/account').json()
        backup=first.client.post('/api/runtime/backups').json()
        bundle=first.client.get('/api/runtime/backups/'+backup['backup_id']+'/export').content
        peer=Server(directory)
        assert first.client.post('/api/runtime/restores',content=bundle).status_code==202
        failed=launch_failure(directory)
        assert failed.returncode==1 and b'RESTORE_PENDING_STOP_ALL_LOCAL_HOSTS' in failed.stderr
        assert first.client.get('/api/account').json()==original
        first.stop()
        still_blocked=launch_failure(directory)
        assert still_blocked.returncode==1 and b'RESTORE_PENDING_STOP_ALL_LOCAL_HOSTS' in still_blocked.stderr
        assert peer.client.get('/api/account').json()==original
    finally:
        first.stop()
        if peer:peer.stop()
    restored=Server(directory)
    try:
        assert restored.client.get('/api/account').json()==original
        assert restored.client.get('/api/capabilities').json()['runtime_state']=='RECOVERY_LOCK'
        assert restored.client.get('/api/runtime/backups/status').json()['pending_restore'] is None
    finally:restored.stop()


def test_offline_cli_restores_physical_database_damage_with_complete_original_bundle(tmp_path):
    directory=tmp_path/'data';server=Server(directory)
    try:
        draft=server.client.post('/api/account/drafts',json=BASELINE).json()
        command={'draft_id':draft['draft_id'],'idempotency_key':'baseline'}
        receipt=server.client.post('/api/account/confirm',json=command).json()
        original=server.client.get('/api/account').json()
        backup=server.client.post('/api/runtime/backups').json()
        raw=server.client.get('/api/runtime/backups/'+backup['backup_id']+'/export').content
    finally:server.stop()
    bundle=tmp_path/'recovery.zip';bundle.write_bytes(raw)
    # A genuine damaged main file: HTTP cannot initialize, so use the documented
    # stopped-host CLI which does not construct or migrate Ledger first.
    (directory/'roll.sqlite3').write_bytes(b'physically-damaged-database')
    result=subprocess.run([sys.executable,'-m','roll.runtime.backups','restore','--data-dir',str(directory),'--bundle',str(bundle)],
        cwd=Path(__file__).resolve().parents[2],capture_output=True,timeout=30)
    assert result.returncode==0,result.stderr.decode(errors='replace')
    assert json.loads(result.stdout)['state']=='RESTORED_RECOVERY_LOCK'
    new=Server(directory)
    try:
        assert new.client.get('/api/account').json()==original
        assert new.client.post('/api/account/confirm',json=command).json()==receipt
        assert new.client.get('/api/capabilities').json()['runtime_state']=='RECOVERY_LOCK'
    finally:new.stop()


@pytest.mark.parametrize('fault',['after_lock','after_attachments','after_database'])
def test_actual_restore_crash_never_clears_lock_or_duplicates_confirmed_facts(tmp_path,fault):
    directory=tmp_path/'data';server=Server(directory)
    try:
        draft=server.client.post('/api/account/drafts',json=BASELINE).json()
        command={'draft_id':draft['draft_id'],'idempotency_key':'baseline'}
        receipt=server.client.post('/api/account/confirm',json=command).json()
        original=server.client.get('/api/account').json();events=server.client.get('/api/account/events').json()
        columns=next(__import__('csv').reader(io.StringIO(server.client.get('/api/account/csv/template').text.lstrip('\ufeff'))))
        output=io.StringIO();writer=__import__('csv').DictWriter(output,columns);writer.writeheader()
        writer.writerow({'template_version':'ROLL-CSV-3','kind':'CASH_IN','effective_at':'2026-10-07T11:00:00+08:00','source':'真实原件恢复故障案例','record_id':'deposit','amount':'10','basis':'已核对原现金凭证'})
        uploaded=server.client.post('/api/account/csv/drafts',params={'filename':'original.csv','encoding':'utf-8','expected_account_version':1},content=output.getvalue().encode()).json()
        csv_command={'draft_id':uploaded['draft_id'],'idempotency_key':'csv-deposit'}
        csv_receipt=server.client.post('/api/account/confirm',json=csv_command)
        assert csv_receipt.status_code==200,csv_receipt.text
        csv_receipt=csv_receipt.json()
        original=server.client.get('/api/account').json()
        events=server.client.get('/api/account/events').json()
        backup=server.client.post('/api/runtime/backups').json()
        bundle=server.client.get('/api/runtime/backups/'+backup['backup_id']+'/export').content
        assert server.client.post('/api/runtime/restores',content=bundle).status_code==202
    finally:server.stop()
    crashed=launch_failure(directory,ROLL_TEST_RESTORE_FAULT=fault)
    assert crashed.returncode==89
    assert json.loads((directory/'backups'/'recovery-lock.json').read_text())['state']=='RECOVERY_LOCK'
    restored=Server(directory)
    try:
        client=restored.client
        assert client.get('/api/account').json()==original
        assert client.get('/api/account/events').json()==events
        assert client.post('/api/account/confirm',json=command).json()==receipt
        assert client.post('/api/account/confirm',json=csv_command).json()==csv_receipt
        assert client.get('/api/account').json()['cash_balance']==original['cash_balance']
        assert client.get('/api/account/csv/files/'+uploaded['file']['sha256']).content==output.getvalue().encode()
        assert client.get('/api/capabilities').json()['runtime_state']=='RECOVERY_LOCK'
        assert client.get('/api/runtime/backups/status').json()['last_restore']['state']=='APPLIED'
    finally:restored.stop()
