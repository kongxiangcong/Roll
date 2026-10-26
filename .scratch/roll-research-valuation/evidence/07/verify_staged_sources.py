"""Check the exact indexed source bytes against the tested working files."""
import subprocess,hashlib,json
from pathlib import Path
paths=subprocess.run(['git','-c','gc.auto=0','diff','--cached','--name-only','--diff-filter=ACM'],check=True,capture_output=True,text=True).stdout.splitlines()
rows=[]
for path in paths:
    if Path(path).suffix not in {'.py','.tsx','.ts','.css','.mjs'}:
        continue
    staged=subprocess.run(['git','-c','gc.auto=0','show',':'+path],check=True,capture_output=True).stdout
    working=Path(path).read_bytes()
    rows.append(dict(path=path,matches_working=staged==working,sha256=hashlib.sha256(working).hexdigest()))
result=dict(status='PASS' if all(row['matches_working'] for row in rows) else 'FAIL',files_checked=len(rows),files=rows)
Path(__file__).with_name('staged-source-check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
assert result['status']=='PASS'
