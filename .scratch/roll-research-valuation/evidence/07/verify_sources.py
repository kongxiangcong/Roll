"""Ensure prior valuation/comparison implementation bytes remain frozen."""
import subprocess,json,hashlib
from pathlib import Path
base='1e493f043a8a042b29a5d170272c953c6afc848e'
paths=['calculator.py','valuation.py','economics.py','changes.py','change_calculator.py',
 'valuation_reference/fundamental_valuation.py','valuation_reference/original_fundamental_valuation.py',
 'valuation_reference/LICENSE','valuation_reference/equity-research-LICENSE.txt','valuation_reference/THIRD_PARTY_NOTICES.md']
rows=[]
for name in paths:
 path='backend/src/roll/research/company/'+name
 frozen=subprocess.run(['git','-c','gc.auto=0','show',base+':'+path],check=True,capture_output=True).stdout
 current=Path(path).read_bytes()
 rows.append(dict(path=path,matches_base=current==frozen,sha256=hashlib.sha256(current).hexdigest()))
assert all(row['matches_base'] for row in rows)
result=dict(base=base,status='PASS',files_checked=len(rows),files=rows)
Path(__file__).with_name('method-source-check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
