"""Explicit daily API-only host, no environment file or model configuration."""
import os
from pathlib import Path
import json
for key in list(os.environ):
    if key.startswith(('ROLL_CODEX_', 'ROLL_DEEPSEEK_')):
        os.environ.pop(key, None)
import uvicorn
import roll.app
root=Path('D:/dsh-proj/Roll/.scratch/rv12-daily01')
logs=root/'logs'
logs.mkdir(exist_ok=True)
(logs/'module-paths.json').write_text(json.dumps(dict(app=roll.app.__file__,auth_configured=False)),encoding='utf-8')
app=roll.app.create_app(root,runtime_role='API')
uvicorn.run(app,host='127.0.0.1',port=8033)
