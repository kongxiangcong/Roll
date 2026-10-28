"""Local-only new-source preparation API; never load auth or a worker."""
import os
from pathlib import Path
for key in list(os.environ):
 if key.startswith(('ROLL_CODEX_','ROLL_DEEPSEEK_')):os.environ.pop(key,None)
import uvicorn,roll.app
app=roll.app.create_app(Path('D:/dsh-proj/Roll/.scratch/rv12-economic-prep07'),runtime_role='API')
Path(__file__).with_name('module-proof.json').write_text(__import__('json').dumps(dict(app_module=roll.app.__file__,runtime_role='API',dotenv_loaded=False,auth_keys_removed=True,worker_started=False)),encoding='utf-8')
uvicorn.run(app,host='127.0.0.1',port=8035)
