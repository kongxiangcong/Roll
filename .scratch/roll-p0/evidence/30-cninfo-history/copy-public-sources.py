"""Only the eight pre-existing issuer query receipts and six named public raw indexes."""
import hashlib
import json
from pathlib import Path

repo=Path(__file__).resolve().parents[4]
root=Path('D:/dsh-proj/Roll')
metadata=repo/'.scratch/roll-p0/evidence/19-completion-2026-10-09/collections/rights-public--manifest.json'
original=json.loads(metadata.read_bytes())
target=repo/'backend/src/roll/market/reference/cninfo-history'
public=root/'.scratch/roll-p0/evidence/19-completion-2026-10-09/.roll-data/rights-public/raw'
queries=[];records={}
target.mkdir(parents=True,exist_ok=True)
for index,q in enumerate(original['collection']['queries']):
 assert q['request_form']['stock']=='600362,gssh0600362' and q['request_form']['seDate']=='2013-01-01~2025-12-31'
 name=q['sha256']+'.json'
 assert Path(q['path']).name==name
 raw=(public/name).read_bytes()
 assert len(raw)==q['bytes'] and hashlib.sha256(raw).hexdigest()==q['sha256']
 file=q['sha256']+'.raw';destination=target/file
 assert not destination.exists() or destination.read_bytes()==raw
 destination.write_bytes(raw)
 queries.append({k:q[k] for k in ['request_form','requested_at','url','sha256','bytes','http_status','received_at']}|
  {'query_id':'fixed-cninfo-'+str(index+1),'file':file})
 records[q['sha256']]={'source':str(public/name),'destination':str(destination),'sha256':q['sha256'],'bytes':q['bytes']}
manifest={'instrument':'SSE:600362','scope':'FINITE_KEYWORD_INDEX_CANDIDATES_NOT_COMPLETE_ACTION_COVERAGE',
 'original_compact_manifest_sha256':hashlib.sha256(metadata.read_bytes()).hexdigest(),
 'original_full_manifest_sha256':original['source_metadata_sha256'],'queries':queries}
(target/'sources.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
receipt={'files':len(records),'bytes':sum(r['bytes'] for r in records.values()),'queries':len(queries),
 'sha_or_length_mismatches':0,'network_calls':0,'records':list(records.values())}
Path(__file__).with_name('source-copy.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
cash=json.loads((repo/'backend/src/roll/research/reference/cash-rights/sources.json').read_bytes())['events']
rows=[row for q in queries for row in (json.loads((target/q['file']).read_bytes())['announcements'] or [])]
ids={r['announcementId'] for r in rows}
known={e['source']['url'].rsplit('/',1)[-1].split('.')[0] for e in cash}
print(json.dumps({k:receipt[k] for k in ['files','bytes','queries','sha_or_length_mismatches']}))
print(json.dumps({'candidate_rows':len(rows),'unique_ids':len(ids),'known_cash_index_matches':len(ids&known),
 'known_cash_unreturned_ids':sorted(known-ids),'last_candidate':next(r for r in rows if r['announcementId']=='1224816852')},ensure_ascii=False))
