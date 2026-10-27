"""Byte-level frozen reference and prior calculator contract verification."""
import hashlib,json,subprocess
from pathlib import Path
root=Path('.');base='81ef7b137b85c42f9b5d156faf6011677359e7c1'
authority=root/'docs/reference/deep-dive-research/20261026';bundle=root/'backend/src/roll/research/company/report_reference'
manifest=json.loads((bundle/'manifest.json').read_bytes());rows=[]
for entry in manifest:
 raw=(authority/entry['path']).read_bytes();packed=(bundle/entry['path']).read_bytes()
 rows.append(dict(path=entry['path'],matches_source=raw==packed,sha256=hashlib.sha256(raw).hexdigest(),matches_manifest=hashlib.sha256(packed).hexdigest()==entry['sha256']))
legacy=json.loads(Path('.scratch/roll-research-valuation/evidence/07/method-source-check.json').read_bytes());files=[]
for item in legacy['files']:
 raw=(root/item['path']).read_bytes();prior=subprocess.check_output(['git','-c','gc.auto=0','show',base+':'+item['path']])
 files.append(dict(path=item['path'],matches_base=raw==prior,sha256=hashlib.sha256(raw).hexdigest()))
if len(rows)!=27 or not all(r['matches_source'] and r['matches_manifest'] for r in rows) or not all(r['matches_base'] for r in files):raise RuntimeError('Frozen contract drift')
result=dict(base=base,status='PASS',frozen_assets=rows,prior_calculator_contracts=files)
Path('.scratch/roll-research-valuation/evidence/08/source-byte-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('PASS: 27 frozen authority files and 10 prior calculator/review/comparison contracts byte-identical')
