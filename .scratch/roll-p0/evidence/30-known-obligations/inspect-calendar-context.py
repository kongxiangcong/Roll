import json
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app
repo=Path(__file__).resolve().parents[4]
with TestClient(create_app(repo/'.scratch/t30o-calendar-schema')) as client:
 response=client.get('/api/market/calendar',params={'exchange':'SSE','date':'2026-10-12','at':'2026-10-12T15:06:00+08:00'})
 assert response.status_code==200,response.text
 Path(__file__).with_name('calendar-context.json').write_text(json.dumps(response.json(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
 print(json.dumps(response.json(),ensure_ascii=False))
