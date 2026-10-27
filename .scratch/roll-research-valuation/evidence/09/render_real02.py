"""Append a corrected file-delivery version without changing the08 report."""
import json
import hashlib
from pathlib import Path
from verify_real_delivery import research, ROOT, OUT, REPORT
from roll.research.company.report_deliveries import DeliveryCommand

service=research(ROOT/'rv09-real01')
prior=json.loads((OUT/'real-delivery01.json').read_text(encoding='utf-8'))
old=service.report_deliveries.read(prior['delivery_id'])
report=service.reports.read(REPORT)
delivery=service.report_deliveries.create(DeliveryCommand(report_id=REPORT,idempotency_key='actual09-02',parent_delivery_id=old['delivery_id']))
(OUT/'real-delivery02.json').write_text(json.dumps(delivery,ensure_ascii=False,indent=2),encoding='utf-8')
if delivery['status']!='COMPLETE':raise RuntimeError(delivery['render_error'])
artifacts={}
for name in ['markdown','pdf','manifest','references','valuation','input']:
    raw,media,filename=service.report_deliveries.download(delivery['delivery_id'],name)
    path=OUT/'output'/filename;path.write_bytes(raw)
    artifacts[name]=dict(path=str(path.resolve()),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),media_type=media)
assert service.report_deliveries.read(old['delivery_id'])==old
assert service.reports.read(REPORT)==report
assert artifacts['markdown']['sha256']==report['markdown_archive']['sha256']
receipt=dict(delivery_id=delivery['delivery_id'],parent_delivery_id=old['delivery_id'],report_id=REPORT,
    pages=delivery['renderer']['pages'],artifacts=artifacts,old_delivery_unchanged=True,report_unchanged=True,
    model_calls=0,source_network_calls=0,auth_read=False,account_version=service.ledger.account()['version'])
(OUT/'real02-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(receipt))
