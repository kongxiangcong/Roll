"""Full owned runtime union; opaque SQLite copy, exact fixture secret exclusions."""
from pathlib import Path
import hashlib, json, os, shutil, subprocess
own=Path(__file__).resolve().parents[4]
out=Path(__file__).parent
target=Path('D:/dsh-proj/Roll/.roll-data/implementation-evidence/final-review-fix/runtime')
assert not target.exists() and target.resolve().is_relative_to(Path('D:/dsh-proj/Roll/.roll-data/implementation-evidence/final-review-fix').resolve())
groups=['.fr','backend/.pytest_cache','frontend/dist']
exclusions={f'.fr/{stage}/fixture/auth.json':'Exact synthetic METHOD_CASE_ONLY writer: backend/tests/support/final_review_method_app.py:22-24; metadata only' for stage in ['chrome-red','chrome-green','chrome-research']}
exclusions['.fr/affected/test_report_preserves_actual_20/data/notification-private/channel.json']='Exact test_reports.py public MockTransport ntfy.example.test configuration, no actual channel; private contents not read/hash/copied'
known_reparse=own/'frontend/node_modules'
assert known_reparse.is_junction() and known_reparse.resolve()==Path('D:/dsh-proj/Roll/frontend/node_modules').resolve()
def long(path):return '\\\\?\\'+str(path.resolve())
def digest(path):
    with open(long(path),'rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
source_files=[]
for group in groups:
    base=own/group
    assert base.is_dir() and base.resolve().is_relative_to(own.resolve())
    for directory,folders,files in os.walk(long(base),followlinks=False):
        for folder in folders:
            assert not os.lstat(os.path.join(directory,folder)).st_file_attributes & 1024, 'Unknown runtime reparse'
        for name in files:
            file=Path(directory)/name
            assert not file.lstat().st_file_attributes & 1024, 'Unknown runtime file reparse'
            normal=Path(str(file).removeprefix('\\\\?\\'))
            relative=normal.relative_to(own).as_posix()
            if relative in exclusions:continue
            assert name.lower() not in {'auth.json','credentials.json','channel.json','.env'} and not name.lower().startswith('.env'), f'Unknown private file: {relative}'
            source_files.append((relative,normal))
assert all((own/path).is_file() for path in exclusions)
entries=[]
for relative,source in sorted(source_files):
    destination=target/relative
    before=digest(source);size=source.stat().st_size
    try:
        Path(long(destination.parent)).mkdir(parents=True,exist_ok=True)
        shutil.copyfile(long(source),long(destination))
        assert destination.stat().st_size==size and digest(destination)==before
        assert source.stat().st_size==size and digest(source)==before
    except Exception as error:
        diagnostic=out/'preservation-copy-failure.json'
        assert not diagnostic.exists()
        diagnostic.write_text(json.dumps({'source':str(source),'target':str(destination),'error':repr(error),'copied_before_failure':len(entries)},indent=2)+'\n',encoding='utf-8')
        raise
    entries.append({'source':str(source),'target':str(destination),'path':relative,'bytes':size,'sha256':before})
ignored=subprocess.check_output(['git','ls-files','--others','--ignored','--exclude-standard','--directory'],cwd=own,text=True).splitlines()
assert all(path.startswith('.fr/') or path in ['backend/.pytest_cache/','frontend/dist/','frontend/node_modules/'] for path in ignored), ignored
assert {p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()}=={e['path'] for e in entries}
result={'source_tree':str(own),'source_product_oid':'bbb84a57f624dec9351b32373fd9d10e1447eed3','target_namespace':str(target),
        'runtime_groups':groups,'files':len(entries),'bytes':sum(e['bytes'] for e in entries),'double_end_checks':2*len(entries),'mismatches':0,
        'SQLite_connections':0,'copy_only':True,'source_tree_retained':True,'exact_private_exclusions':[{'path':p,'basis':basis,'content_read':False,'hashed':False,'copied':False} for p,basis in exclusions.items()],
        'known_dependency_junction_not_copied':str(known_reparse),'git_ignored_inventory':ignored,'entries':entries}
path=out/'runtime-preservation-manifest.json';assert not path.exists()
path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:result[k] for k in ['files','bytes','double_end_checks','mismatches','SQLite_connections']}))
