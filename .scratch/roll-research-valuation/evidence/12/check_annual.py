"""Actual bounded primary-source no-new check through the public service seam."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import httpx
from roll.accounts.ledger import Ledger
from roll.market.directory import MarketDirectory
from roll.market.evidence import EvidenceStore
from roll.research.company import CompanyResearch
from roll.research.company.models import CheckCommand

out=Path(__file__).parent
ledger=Ledger(Path('D:/dsh-proj/Roll/.scratch/rv12-real01'))
research=CompanyResearch(EvidenceStore(ledger,MarketDirectory(ledger)))
cid='54abcc3d-67c2-453e-83b4-8fdc92b7a292'
source=json.loads((out/'primary-acquisition.json').read_text(encoding='utf-8'))[0]
network=[]
def supplier(scope):
    started=datetime.now(timezone.utc).isoformat()
    with httpx.Client(trust_env=False,timeout=35,follow_redirects=True) as client:
        response=client.get(source['url']);response.raise_for_status()
    sha=hashlib.sha256(response.content).hexdigest()
    network.append(dict(scope=scope,url=source['url'],started_at=started,finished_at=datetime.now(timezone.utc).isoformat(),
                        status=response.status_code,bytes=len(response.content),sha256=sha))
    if sha!=source['sha256']:
        raise RuntimeError('Source bytes changed; require explicit new material review')
    # Complete scope is this one exact annual PDF, never all company disclosures.
    return []
check=research.check_source(CheckCommand(company_id=cid,source_id='actual12-cninfo-annual2025',
    requested_scopes=['EXACT_ANNUAL_2025_PDF_BYTES'],idempotency_key='actual12-annual-recheck'),supplier)
assert check['status']=='SUCCESS' and check['new_material_count']==0
assert not network or len(network)==1
with httpx.Client(base_url='http://127.0.0.1:8032',trust_env=False,timeout=90) as client:
    snapshots=client.get(f'/api/company-research/companies/{cid}/snapshots').json()['snapshots']
    parent=snapshots[-1]
    if parent.get('enrichment_kind')=='RESEARCH_CONTEXT' and check['check_id'] in parent['check_ids']:
        child=parent
    else:
        response=client.post('/api/company-research/contexts',json=dict(snapshot_id=parent['snapshot_id'],check_ids=[check['check_id']],
            change_reason='Actual current exact2025 annual PDF re-fetch matches archived SHA; no other disclosure/public scope checked; no new operating inference'))
        response.raise_for_status();child=response.json()
    daily=client.get(f'/api/company-research/companies/{cid}/daily').json()
    assert daily['snapshot']['snapshot_id']==child['snapshot_id']
    assert child['core_sha256']==parent['core_sha256']
    report=client.get('/api/company-research/reports/b9cfb2a0-8f93-516a-a4cd-7b7801fd7911').json()
    assert report['snapshot_id']=='7a430e8b-4172-4598-af21-6fe8600b6b93'
receipt=dict(check=check,network_receipts=network,snapshot_id=child['snapshot_id'],
    core_sha256=child['core_sha256'],research_basis_as_of=child['research_basis_as_of'],
    daily_snapshot_id=daily['snapshot']['snapshot_id'],old_report_snapshot_id=report['snapshot_id'],
    original_report_unchanged=True,new_operating_inference=False,model_calls=0,auth_read=False)
(out/'actual-annual-check.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(check_id=check['check_id'],status=check['status'],new_material_count=0,network_calls=len(network),
    snapshot_id=child['snapshot_id'],core_sha256=child['core_sha256'],model_calls=0)))
