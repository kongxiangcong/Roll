"""Local consistent recovery bundles. Runtime credentials are never attachments.

Restore is staged by HTTP and applied only before application constructors run.
"""
import hashlib
import io
import json
import os
import shutil
import sqlite3
import threading
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path, PurePosixPath
from uuid import uuid4,UUID

from fastapi import HTTPException


def now():
    return datetime.now(timezone.utc).isoformat()


def encode(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def file_path(path):
    path=Path(path)
    if os.name=='nt' and not str(path).startswith('\\\\?\\'):
        return Path('\\\\?\\'+str(path.resolve()))
    return path


def persist(path,raw):
    path=file_path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name('.tmp-'+uuid4().hex[:12])
    with temporary.open('xb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)


def private_directory(path):
    path=file_path(path)
    path.mkdir(parents=True,exist_ok=True)
    if os.name=='nt':
        import win32api,win32con,win32security,ntsecuritycon
        token=win32security.OpenProcessToken(win32api.GetCurrentProcess(),win32con.TOKEN_QUERY)
        sid=win32security.GetTokenInformation(token,win32security.TokenUser)[0]
        acl=win32security.ACL()
        flags=win32con.OBJECT_INHERIT_ACE|win32con.CONTAINER_INHERIT_ACE
        for principal in [sid,win32security.CreateWellKnownSid(win32security.WinLocalSystemSid)]:
            acl.AddAccessAllowedAceEx(win32security.ACL_REVISION_DS,flags,ntsecuritycon.FILE_ALL_ACCESS,principal)
        win32security.SetNamedSecurityInfo(str(path),win32security.SE_FILE_OBJECT,
            win32security.DACL_SECURITY_INFORMATION|win32security.PROTECTED_DACL_SECURITY_INFORMATION,None,None,acl,None)
        return 'WINDOWS_CURRENT_USER_AND_SYSTEM'
    path.chmod(0o700)
    return 'OWNER_ONLY_0700'


@contextmanager
def connection(path):
    db=sqlite3.connect(path,timeout=10)
    try:
        with db:yield db
    finally:db.close()


def tables(db):
    return {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def references(db,directory):
    names=tables(db);result={}
    if 'evidence_archives' in names:
        for row in db.execute('SELECT sha256,value FROM evidence_archives'):
            item=json.loads(row[1]);result[item['path']]={'path':item['path'],'sha256':row[0],'kind':item['kind']}
    if 'account_csv_imports' in names:
        for row in db.execute('SELECT DISTINCT sha256 FROM account_csv_imports'):
            path='raw/account-csv/'+row[0];result[path]={'path':path,'sha256':row[0],'kind':'ACCOUNT_CSV_ORIGINAL'}
    if 'research_datasets' in names:
        for row in db.execute('SELECT value FROM research_datasets'):
            value=json.loads(row[0]);path='research-inputs/'+value['archive_id']+'/browser-live.json'
            result[path]={'path':path,'sha256':value['source_bundle_sha256'],'kind':'RESEARCH_SOURCE_BUNDLE'}
            for original in value['original_archives']:
                path='research-inputs/'+value['archive_id']+'/'+original['sha256']+('.parquet' if original['path'].endswith('.parquet') else '.raw')
                result[path]={'path':path,'sha256':original['sha256'],'kind':'RESEARCH_SOURCE_ORIGINAL'}
            if value.get('engineering_exposure') is not None:
                path='research-inputs/'+value['archive_id']+'/engineering-exposure.json'
                material=attachment_path(directory,path)
                if not material.is_file():raise HTTPException(409,{'code':'ATTACHMENT_MISSING_OR_CORRUPT','attachment_kind':'ENGINEERING_EXPOSURE'})
                raw=material.read_bytes()
                if json.loads(raw)!=value['engineering_exposure']:raise HTTPException(409,{'code':'RESEARCH_EXPOSURE_METADATA_MISMATCH'})
                result[path]={'path':path,'sha256':sha(raw),'kind':'RESEARCH_ENGINEERING_EXPOSURE'}
    for item in result.values():
        safe_relative(item['path'])
    return sorted(result.values(),key=lambda item:item['path'])


def safe_relative(raw):
    path=PurePosixPath(raw)
    if not isinstance(raw,str) or '\\' in raw or ':' in raw or path.is_absolute() or '..' in path.parts or path.parts[0] not in {'raw','parquet','research-inputs'}:
        raise HTTPException(409,{'code':'UNSAFE_ATTACHMENT_REFERENCE'})
    return path


def attachment_path(directory,relative):
    safe_relative(relative)
    target=directory/relative
    if not target.resolve().is_relative_to(directory.resolve()):raise HTTPException(409,{'code':'ATTACHMENT_OUTSIDE_RUNTIME'})
    for part in [target,*target.parents]:
        if part==directory.parent:break
        if part.exists() and (part.is_symlink() or getattr(part.lstat(),'st_file_attributes',0)&0x400):
            raise HTTPException(409,{'code':'ATTACHMENT_REPARSE_POINT'})
    return file_path(target)


def facts(db):
    names=tables(db)
    account=db.execute('SELECT snapshot FROM account_versions ORDER BY version DESC LIMIT 1').fetchone() if 'account_versions' in names else None
    count=db.execute('SELECT COUNT(*) FROM account_events').fetchone()[0] if 'account_events' in names else 0
    snapshot=json.loads(account[0]) if account else None
    return {'account_version':snapshot['version'] if snapshot else 0,'account_projection_sha256':sha(encode(snapshot).encode()),
        'event_count':count,'account_confirmed_at':snapshot.get('confirmed_at') if snapshot else None,'schema_version':db.execute('PRAGMA user_version').fetchone()[0]}


def change_fingerprint(db):
    # Heartbeats are liveness, not new recoverable user facts. All business tables remain covered.
    skip={'review_worker','review_sessions','sqlite_sequence'}
    digest=hashlib.sha256()
    for name in sorted(tables(db)-skip):
        digest.update(name.encode())
        rows=db.execute('SELECT * FROM "'+name.replace('"','""')+'"').fetchall()
        for row in sorted(encode(list(r)) for r in rows):digest.update(row.encode())
    return digest.hexdigest()


def source_fingerprint():
    import sys
    from importlib.metadata import version
    root=Path(__file__).parents[1]
    return sha(encode({'source':{p.relative_to(root).as_posix():sha(p.read_bytes()) for p in root.rglob('*.py')},
        'dependency_lock':sha((Path(__file__).parents[3]/'uv.lock').read_bytes()),'python':sys.version,
        'runtime_versions':{name:version(name) for name in ['openai-codex','openai-agents','openai','httpx','pyarrow']}}).encode())


def verify_database(path,manifest):
    with connection(path) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise HTTPException(409,{'code':'DATABASE_INTEGRITY_FAILED'})
        actual=facts(db)
        if actual['schema_version'] not in {1,2}:raise HTTPException(409,{'code':'UNSUPPORTED_DATABASE_SCHEMA'})
        for key in ['account_version','account_projection_sha256','event_count','schema_version']:
            if actual[key]!=manifest[key]:raise HTTPException(409,{'code':'RESTORE_POINT_MISMATCH','field':key})
        refs=references(db,path.parent)
        expected={r['path']:r['sha256'] for r in refs}
        if expected!={r['path']:r['sha256'] for r in manifest['attachments']}:raise HTTPException(409,{'code':'ATTACHMENT_MANIFEST_MISMATCH'})
    if actual['schema_version']==2:
        # Replay through the existing public ledger use case; no migration is run here.
        from roll.accounts.ledger import Ledger
        ledger=object.__new__(Ledger);ledger.path=path
        projected=ledger.replay()
        current=ledger.account()
        if current['version']==0:current['latest_effective_fact_at']=None
        # Old immutable published versions predate later derived metadata. Check
        # every persisted value; do not demand invented fields on an old snapshot.
        def retained_equal(original,replayed):
            if isinstance(original,dict):return isinstance(replayed,dict) and all(k in replayed and retained_equal(v,replayed[k]) for k,v in original.items())
            if isinstance(original,list):return isinstance(replayed,list) and len(original)==len(replayed) and all(retained_equal(a,b) for a,b in zip(original,replayed))
            return original==replayed
        if not retained_equal(current,projected):raise HTTPException(409,{'code':'ACCOUNT_EVENT_REPLAY_MISMATCH'})


class Backups:
    def __init__(self,directory,clock=None):
        self.directory=Path(directory).resolve();self.path=self.directory/'roll.sqlite3'
        self.access=private_directory(self.directory)
        self.root=file_path(self.directory/'backups');private_directory(self.root)
        self.clock=clock or (lambda:datetime.now(timezone.utc))
        self.lock=threading.Lock();self.stop_event=threading.Event();self.thread=None

    def list(self):
        result=[]
        for path in self.root.glob('*/manifest.json'):
            if path.parent.name.startswith('.'):continue
            manifest=json.loads(path.read_text(encoding='utf-8'))
            result.append(self.summary(manifest))
        return sorted(result,key=lambda item:(item['completed_at'],item['published_at']),reverse=True)

    def summary(self,manifest):
        return {'backup_id':manifest['backup_id'],'status':'COMPLETE','reason':manifest['reason'],
            'completed_at':manifest['completed_at'],'restore_point':{k:manifest[k] for k in ['account_version','event_count','account_confirmed_at','capture_finished_at']},
            'published_at':manifest['published_at'],
            'attachment_count':len(manifest['attachments']),'change_fingerprint':manifest['change_fingerprint']}

    def create(self,reason='MANUAL'):
        with self.lock:
            identifier=str(uuid4());staging=self.root/('.building-'+identifier);private_directory(staging)
            try:
                with connection(self.path) as source,connection(staging/'roll.sqlite3') as destination:
                    source.backup(destination)
                captured_at=now()
                with connection(staging/'roll.sqlite3') as snapshot:
                    refs=references(snapshot,self.directory);point=facts(snapshot);fingerprint=change_fingerprint(snapshot)
                for item in refs:
                    source=attachment_path(self.directory,item['path']);target=attachment_path(staging,item['path'])
                    if not source.is_file() or sha(source.read_bytes())!=item['sha256']:
                        raise HTTPException(409,{'code':'ATTACHMENT_MISSING_OR_CORRUPT','attachment_kind':item['kind']})
                    persist(target,source.read_bytes())
                    item['bytes']=target.stat().st_size
                stamp=self.clock().astimezone(timezone.utc).isoformat()
                manifest={'format':'ROLL-RECOVERY-1','backup_id':identifier,'reason':reason,'completed_at':stamp,'published_at':now(),
                    **point,'capture_finished_at':captured_at,'attachments':refs,'database_sha256':sha((staging/'roll.sqlite3').read_bytes()),
                    'change_fingerprint':fingerprint,'deployment_fingerprint':json.loads((self.root/'deployment.json').read_text(encoding='utf-8'))['fingerprint'] if (self.root/'deployment.json').exists() else None,
                    'backup_writer_fingerprint':source_fingerprint(),
                    'access_control':self.access,'credentials':'EXCLUDED; referenced original evidence retained'}
                self.validate(staging,manifest)
                with (staging/'roll.sqlite3').open('r+b') as stream:os.fsync(stream.fileno())
                persist(staging/'manifest.json',encode(manifest).encode())
                if reason=='MANUAL' and os.environ.get('ROLL_ENV')=='test' and os.environ.get('ROLL_TEST_BACKUP_FAULT')=='before_publication':os._exit(88)
                os.replace(staging,self.root/identifier)
                persist(self.root/'last-check.json',encode({'checked_at':stamp,'last_success':identifier,'error':None}).encode())
                return self.summary(manifest)
            except Exception as error:
                persist(self.root/'last-check.json',encode({'checked_at':now(),'error':{'code':error.detail.get('code') if isinstance(error,HTTPException) and isinstance(error.detail,dict) else type(error).__name__}}).encode())
                raise

    def get(self,identifier):
        try:identifier=str(UUID(identifier))
        except ValueError:raise HTTPException(404,'备份不存在')
        path=self.root/identifier
        if not (path/'manifest.json').is_file():raise HTTPException(404,'备份不存在')
        manifest=json.loads((path/'manifest.json').read_text(encoding='utf-8'))
        return path,manifest

    def export(self,identifier):
        path,manifest=self.get(identifier)
        identifier=manifest['backup_id']
        try:self.validate(path,manifest)
        except HTTPException as error:
            persist(self.root/'last-verification.json',encode({'backup_id':identifier,'checked_at':now(),'state':'CORRUPT','error':error.detail}).encode())
            raise
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED) as bundle:
            for name in ['manifest.json','roll.sqlite3']+[item['path'] for item in manifest['attachments']]:bundle.write(path/name,name)
        return buffer.getvalue()

    def validate(self,path,manifest):
        if manifest.get('format')!='ROLL-RECOVERY-1':raise HTTPException(409,{'code':'UNSUPPORTED_RECOVERY_FORMAT'})
        database=path/'roll.sqlite3'
        if not database.is_file() or sha(database.read_bytes())!=manifest['database_sha256']:raise HTTPException(409,{'code':'DATABASE_MISSING_OR_CORRUPT'})
        for item in manifest['attachments']:
            attachment=attachment_path(path,item['path'])
            if not attachment.is_file() or sha(attachment.read_bytes())!=item['sha256']:raise HTTPException(409,{'code':'ATTACHMENT_MISSING_OR_CORRUPT'})
        verify_database(database,manifest)

    def stage_restore(self,raw):
        with self.lock:
            staging=self.root/('.restore-'+str(uuid4()));private_directory(staging)
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
                    names=bundle.namelist()
                    if len(set(names))!=len(names) or sum(item.file_size for item in bundle.infolist())>1024*1024*1024:raise ValueError()
                    manifest=json.loads(bundle.read('manifest.json'))
                    allowed={'manifest.json','roll.sqlite3',*[r['path'] for r in manifest['attachments']]}
                    if set(names)!=allowed:raise ValueError()
                    for name in names:
                        if name not in {'manifest.json','roll.sqlite3'}:safe_relative(name)
                        persist(staging/name,bundle.read(name))
                self.validate(staging,manifest)
                for name in names:
                    if name not in {'manifest.json','roll.sqlite3'}:
                        attachment_path(self.directory,name)
                with startup_lock(self.directory):
                    pending=self.root/'pending-restore.json'
                    if pending.exists():
                        prior=json.loads(pending.read_text(encoding='utf-8'))
                        if prior['bundle_sha256']!=sha(raw):raise HTTPException(409,{'code':'RESTORE_ALREADY_PENDING'})
                        return {'state':'PENDING_RESTART','backup_id':prior['backup_id'],'reason':'同一恢复请求已保留；停止所有本机服务后重新启动。'}
                    persist(pending,encode({'state':'PENDING_RESTART','staging':staging.name,'bundle_sha256':sha(raw),
                        'backup_id':manifest['backup_id'],'requested_at':now()}).encode())
                return {'state':'PENDING_RESTART','backup_id':manifest['backup_id'],'reason':'当前服务继续使用原数据库；停止所有本机宿主后启动，才应用已校验恢复点。'}
            except HTTPException:raise
            except (ValueError,KeyError,TypeError,IndexError,zipfile.BadZipFile,json.JSONDecodeError,sqlite3.DatabaseError):raise HTTPException(409,{'code':'INVALID_RECOVERY_BUNDLE'})

    def recovery(self):
        path=self.root/'recovery-lock.json'
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'state':'NOT_RESTORED'}

    def status(self):
        history=self.list();latest=history[0] if history else None
        with connection(self.path) as db:current=change_fingerprint(db)
        last=self.root/'last-check.json'
        pending=self.root/'pending-restore.json'
        checked=self.root/'last-verification.json'
        validation=json.loads(checked.read_text(encoding='utf-8')) if checked.exists() else None
        damaged=bool(latest and validation and validation['backup_id']==latest['backup_id'] and validation['state']=='CORRUPT')
        return {'latest_success':latest,'uncovered_changes':damaged or latest is None or current!=latest['change_fingerprint'],
            'recommended_interval_hours':24,'offline_backup_promised':False,'access_control':self.access,
            'last_check':json.loads(last.read_text(encoding='utf-8')) if last.exists() else None,
            'pending_restore':json.loads(pending.read_text(encoding='utf-8')) if pending.exists() else None,'recovery':self.recovery(),
            'migration_failure':json.loads((self.root/'migration-failure.json').read_text(encoding='utf-8')) if (self.root/'migration-failure.json').exists() else None,
            'latest_export_validation':validation,'latest_backup_known_corrupt':damaged,
            'last_restore':json.loads((self.root/'last-restore.json').read_text(encoding='utf-8')) if (self.root/'last-restore.json').exists() else None}

    def check(self,resume=False):
        state=self.status();latest=state['latest_success'];stamp=self.clock().astimezone(timezone.utc)
        due=not latest or (stamp-datetime.fromisoformat(latest['completed_at'])).total_seconds()>=60 or stamp.astimezone(timezone(timedelta(hours=8))).date()!=datetime.fromisoformat(latest['completed_at']).astimezone(timezone(timedelta(hours=8))).date()
        if state['uncovered_changes'] and (due or resume):return self.create('RESTART_CATCHUP' if resume and latest else 'RUNNING_DAY_CHANGED')
        return {'state':'UNCHANGED_OR_NOT_DUE','checked_at':stamp.isoformat()}

    def start(self):
        self.stop_event.clear()
        def work():
            try:self.check(resume=True)
            except Exception as error:self.record_check_error(error)
            while not self.stop_event.is_set():
                try:self.check()
                except Exception as error:self.record_check_error(error)
                self.stop_event.wait(30)
        self.thread=threading.Thread(target=work,name='roll-backups',daemon=True);self.thread.start()

    def record_check_error(self,error):
        persist(self.root/'last-check.json',encode({'checked_at':now(),'error':{'code':error.detail.get('code') if isinstance(error,HTTPException) and isinstance(error.detail,dict) else type(error).__name__}}).encode())

    def close(self):
        self.stop_event.set()
        if self.thread:self.thread.join()


@contextmanager
def startup_lock(directory):
    directory.mkdir(parents=True,exist_ok=True)
    with (directory/'.startup.lock').open('a+b') as stream:
        if os.name=='nt':
            import msvcrt
            stream.seek(0);stream.write(b'0');stream.flush();stream.seek(0)
            msvcrt.locking(stream.fileno(),msvcrt.LK_LOCK,1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(),fcntl.LOCK_EX)
        try:yield
        finally:
            if os.name=='nt':stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(stream.fileno(),fcntl.LOCK_UN)


def live_hosts(directory):
    from roll.agents.codex_process import owner_alive
    result=[]
    for path in (directory/'backups').glob('.host-*.json'):
        owner=json.loads(path.read_text(encoding='utf-8'))
        if owner_alive({'host_owner':owner}):result.append(owner)
    path=directory/'roll.sqlite3'
    if path.exists():
        try:
            with connection(path) as db:
                names=tables(db)
                if 'review_worker' in names:
                    for raw, in db.execute('SELECT value FROM review_worker'):
                        run=json.loads(raw)
                        if owner_alive(run):result.append(run['host_owner'])
                if 'retrieval_runs' in names:
                    for raw, in db.execute('SELECT value FROM retrieval_runs'):
                        run=json.loads(raw)
                        if run['status']=='RUNNING' and owner_alive(run):result.append(run.get('host_owner') or run.get('process'))
        except sqlite3.DatabaseError:
            persist(directory/'backups'/'host-check-db-error.json',encode({'checked_at':now(),'code':'DATABASE_UNREADABLE','owner_check':'PROCESS_MARKERS_ONLY'}).encode())
    return result


def replace_database(directory,source):
    # Only called while startup lock is held and every previous host is dead.
    target=directory/'roll.sqlite3'
    for path in [directory/'roll.sqlite3-wal',directory/'roll.sqlite3-shm']:
        path.unlink(missing_ok=True)
    temporary=directory/('roll.sqlite3.restore-'+str(uuid4()))
    shutil.copyfile(source,temporary)
    with temporary.open('r+b') as stream:os.fsync(stream.fileno())
    os.replace(temporary,target)


def restore_at_start(backups):
    pending=backups.root/'pending-restore.json'
    if not pending.exists():return
    if live_hosts(backups.directory):raise RuntimeError('RESTORE_PENDING_STOP_ALL_LOCAL_HOSTS')
    request=json.loads(pending.read_text(encoding='utf-8'))
    name=request['staging']
    if not name.startswith('.restore-') or Path(name).name!=name:raise RuntimeError('UNSAFE_RESTORE_STAGE')
    source=backups.root/name;manifest=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
    backups.validate(source,manifest)
    # Lock survives failure at any replacement boundary, and cannot be cleared by restore.
    persist(backups.root/'recovery-lock.json',encode({'state':'RECOVERY_LOCK','locked_at':now(),
        'backup_id':manifest['backup_id'],'restore_point':backups.summary(manifest)['restore_point'],
        'source_deployment_fingerprint':manifest['deployment_fingerprint'],'current_deployment_fingerprint':source_fingerprint(),
        'account_check':'PENDING_CURRENT_BROKER_RECONCILIATION','current_authorization':'UNVERIFIED',
        'possibly_missing_revocations':'UNVERIFIED','old_active_records':'HISTORY_ONLY',
        'formal_actions_allowed':False,'old_notifications_allowed':False,'observation_allowed':True,
        'permission_consumer_27':'NOT_CONNECTED','analysis_gap':'RESTORED_TO_SUCCESSFUL_BACKUP; OFFLINE_COVERAGE_NOT_PROMISED'}).encode())
    restore_fault('after_lock')
    if backups.path.exists() and not request.get('previous_backup'):
        try:
            previous=backups.create('PRE_RESTORE')
            request['previous_backup']=previous['backup_id']
        except (sqlite3.DatabaseError,HTTPException):
            damaged=backups.root/('.damaged-current-'+str(uuid4()));private_directory(damaged)
            for name in ['roll.sqlite3','roll.sqlite3-wal','roll.sqlite3-shm']:
                path=backups.directory/name
                if path.exists():persist(damaged/name,path.read_bytes())
            persist(damaged/'unverified.json',encode({'state':'DAMAGED_OR_INCOMPLETE; NOT_A_RECOVERABLE_BACKUP','retained_at':now()}).encode())
            request['previous_backup']='UNVERIFIABLE_CURRENT_FILES_RETAINED'
        persist(pending,encode(request).encode())
    for item in manifest['attachments']:
        target=attachment_path(backups.directory,item['path'])
        persist(target,(source/item['path']).read_bytes())
    restore_fault('after_attachments')
    replace_database(backups.directory,source/'roll.sqlite3')
    restore_fault('after_database')
    verify_database(backups.path,manifest)
    with connection(backups.path) as db:
        names=tables(db)
        if 'review_worker' in names:db.execute('DELETE FROM review_worker')
        if 'review_tasks' in names:
            for identifier,raw in db.execute('SELECT id,value FROM review_tasks').fetchall():
                task=json.loads(raw)
                if task['status'] in {'RUNNING','QUEUED'}:
                    task.update(status='CANCELLED',finished_at=now(),recovery_reason='RESTORED_PENDING_TASK_HISTORY_ONLY')
                    db.execute('UPDATE review_tasks SET value=? WHERE id=?',(encode(task),identifier))
        if 'retrieval_runs' in names:
            for identifier,raw in db.execute('SELECT id,value FROM retrieval_runs').fetchall():
                run=json.loads(raw)
                if run['status']=='RUNNING':
                    run.update(status='INTERRUPTED',finished_at=now(),recovery_reason='RESTORED_RUNNING_TASK_HISTORY_ONLY')
                    db.execute('UPDATE retrieval_runs SET value=? WHERE id=?',(encode(run),identifier))
    persist(backups.root/'last-restore.json',encode({**request,'state':'APPLIED','applied_at':now()}).encode())
    pending.unlink()


def restore_fault(point):
    if os.environ.get('ROLL_ENV')=='test' and os.environ.get('ROLL_TEST_RESTORE_FAULT')==point:os._exit(89)


def bootstrap(directory):
    """Pre-DDL boundary for actual v1 migration and existing module additions."""
    directory=Path(directory).resolve();backups=Backups(directory)
    previous=None
    with startup_lock(directory):
        interrupted=backups.root/'upgrade-pending.json'
        if interrupted.exists():
            if live_hosts(directory):raise RuntimeError('UPGRADE_REQUIRES_STOP_ALL_LOCAL_HOSTS')
            value=json.loads(interrupted.read_text(encoding='utf-8'))
            source,manifest=backups.get(value['backup_id']);backups.validate(source,manifest)
            replace_database(directory,source/'roll.sqlite3')
            persist(backups.root/'migration-failure.json',encode({'state':'ROLLED_BACK','backup_id':value['backup_id'],'failed_at':now(),'code':'INTERRUPTED_INITIALIZATION'}).encode())
            interrupted.unlink()
        restore_at_start(backups)
        if backups.path.exists():
            with connection(backups.path) as db:
                names=tables(db);version=db.execute('PRAGMA user_version').fetchone()[0]
                missing={'account_csv_imports','review_tasks','valuation_versions','research_executions'}-names
            deployment=backups.root/'deployment.json'
            changed=not deployment.exists() or json.loads(deployment.read_text(encoding='utf-8'))['fingerprint']!=source_fingerprint()
            if version==1 or missing or changed:
                if live_hosts(directory):raise RuntimeError('UPGRADE_REQUIRES_STOP_ALL_LOCAL_HOSTS')
                previous=backups.create('PRE_UPGRADE')
        from roll.agents.codex_process import process_creation
        owner={'pid':os.getpid(),'creation_ticks':process_creation(os.getpid()),'nonce':str(uuid4())}
        marker=backups.root/('.host-'+owner['nonce']+'.json');persist(marker,encode(owner).encode())
        if previous:persist(backups.root/'upgrade-pending.json',encode({'backup_id':previous['backup_id'],'host_owner':owner}).encode())
    return backups,marker,previous


def finish_bootstrap(backups):
    with startup_lock(backups.directory):
        persist(backups.root/'deployment.json',encode({'fingerprint':source_fingerprint(),'initialized_at':now()}).encode())
        (backups.root/'upgrade-pending.json').unlink(missing_ok=True)


def rollback_bootstrap(backups,marker,previous):
    with startup_lock(backups.directory):
        if previous:
            source,manifest=backups.get(previous['backup_id']);backups.validate(source,manifest)
            replace_database(backups.directory,source/'roll.sqlite3')
            persist(backups.root/'migration-failure.json',encode({'state':'ROLLED_BACK','backup_id':previous['backup_id'],'failed_at':now(),'code':'INITIALIZATION_FAILED_OR_INTERRUPTED'}).encode())
        (backups.root/'upgrade-pending.json').unlink(missing_ok=True)
        marker.unlink(missing_ok=True)


def main():
    import argparse
    parser=argparse.ArgumentParser(description='Roll 本机离线恢复。先停止所有运行该目录的宿主。')
    parser.add_argument('operation',choices=['restore','rollback-upgrade'])
    parser.add_argument('--data-dir',type=Path,required=True)
    parser.add_argument('--bundle',type=Path)
    args=parser.parse_args();backups=Backups(args.data_dir)
    try:
        if live_hosts(backups.directory):raise RuntimeError('STOP_ALL_LOCAL_HOSTS_BEFORE_OFFLINE_RECOVERY')
        if args.operation=='rollback-upgrade':
            candidates=[item for item in backups.list() if item['reason']=='PRE_UPGRADE']
            if not candidates:raise RuntimeError('NO_SUCCESSFUL_PRE_UPGRADE_BACKUP')
            raw=backups.export(candidates[0]['backup_id'])
        else:
            if not args.bundle:parser.error('restore 需要 --bundle')
            raw=args.bundle.read_bytes()
        backups.stage_restore(raw)
        with startup_lock(backups.directory):restore_at_start(backups)
        print(encode({'state':'RESTORED_RECOVERY_LOCK','restore_point':backups.recovery()['restore_point']}))
    except (HTTPException,RuntimeError,OSError) as error:
        print(encode({'state':'FAILED','code':error.detail if isinstance(error,HTTPException) else str(error) if isinstance(error,RuntimeError) else type(error).__name__}))
        raise SystemExit(1)


if __name__=='__main__':main()

