from pathlib import Path
import json,hashlib,concurrent.futures,subprocess,math
from roll.decisions.capabilities import source_inventory
root=Path('D:/dsh-proj/Roll')
source=Path.cwd().resolve()
out=root/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket25-independent'
ev=source/'.scratch/roll-p0/evidence/ticket25'
manifest=json.loads((ev/'runtime-preservation-handoff.json').read_text(encoding='utf-8'))
guard=json.loads((ev/'source-guard-handoff.json').read_text(encoding='utf-8'))
benchmark=json.loads((ev/'benchmark-results.json').read_text(encoding='utf-8'))
def check(path,sha,size):
    p=Path(path)
    with p.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
    actual_size=p.stat().st_size
    assert actual==sha and actual_size==size,str(p)
    return {'path':str(p),'sha256':actual,'bytes':actual_size,'matches':True}
assert len(manifest['files'])==manifest['file_count']==1934
jobs=[]
for item in manifest['files']:
    s,d=Path(item['source']).resolve(),Path(item['destination']).resolve()
    assert s.is_relative_to(source/'.scratch') and d.is_relative_to(root/'.roll-data/implementation-evidence/ticket25')
    assert not any(word in s.name.lower() for word in ['auth.json','.env','credential','token'])
    jobs.extend([(s,item['sha256'],item['bytes']),(d,item['sha256'],item['bytes'])])
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    hashes=list(pool.map(lambda row:check(*row),jobs))
protected=json.loads((root/'.scratch/roll-p0/evidence/codex-review-repairs-2026-10-11/source-final.json').read_text(encoding='utf-8'))[:15]
source_checks=[]
for item in protected:
    for repo in [source,root]:source_checks.append(check(repo/item['path'],item['sha256'],item['bytes']))
original=guard['original_database']
db_checksum=check(root/original['path'],original['sha256'],original['bytes'])
artifacts=[check(item['path'],item['sha256'],item['bytes']) for item in guard['allowed_model_artifacts_unchanged']]
frontend=[check(source/item['path'],item['sha256'],item['bytes']) for item in guard['frontend']]
assert source_inventory()==guard['application_sources']==benchmark['application_sources']
durations=benchmark['samples_seconds']
assert len(durations)==len(benchmark['numeric_layer_seconds'])==len(benchmark['application_layer_seconds'])==21
p95=sorted(durations)[math.ceil(21*.95)-1]
assert abs(p95-benchmark['nearest_rank_p95_seconds'])<1e-10
assert all(abs(total-numeric-application)<1e-7 for total,numeric,application in zip(durations,benchmark['numeric_layer_seconds'],benchmark['application_layer_seconds']))
assert len(benchmark['stocks'])==30 and len(benchmark['indices'])==5
assert benchmark['external_acquisition_seconds']==benchmark['network_calls']==0 and benchmark['distinct_evaluation_ids']==1
result={'source_oid':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'archive_manifest':str(ev/'runtime-preservation-handoff.json'),'archive_files':1934,'source_and_destination_checks':len(hashes),'mismatches':0,'archive_bytes':sum(i['bytes'] for i in manifest['files']),'archive_hashes':hashes,'protected_15_in_source_and_root':source_checks,'original19_checksum_only':db_checksum,'allowed_model_artifacts':artifacts,'frontend_same_as_archived_ui':frontend,'benchmark_receipt_review':{'samples':21,'nearest_rank_p95_seconds':p95,'stage_sum_consistent':True,'scope_stocks':30,'scope_indices':5,'eligible_actual_candidate_scope':benchmark['admitted_scope'],'application_sources_match_final_source':True,'math_is_rerun_and_writer_checked_before_prior':'Reviewed benchmark.py loop and Actions.evaluate; no early prior cache lookup. 1 in-scope existing holding path;29 refused out-of-scope; no30qualified claim.'}}
(out/'integrity.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k in ['source_oid','archive_files','source_and_destination_checks','mismatches','archive_bytes','benchmark_receipt_review']}))
