"""Corroborate actions already performed through CUA, not fabricate UI triggers."""
import hashlib
import json
from pathlib import Path
import httpx

out=Path(__file__).parent
job_id='3bbfac4c-1e78-413a-86d0-950aeb72337f'
paths=dict(original_markdown=Path('C:/Users/72449/Downloads/report-e3e6e93c-0a17-4bfc-92af-82b86aa86487-markdown (1).md'),
    original_pdf=Path('C:/Users/72449/Downloads/report-e3e6e93c-0a17-4bfc-92af-82b86aa86487-pdf (1).pdf'),
    new_partial_markdown=Path('C:/Users/72449/Downloads/report-a632edd6-7724-4bb3-b74b-bca96ca611ab-markdown.md'))
downloads={k:dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for k,p in paths.items()}
assert downloads['original_pdf']['sha256']=='b135d59a72287ea6f998fd591882cc28de078f745741b7bc6d225ec1d7ddf408'
assert downloads['original_markdown']['sha256']=='3970917631045c9c5a0ed88651849a8f2775b8a2d90711b8c0bdd2ebbc032720'
with httpx.Client(base_url='http://127.0.0.1:8032',trust_env=False,timeout=90) as c:
    def get(path):
        r=c.get(path);r.raise_for_status();return r.json()
    job=get('/api/company-research/jobs/'+job_id)
    report=get('/api/company-research/reports/'+job['report_id'])
    sections=[get('/api/company-research/report-sections/'+s) for s in report['section_ids']]
    runs=[get('/api/company-research/report-runs/'+s['run_id']) for s in sections]
    assert job['stage']=='PUBLISHED' and job['status']=='PARTIAL'
    assert len(runs)==12 and all(not r.get('model_executed') for r in runs)
    assert all(r['status']=='UNAVAILABLE' for r in runs)
    assert report['snapshot_id']=='6b94c24a-f27a-4e5b-a6f9-57358d8242a6'
    assert report['core_sha256']=='37b71966590cb1cb8d0c2898c4bace4c7ec1bc3b216018d2f941204f22dcac1d'
    assert hashlib.sha256(paths['new_partial_markdown'].read_bytes()).hexdigest()==report['markdown_archive']['sha256']
    for name,value in [('browser-job',job),('browser-new-report',report),('browser-runs',runs)]:
        (out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    receipt=dict(browser='CUA IAB browser2/tab2',url='http://127.0.0.1:5212',downloads=downloads,
        original_report='b9cfb2a0-8f93-516a-a4cd-7b7801fd7911',new_report_id=report['report_id'],
        new_job_id=job_id,new_snapshot_id=report['snapshot_id'],core_sha256=report['core_sha256'],
        new_status='PARTIAL',new_stage='PUBLISHED',section_attempts=12,model_calls=0,model_auth_read=False,
        unavailable_runs=12,source_network_calls=0,
        limitation='New browser job used real existing worker but no model auth; twelve UNAVAILABLE attempts, not twelve generated chapters or full report acceptance',
        performed=['input000848 and identity resolution','old report preview/job/history','actual oldMD/PDF downloads',
            'same-snapshot read-only tracking link','new task pinned to actual annual-check context child',
            'new task progress and MODEL_UNAVAILABLE gaps','new PARTIAL preview/history and actualMD download'],
        cancel_click_after_publish='No matching cancel control after rapid PARTIAL publication; no cancel action occurred')
    (out/'browser-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ['downloads','performed']}))
