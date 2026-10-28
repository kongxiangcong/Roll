"""Explicit API-only acceptance host; no worker, model configuration or .env."""
from pathlib import Path
import json
import roll.app
from roll.research.company import service, daily, features
import uvicorn

root = Path('D:/dsh-proj/Roll/.scratch/rv12-real01')
logs = root / 'logs'
logs.mkdir(exist_ok=True)
(logs / 'module-paths.json').write_text(json.dumps(dict(app=roll.app.__file__,
    service=service.__file__, daily=daily.__file__, features=features.__file__)), encoding='utf-8')
app = roll.app.create_app(root, runtime_role='API')
uvicorn.run(app, host='127.0.0.1', port=8032)
