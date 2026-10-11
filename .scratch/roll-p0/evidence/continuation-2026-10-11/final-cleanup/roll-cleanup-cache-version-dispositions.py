import json,hashlib,os,stat,shutil
from pathlib import Path
v=Path(__file__).parent;r=Path('D:/dsh-proj/Roll')
def rd(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
m=rd(v/'roll-cleanup-batch-v6-metadata.json');release=rd(v/'roll-cleanup-release-v13-exact3802.json')
def ext(p):return '\\\\?\\'+os.path.abspath(p)
def guard(p):
 for x in [p,*p.parents]:
  s=os.stat(ext(x),follow_symlinks=False)
  assert not s.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
 assert p.is_file()
versions=[];current={};verified=0
for t in m['trees']:
 tree=Path(t['path']) if t.get('path') else None
 if not tree:continue
 for d in t['manifests']:
  if d.get('special')=='runner':continue
  vals=rd(d['path']); vals=vals if d['field']=='array' else vals[d['field']]
  for x in vals:
   source=Path(x['source']);source=source if source.is_absolute() else Path(d['source_base'])/source
   try:relative=source.relative_to(tree)
   except ValueError:continue
   if not str(relative).replace('\\','/').startswith('.pytest_cache/'):continue
   assert source.name in {'nodeids','lastfailed','stepwise','README.md','.gitignore','CACHEDIR.TAG'}
   guard(source);b=source.read_bytes();nowsha=hashlib.sha256(b).hexdigest();verified+=1
   if len(b)==x['bytes'] and nowsha==x['sha256']:continue
   dp=x.get('destination',x.get('preserved',x.get('target')));dest=Path(dp);dest=dest if dest.is_absolute() else Path(d['destination_base'])/dest
   guard(dest);old=dest.read_bytes();assert len(old)==x['bytes'] and hashlib.sha256(old).hexdigest()==x['sha256']
   target=r/'.roll-data/implementation-evidence/final-cleanup-cache-current-20261012'/t['name']/relative
   if str(source) not in current:
    assert not target.exists();target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    guard(target);assert target.read_bytes()==b
    current[str(source)]=dict(source=str(source),destination=str(target),bytes=len(b),sha256=nowsha)
   rt=next(a for a in release['trees'] if a['name']==t['name'])
   versions.append(dict(source=str(source),manifest=d['path'],historical_destination=str(dest),historical_bytes=x['bytes'],historical_sha256=x['sha256'],current_destination=str(target),current_bytes=len(b),current_sha256=nowsha,kind='PUBLIC_PYTEST_CACHE_CURRENT_VERSION',tree=t['name'],source_owner_receipt=rt['finite_acceptance_receipt']))
assert versions and current
(v/'roll-cleanup-cache-version-dispositions.json').write_text(json.dumps(dict(exact_historical_source_versions=versions,current_rows=list(current.values()),public_cache_manifest_rows_checked=verified,private_reads=0,sqlite_connections=0),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(changed_exact_sources=len(current),historical_rows=len(versions),checked_cache_rows=verified)))
