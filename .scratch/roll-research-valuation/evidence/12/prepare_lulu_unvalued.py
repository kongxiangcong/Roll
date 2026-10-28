"""Fixed public copy of original unvalued Lulu snapshot for new-flow preview."""
import hashlib
import json
from pathlib import Path
import httpx

out=Path(__file__).parent/'next-request-preview'
out.mkdir(exist_ok=True)
snapshot_id='c54935d7-760e-4dbd-9156-2f0b4a686a26'
with httpx.Client(base_url='http://127.0.0.1:8032',trust_env=False,timeout=90) as c:
    def get(path):
        r=c.get(path);r.raise_for_status();return r.json()
    snapshot=get('/api/company-research/snapshots/'+snapshot_id+'?purpose=REPORT')
    assert not snapshot.get('valuation_ids') and not snapshot.get('economic_review_ids')
    packet=get('/api/company-research/analysis/inputs/'+snapshot['input_id'])
    company=get('/api/company-research/companies/'+snapshot['company_id'])
    facts=packet['payload']['facts']
    assert {f['version_id'] for f in facts}==set(snapshot['fact_version_ids'])
    assert all(f['company_id']==company['company_id'] for f in facts)
    reviewed=get('/api/company-research/snapshots/7a430e8b-4172-4598-af21-6fe8600b6b93')
    assert reviewed['parent_snapshot_id']==snapshot_id and reviewed['economic_review_ids'] and reviewed['valuation_ids']
value=dict(kind='PUBLIC_STATIC_NEW_VALUATION_PREVIEW_INPUT_NOT_EXISTING_REVIEW_REUSE',
    snapshot=snapshot,analysis_input=packet,company=company,facts=facts,materials=packet['payload']['materials'],
    boundary=dict(original_unvalued_snapshot_id=snapshot_id,existing_review_child_id=reviewed['snapshot_id'],
        excluded_existing_valuation_ids=reviewed['valuation_ids'],excluded_existing_economic_review_ids=reviewed['economic_review_ids'],
        purpose_for_future_explicit_request='BASELINE_RESEARCH',original_fact_cutoff=snapshot['as_of'],
        actual_source_acquisition='CURRENT_RECONSTRUCTION_NOT_HISTORICAL_PIT',model_calls=0,auth_read=False,
        source_network_calls=0,not_send_authorization=True))
raw=json.dumps(value,ensure_ascii=False,indent=2).encode('utf-8')
(out/'lulu-unvalued-static.json').write_bytes(raw)
receipt=dict(snapshot_id=snapshot_id,input_id=packet['input_id'],input_sha256=packet['packet_sha256'],
    company_id=company['company_id'],fact_count=len(facts),material_count=len(value['materials']),
    core_sha256=snapshot['core_sha256'],valuation_ids=snapshot.get('valuation_ids',[]),economic_review_ids=snapshot.get('economic_review_ids',[]),
    static_bytes=len(raw),static_sha256=hashlib.sha256(raw).hexdigest(),existing_review_child_excluded=True,
    model_calls=0,auth_read=False,source_network_calls=0)
(out/'lulu-unvalued-static-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt))
