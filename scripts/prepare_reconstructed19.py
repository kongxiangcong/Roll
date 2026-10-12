"""Read-only source inventory and opaque isolated backup. Never decode SEALED inputs."""
import hashlib,json,sqlite3,shutil,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.scratch/roll-p0/evidence/19-reconstruction-2026-10-10'
TARGET=ROOT/'.roll-data/reconstructed19-v1'

def digest(body):return hashlib.sha256(body).hexdigest()
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    receipt=json.loads((ROOT/'.scratch/roll-p0/evidence/19-workbuddy-wind-sync-2026-10-10/live-sync-receipt.json').read_text(encoding='utf-8'))
    source=Path(receipt['source_views'][0]['data_directory'])
    if (TARGET/'roll.sqlite3').exists():raise RuntimeError('Existing isolated directory; preserve it, do not overwrite')
    TARGET.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect((source/'roll.sqlite3').as_uri()+'?mode=ro',uri=True) as db,sqlite3.connect(TARGET/'roll.sqlite3') as copied:
        db.backup(copied)
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        protected={t:digest(json.dumps(list(db.execute(f'SELECT * FROM "{t}" ORDER BY rowid')),ensure_ascii=False,default=str).encode()) for t in tables}
        datasets=[json.loads(r[0]) for r in db.execute('SELECT value FROM research_datasets')]
        protocols=[json.loads(r[0]) for r in db.execute('SELECT value FROM research_protocols')]
        attempts=[json.loads(r[0]) for r in db.execute('SELECT value FROM research_attempts')]
        inventory={'source':str(source),'target':str(TARGET),'source_tables_sha256':protected,
            'datasets':[dict(dataset_id=d['dataset_id'],source_run_id=d['source_run_id'],instrument=d['scope']['instruments'],coverage={k:d['coverage'].get(k) for k in ['first_date','last_date','session_count']},partitions={k:{a:v[a] for a in ['state','first_date','last_date','context_first_date'] if a in v} for k,v in d['partitions'].items()}) for d in datasets],
            'protocols':[dict(protocol_id=p['protocol_id'],predecessor_id=p['predecessor_id'],dataset_id=p['dataset_id'],forward_started_at=p['forward_started_at']) for p in protocols],
            'attempts':[{k:a[k] for k in ['attempt_id','protocol_id','category','status']} for a in attempts],
            'sealed_payloads_decoded':False,'copies':[]}
    for folder in ['raw','parquet']:
        for path in sorted((source/folder).glob('*')):
            if not path.is_file():continue
            target=TARGET/folder/path.name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(path,target)
            sha=digest(path.read_bytes());assert digest(target.read_bytes())==sha
            inventory['copies'].append({'path':str(path.relative_to(source)),'bytes':path.stat().st_size,'sha256':sha,'purpose':'OPAQUE_PRESERVATION_NOT_INPUT_CONSUMPTION'})
    status=subprocess.check_output(['git','status','--porcelain','-uall'],cwd=ROOT,text=True)
    dirty=[]
    for line in status.splitlines():
        path=ROOT/line[3:]
        if path.is_file():dirty.append({'path':line[3:],'sha256':digest(path.read_bytes())})
    inventory['initial_dirty_files']=dirty
    (OUT/'initial-state.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:inventory[k] for k in ['datasets','protocols','attempts','sealed_payloads_decoded']},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
