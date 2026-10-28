"""Public backup clone for actual read-only feature validation; no model/auth."""
import json
from pathlib import Path
from roll.runtime.backups import Backups,restore_at_start

root=Path('D:/dsh-proj/Roll/.scratch')
target=root/'rv11-real01'
if target.exists():raise RuntimeError('Never overwrite an acceptance store')
source=Backups(root/'rv10-real01')
saved=source.create();bundle=source.export(saved['backup_id'])
restored=Backups(target);restored.stage_restore(bundle);restore_at_start(restored)
receipt=dict(source='rv10-real01',target=str(target),backup_id=saved['backup_id'],bundle_bytes=len(bundle),model_calls=0,source_network_calls=0,auth_read=False)
Path(__file__).with_name('real-store.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt))
