"""Isolated09 API acceptance host; explicit directory avoids loading .env/auth."""
from pathlib import Path
import json
import uvicorn
import roll.app
from roll.research.company import report_deliveries, report_pdf

root=Path('D:/dsh-proj/Roll/.scratch/rv09-real01')
log=root/'logs';log.mkdir(exist_ok=True)
(log/'module-paths.json').write_text(json.dumps(dict(app=roll.app.__file__,deliveries=report_deliveries.__file__,pdf=report_pdf.__file__)),encoding='utf-8')
app=roll.app.create_app(root,runtime_role='API')
uvicorn.run(app,host='127.0.0.1',port=8029)
