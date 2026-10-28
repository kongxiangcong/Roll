"""Fresh public-backup clone; source and previous three real calls stay untouched."""
import json
from pathlib import Path
from roll.runtime.backups import Backups,restore_at_start
H=Path(__file__).resolve().parent
source=Path('D:/dsh-proj/Roll/.scratch/rv12-capital-prep01')
target=Path('D:/dsh-proj/Roll/.scratch/rv12-economic-prep07')
assert not target.exists(),'Never overwrite preparation stores'
b=Backups(source);saved=b.create();bundle=b.export(saved['backup_id'])
r=Backups(target);r.stage_restore(bundle);restore_at_start(r)
(H/'store-receipt.json').write_text(json.dumps(dict(source=str(source),target=str(target),backup_id=saved['backup_id'],bundle_bytes=len(bundle),model_calls=0,source_network_calls=0,auth_read=False),indent=2),encoding='utf-8')
print(json.dumps(dict(target=str(target),bytes=len(bundle))))
