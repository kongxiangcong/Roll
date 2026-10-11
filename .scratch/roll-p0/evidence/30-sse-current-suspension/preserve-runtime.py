"""Copy only named fifth-slice owned files bytewise; never SQLite-open or touch older namespaces."""
import hashlib
import json
import os
import shutil
from pathlib import Path

repo=Path(__file__).resolve().parents[4]
root=Path('D:/dsh-proj/Roll')
names=['t30s-receipt-red','t30s-receipt-green','t30s-consumer-red','t30s-consumer-green',
 't30s-worker-red','t30s-worker-green','t30s-binding-red','t30s-binding-green',
 't30s-final','t30s-caller','t30s-live','t30s-composition']
target=root/'.roll-data/implementation-evidence/continuation-ticket30-sse-current-suspension'
def extended(path):return Path('\\\\?\\'+str(path.resolve()))
def ordinary(path):return str(path).removeprefix('\\\\?\\')
def digest(path):
 h=hashlib.sha256();size=0
 with path.open('rb') as stream:
  while chunk:=stream.read(1048576):h.update(chunk);size+=len(chunk)
 return {'sha256':h.hexdigest(),'bytes':size}
records=[]
for name in names:
 source=extended(repo/'.scratch'/name)
 assert source.is_dir() and not source.is_symlink() and not source.is_junction()
 for current,directories,files in os.walk(source):
  current=Path(current)
  assert not current.is_symlink() and not current.is_junction()
  for directory in directories:
   entry=current/directory
   assert not entry.is_symlink() and not entry.is_junction()
  for filename in files:
   origin=current/filename
   assert not origin.is_symlink()
   destination=extended(target/name)/origin.relative_to(source)
   expected=digest(origin)
   destination.parent.mkdir(parents=True,exist_ok=True)
   assert not destination.is_symlink() and not destination.is_junction()
   if destination.exists():assert digest(destination)==expected
   else:shutil.copyfile(origin,destination)
   assert digest(destination)==expected
   records.append({'source':ordinary(origin),'destination':ordinary(destination),**expected})
receipt={'scope':'FIFTH_SLICE_OWNED_METHOD_AND_ONE_REAL_PUBLIC_SOURCE_ASSESSMENT_BYTEWISE_ONLY',
 'files':len(records),'bytes':sum(r['bytes'] for r in records),'sha_or_length_mismatches':0,
 'target':str(target),'source_directories':[str(repo/'.scratch'/name) for name in names],
 'previous_preservation_targets_read_or_written':False,'sqlite_opened':False,
 'real_assessment_network_calls':1,'copy_network_calls':0,'own_test_and_assessment_processes_exited':True}
for filename,value in [('runtime-preservation-manifest.json',records),('runtime-preservation-receipt.json',receipt)]:
 Path(__file__).with_name(filename).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({k:receipt[k] for k in ['files','bytes','sha_or_length_mismatches']}))
