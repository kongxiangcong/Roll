"""Copy only this stopped tree's public METHOD runtime; never connect SQLite."""
from pathlib import Path
import hashlib, json, os, re, shutil, sys, time

own=Path(__file__).resolve().parents[4]
root=Path('D:/dsh-proj/Roll')
target=root/'.roll-data/implementation-evidence/ticket25-ordering'
receipt=Path(__file__).parent
roots=[own/'.ord',own/'.scratch/roll-p0/run-ordering',own/'.pytest_cache']

def absolute(path): return os.path.normcase(os.path.abspath(path))
def inside(path, parent): return os.path.commonpath([absolute(path),absolute(parent)])==absolute(parent)
def long(path):
    value=os.path.abspath(path)
    return '\\\\?\\'+value if os.name=='nt' and not value.startswith('\\\\?\\') else value
def mkdir(path):
    pending=[]
    while not path.exists(): pending.append(path);path=path.parent
    if path.is_symlink() or (path.stat().st_file_attributes & 0x400 if os.name=='nt' else False): raise ValueError('REPARSE_PARENT')
    for folder in reversed(pending): os.mkdir(long(folder))
def checksum(path):
    with open(long(path),'rb') as stream: digest=hashlib.file_digest(stream,'sha256').hexdigest()
    return os.stat(long(path)).st_size,digest

assert target.is_absolute() and inside(target,root/'.roll-data/implementation-evidence')
assert all(inside(path,own) for path in roots)
if target.exists(): raise ValueError('NEW_NAMESPACE_REQUIRED_DO_NOT_OVERWRITE')
files=[]; exclusions=[]; failures=[]
for directory in roots:
    if not directory.exists(): continue
    for folder,dirs,names in os.walk(long(directory),followlinks=False):
        for name in [*dirs,*names]:
            path=Path(folder)/name
            if os.stat(path,follow_symlinks=False).st_file_attributes & 0x400:
                raise ValueError('REPARSE_OR_UNKNOWN_ENTRY: '+str(path))
        for name in names:
            path=Path(str(Path(folder)/name).removeprefix('\\\\?\\'))
            assert inside(path,own)
            if re.search(r'(?i)(auth|credential|secret|token|(^|\.)env($|\.))',name):
                exclusions.append({'path':str(path),'category':'PRIVATE_OR_UNKNOWN_NAME_NOT_READ_HASHED_COPIED','cleanup_allowed':False})
                continue
            files.append(path)
mkdir(target)
rows=[]
for source in sorted(files):
    relative=source.relative_to(own)
    destination=target/'runtime'/relative
    assert inside(destination,target)
    try:
        before=checksum(source)
        mkdir(destination.parent)
        if destination.exists(): raise ValueError('DESTINATION_EXISTS')
        shutil.copyfile(long(source),long(destination))
        after=checksum(source);copied=checksum(destination)
        if before!=after or before!=copied: raise ValueError('SOURCE_DESTINATION_BYTE_MISMATCH')
        rows.append({'source':str(source),'destination':str(destination),'relative':relative.as_posix(),'bytes':before[0],'sha256':before[1]})
    except Exception as error:
        failures.append({'source':str(source),'destination':str(destination),'error_type':type(error).__name__,'error':str(error)})
        (receipt/'preservation-failures.json').write_text(json.dumps(failures,indent=2)+'\n',encoding='utf-8')
# Independent second complete pass over both ends, no SQLite connection.
for row in rows:
    for key in ['source','destination']:
        try:
            if checksum(Path(row[key]))!=(row['bytes'],row['sha256']): raise ValueError('FINAL_BYTE_MISMATCH')
        except Exception as error:
            failures.append({'path':row[key],'error_type':type(error).__name__,'error':str(error)})
manifest={'namespace':str(target),'kind':'PUBLIC_METHOD_RUNTIME_PRESERVATION_ONLY','own_tree':str(own),
          'file_count':len(rows),'bytes':sum(row['bytes'] for row in rows),'dual_end_final_checks':2*len(rows),
          'exclusions':exclusions,'failures':failures,'mismatches':len(failures),'rows':rows,
          'source_retained':True,'sqlite_connections':0,'deleted_files':0,
          'cleanup_allowed':not exclusions and not failures,'recorded_unix':time.time()}
file=receipt/'preservation-manifest.json'
if file.exists(): raise ValueError('MANIFEST_EXISTS')
file.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
shutil.copyfile(long(file),long(target/'preservation-manifest.json'))
assert checksum(file)==checksum(target/'preservation-manifest.json')
print(json.dumps({k:v for k,v in manifest.items() if k!='rows'},ensure_ascii=False))
if failures:sys.exit(1)
