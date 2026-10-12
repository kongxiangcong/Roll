"""Own METHOD-only public protocol context inspection; no fit/SEALED/account IO."""
import json
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app
from test_post_close_packet import setup
repo=Path(__file__).resolve().parents[4]
with TestClient(create_app(repo/'.scratch/t30o-schema')) as client:
 plan=setup(client)
 result=client.post('/api/research/protocols',json={'basis':'METHOD context inspection, no fitting or freeze'})
 assert result.status_code==201,result.text
 protocol=result.json()
 value={'plan_id':plan,'protocol':protocol,'runtime_scope':'OWN_METHOD_ONLY_NO_FIT_OR_SEALED','network_calls':0}
 Path(__file__).with_name('protocol-context.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
 print(json.dumps(protocol,ensure_ascii=False))
