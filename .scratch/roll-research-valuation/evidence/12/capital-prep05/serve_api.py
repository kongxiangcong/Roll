"""Explicit local capital-preparation API, no worker/environment/auth loading."""
import os
from pathlib import Path
for key in list(os.environ):
    if key.startswith(('ROLL_CODEX_','ROLL_DEEPSEEK_')):os.environ.pop(key,None)
import uvicorn
import roll.app
app=roll.app.create_app(Path('D:/dsh-proj/Roll/.scratch/rv12-capital-prep01'),runtime_role='API')
uvicorn.run(app,host='127.0.0.1',port=8034)
