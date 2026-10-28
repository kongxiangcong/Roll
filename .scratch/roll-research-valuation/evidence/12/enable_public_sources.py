"""Enable only two existing public JCC source policies in the isolated daily copy."""
import json
import subprocess
from datetime import datetime,timezone
from pathlib import Path
import httpx
out=Path(__file__).parent
runtime={}
for package in ['akshare','trafilatura']:
    executable=Path('D:/dsh-proj/Roll/.scratch/rce-runtime')/package/'Scripts/python.exe'
    code="import importlib.metadata as m,importlib.util as u,json,sys;print(json.dumps(dict(python=sys.executable,version=m.version('"+package+"'),module_path=u.find_spec('"+package+"').origin)))"
    runtime[package]=json.loads(subprocess.check_output([str(executable),'-c',code],text=True))
assert runtime['akshare']['version']=='1.19.1'
with httpx.Client(base_url='http://127.0.0.1:8033',trust_env=False,timeout=90) as c:
    response=c.get('/api/research/collection-sources');response.raise_for_status();sources=response.json()
    selected={s['id']:s for s in sources if s['id'] in ['akshare-news-em','akshare-financial-em']}
    after={}
    for key,old in selected.items():
        assert old['scope']==['SSE:600362'] and old['max_calls']==8 and old['timeout_seconds']==18 and old['retries']==0
        response=c.post('/api/research/collection-sources/'+key+'/policy',json=dict(enabled=True,expected_revision=old['revision'],
            basis='Actual12 isolated existing public JCC-only source collection; unchanged8calls/18s/0retry/cooldown; no model auth, no qualification uplift'))
        response.raise_for_status();after[key]=response.json()
        assert after[key]['enabled'] and after[key]['scope']==old['scope']
        for field in ['max_calls','timeout_seconds','retries','max_bytes','cooldown_seconds','failure_threshold']:
            assert after[key][field]==old[field]
receipt=dict(at=datetime.now(timezone.utc).isoformat(),store='rv12-daily01',before=selected,after=after,runtime=runtime,
    source_network_calls=0,model_calls=0,auth_read=False,scope_expanded=False,collection_completed=False)
(out/'public-source-enablement.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(after={k:dict(enabled=v['enabled'],revision=v['revision'],scope=v['scope']) for k,v in after.items()},
    runtime=runtime,collection_completed=False),ensure_ascii=False))
