import os,subprocess,json,time
from pathlib import Path
out=Path(__file__).parent;root=out.parents[3]
started=time.time();env={k:v for k,v in os.environ.items() if k.upper() in {'PATH','SYSTEMROOT','WINDIR','USERPROFILE','APPDATA','LOCALAPPDATA','TEMP','TMP'}};env.update(UV_HTTP_RETRIES='0',UV_HTTP_TIMEOUT='60',UV_CONCURRENT_DOWNLOADS='1',UV_CACHE_DIR=str(root/'.scratch/rce-runtime/docling-cache'))
command=['uv','--no-config','pip','compile',str(out/'requirements-pypi.in'),'--python',str(root/'backend/.venv/Scripts/python.exe'),'--default-index','https://pypi.org/simple','--index-strategy','first-index','--only-binary',':all:','--generate-hashes','--output-file',str(out/'requirements.lock')]
result={'status':'CLOSED','phase':'DEPENDENCY_RESOLUTION','downloaded_models':False}
try:
    with (out/'resolve-pypi.log').open('wb') as log:
        completed=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=240)
    result['exit_code']=completed.returncode
finally:
    result['elapsed_seconds']=time.time()-started;(out/'resolve-pypi-receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
