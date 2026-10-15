"""One bounded anonymous binary-only bootstrap in a new isolated runtime."""
import json,os,subprocess,time
from pathlib import Path
out=Path(__file__).resolve().parent;root=out.parents[3];runtime=root/'.scratch/rce-runtime/trafilatura';start=time.monotonic()
guard=out/'dependency-attempt.json'
with guard.open('x',encoding='utf-8') as f:json.dump({'status':'RUNNING','maximum_seconds':600,'retries':0},f)
env={k:v for k,v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','TEMP','TMP','PATH'}};env.update(NO_PROXY='*',PIP_CONFIG_FILE='NUL',PIP_DISABLE_PIP_VERSION_CHECK='1')
receipt={'status':'CLOSED','models':False}
try:
 subprocess.run([str(root/'backend/.venv/Scripts/python.exe'),'-m','venv',str(runtime)],env=env,check=True,timeout=40,capture_output=True)
 command=[str(runtime/'Scripts/python.exe'),'-I','-B',str(out/'pip_binary_entry.py'),'install','--only-binary',':all:','--index-url','https://pypi.org/simple','--retries','0','--timeout','15','--report',str(out/'dependency-report.json'),'--cache-dir',str(root/'.scratch/rce-runtime/trafilatura-cache'),'trafilatura==2.3.1']
 with (out/'dependency-install.log').open('w',encoding='utf-8') as log:
  result=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=max(1,600-(time.monotonic()-start)))
 receipt.update(exit_code=result.returncode,status='INSTALLED' if result.returncode==0 else 'CLOSED')
except Exception as e:receipt['error']=type(e).__name__
finally:
 receipt['elapsed_seconds']=time.monotonic()-start;guard.write_text(json.dumps(receipt,indent=2))
