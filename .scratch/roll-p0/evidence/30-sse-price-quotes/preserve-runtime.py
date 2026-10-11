"""Copy only nine named eighth-slice METHOD directories; never SQLite-open old targets."""
import hashlib
import json
import os
import shutil
from pathlib import Path
repo=Path(__file__).resolve().parents[4]
target=Path('D:/dsh-proj/Roll/.roll-data/implementation-evidence/continuation-ticket30-sse-price-quotes')
names=['t30q-assessment-red','t30q-assessment-green','t30q-assessment-green-clock',
 't30q-consumer-red','t30q-consumer-green','t30q-contract','t30q-refused-source-red',
 't30q-refused-source-green','t30q-composition']
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
  current=Path(current);assert not current.is_symlink() and not current.is_junction()
  for directory in directories:
   entry=current/directory;assert not entry.is_symlink() and not entry.is_junction()
  for filename in files:
   origin=current/filename;assert not origin.is_symlink()
   destination=extended(target/name)/origin.relative_to(source)
   expected=digest(origin);destination.parent.mkdir(parents=True,exist_ok=True)
   assert not destination.is_symlink() and not destination.is_junction()
   if destination.exists():assert digest(destination)==expected
   else:shutil.copyfile(origin,destination)
   assert digest(destination)==expected
   records.append({'source':ordinary(origin),'destination':ordinary(destination),**expected})
receipt={'scope':'EIGHTH_OWNED_OFFLINE_METHOD_ONLY_BYTEWISE_APPEND_NEW_NAMESPACE',
 'files':len(records),'bytes':sum(r['bytes'] for r in records),'sha_or_length_mismatches':0,
 'target':str(target),'source_directories':[str(repo/'.scratch'/name) for name in names],
 'previous_preservation_targets_read_or_written':False,'sqlite_opened':False,
 'actual_network_calls':0,'copy_network_calls':0,'own_test_processes_exited':True}
for filename,value in [('runtime-preservation-manifest.json',records),('runtime-preservation-receipt.json',receipt)]:
 Path(__file__).with_name(filename).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({k:receipt[k] for k in ['files','bytes','sha_or_length_mismatches']}))
