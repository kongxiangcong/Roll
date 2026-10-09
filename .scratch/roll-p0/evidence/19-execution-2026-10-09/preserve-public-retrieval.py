"""Preserve required ignored retrieval originals from a managed implementation tree."""
from pathlib import Path
import hashlib
import json

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
CHILD=Path('C:/Users/72449/.codex/worktrees/ticket19-rights-treatment/Roll').resolve()
metadata=ROOT/'.scratch/roll-p0/evidence/19-rights-treatment-2026-10-09/ignored-preservation.json'
entries=json.loads(metadata.read_bytes())['files']
saved=[]
for entry in entries:
    source=Path(entry['path']).resolve()
    source.relative_to(CHILD)
    relative=Path(entry['relative_path'])
    if relative.is_absolute() or not relative.as_posix().startswith('.roll-data/'):
        raise ValueError('UNEXPECTED_PRESERVATION_SCOPE')
    target=(metadata.parent/relative).resolve()
    target.relative_to(metadata.parent.resolve())
    raw=source.read_bytes()
    if len(raw)!=entry['bytes'] or hashlib.sha256(raw).hexdigest()!=entry['sha256']:
        raise ValueError('SOURCE_CHANGED')
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists() and target.read_bytes()!=raw:
        raise ValueError('DESTINATION_ALREADY_DIFFERS')
    target.write_bytes(raw)
    if target.read_bytes()!=raw:
        raise ValueError('PRESERVATION_COPY_DIFFERS')
    saved.append({**entry,'preserved_path':str(target)})
report={'files':saved,'file_count':len(saved),'bytes':sum(e['bytes'] for e in saved),
        'hash_length_mismatches':0,'classification':'PUBLIC_RETRIEVAL_ORIGINALS_ONLY',
        'runtime_db_or_sealed_opened':False}
(OUT/'public-retrieval-preservation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:report[k] for k in ['file_count','bytes','hash_length_mismatches']}))
