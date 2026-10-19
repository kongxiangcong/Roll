"""Read-only acquisition and cardinality audit. No torch/model/network calls."""
import hashlib,json,math
from pathlib import Path

out=Path(__file__).resolve().parent;repo=out.parents[4]
def read(name):return json.loads((out/name).read_bytes())
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
freeze_names=['acquisition-freeze.json','contract-review-freeze.json','contract-js-freeze.json','sina-contract-freeze.json',
              'sina-canonical-freeze.json','sina-js-freeze.json','sina-routes-freeze.json','sina-history01-freeze.json','remaining-freeze.json']
for name in freeze_names:
    for filename,expected in read(name)['files'].items():assert digest(out/filename)==expected,(name,filename)
names=read('remaining-plan.json')['prior_receipts']+['remaining-receipt.json']
receipts=[read(name) for name in names]
assert len(names)==len(set(names))
calls=sum(len(r['requests']) for r in receipts);size=sum(r['bytes'] for r in receipts);elapsed=sum(r['transfer_seconds'] for r in receipts)
assert calls==32 and size==2723000 and elapsed<=120 and size<=16777216
hash_count=0;redirect_responses=[];raw_digests=set()
for name,receipt in zip(names,receipts):
    assert receipt['retries']==0 and receipt['redirects']==0
    for request in receipt['requests']:
        prefix='source/' if name=='acquisition-receipt.json' else 'source-remaining/' if name=='remaining-receipt.json' else ''
        assert digest(out/(prefix+request['file']))==request['sha256']
        raw_digests.add(request['sha256'])
        hash_count+=1
        if 300<=request['status_code']<400:redirect_responses.append({'receipt':name,'status':request['status_code']})
assert len(redirect_responses)==1 and redirect_responses[0]['status']==301
assert receipts[-1]['cumulative']['requests']==calls and receipts[-1]['cumulative']['bytes']==size
assert math.isclose(receipts[-1]['cumulative']['transfer_seconds'],elapsed,abs_tol=1e-8)
assert read('sina-history01.raw')['code']==0
assert len(read('sina-history01.raw')['data']['list'])==20
assert receipts[-1]['requests'][-1]['same_as_invalid50_page1'] is False
assert receipts[-1]['requests'][-1]['command']['form']['pageSize']=='30'
bad_ids={str(r['announcementId']) for r in read('source/06.raw')['announcements']}
good_ids={str(r['announcementId']) for r in read('source-remaining/32.raw')['announcements']}
assert len(good_ids)==30 and not bad_ids&good_ids
inventory=read('source-inventory.json');bounds=inventory['fixed_period_source_upper_bounds']
normalized=[r for name in ('corpus.json','sina-probe-corpus.json','remaining-corpus.json') for r in read(name)['items']]
assert len(normalized)==499 and all(r['raw_sha256'] in raw_digests for r in normalized)
candidates=read('unseen-candidates.json')['items']
assert len(candidates)==inventory['remaining_unique']==1539
assert sum(r['date'][:10]<='2022-12-31' for r in candidates)==243
assert sum('2023-01-01'<=r['date'][:10]<='2024-12-31' for r in candidates)==82
assert inventory['gold_labels']==0 and inventory['training_started'] is False
assert bounds['TRAIN']['raw_unique_candidates']==243<400
assert bounds['DEVELOPMENT']['raw_unique_candidates']==82<120
for name,expected in inventory['source_sha256'].items():assert digest(out.parent/name)==expected
production=repo/'backend/src/roll/market/sentiment-reference.json'
assert digest(production)=='29afd27bf5245cf73e6e524b45faa8db55f2abc37ef6990e9d71b517e2a6f40a'
assert not (out/'inference.json').exists()
assert not (out/'trained-model').exists()
assert digest(out/'object_contract.py')==digest(out.parent/'fresh-02/object_contract.py')
report={'status':'VERIFIED_DATA_GATE_FAILED_NO_TRAINING','source_requests':calls,'source_bytes':size,'transfer_seconds':elapsed,
        'raw_hashes_verified':hash_count,'all_prefreezes_unchanged':True,'retries':0,'automatic_redirects':0,
        'closed_301_response_preserved':redirect_responses,'new_canonical_endpoint_separately_budgeted':True,
        'cninfo_page30_real_distinct':True,'sina_actual_page_size':20,
        'raw_support_upper_bounds':{name:v['raw_unique_candidates'] for name,v in bounds.items()},
        'trained_gold_rows':0,'training_runs':0,'new_model_evaluations':0,'no_model_quality_claim':True,
        'production_reference_unchanged':True,'ticket_completion':'partial','next_source_plan_authorization':'PENDING'}
(out/'verification.json').write_bytes(json.dumps(report,ensure_ascii=False,indent=2).encode())
print(json.dumps(report,ensure_ascii=False,indent=2))
