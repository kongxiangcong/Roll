"""Stable public records before/after a real API process restart."""
import hashlib
import json
import sys
from pathlib import Path
import httpx
out=Path(__file__).parent
paths=['/api/company-research/snapshots/7a430e8b-4172-4598-af21-6fe8600b6b93',
 '/api/company-research/snapshots/6b94c24a-f27a-4e5b-a6f9-57358d8242a6',
 '/api/company-research/reports/b9cfb2a0-8f93-516a-a4cd-7b7801fd7911',
 '/api/company-research/reports/8625ead2-a42c-5496-95dd-eec52dd17f5a',
 '/api/company-research/jobs/3bbfac4c-1e78-413a-86d0-950aeb72337f',
 '/api/company-research/report-deliveries/e3e6e93c-0a17-4bfc-92af-82b86aa86487','/api/account']
with httpx.Client(base_url='http://127.0.0.1:8032',trust_env=False,timeout=90) as c:
    values={}
    for path in paths:
        r=c.get(path);r.raise_for_status();values[path]=r.json()
    raw=c.get('/api/company-research/materials/196c4aba-1620-496a-bc8b-dfddcca95d13/original');raw.raise_for_status()
    values['new_original_sha256']=hashlib.sha256(raw.content).hexdigest()
if sys.argv[1]=='before':
    (out/'restart-before.json').write_text(json.dumps(values,ensure_ascii=False,indent=2),encoding='utf-8')
else:
    before=json.loads((out/'restart-before.json').read_text(encoding='utf-8'))
    assert before==values
    receipt=dict(stable_public_records=len(paths),all_equal=True,new_original_sha256=values['new_original_sha256'],
                 actual_process_restart=True,model_calls=0,source_network_calls=0,auth_read=False)
    (out/'restart-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(dict(mode=sys.argv[1],records=len(paths),success=True)))
