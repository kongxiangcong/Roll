"""Verify this run's explicit public files, never runtime datasets or SEALED."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime, timezone
import json
import subprocess

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
base = '1bf2260bc99f41916fdfdd772af8f64fbbf1be8e'
checks = []
for relative in ['.scratch/roll-p0/evidence/19-execution-2026-10-09/.roll-data',
                 '.scratch/roll-p0/evidence/19-rights-treatment-2026-10-09/.roll-data',
                 'backend/src/roll/research/reference/cash-rights']:
    for path in sorted((ROOT / relative).rglob('*')):
        if path.is_file():
            raw = path.read_bytes()
            checks.append({'path': path.relative_to(ROOT).as_posix(),
                           'sha256': sha256(raw).hexdigest(), 'bytes': len(raw)})
preserved = json.loads((OUT/'public-retrieval-preservation.json').read_bytes())
for item in preserved['files']:
    raw = Path(item['preserved_path']).read_bytes()
    assert sha256(raw).hexdigest() == item['sha256'] and len(raw) == item['bytes']
model = ROOT/'backend/src/roll/research/models.py'
original = subprocess.check_output(['git', 'show', base+':backend/src/roll/research/models.py'],cwd=ROOT)
assert model.read_bytes() == original
changed = subprocess.check_output(['git','diff','--name-only',base],cwd=ROOT,text=True).splitlines()
allowed_exact = {'.gitattributes', 'docs/transparent-model-contract.md',
                 '.scratch/roll-p0/execution-status.md', '.scratch/roll-p0/issues/19-transparent-model.md',
                 'backend/src/roll/app.py', 'backend/src/roll/research/registry.py',
                 'backend/src/roll/research/training_preflight.py',
                 'backend/src/roll/research/corporate_actions.py',
                 'backend/tests/application/test_cash_rights.py',
                 'backend/tests/application/test_research_acquisition_import.py',
                 'backend/tests/application/test_training_preflight.py',
                 'backend/tests/application/test_transparent_models.py',
                 'backend/tests/application/test_research_protocol.py'}
allowed_prefixes = ['.scratch/roll-p0/evidence/19-execution-2026-10-09/',
                    '.scratch/roll-p0/evidence/19-real-path-2026-10-09/',
                    '.scratch/roll-p0/evidence/19-rights-treatment-2026-10-09/',
                    'backend/src/roll/research/reference/cash-rights/']
unexpected = [path for path in changed if path not in allowed_exact and not any(path.startswith(p) for p in allowed_prefixes)]
# Issue filename is repository-owned; identify the one ticket 19 path explicitly.
unexpected = [p for p in unexpected if not (p.startswith('.scratch/roll-p0/issues/19-') and p.endswith('.md'))]
assert not unexpected, unexpected
report = {'checked_at':datetime.now(timezone.utc).isoformat(), 'base':base,
          'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
          'scope':'EXPLICIT_PUBLIC_RETRIEVAL_AND_SOURCE_REFERENCE_FILES_ONLY',
          'files':checks, 'file_count':len(checks), 'bytes':sum(c['bytes'] for c in checks),
          'models_byte_identical_to_base':True, 'models_sha256':sha256(original).hexdigest(),
          'preserved_retrieval_files_verified':len(preserved['files']), 'preserved_retrieval_mismatches':0,
          'tracked_changes':changed, 'unexpected_tracked_changes':unexpected,
          'runtime_data_or_sealed_opened':False,
          'retrieval_preservation_receipt_sha256':sha256((OUT/'public-retrieval-preservation.json').read_bytes()).hexdigest()}
(OUT/'final-public-integrity.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:report[k] for k in ['file_count','bytes','models_byte_identical_to_base','unexpected_tracked_changes','runtime_data_or_sealed_opened']}))
