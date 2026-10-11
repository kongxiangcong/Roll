"""Preserve only this follow-up's explicitly owned METHOD test files, bytewise only."""
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

repo=Path(__file__).resolve().parents[4]
root=Path('D:/dsh-proj/Roll')
composition=len(sys.argv)>1 and sys.argv[1]=='composition'
names=['t30c-composition'] if composition else ['t30c-index-red','t30c-index-green',
 't30c-cash-red','t30c-cash-green','t30c-binding-check','t30c-final']
suffix='-composition' if composition else ''
target=root/('.roll-data/implementation-evidence/continuation-ticket30-cninfo-history'+suffix)
def extended(path):
 return Path('\\\\?\\'+str(path.resolve()))
def ordinary(path):
 return str(path).removeprefix('\\\\?\\')
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
receipt={'scope':'OWNED_OFFLINE_METHOD_TESTS_ONLY_NO_SQLITE_OPEN',
 'files':len(records),'bytes':sum(r['bytes'] for r in records),'sha_or_length_mismatches':0,
 'target':str(target),'source_directories':[str(repo/'.scratch'/name) for name in names],
 'previous_preservation_targets_read_or_written':False,'original19_sqlite_read':False,'network_calls':0}
prefix='composition-preservation' if composition else 'runtime-preservation'
for filename,value in [(prefix+'-manifest.json',records),(prefix+'-receipt.json',receipt)]:
 Path(__file__).with_name(filename).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({k:receipt[k] for k in ['files','bytes','sha_or_length_mismatches']}))
