"""One direct metadata and hash-locked wheel preparation, with no request retries."""
import hashlib,json,os,socket,subprocess,time,urllib.request
from pathlib import Path
from pip._vendor.packaging.requirements import Requirement
from pip._vendor.packaging.tags import sys_tags
from pip._vendor.packaging.utils import canonicalize_name,parse_wheel_filename
out=Path(__file__).resolve().parent;root=out.parents[3];start=time.monotonic();calls=0;received=0
guard=out/'dependency-recovery-receipt.json'
with guard.open('x') as f:json.dump({'status':'RUNNING'},f)
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise ValueError('DEPENDENCY_REDIRECT_REJECTED')
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
resolve=socket.getaddrinfo
def ipv4(host,port,*args,**kwargs):return resolve(host,port,socket.AF_INET,socket.SOCK_STREAM)
socket.getaddrinfo=ipv4
def fetch(url):
 global calls,received
 from urllib.parse import urlsplit
 p=urlsplit(url);calls+=1
 if p.scheme!='https' or p.hostname not in {'pypi.org','files.pythonhosted.org'} or p.username or p.port not in (None,443) or calls>100 or time.monotonic()-start>600:raise ValueError('DEPENDENCY_TARGET_OR_CALL_BUDGET')
 with opener.open(url,timeout=min(20,600-(time.monotonic()-start))) as response:
  parts=[]
  while chunk:=response.read(65536):
   received+=len(chunk)
   if received>104857600 or time.monotonic()-start>600:raise ValueError('DEPENDENCY_BYTE_OR_TIME_BUDGET')
   parts.append(chunk)
 with (out/'dependency-recovery-network.jsonl').open('a') as f:f.write(json.dumps({'url':url,'ordinal':calls,'bytes':sum(map(len,parts))})+'\n')
 return b''.join(parts)
receipt={'status':'CLOSED','retries':0};selected={};requirements=[Requirement('trafilatura==2.3.1')];queue=requirements.copy();tags=list(sys_tags());rank={tag:i for i,tag in enumerate(tags)}
try:
 while queue:
  requirement=queue.pop(0);name=canonicalize_name(requirement.name)
  if requirement.marker and not requirement.marker.evaluate({'extra':''}):continue
  if name in selected:
   if selected[name]['version'] not in requirement.specifier:raise ValueError('DEPENDENCY_CONSTRAINT_MISMATCH:'+name)
   continue
  metadata=json.loads(fetch('https://pypi.org/pypi/'+name+'/json'));info=metadata['info'];version=info['version']
  if version not in requirement.specifier:raise ValueError('DEPENDENCY_CURRENT_VERSION_NOT_COMPATIBLE:'+name)
  choices=[]
  for item in metadata['urls']:
   if item['filename'].endswith('.whl') and not item.get('yanked'):
    wheel_tags=parse_wheel_filename(item['filename'])[3];ranks=[rank[t] for t in wheel_tags if t in rank]
    if ranks:choices.append((min(ranks),item['filename'],item))
  if not choices:raise ValueError('DEPENDENCY_BINARY_WHEEL_UNAVAILABLE:'+name)
  artifact=min(choices)[2];selected[name]={'version':version,'artifact':artifact,'requires_dist':info.get('requires_dist') or [],'license_expression':info.get('license_expression'),'license':info.get('license')}
  queue.extend(Requirement(text) for text in info.get('requires_dist') or [])
  (out/'dependency-artifact-lock.json').write_text(json.dumps(selected,indent=2))
 wheelhouse=root/'.scratch/rce-runtime/trafilatura-wheelhouse';wheelhouse.mkdir(exist_ok=True)
 lock=[]
 for name,item in selected.items():
  artifact=item['artifact'];raw=fetch(artifact['url']);sha=hashlib.sha256(raw).hexdigest()
  if sha!=artifact['digests']['sha256']:raise ValueError('DEPENDENCY_WHEEL_SHA_MISMATCH:'+name)
  target=wheelhouse/artifact['filename'];target.write_bytes(raw);lock.append(target.as_uri()+' --hash=sha256:'+sha)
 requirements_file=out/'requirements-local.lock';requirements_file.write_text('\n'.join(lock)+'\n')
 env={k:v for k,v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','TEMP','TMP','PATH'}};env.update(PIP_CONFIG_FILE='NUL',PIP_DISABLE_PIP_VERSION_CHECK='1')
 with (out/'dependency-offline-install.log').open('w') as log:
  result=subprocess.run([str(root/'.scratch/rce-runtime/trafilatura/Scripts/python.exe'),'-m','pip','install','--no-index','--no-deps','--require-hashes','--no-compile','-r',str(requirements_file)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=max(1,600-(time.monotonic()-start)))
 receipt.update(status='INSTALLED' if result.returncode==0 else 'CLOSED',exit_code=result.returncode,packages=len(selected))
except Exception as e:receipt['error']=str(e)[:300]
finally:
 receipt.update(elapsed_seconds=time.monotonic()-start,requests=calls,bytes=received);guard.write_text(json.dumps(receipt,indent=2))
