"""Preserve ended, isolated METHOD runtimes; never reads an actual research profile."""
import hashlib,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
TARGET=Path('D:/dsh-proj/Roll/.roll-data/implementation-evidence/30')
profiles={'browser-method-final':ROOT/'.scratch/browser-30-final',
 'browser-method-offset-final':ROOT/'.scratch/browser-30-offset-final',
 'account-snapshot-offset-final':ROOT/'.scratch/pytest-30-offset-final/test_unique_method_sample_and_0',
 'mature-offset-final':ROOT/'.scratch/pytest-30-offset-final/test_mature_settlement_only_sc0',
 'fault-after-archive':ROOT/'.scratch/pytest-30-final/test_real_process_archive_and_0',
 'fault-before-commit':ROOT/'.scratch/pytest-30-final/test_real_process_archive_and_1',
 'fault-after-commit':ROOT/'.scratch/pytest-30-final/test_real_process_archive_and_2',
 'fault-concurrent-restart':ROOT/'.scratch/pytest-30-final/test_real_http_concurrent_trig0',
 'fault-close-claim':ROOT/'.scratch/pytest-30-final/test_process_interrupted_close0',
 'recovery-lock':ROOT/'.scratch/pytest-30-final/test_actual_backup_restore_loc0',
 'account-snapshot-revision':ROOT/'.scratch/pytest-30-revision-fixed/test_unique_method_sample_and_0'}
out=[]
for name,source in profiles.items():
    target=TARGET/name;rows=[]
    for file in sorted(source.rglob('*')):
        if not file.is_file():continue
        assert 'auth' not in file.name.lower()
        relative=file.relative_to(source);raw=file.read_bytes();sha=hashlib.sha256(raw).hexdigest()
        copy=target/relative;copy.parent.mkdir(parents=True,exist_ok=True)
        if not copy.exists():shutil.copy2(file,copy)
        preserved=copy.read_bytes();assert len(preserved)==len(raw) and hashlib.sha256(preserved).hexdigest()==sha
        rows.append({'path':relative.as_posix(),'sha256':sha,'length':len(raw),'target_matches':True})
    assert rows
    out.append({'namespace':'METHOD_CASE','source':str(source),'target':str(target),'file_count':len(rows),'files':rows})
Path(sys.argv[1]).write_text(json.dumps({'profiles':out,'mismatches':0},indent=2)+'\n',encoding='utf-8')
print('profiles',len(out),'files',sum(v['file_count'] for v in out),'mismatches 0')
