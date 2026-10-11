"""Extract one own METHOD API audit from its raw archive, without SQLite-open."""
import hashlib
import json
from pathlib import Path

repo=Path(__file__).resolve().parents[4]
owned=repo/'.scratch/t30o-final/test_known_notice_audit_binds_0/raw'
found=[]
for path in owned.glob('*.raw'):
 body=path.read_bytes()
 try:value=json.loads(body)
 except (ValueError,UnicodeDecodeError):continue
 if isinstance(value,dict) and value.get('audit_id') and value.get('known_notice_count')==14:
  assert path.stem==hashlib.sha256(body).hexdigest()
  found.append((path,value))
assert len(found)==1
path,audit=found[0]
proof={'scope':'OWN_METHOD_FINAL_TEST_ARCHIVE_ONLY_NO_SQLITE_OPEN',
 'raw_audit_path':str(path),'raw_audit_hash':path.stem,'bytes':path.stat().st_size,
 'protocol_context':audit['protocol_context'],'protocol_effective_window':audit['protocol_effective_window'],
 'knowledge_cutoff':audit['knowledge_cutoff'],'normalized_known_at':audit['normalized_known_at'],
 'notices':audit['notices'],'gaps':audit['gaps'],'known_notice_count':audit['known_notice_count'],
 'resolution_unknown_count':audit['resolution_unknown_count'],
 'pending_older_obligations_complete':audit['pending_older_obligations_complete'],
 'complete_action_coverage':audit['complete_action_coverage'],
 'evidence_kind':audit['evidence_kind'],'network_calls':audit['network_calls']}
assert audit['resolution_unknown_count']==14 and audit['evidence_kind']=='METHOD_CASE'
Path(__file__).with_name('known-notices-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',
 encoding='utf-8',newline='\n')
print('ONE_OWN_API_AUDIT_14_SOURCE_BOUND_SCHEDULES_RESOLUTION_UNKNOWN_NO_DB_OPEN')
