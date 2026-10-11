"""Byte-only protected source/original proof; never open runtime SQLite."""
from pathlib import Path
import hashlib, json, sys
root = Path('D:/dsh-proj/Roll')
tree = root / '.scratch/worktrees/ticket29'
out = tree / '.scratch/roll-p0/evidence/continuation-2026-10-11/ticket29'
paths = [r['path'] for r in json.loads((root / '.scratch/roll-p0/evidence/codex-review-repairs-2026-10-11/source-final.json').read_text())[:15]]
def proof(p):
    with p.open('rb') as stream: digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'bytes': p.stat().st_size, 'sha256': digest}
sources = [{'path': p, 'root': proof(root / p), 'tree': proof(tree / p)} for p in paths]
assert len(sources) == 15 and all(r['root'] == r['tree'] for r in sources)
original = proof(root / '.roll-data/reconstructed19-v1/roll.sqlite3')
assert original == {'bytes':165814272,'sha256':'ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4'}
result = {'sources': sources, 'original19_checksum_only': original, 'sqlite_opened': False}
before = out / 'protected-before.json'
if before.exists(): assert result == json.loads(before.read_text())
(out / sys.argv[1]).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print('15 protected root/tree sources + original19 checksum: PASS')

