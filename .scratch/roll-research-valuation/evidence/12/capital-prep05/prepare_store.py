"""Public backup clone for local source-only capital preparation. No auth/model."""
import json
from pathlib import Path
from roll.runtime.backups import Backups,restore_at_start
root=Path('D:/dsh-proj/Roll/.scratch')
target=root/'rv12-capital-prep01'
if target.exists():raise RuntimeError('Never overwrite capital preparation store')
source=Backups(root/'rv12-real01')
saved=source.create();bundle=source.export(saved['backup_id'])
restore=Backups(target);restore.stage_restore(bundle);restore_at_start(restore)
receipt=dict(source='rv12-real01',target=str(target),backup_id=saved['backup_id'],bundle_bytes=len(bundle),
    model_calls=0,source_network_calls=0,auth_read=False,old_packet_mutated=False)
Path(__file__).with_name('store-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt))
