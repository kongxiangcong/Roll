"""Read-only copy of preserved 07 acquisition; no network or new market claims."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
from datetime import datetime,timezone
from fastapi.testclient import TestClient
from roll.app import create_app

parser=argparse.ArgumentParser()
parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--data',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
assert args.source.resolve()!=args.data.resolve()
before={p.relative_to(args.source).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in args.source.rglob('*') if p.is_file()}
shutil.copytree(args.source,args.data,dirs_exist_ok=True)
assert all(hashlib.sha256((args.data/name).read_bytes()).hexdigest()==sha for name,sha in before.items())
started=datetime.now(timezone.utc).isoformat()
with TestClient(create_app(args.data)) as client:
    basis=client.get('/api/account/valuation-basis').json()
    request={k:basis[k] for k in ['baseline_account_version','origin_at','as_of','scope_kind','scope_id']}
    response=client.post('/api/account/valuations',json=request)
    assert response.status_code==201,response.text
    value=response.json()
    quoted=[p for p in value['positions'] if p['quote']]
    assert quoted and all(p['quote']['evidence_kind']=='REAL_ACQUISITION' for p in quoted)
    assert any(p['quote']['upstream_at'].startswith('2026-09-30') for p in quoted)
    assert all(p['quote_status']=='STALE' for p in quoted)
    assert value['facts']['valuation_status'] in {'STALE','MISSING'}
    assert client.post('/api/account/valuations/'+value['valuation_id']+'/replay').json()==value
    result={'started_at':started,'finished_at':datetime.now(timezone.utc).isoformat(),'source':str(args.source.resolve()),
        'data_copy':str(args.data.resolve()),'copied_files':len(before),'source_hashes':before,
        'scope':'07 original real market acquisition with its synthetic acceptance account; not a user-owned wealth statement',
        'network_calls':0,'original_source_unchanged':True,'request':request,'valuation':value}
assert before=={p.relative_to(args.source).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in args.source.rglob('*') if p.is_file()}
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'copied_files':len(before),'quoted_positions':[(p['instrument'],p['price'],p['quote']['upstream_at']) for p in quoted],
    'cash_plus_holdings':value['cash_plus_holdings'],'net_assets':value['facts']['net_assets'],'status':value['facts']['valuation_status'],'network_calls':0}))
