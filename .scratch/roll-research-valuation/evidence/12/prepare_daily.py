"""Clone the real daily deployment through public backups, not a database copy."""
import json
from pathlib import Path
from roll.runtime.backups import Backups, restore_at_start

root = Path('D:/dsh-proj/Roll/.scratch')
target = root/'rv12-daily01'
if target.exists():
    raise RuntimeError('Never overwrite an acceptance store')
source = Backups(root/'rv07-real01')
saved = source.create()
bundle = source.export(saved['backup_id'])
restore = Backups(target)
restore.stage_restore(bundle)
restore_at_start(restore)
receipt = dict(source='rv07-real01',target=str(target),backup_id=saved['backup_id'],
               bundle_bytes=len(bundle),model_calls=0,source_network_calls=0,auth_read=False)
Path(__file__).with_name('daily-store.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt))
