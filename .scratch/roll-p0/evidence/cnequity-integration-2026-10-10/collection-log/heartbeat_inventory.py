"""Metadata/hash inventory for a collection heartbeat; no archive/SEALED consumption."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[5]
db = sqlite3.connect(f'file:{(ROOT/".roll-data/pit/roll.sqlite3").as_posix()}?mode=ro', uri=True)
names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
protected = {}
for name in names:
    if any(part in name for part in ['account', 'research_', 'model', 'attempt', 'forecast', 'funding', 'decision', 'capability', 'execution', 'risk_policy']):
        rows = list(db.execute('SELECT * FROM "'+name.replace('"', '""')+'" ORDER BY rowid'))
        body = json.dumps(rows, ensure_ascii=False, separators=(',', ':'), default=str).encode()
        protected[name] = {'rows': len(rows), 'sha256': hashlib.sha256(body).hexdigest()}
result = {'protected': protected,
          'facts': db.execute('SELECT COUNT(*) FROM pit_fact_versions').fetchone()[0],
          'batches': db.execute('SELECT COUNT(*) FROM pit_collection_batches').fetchone()[0],
          'sources': [{'id': r[0], **json.loads(r[1])} for r in db.execute('SELECT id,value FROM collection_source_health')],
          'policies': [json.loads(r[0]) for r in db.execute('SELECT value FROM collection_source_policies')],
          'runtime_manifest_sha256': hashlib.sha256((ROOT/'.roll-data/cnequity-runtime/runtime.json').read_bytes()).hexdigest()}
db.close()
Path(sys.argv[1]).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
