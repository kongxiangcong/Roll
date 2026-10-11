"""Stopped owned runtime union only. Private metadata is never read/hash/copied."""
from pathlib import Path
import os,json,hashlib,shutil,subprocess,sys
TREE=Path(__file__).resolve().parents[5]
ROOT=Path('D:/dsh-proj/Roll')
OUT=TREE/'.scratch/roll-p0/evidence/31-final'
TARGET=ROOT/'.roll-data/implementation-evidence/31-final-r01'
assert not TARGET.exists()
def long(path):return Path('\\\\?\\'+str(path.resolve())) if os.name=='nt' else path
sources=[TREE/'.roll-data']+sorted(p for p in (TREE/'.scratch').iterdir() if p.is_dir() and p.name.startswith('f31'))
# Only public browser output; physical install/cache directories are not runtimes.
if (TREE/'frontend/test-results').exists():sources.append(TREE/'frontend/test-results')
assert all(p.resolve().is_relative_to(TREE) for p in sources)
receipts=[json.loads(p.read_bytes()) for p in (OUT/'runs').glob('live-*/live-receipt.json')]
checks=[]
for receipt in receipts:
    for item in receipt['processes']:
        for row in item.get('cim_at_start',[]):
            pid=int(row['ProcessId'])
            command=f"Get-CimInstance Win32_Process -Filter 'ProcessId={pid}' | Select-Object ProcessId,CreationDate,ExecutablePath | ConvertTo-Json -Compress"
            raw=subprocess.check_output(['powershell','-NoProfile','-Command',command],text=True).strip()
            current=json.loads(raw) if raw else None
            assert current is None or current['CreationDate']!=row['CreationDate'], 'Owned process still alive'
            checks.append({'pid':pid,'recorded_creation':row['CreationDate'],'current':current})
entries=[];links=[];private=[]
for source in sources:
    for folder,dirs,files in os.walk(long(source),followlinks=False):
        directory=Path(folder)
        for name in list(dirs):
            path=directory/name
            if path.lstat().st_file_attributes & 1024:
                links.append({'path':str(path),'target':str(path.resolve()),'metadata_only':True})
                dirs.remove(name)
        for name in files:
            path=directory/name
            # Refuse any unexpected private locator before touching its bytes.
            if name.lower() in {'auth.json','channel.json','credentials.json','.env'} or name.lower().endswith('.env'):
                private.append(str(path));continue
            if path.lstat().st_file_attributes & 1024:raise AssertionError('Unexpected file reparse metadata: '+str(path))
            ordinary=Path(str(path).removeprefix('\\\\?\\'))
            relative=ordinary.relative_to(TREE).as_posix()
            with path.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
            entries.append({'path':relative,'bytes':path.stat().st_size,'sha256':sha})
assert not private, 'Unexpected private metadata; source retained, no bytes read: '+repr(private)
assert len({r['path'] for r in entries})==len(entries)
for row in entries:
    source=long(TREE/row['path']);destination=long(TARGET/row['path']);destination.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,destination)
    for path in (source,destination):
        with path.open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==row['sha256']
        assert path.stat().st_size==row['bytes']
result={'state':'VERIFIED_STOPPED_OWN_RUNTIME_UNION','source_tree':str(TREE),'destination':str(TARGET),'source_roots':[str(p) for p in sources],'files':len(entries),'bytes':sum(r['bytes'] for r in entries),'entries':entries,'exact_private_metadata_exclusions':[],'unexpected_private_metadata':private,'reparse_metadata_only':links,'cim_stop_checks':checks,'original_sqlite_connections':0,'source_and_destination_mismatches':0,'dependency_cache_bytes_read':0}
raw=(json.dumps(result,indent=2)+'\n').encode()
(OUT/'runtime-union-manifest.json').write_bytes(raw)
(TARGET/'runtime-union-manifest.json').write_bytes(raw)
(OUT/'runtime-preservation-summary.json').write_text(json.dumps({'files':result['files'],'bytes':result['bytes'],'manifest_bytes':len(raw),'manifest_sha256':hashlib.sha256(raw).hexdigest(),'destination':str(TARGET),'mismatches':0,'exact_private_exclusions':0,'cim_stop_checks':len(checks)},indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({'files':result['files'],'bytes':result['bytes'],'target':str(TARGET),'mismatches':0,'private_exclusions':0}))
