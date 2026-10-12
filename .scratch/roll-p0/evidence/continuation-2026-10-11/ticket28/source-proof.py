"""Source/test identity only; private runtime files are not inspected."""
from pathlib import Path
import hashlib, json, sys
tree = Path(__file__).resolve().parents[5]
out = Path(__file__).parent
paths = sorted({*tree.glob('backend/src/roll/**/*.py'), *tree.glob('frontend/src/**/*.ts'), *tree.glob('frontend/src/**/*.tsx'),
    tree/'backend/tests/application/test_notifications.py', tree/'backend/tests/recovery/test_notification_process.py',
    tree/'frontend/tests/e2e/notifications.spec.ts'})
result = [{'path':p.relative_to(tree).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]
before = out/(sys.argv[2] if len(sys.argv)>2 else 'source-before-final.json')
if before.exists(): assert json.loads(before.read_text()) == result, 'Final source/test changed'
(out/sys.argv[1]).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(f'{len(result)} source/test files byte identity PASS')
