"""Copy exactly the two newly captured public responses, never any saved DB."""
import hashlib
import json
from pathlib import Path
folder=Path(__file__).resolve().parent
repo=folder.parents[3]
source=folder/'runtime/source-assessment'
receipt=json.loads((source/'receipt.json').read_bytes())
expected={'dividend':('20243b376bad269c47fffb63cd38034caa0c619eadaf85e9532741ec9a0aa91e',5548),
          'send_share':('b498844359a5f0bd6b2dbddaa1b02b1a9d55e04f708cdb93b14cfb776d553f52',496)}
target=repo/'backend/src/roll/market/reference/sse-company-action-contract'
sources=[]
for role,(sha,size) in expected.items():
    archived=receipt['responses'][role]['archive']
    body=(source/(sha+'.raw')).read_bytes()
    assert archived['sha256']==sha and archived['bytes']==size and len(body)==size and hashlib.sha256(body).hexdigest()==sha
    output=target/(sha+'.raw');assert not output.exists();output.write_bytes(body)
    sources.append({'role':role,'sha256':sha,'bytes':size,'path':sha+'.raw',
        'url':archived['source_url'],'received_at':archived['received_at'],'status_code':archived['status_code'],
        'classification':'REAL_SOURCE_ASSESSMENT_FINITE_FIRST_PAGE_NOT_FULL_COVERAGE',
        'publication_time':None,'effective_time':None})
mapping={'sources':sources,'actual_receipt_id':receipt['receipt_id'],
    'collector_fingerprint':receipt['implementation_fingerprint'],
    'complete_action_coverage':False,'pending_older_obligations_complete':False}
(target/'observed-sources.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({'copied_public_raws':2,'bytes':6044,'sha_length_mismatches':0,'sqlite_opened':False}))
