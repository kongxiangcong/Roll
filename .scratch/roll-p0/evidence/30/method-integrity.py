"""Separate forensic METHOD clocks from public queries; never a real host."""
import json,sqlite3,sys
from pathlib import Path
from datetime import datetime
from fastapi.testclient import TestClient
from roll.app import create_app
directory=Path(sys.argv[1]);db=sqlite3.connect((directory/'roll.sqlite3').as_uri()+'?mode=ro',uri=True)
plans=[json.loads(r[0]) for r in db.execute('SELECT value FROM research_forward_plans')]
protocols=[json.loads(r[0]) for r in db.execute('SELECT value FROM research_protocols')]
samples=db.execute('SELECT protocol_id,checkpoint,trading_date,COUNT(*) FROM research_forward_samples GROUP BY protocol_id,checkpoint,trading_date').fetchall()
assert plans and all(p['namespace']=='METHOD_CASE' for p in plans)
assert all(p.get('forward_started_at') is None and p.get('forward_deadline') is None for p in protocols)
assert all(s[-1]==1 for s in samples);db.close()
out={'raw_registry':[{k:p.get(k) for k in ['protocol_id','forward_started_at','forward_deadline','forward_ended_at','capability']} for p in protocols],
     'unique_sql_identity':samples,'namespace':[p['namespace'] for p in plans],'public_models':[],'public_protocols':[]}
with TestClient(create_app(directory,review_clock=lambda:datetime.fromisoformat('2024-12-02T16:00:00+08:00'))) as client:
    for p in protocols:
        value=client.get('/api/research/protocols/'+p['protocol_id']).json()
        assert value['forward_started_at'] is None
        out['public_protocols'].append({k:value.get(k) for k in ['protocol_id','forward_started_at','forward_deadline','capability']})
    for p in plans:
        frozen=client.get('/api/research/complete-freezes/'+p['freeze_id']).json()
        model=client.get('/api/research/models/'+frozen['model_run_id']).json()
        assert model['evidence_kind']=='METHOD_CASE' and model.get('forward_started_at') is None and model['capability']=='NOT_GRANTED'
        out['public_models'].append({k:model.get(k) for k in ['model_run_id','evidence_kind','forward_started_at','system_usable','capability']})
Path(sys.argv[2]).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
