"""Copy only six manifest-named public SSE originals, verify original bytes."""
import hashlib
import json
from pathlib import Path

repo=Path(__file__).resolve().parents[4]
root=Path('D:/dsh-proj/Roll')
metadata=repo/'.scratch/roll-p0/evidence/19-completion-2026-10-09/collections/pit-status-public--manifest.json'
public=root/'.scratch/roll-p0/evidence/19-completion-2026-10-09/.roll-data/pit-status-public'
target=repo/'backend/src/roll/market/reference/sse-history'
roles={
 'daily':'a51334316a941c30047614138f201d3dd3d988a453fa754b8673ae1fd74bb113',
 'daily_units':'478fb2a72fc5a3725088adb208756e88171f79628956a9f5ca67c900d37def2f',
 'daily_empty':'87c53c172a0a97189c5f1860a4bb8640699a4f194918a5be408f5ef742c61328',
 'suspension':'2511be0a1a618edfd7576563bdbffcc35c697b9e5ebeb9edc81ff9efa2aa01a8',
 'suspension_query_js':'32fc98ea41e599f457609247ba68defb82e6d855aa2551da6923dbf7e44153a7',
 'suspension_inconsistent':'15a1180483592fa133cc4da6907ad84428fe0bb56ffd672241c456d14a715066'}
original=json.loads(metadata.read_bytes())
sources=[]
target.mkdir(parents=True,exist_ok=True)
for role,sha in roles.items():
 record=next(r for r in original['collection']['requests'] if r['sha256']==sha)
 raw=(public/record['path']).read_bytes()
 assert len(raw)==record['bytes'] and hashlib.sha256(raw).hexdigest()==sha
 destination=target/record['path']
 assert not destination.exists() or destination.read_bytes()==raw
 destination.write_bytes(raw)
 sources.append({**record,'role':role})
manifest={'instrument':'SSE:600362','scope':'FINITE_REAL_ARCHIVED_SOURCE_ASSESSMENT_NOT_CURRENT_OR_HISTORICAL_PIT_COVERAGE',
 'original_compact_manifest_sha256':hashlib.sha256(metadata.read_bytes()).hexdigest(),
 'original_full_manifest_sha256':original['source_metadata_sha256'],'sources':sources}
(target/'sources.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
receipt={'files':len(sources),'bytes':sum(s['bytes'] for s in sources),'sha_or_length_mismatches':0,
 'source_root':str(public),'destination':str(target),'sources':sources,'network_calls':0}
Path(__file__).with_name('source-copy.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({k:receipt[k] for k in ['files','bytes','sha_or_length_mismatches','network_calls']}))
