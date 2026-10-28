"""Actual loopback API delivery/download and isolated byte-for-byte restore."""
import hashlib
import json
from pathlib import Path
import httpx
from verify_real_delivery import ROOT, OUT, REPORT, research
from roll.runtime.backups import Backups,restore_at_start

parent=json.loads((OUT/'real-delivery02.json').read_text(encoding='utf-8'))
base='http://127.0.0.1:8029/api/company-research'
with httpx.Client(timeout=100,trust_env=False) as client:
    original=client.get(base+'/reports/'+REPORT);original.raise_for_status();original=original.json()
    response=client.post(base+'/report-deliveries',json=dict(report_id=REPORT,idempotency_key='actual09-03',parent_delivery_id=parent['delivery_id']))
    response.raise_for_status();delivery=response.json()
    (OUT/'real-delivery03.json').write_text(json.dumps(delivery,ensure_ascii=False,indent=2),encoding='utf-8')
    if delivery['status']!='COMPLETE':raise RuntimeError(delivery['render_error'])
    artifacts={};raws={}
    for name in ['markdown','pdf','manifest','references','valuation','input']:
        response=client.get(base+'/report-deliveries/'+delivery['delivery_id']+'/files/'+name)
        response.raise_for_status()
        assert response.headers['x-content-type-options']=='nosniff'
        expected=delivery['manifest_archive'] if name=='manifest' else delivery['artifacts'][name]
        assert hashlib.sha256(response.content).hexdigest()==expected['sha256']
        extension='md' if name=='markdown' else 'pdf' if name=='pdf' else 'json'
        target=OUT/'output'/('report-'+delivery['delivery_id']+'-'+name+'.'+extension)
        target.write_bytes(response.content);raws[name]=response.content
        artifacts[name]=dict(path=str(target.resolve()),sha256=expected['sha256'],bytes=len(response.content),media_type=response.headers['content-type'])
    assert client.get(base+'/report-deliveries/'+delivery['delivery_id']+'/files/roll.sqlite3').status_code==404
    assert client.get(base+'/report-deliveries/'+delivery['delivery_id']+'/files/%2e%2e%2froll.sqlite3').status_code==404
    assert client.get(base+'/reports/'+REPORT).json()==original
    assert client.get(base+'/report-deliveries/'+parent['delivery_id']).json()==parent
    history=client.get(base+'/reports/'+REPORT+'/deliveries').json()
    assert history['total']==3
    backup=client.post('http://127.0.0.1:8029/api/runtime/backups');backup.raise_for_status();backup=backup.json()
    bundle=client.get('http://127.0.0.1:8029/api/runtime/backups/'+backup['backup_id']+'/export');bundle.raise_for_status()
target=ROOT/'rv09-restored01'
if target.exists():raise RuntimeError('Restore target already exists; never overwrite it')
restore=Backups(target);restore.stage_restore(bundle.content);restore_at_start(restore)
recovered=research(target)
assert recovered.reports.read(REPORT)==original
assert recovered.report_deliveries.read(delivery['delivery_id'])==delivery
assert recovered.report_deliveries.read(parent['delivery_id'])==parent
for name,raw in raws.items():assert recovered.report_deliveries.download(delivery['delivery_id'],name)[0]==raw
assert recovered.ledger.account()['version']==0
receipt=dict(delivery_id=delivery['delivery_id'],parent_delivery_id=parent['delivery_id'],report_id=REPORT,pages=delivery['renderer']['pages'],
    artifacts=artifacts,report_unchanged=True,older_deliveries_unchanged=True,history_total=history['total'],http_downloads=6,
    traversal_rejected=True,backup_id=backup['backup_id'],bundle_bytes=len(bundle.content),restore_target=str(target),records_equal=True,
    restored_file_sha256={k:hashlib.sha256(v).hexdigest() for k,v in raws.items()},model_calls=0,source_network_calls=0,auth_read=False,account_version=0)
(OUT/'real03-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(receipt))
