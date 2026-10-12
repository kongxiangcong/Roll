from pathlib import Path
import hashlib,json,shutil,os
from fastapi.testclient import TestClient
from roll.app import create_app
source=Path.cwd().resolve();root=Path('D:/dsh-proj/Roll')
out=root/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket25-independent'
manifest=json.loads((source/'.scratch/roll-p0/evidence/ticket25/runtime-preservation-handoff.json').read_text(encoding='utf-8'))
archive=root/'.roll-data/implementation-evidence/ticket25'
marker='test_qualified_host_packet_all0'
selected=[item for item in manifest['files'] if marker in Path(item['destination']).parts and 'api-handoff' in Path(item['destination']).parts]
assert selected,'Qualified archived profile missing'
case=Path(selected[0]['destination'])
while case.name!=marker:case=case.parent
copy=root/'.roll-data/r25copy';assert not copy.exists()
files=[]
for item in selected:
    src=Path(item['destination']);dest=copy/src.relative_to(case)
    assert src.resolve().is_relative_to(archive.resolve()) and dest.resolve().is_relative_to(copy.resolve())
    assert src.name!='auth.json'
    dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
    with dest.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
    assert sha==item['sha256'] and dest.stat().st_size==item['bytes']
    files.append({'source':str(src),'copy':str(dest),'sha256':sha,'bytes':item['bytes']})
os.environ['ROLL_ENV']='test'
method=copy/'qualification.json';assert method.is_file()
with TestClient(create_app(copy/'data',capability_method_file=method)) as client:
    current=client.get('/api/actions/current').json()
    original=current['evaluation'];assert original and len(original['decisions'])==1
    assert original['namespace']=='METHOD_ENGINEERING' and original['system_usable'] is False
    assert original['decisions'][0]['quantity']=='200'
    identifier=original['evaluation_id']
    account=client.get('/api/account').json()
    replay=client.post('/api/actions/evaluations/'+identifier+'/replay')
    assert replay.status_code==200,replay.text
    assert replay.json()['matches_original'] and replay.json()['network_calls']==0
    assert client.get('/api/actions/evaluations/'+identifier).json()==original
    assert client.get('/api/account').json()==account
with TestClient(create_app(copy/'data',capability_method_file=method)) as client:
    assert client.get('/api/actions/evaluations/'+identifier).json()==original
    assert client.post('/api/actions/evaluations/'+identifier+'/replay').json()['matches_original']
result={'status':'PASS','archived_root_database_opened':False,'owned_copy':str(copy),'copied_verified_files':len(files),'copies':files,'evaluation_id':identifier,'namespace':'METHOD_ENGINEERING','system_usable':False,'two_owned_lifecycles_replay_matches':True,'network_calls':0,'account_unchanged':True}
(out/'archive-copy-replay.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='copies'}))
