"""Real64 source integrity and source-support audit; never imports a model."""
import hashlib,json,math
from pathlib import Path

out=Path(__file__).resolve().parent;repo=out.parents[4]
def read(name):return json.loads((out/name).read_bytes())
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
for name in ('acquisition-freeze.json','continuation-freeze.json','object-candidate-freeze.json'):
    for filename,expected in read(name)['files'].items():assert digest(out/filename)==expected,(name,filename)
plan=read('acquisition-plan.json');old=read('acquisition-receipt.json');new=read('continuation-receipt.json')
assert old['status']=='FAILED_CLOSED' and old['error_type']=='TypeError'
assert read('source/09.raw')=={'code':0,'message':'success','data':{'list':None,'total':0,'page':1,'size':20}}
assert new['status']=='CAPTURED_CLOSED'
requests=old['requests']+new['requests'];assert [r['number'] for r in requests]==list(range(1,65))
actual_rows=0
for request in requests:
    command=plan['commands'][request['number']-1];assert request['command']==command
    path=out/'source'/request['file'];assert digest(path)==request['sha256']
    assert path.stat().st_size==request['bytes'] and request['http_status']==200 and request['code']==0
    data=json.loads(path.read_bytes());rows=data['data']['list'] or []
    assert len(rows)<=20
    for row in rows:assert command['minimum_date']<=(row.get('dataTime') or row.get('time'))[:10]<=command['maximum_date']
    actual_rows+=len(rows)
assert actual_rows==835==len(read('corpus.json')['items'])+len(read('continuation-corpus.json')['items'])
total_bytes=old['bytes']+new['bytes'];total_seconds=old['transfer_seconds']+new['transfer_seconds']
assert total_bytes==952514<=33554432 and total_seconds<=240
assert old['retries']==new['retries']==old['automatic_redirects']==new['automatic_redirects']==0
assert new['cumulative']['requests']==64 and new['cumulative']['bytes']==total_bytes
assert math.isclose(new['cumulative']['transfer_seconds'],total_seconds,abs_tol=1e-8)
inventory=read('candidate-inventory.json');rows=read('candidate-rows.json')['items']
train=[r for r in rows if r['date'][:10]<='2022-12-31' and r['projection']['text']]
assert len(train)==376 and len({r['projection']['text'] for r in train})==348<400
negative=read('primary-negative-source-audit.json');eligible=[r for r in negative['rows'] if r['exclude_from_primary'] is None]
assert len(eligible)==negative['eligible_unique_inputs']==15<30
assert len({r['event_id'] for r in eligible})==negative['eligible_event_groups']==11
assert len({r['input_sha256'] for r in eligible})==len(eligible)
for filename,expected in inventory['source_sha256'].items():assert digest(out.parent/filename)==expected
assert digest(repo/'backend/src/roll/market/sentiment-reference.json')=='29afd27bf5245cf73e6e524b45faa8db55f2abc37ef6990e9d71b517e2a6f40a'
assert not (out/'training-result.json').exists() and not (out/'inference.json').exists()
compile((out/'train_candidate.py').read_bytes(),str(out/'train_candidate.py'),'exec')
report={'status':'VERIFIED_SOURCE_SUPPORT_INCOMPLETE_NO_TRAINING','source_requests':64,'source_bytes':total_bytes,'transfer_seconds':total_seconds,
        'real_returned_rows':actual_rows,'raw_hashes_verified':64,'first9_not_refetched':True,'network_retries':0,'automatic_redirects':0,
        'technical_null_fix_preserved':True,'training_unique_projected_inputs':348,'required_training_inputs':400,
        'reviewed_eligible_primary_negative_inputs':15,'required_primary_negative_inputs':30,'eligible_negative_events':11,
        'not_full_gold_dataset':True,'training_runs':0,'new_model_evaluations':0,'production_reference_unchanged':True,
        'candidate_object_implementation_changed_before_model':True,'object_policy_and_numeric_gates_unchanged':True,
        'additional20_source_plan':'PENDING_AUTHORIZATION'}
(out/'verification.json').write_bytes(json.dumps(report,ensure_ascii=False,indent=2).encode());print(json.dumps(report,ensure_ascii=False,indent=2))
