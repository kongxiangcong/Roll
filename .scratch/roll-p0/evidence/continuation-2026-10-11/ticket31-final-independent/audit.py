"""Independent finite artifact/byte audit. No application imports or DB connections."""
from pathlib import Path
import hashlib, json, math, os, subprocess

ROOT = Path('D:/dsh-proj/Roll')
OWN = ROOT/'.scratch/worktrees/ticket31-final'
E = OWN/'.scratch/roll-p0/evidence/31-final'
OUT = Path(__file__).parent
BASE = '6bbc3f94c05fd62e0afb9d0c4be2f1f502fffbf2'
HEAD = '792389c8c3e6d211199e6d73ed45b5940cb6ece7'
ACCEPTED = '076e67d53e4e550d4027b4f76909fb693c952957'
def read(name): return json.loads((E/name).read_bytes())
def proof(path):
    if os.name=='nt': path=Path('\\\\?\\'+str(path.resolve()))
    with path.open('rb') as stream: sha=hashlib.file_digest(stream,'sha256').hexdigest()
    return {'bytes':path.stat().st_size,'sha256':sha}
def git(*args, tree=ROOT): return subprocess.check_output(['git',*args],cwd=tree).decode().strip()
assert git('rev-parse','HEAD') == BASE
assert git('rev-parse','HEAD',tree=OWN) == HEAD
assert not git('diff','--name-only') and not git('diff','--cached','--name-only')
for ancestor in (BASE,ACCEPTED): subprocess.run(['git','merge-base','--is-ancestor',ancestor,HEAD],cwd=OWN,check=True)
changed=git('diff','--name-only',BASE,HEAD).splitlines()
allowed=lambda p: p.startswith('.scratch/roll-p0/evidence/31-final/') or p in ('backend/tests/application/test_reviews.py','frontend/playwright.final31-report.config.ts')
assert all(allowed(p) for p in changed)
guard=read('guard-final.json'); assert guard==read('guard-before.json')
for row in guard['protected15']:
    assert proof(ROOT/row['path'])==row['root']==proof(OWN/row['path'])==row['own']
for row in guard['allowed3']: assert proof(Path(row['path']))=={k:row[k] for k in ('bytes','sha256')}
original=proof(ROOT/'.roll-data/reconstructed19-v1/roll.sqlite3')
assert original==guard['original19_checksum_only']
source_mismatches=[]
assert subprocess.check_output(['git','ls-tree','-r',BASE,'backend/src','frontend/src'],cwd=ROOT)==subprocess.check_output(['git','ls-tree','-r',HEAD,'backend/src','frontend/src'],cwd=ROOT)
for row in guard['sources']:
    for tree in (ROOT,OWN):
        if hashlib.sha256((tree/row['path']).read_bytes().replace(b'\r\n',b'\n')).hexdigest()!=row['sha256_lf']: source_mismatches.append(str(tree/row['path']))
assert not source_mismatches
numeric=read('runs/4c8ac26b2cee4753822177d3176f8971/numeric-p95.json')
for path,sha in numeric['application_sources'].items(): assert hashlib.sha256((OWN/'backend/src/roll'/path).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==sha
assert len(numeric['application_sources'])==75 and len(numeric['stocks'])==30 and len(numeric['indices'])==5
assert numeric['admitted_scope']==['SSE:600362'] and numeric['network_calls']==0 and numeric['distinct_evaluation_ids']==1
p95=[]
for name,key,n,w,reported,limit,unit in [
 ('runs/live-20261011-223216/home-p95.json','samples_ms',100,10,'p95_ms',2000,'ms'),
 ('runs/live-20261011-223216/confirmation-p95.json','samples_ms',100,10,'p95_ms',2000,'ms'),
 ('runs/4c8ac26b2cee4753822177d3176f8971/numeric-p95.json','samples_seconds',21,None,'nearest_rank_p95_seconds',30,'s')]:
    d=read(name);samples=d[key]
    assert len(samples)==n and all(isinstance(x,(int,float)) and math.isfinite(x) and x>=0 for x in samples)
    if w is not None: assert d['samples']==n and d['warmup']==w and d['fit_calls']==d['forecast_calls']==0
    index=math.ceil(.95*n)-1;value=sorted(samples)[index]
    assert value==d[reported] and value<=limit
    p95.append({'artifact':name,'samples':n,'warmup':w,'nearest_rank_index':index,'recomputed':value,'unit':unit,'threshold':limit,'pass':True,'artifact_proof':proof(E/name)})
assert all(abs(a+b-c)<1e-9 for a,b,c in zip(numeric['numeric_layer_seconds'],numeric['application_layer_seconds'],numeric['samples_seconds']))
locks=read('install/source-install-input.json')['locks']
assert locks==read('install/source-install-after.json')['locks']
for row in locks: assert proof(OWN/row['path'])=={k:row[k] for k in ('bytes','sha256')}
physical=[]
for relative in ('backend/.venv','frontend/node_modules'):
    p=OWN/relative; assert p.is_dir() and not p.is_symlink() and not (p.stat().st_file_attributes & 1024)
    physical.append({'path':str(p),'reparse':False})
assert 'include-system-site-packages = false' in (OWN/'backend/.venv/pyvenv.cfg').read_text().lower()
installed=read('install/python-installed.json'); assert installed['roll_module_path']==str(OWN/'backend/src/roll/__init__.py')
delta=read('current-agent-component-delta.json')
for row in delta['source_rows']: assert proof(OWN/row['path'])=={k:row[k] for k in ('bytes','sha256')}
assert proof(E/'install/public-component-verification.json')['sha256']==delta['prior_public_component_record']['sha256']
manifest=read('runtime-union-manifest.json'); summary=read('runtime-preservation-summary.json')
manifest_proof=proof(E/'runtime-union-manifest.json')
assert manifest_proof=={'bytes':178259,'sha256':'ca3331799dbf8ffcf298e45d0c2fe076ac94a939361a000cf378dfe91252ba7d'}
assert manifest['files']==len(manifest['entries'])==summary['files']==645
assert manifest['bytes']==sum(x['bytes'] for x in manifest['entries'])==summary['bytes']==291181324
assert not manifest['unexpected_private_metadata'] and not manifest['exact_private_metadata_exclusions'] and not manifest['reparse_metadata_only']
dest=Path(manifest['destination']); assert proof(dest/'runtime-union-manifest.json')==manifest_proof
for row in manifest['entries']:
    relative=Path(row['path']); assert not relative.is_absolute() and '..' not in relative.parts
    expected={k:row[k] for k in ('bytes','sha256')}
    for tree in (OWN,dest): assert proof(tree/relative)==expected, str(tree/relative)
assert len(manifest['cim_stop_checks'])==39 and all(x['current'] is None for x in manifest['cim_stop_checks'])
live=read('runs/live-20261011-223216/live-receipt.json'); assert live['status']=='PASS' and all(live['checks'].values())
assert live['source_oid']==numeric['source_oid']=='d4864a4e29ddcb80462e44250569d652e8cc03cf'
assert live['recovery']['state']=='RECOVERY_LOCK' and not live['recovery']['formal_actions_allowed']
for item in live['processes']:
    if 'cim_after_stop' in item: assert all(x is None for x in item['cim_after_stop'])
five=read('runs/live-20261011-223216/five-entry/five-entry.json'); assert five['status']=='PASS' and not five['errors'] and len(five['checks'])==6 and all(five['checks'].values())
retry=read('runs/retry-contract-sourcebound/public-retry-receipt.json'); assert len(retry['runs'])==6 and retry['task']['attempts']==3
dup=retry['audit']['metrics']['duplicate_notifications']; notices=retry['notifications_at_assertion']; task=retry['task']
assert dup['status']=='CHECKED' and dup['value']==0 and len(notices)==dup['business_notifications']==1
assert dup['transmission_attempts']==0 and dup['delivery_status']=='UNKNOWN'
assert notices[0]['source']['kind']=='RUN_SUMMARY' and notices[0]['source']['id']==task['result']['snapshot_id'] and notices[0]['source']['version']==task['task_id']
assert (E/'runs/retry-contract-sourcebound/exit.txt').read_text().strip()=='0'
result={'state':'INDEPENDENT_ARTIFACT_BYTE_AUDIT_PASS','root_before':BASE,'owner_head':HEAD,'accepted_fix':ACCEPTED,'changed_files':len(changed),'changed_scope':changed,'product_source_files':len(guard['sources']),'numeric_application_sources':75,'raw_git_source_equal':True,'protected15':15,'allowed_json_artifacts':3,'original19_byte_only':original,'p95':p95,'physical_dependencies':physical,'locks':locks,'manifest_proof':manifest_proof,'runtime_files_both_sides':645,'runtime_bytes_each_side':291181324,'runtime_mismatches':0,'stored_cim_stop_checks':39,'stored_alive':0,'five_entry_checks':6,'retry_runs':6,'retry_attempts':3,'original_sqlite_connections':0,'new_tests':0,'new_http':0,'new_provider_calls':0,'actual_grants':0,'method_fixture_grants':'AUTHORIZED_OWNER_SCOPE_RETAINED','credential_reads_hashes_copies':0,'limitations':['No new behavior tests or three benchmark reruns; existing raw evidence audited.','API CTRL_BREAK exit3, Vite3221225786, worker0 retained; not all exit0.','31 policy/source prerequisite partial and actual scientific/formal gaps unchanged.']}
(OUT/'audit.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({k:result[k] for k in ('state','changed_files','product_source_files','numeric_application_sources','runtime_files_both_sides','runtime_bytes_each_side','runtime_mismatches','p95')},ensure_ascii=False))
