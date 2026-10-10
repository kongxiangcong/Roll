"""Copy this closed METHOD profile and prove every retained byte; no deletion."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

source, destination, receipt = (Path(value).resolve() for value in sys.argv[1:])
assert source.is_dir(), 'The exact completed runtime directory must exist'
allowed = {'review-fixes-old-method': 'old-method',
           'test_continuous_joint_budget_r0': 'new-method',
           'test_natural_month_deadline_ke0': 'new-forward-endpoint',
           'test_mature_settlement_only_sc0': 'failed-forward'}
assert source.name in allowed
assert destination == Path('D:/dsh-proj/Roll/.roll-data/implementation-evidence/continuation-review-fixes/' + allowed[source.name]).resolve()
assert not destination.exists(), 'Never replace a retained runtime'
destination.mkdir(parents=True)
files = []
for original in sorted(source.rglob('*')):
    if not original.is_file():
        continue
    assert original.name != '.env', 'No credentials belong to this METHOD runtime'
    relative = original.relative_to(source)
    retained = destination / relative
    retained.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(original, retained)
    content, copied = original.read_bytes(), retained.read_bytes()
    assert content == copied
    files.append({'path': relative.as_posix(), 'bytes': len(content),
                  'sha256': hashlib.sha256(content).hexdigest()})
assert files, 'An empty runtime is not preservation evidence'
result = {'source': str(source), 'destination': str(destination), 'files': files,
          'file_count': len(files), 'bytes': sum(item['bytes'] for item in files),
          'sha256_and_length_mismatches': 0, 'evidence_kind': 'METHOD_CASE'}
receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({key: value for key, value in result.items() if key != 'files'}))
