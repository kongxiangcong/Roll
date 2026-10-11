"""Compare this exact new six-file public bundle with staged Git blob bytes."""
import hashlib
import json
import subprocess
from pathlib import Path

repo=Path(__file__).resolve().parents[4]
base=Path('backend/src/roll/market/reference/cninfo-history')
manifest=json.loads((repo/base/'sources.json').read_bytes())
records=[]
for source in {s['sha256']:s for s in manifest['queries']}.values():
    path=base/source['file']
    blob=subprocess.run(['git','show',':'+path.as_posix()],cwd=repo,check=True,capture_output=True).stdout
    actual={'sha256':hashlib.sha256(blob).hexdigest(),'bytes':len(blob)}
    assert actual=={'sha256':source['sha256'],'bytes':source['bytes']}
    assert blob==(repo/path).read_bytes()
    records.append({'path':path.as_posix(),**actual})
path=base/'sources.json'
assert subprocess.run(['git','show',':'+path.as_posix()],cwd=repo,check=True,capture_output=True).stdout==(repo/path).read_bytes()
value={'originals':records,'files':len(records),'bytes':sum(r['bytes'] for r in records),
    'sha_or_length_mismatches':0,'manifest_blob_equals_worktree':True,'original19_sqlite_read':False}
Path(__file__).with_name('staged-originals.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
print('CNINFO_STAGED6_ORIGINAL_BYTES_PASS')
