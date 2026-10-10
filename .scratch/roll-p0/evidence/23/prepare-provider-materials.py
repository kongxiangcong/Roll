"""Local preparation only. No provider task, subprocess worker or external transmission."""
import hashlib
import json
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app
from roll.accounts.ledger import encode
from roll.agents.review_runtime import command
from roll.agents.codex_evidence import MODEL as CODEX_MODEL
from roll.agents.deepseek_evidence import MODEL as DEEPSEEK_MODEL

ROOT=Path(__file__).resolve().parents[4]
OUT=ROOT/'.scratch/roll-p0/evidence/23'
PACKET=OUT/'provider-materials'
PACKET.mkdir(exist_ok=True)
with TestClient(create_app(Path('D:/dsh-proj/Roll/.roll-data/implementation-evidence/23/actual-current-copy'))) as client:
    response=client.post('/api/research/validations/baf981b6-b2bf-4f6f-b46f-1726f261de8e/review-materials',json={})
    response.raise_for_status();material=response.json()
    (OUT/'actual-material.json').write_text(json.dumps(material,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    files=[]
    for item in material['inventory']:
        raw=client.get('/api/data/archives/'+item['sha256']);raw.raise_for_status()
        payload={'material_id':item['material_id'],'sha256':item['sha256'],'content':raw.content.decode()}
        content=encode(payload).encode();path=PACKET/(item['material_id']+'.json');path.write_bytes(content)
        files.append({'material_id':item['material_id'],'material_sha256':item['sha256'],'content_bytes':item['bytes'],
            'tool_response_bytes':len(content),'tool_response_sha256':hashlib.sha256(content).hexdigest(),'path':str(path)})
    for backend,model in [('CODEX',CODEX_MODEL),('DEEPSEEK',DEEPSEEK_MODEL)]:
        content=encode(command({'model':model},material)).encode();path=PACKET/(backend.lower()+'-command.json');path.write_bytes(content)
        files.append({'backend':backend,'kind':'INITIAL_COMMAND_WITH_PROMPT_AND_TOOL_SCHEMAS','bytes':len(content),'sha256':hashlib.sha256(content).hexdigest(),'path':str(path)})
    replay=client.post('/api/research/validations/baf981b6-b2bf-4f6f-b46f-1726f261de8e/replay',json={});replay.raise_for_status();proof=replay.json()
    content=encode({'check_id':'validation-reproduction','result_sha256':proof['result_fingerprint'],'matches_original':proof['matches_original'],'network_calls':0}).encode()
    (PACKET/'reproduction.json').write_bytes(content)
    report={'material_id':material['material_id'],'material_fingerprint':material['material_fingerprint'],'validation_id':material['basis_id'],
        'inventory_content_bytes':sum(i['content_bytes'] for i in files if 'content_bytes' in i),
        'maximum_tool_payload_bytes':sum(i['tool_response_bytes'] for i in files if 'tool_response_bytes' in i)+len(content),
        'files':files,'source_files':['backend/src/roll/research/'+name+'.py' for name in ['models','execution','shadow','statistics','validation']],
        'destinations':[{'backend':'CODEX','model':CODEX_MODEL,'service':'OpenAI Codex runtime using already configured ChatGPT auth; runtime selects OpenAI endpoint, not a custom host URL'},
            {'backend':'DEEPSEEK','model':DEEPSEEK_MODEL,'endpoint':'https://api.deepseek.com/responses'}],
        'external_transmissions':0,'credential_values_in_packet':False,'personal_account_in_packet':False,'sealed_content_in_packet':False,
        'scope':['Frozen experiment protocol/objectives/scope/costs/windows/method/stopping/fingerprints','Complete research and validation attempt metadata','Gate statuses, reasons, G5 component summaries, incompleteness and limitations','Five current frozen relevant Python source files','Host deterministic reproduction ID/result SHA/match and zero network count'],
        'excluded':['Actual account baseline amounts and holdings','Funding authorization and account identity','Full model input/raw archives','Protected SEALED content','Credentials or personal config','Whole database or unrelated registered evidence']}
    (OUT/'provider-material-manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['material_id','material_fingerprint','inventory_content_bytes','maximum_tool_payload_bytes','external_transmissions']},ensure_ascii=False),flush=True)
