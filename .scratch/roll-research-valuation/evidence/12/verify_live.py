"""Actual public HTTP identity, fixed-core, source import and protection checks.

No model, generated facts, financial assumptions, synthetic returns or private
database mutations. The new disclosure remains unanalysed shared evidence.
"""
import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import httpx

OUT=Path(__file__).parent
CID='54abcc3d-67c2-453e-83b4-8fdc92b7a292'
JCC='469c1865-a145-4a47-a8ec-3056eeff81a2'
SNAP='7a430e8b-4172-4598-af21-6fe8600b6b93'
REPORT='b9cfb2a0-8f93-516a-a4cd-7b7801fd7911'
DELIVERY='e3e6e93c-0a17-4bfc-92af-82b86aa86487'
REVIEW='c29b0d46-576b-4b36-afc5-4c9bef8eccde'
VALUATION='6da4d05b-e2fc-4e99-b57d-f37f12e45109'

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

with httpx.Client(base_url='http://127.0.0.1:8032',trust_env=False,timeout=90) as c, httpx.Client(base_url='http://127.0.0.1:8033',trust_env=False,timeout=90) as d:
    def get(path,client=c):
        response=client.get(path);response.raise_for_status();return response.json()
    def post(path,value,client=c):
        response=client.post(path,json=value);response.raise_for_status();return response.json()
    def protected():
        return {p:get(p) for p in ['/api/account','/api/research/protocols','/api/research/feature-plans',
            '/api/research/feature-snapshots','/api/capabilities/grants','/api/capabilities/events']}
    before=protected()
    saved_report=get('/api/company-research/reports/'+REPORT)
    saved_delivery=get('/api/company-research/report-deliveries/'+DELIVERY)
    snapshot=get('/api/company-research/snapshots/'+SNAP)
    report_snapshot=get('/api/company-research/snapshots/'+SNAP+'?purpose=REPORT')
    daily=get(f'/api/company-research/companies/{CID}/daily?snapshot_id={SNAP}')
    assert snapshot==report_snapshot==daily['snapshot']
    assert saved_report['snapshot_id']==SNAP and saved_report['core_sha256']==snapshot['core_sha256']
    current=get('/api/company-research/economic-reviews/'+REVIEW+'/presentation')
    baseline=get('/api/company-research/economic-reviews/'+REVIEW+'/presentation?purpose=BASELINE_RESEARCH')
    assert not current['usable_range'] and baseline['usable_range']
    replay=post('/api/company-research/valuations/'+VALUATION+'/replay',None)
    issuer=get('/api/company-research/companies/'+JCC,d)
    command={k:issuer[k] for k in ['legal_name','aliases','jurisdiction','accounting_standard','year_end','industry','identity_basis']}
    command['listings']=[{k:v[k] for k in ['exchange','code','share_class','currency','valid_from']} for v in issuer['listings']]
    command.update(change_reason='Actual12 real identity reused from archived07 issuer evidence; no prices or financial records transplanted',idempotency_key='actual12-jcc-identity')
    jcc=post('/api/company-research/companies',command)
    resolutions={q:post('/api/company-research/resolve',dict(query=q)) for q in ['000848','600362','00358','HKEX:00358','SZSE:000848']}
    assert resolutions['000848']['company']['company_id']==CID
    assert all(resolutions[q]['company']['company_id']==jcc['company_id'] for q in ['600362','00358','HKEX:00358'])
    cross=c.get(f"/api/company-research/companies/{jcc['company_id']}/daily?snapshot_id={SNAP}")
    assert cross.status_code==422 and cross.json()['detail']['code']=='CROSS_COMPANY_REFERENCE'
    jcc_daily=get(f'/api/company-research/companies/{JCC}/daily',d)
    assert jcc_daily['snapshot']['company_id']==JCC
    assert not jcc_daily['valuation'].get('usable_range',False)
    source=json.loads((OUT/'primary-acquisition.json').read_text(encoding='utf-8'))[1]
    assert source['status']=='SUCCESS' and not source['previous_matching_material_ids']
    raw=Path('D:/dsh-proj/Roll/.scratch/rv12-real01/acceptance-source/halfyear2026.pdf').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==source['sha256']
    material=post('/api/company-research/materials',dict(company_id=CID,source_id='SZSE_LULU_2026_HALF_YEAR',
        origin_root_id=source['url'],source_url=source['url'],subject_name='承德露露股份公司',media_type='application/pdf',
        disclosed_at=source['disclosed_at'],period_start=source['period_start'],period_end=source['period_end'],
        unit='YUAN',currency='CNY',scope='CONSOLIDATED',page='1',
        limitations=['Actual issuer PDF identity and period checked on cover only;139 pages are not extracted financial facts',
            'Actual current acquisition; not historical PIT;2026Q3 remains newer; no current valuation uplift'],
        idempotency_key='actual12-halfyear-import',content_base64=base64.b64encode(raw).decode()))
    response=c.get('/api/company-research/materials/'+material['material_id']+'/original');response.raise_for_status()
    assert response.content==raw
    assert get('/api/company-research/reports/'+REPORT)==saved_report
    assert get('/api/company-research/report-deliveries/'+DELIVERY)==saved_delivery
    assert get('/api/company-research/snapshots/'+SNAP)==snapshot
    after=protected();assert before==after
    files={}
    for artifact in ['markdown','pdf','manifest','references','valuation','input']:
        response=c.get('/api/company-research/report-deliveries/'+DELIVERY+'/files/'+artifact);response.raise_for_status()
        files[artifact]=dict(bytes=len(response.content),sha256=hashlib.sha256(response.content).hexdigest())
    assert files['pdf']['sha256']=='b135d59a72287ea6f998fd591882cc28de078f745741b7bc6d225ec1d7ddf408'
    for name,value in [('protected-before',before),('protected-after',after),('new-source-material',material),
                       ('resolutions',resolutions),('jcc-real-daily',jcc_daily),('valuation-replay',replay),
                       ('baseline-presentation',baseline),('current-presentation',current)]:
        (OUT/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    receipt=dict(at=datetime.now(timezone.utc).isoformat(),snapshot_id=SNAP,core_sha256=snapshot['core_sha256'],
        report_id=REPORT,report_status=saved_report['completeness'],shared_snapshot_equal=True,old_report_unchanged=True,
        jcc_source_company_id=JCC,jcc_registered_company_id=jcc['company_id'],jcc_daily_snapshot_id=jcc_daily['snapshot']['snapshot_id'],jcc_valuation_usable=False,
        ah_identity_equal=True,cross_company_snapshot_status=cross.status_code,current_usable=False,baseline_usable=True,
        new_material_id=material['material_id'],new_material_sha256=source['sha256'],new_material_extracted=False,
        files=files,protected_objects_equal=True,protected_digest=digest(before),model_calls=0,auth_read=False,
        sources_network_calls=2,real_new_complete_report=False,actual_postclose_cycles=0)
    (OUT/'live-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False))
