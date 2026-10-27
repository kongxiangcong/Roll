"""Verify real browser artifacts against preserved public service records, no model."""
import hashlib,json
from pathlib import Path
from roll.accounts.ledger import Ledger
from roll.market.directory import MarketDirectory
from roll.market.evidence import EvidenceStore
from roll.research.company import CompanyResearch
ROOT=Path('D:/dsh-proj/Roll/.scratch');OUT=Path(__file__).parent
def service(path):
    ledger=Ledger(path);return CompanyResearch(EvidenceStore(ledger,MarketDirectory(ledger)))
old=service(ROOT/'rv09-real01');current=service(ROOT/'rv10-real01')
rid='b9cfb2a0-8f93-516a-a4cd-7b7801fd7911';did='e3e6e93c-0a17-4bfc-92af-82b86aa86487';jid='2c427d2d-0dda-4f5d-9c6f-ea7de8303995'
report=current.reports.read(rid);delivery=current.report_deliveries.read(did)
assert report==old.reports.read(rid)
assert delivery==old.report_deliveries.read(did)
downloads={}
for name in ['markdown','pdf']:
    raw,media,filename=current.report_deliveries.download(did,name)
    actual=(OUT/'downloads'/filename).read_bytes()
    assert actual==raw
    downloads[name]=dict(bytes=len(actual),sha256=hashlib.sha256(actual).hexdigest(),media_type=media,browser_download=True)
job=current.reports.get(jid)
assert job['status']=='CANCELLED' and job['section_ids']==[] and job['input_id'] is None
assert job['snapshot_id']==report['snapshot_id']
assert current.ledger.account()['version']==old.ledger.account()['version']==0
receipt=dict(report_id=rid,original_job_id=report['job_id'],snapshot_id=report['snapshot_id'],core_sha256=report['core_sha256'],report_status=report['completeness'],delivery_id=did,report_unchanged=True,delivery_unchanged=True,downloads=downloads,new_browser_job=dict(job_id=jid,status=job['status'],stage=job['stage'],attempts=job['attempts'],section_count=0,input_id=None),model_calls=0,source_network_calls=0,auth_read=False,account_version=0,real_browser='IAB browser3/tab1 on127.0.0.1:5210; explicit existing-report reuse, not new CODEX execution',model_provenance='Existing08 archived real CODEX calls; see evidence08/final05.md. The browser new job was never executed and was explicitly cancelled.',source_provenance='Existing05/08 primary sources and09 immutable file delivery; no new public-source acquisition in10.')
(OUT/'real-final-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'real-new-job.json').write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(receipt))
