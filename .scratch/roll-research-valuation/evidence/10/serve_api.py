"""Current10 API-only host with an explicit cloned directory; no .env/model worker."""
from pathlib import Path
import json
import uvicorn
import roll.app
from roll.research.company import reports,report_deliveries
root=Path('D:/dsh-proj/Roll/.scratch/rv10-real01')
logs=root/'logs';logs.mkdir(exist_ok=True)
(logs/'module-paths.json').write_text(json.dumps(dict(app=roll.app.__file__,reports=reports.__file__,deliveries=report_deliveries.__file__)),encoding='utf-8')
app=roll.app.create_app(root,runtime_role='API')
uvicorn.run(app,host='127.0.0.1',port=8030)
