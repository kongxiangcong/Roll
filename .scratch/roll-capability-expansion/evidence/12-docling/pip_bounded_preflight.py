import os,subprocess,json,time
from pathlib import Path
out=Path(__file__).parent;root=out.parents[3];runtime=root/'.scratch/rce-runtime/docling';assert (runtime/'Scripts/python.exe').is_file()
started=time.time();env={k:v for k,v in os.environ.items() if k.upper() in {'PATH','SYSTEMROOT','WINDIR','USERPROFILE','APPDATA','LOCALAPPDATA','TEMP','TMP'}}
env.update(NO_PROXY='*',PIP_CONFIG_FILE=os.devnull)
result={'phase':'BOUNDED_EXPLICIT_BINARY_RESOLUTION','status':'CLOSED','model_downloads':False,'temporary_proxy_bypass':True}
try:
 command=[str(runtime/'Scripts/python.exe'),str(out/'pip_binary_entry.py'),'--disable-pip-version-check','install','--dry-run','--report',str(out/'pip-bounded-resolution.json'),'--only-binary',':all:','--index-url','https://pypi.org/simple','--retries','0','--timeout','15','--cache-dir',str(root/'.scratch/rce-runtime/docling-pip-cache'),'-r',str(out/'requirements-pypi.in')]
 with (out/'pip-bounded-resolution.log').open('wb') as log:completed=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
 result['exit_code']=completed.returncode
except subprocess.TimeoutExpired:result['error']='RESOLUTION_WALL_TIME_LIMIT'
finally:
 result['elapsed_seconds']=time.time()-started;(out/'pip-bounded-resolution-receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
