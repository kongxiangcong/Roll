"""Explicit11 API-only runtime: no .env load, worker, model or source refresh."""
from pathlib import Path
import json
import uvicorn
import roll.app
from roll.research.company import features,feature_protocol
root=Path('D:/dsh-proj/Roll/.scratch/rv11-real01')
logs=root/'logs';logs.mkdir(exist_ok=True)
(logs/'module-paths.json').write_text(json.dumps(dict(app=roll.app.__file__,features=features.__file__,feature_protocol=feature_protocol.__file__)),encoding='utf-8')
app=roll.app.create_app(root,runtime_role='API')
uvicorn.run(app,host='127.0.0.1',port=8031)
