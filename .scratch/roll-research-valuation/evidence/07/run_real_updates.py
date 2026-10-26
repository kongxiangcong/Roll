"""Actual isolated worker jobs. No fake clock, source facts, or model output."""
import json,time,urllib.request,argparse
from pathlib import Path

ROOT='http://127.0.0.1:8027/api'
parser=argparse.ArgumentParser();parser.add_argument('--prefix',default='rv07-actual');parser.add_argument('--output',default=str(Path(__file__).with_name('real-updates.json')))
args=parser.parse_args()
def call(path,value=None):
    data=json.dumps(value).encode() if value is not None else None
    request=urllib.request.Request(ROOT+path,data=data,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=20) as response:
        return json.load(response)

def configure(instrument):
    base='/observation-updates/'+instrument
    old=call(base)['settings']
    return call(base+'/settings',dict(enabled=True,expected_revision=old['revision'],basis='Actual07 isolated manual acceptance; postclose schedules remain off'))

def run(instrument,key,refresh):
    job=call('/observation-updates/'+instrument+'/requests',dict(kind='RESEARCH',idempotency_key=key,
        basis='Actual07 archive catalog versus supported source scope, explicit bounded attempt',refresh_sources=refresh))
    deadline=time.monotonic()+60
    while time.monotonic()<deadline:
        job=call('/observation-update-jobs/'+job['job_id'])
        if job['status'] not in ['QUEUED','RUNNING']:
            return job
        time.sleep(.5)
    raise RuntimeError('Bounded acceptance wait exceeded; job remains saved')

configure('SSE:600362');configure('SZSE:000848')
first=run('SSE:600362',args.prefix+'-jcc-archive1',False)
second=run('SSE:600362',args.prefix+'-jcc-archive2',False)
failure=run('SZSE:000848',args.prefix+'-lulu-source-scope1',True)
retry=run('SZSE:000848',args.prefix+'-lulu-archive-retry1',False)
assert first['status']==second['status']=='COMPLETE'
assert first['observation_id']==second['observation_id'] and second['cache_reused']
assert failure['status']=='PARTIAL' and 'PUBLIC_SOURCE_SCOPE_UNSUPPORTED_FOR_SELECTED_COMPANY' in failure['errors']
assert retry['status']=='COMPLETE'
company='469c1865-a145-4a47-a8ec-3056eeff81a2'
view=call('/company-research/companies/'+company+'/daily')
assert view['snapshot']['snapshot_id']=='e28c866f-5fa5-458d-a48a-1ed1869d40ea'
assert view['snapshot']['core_sha256']=='cce09e5c244b4a6cdf4293477c6d46d804de46ee4801ce8f5a60f05a4623fc52'
receipt=dict(data_directory='D:/dsh-proj/Roll/.scratch/rv07-real01',jcc_archive_first=first,jcc_archive_repeated=second,
    lulu_scope_failure=failure,lulu_archive_only_retry=retry,current_daily_view=view,account_version=call('/account')['version'],
    actual_postclose_cycles_observed=0,scope='Manual actual archived source checks; no public-source refresh succeeded, no new operating facts/model rerun')
Path(args.output).write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(jcc=[first['status'],second['status']],duplicate_publication=False,lulu_failure=failure['status'],explicit_retry=retry['status'],snapshot_id=view['snapshot']['snapshot_id'],account_version=receipt['account_version'])))
