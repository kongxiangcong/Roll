"""One bounded, hash-pinned binary installation in the prepared isolated runtime."""
import argparse,hashlib,json,os,re,subprocess,time
from pathlib import Path
from urllib.parse import urlsplit
out=Path(__file__).parent;root=out.parents[3];runtime=root/'.scratch/rce-runtime/docling';cache=root/'.scratch/rce-runtime/docling-pip-cache'
parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');args=parser.parse_args()
if not args.execute:raise SystemExit('Prepared only')
report=json.loads((out/'pip-direct-resolution.json').read_text(encoding='utf-8'));receipt=json.loads((out/'pip-direct-resolution-receipt.json').read_text());assert receipt.get('exit_code')==0
lines=[]
for item in report['install']:
 name=item['metadata']['name'];url=item['download_info']['url'];parsed=urlsplit(url);sha=item['download_info']['archive_info']['hashes']['sha256']
 assert re.fullmatch(r'[A-Za-z0-9_.-]+',name) and re.fullmatch(r'[0-9a-f]{64}',sha)
 assert parsed.scheme=='https' and parsed.hostname=='files.pythonhosted.org' and parsed.port in (None,443) and not parsed.username and parsed.path.endswith('.whl')
 lines.append(f'{name} @ {url} --hash=sha256:{sha}')
lock=out/'requirements.lock';lock.write_text('\n'.join(lines)+'\n',encoding='utf-8')
with (out/'install-attempt.json').open('x',encoding='utf-8') as file:json.dump({'status':'RUNNING','lock_sha256':hashlib.sha256(lock.read_bytes()).hexdigest()},file)
plan=json.loads((out/'runtime-plan.json').read_text());started=time.monotonic();result={'status':'FAILED_CLOSED','installed_packages':len(lines),'models_downloaded':False};process=None
try:
 env={k:v for k,v in os.environ.items() if k.upper() in {'PATH','SYSTEMROOT','WINDIR','USERPROFILE','APPDATA','LOCALAPPDATA','TEMP','TMP'}};env.update(NO_PROXY='*',PIP_CONFIG_FILE=os.devnull)
 with (out/'install.log').open('wb') as log:
  process=subprocess.Popen([str(runtime/'Scripts/python.exe'),'-m','pip','--disable-pip-version-check','install','--no-index','--no-deps','--require-hashes','--no-compile','--only-binary',':all:','--retries','0','--timeout','15','--cache-dir',str(cache),'-r',str(lock)],env=env,stdout=log,stderr=subprocess.STDOUT)
  while process.poll() is None:
   sizes={label:sum(p.stat().st_size for p in directory.rglob('*') if p.is_file()) for label,directory in [('cache',cache),('runtime',runtime)]}
   if time.monotonic()-started>plan['installation_timeout_seconds'] or sizes['cache']>plan['max_new_download_bytes'] or sizes['runtime']>plan['max_runtime_disk_bytes']:
    process.kill();process.wait();raise RuntimeError('ISOLATED_INSTALL_RESOURCE_LIMIT')
   time.sleep(2)
  result['exit_code']=process.returncode
  if process.returncode==0:result['status']='INSTALLED'
except Exception as error:
 if process and process.poll() is None:process.kill();process.wait()
 result['error']=type(error).__name__+':'+str(error)[:300]
finally:
 result['elapsed_seconds']=time.monotonic()-started;(out/'install-attempt.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
