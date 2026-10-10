"""Approved mode=ro registered collection metadata; no raw/SEALED/account reads."""
import hashlib,json,sqlite3,sys
from pathlib import Path
path=Path('D:/dsh-proj/Roll/.roll-data/implementation-evidence/21/actual-current-copy/roll.sqlite3')
def sha():return hashlib.sha256(path.read_bytes()).hexdigest()
before=sha();db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
out={'database_sha256_before':before,'read_only':True,'plans':[],'batches':[],'snapshots':[]}
for row in db.execute('SELECT value FROM pit_collection_plans'):
    value=json.loads(row[0]);out['plans'].append({k:value.get(k) for k in ['plan_id','instrument','started_at','namespace','source_policy','forward_started_at']})
for row in db.execute('SELECT value FROM pit_collection_batches'):
    value=json.loads(row[0]);out['batches'].append({k:value.get(k) for k in ['batch_id','plan_id','run_id','snapshot_id','received_at','known_at','evidence_kind','source_policy','gaps']})
for row in db.execute('SELECT value FROM market_evidence_snapshots'):
    value=json.loads(row[0]);observations=value.get('facts',[])
    out['snapshots'].append({'snapshot_id':value.get('snapshot_id'),'evidence_kind':value.get('evidence_kind'),'observation_count':len(observations),
        'groups':sorted({r.get('group','UNKNOWN') for r in observations}),
        'completion_states':sorted({str(r.get('completion_state')) for r in observations if r.get('group')=='DAILY'}),
        'complete_status_verified_count':sum(r.get('complete_status_verified') is True for r in observations),
        'complete_company_actions_count':sum(r.get('execution_evidence',{}).get('company_actions') in {'CONFIRMED_NONE','SOURCE_BOUND_CASH_AND_ANNUAL_SHARE_AUDIT'} for r in observations),
        'status_unknown_fields':sorted({k for r in observations if r.get('group')=='STATUS' for k in ['suspension','risk_warning','listing_stage','current_ex_rights'] if r.get(k) in {None,'UNKNOWN'}})})
db.close();out['database_sha256_after']=sha();assert before==out['database_sha256_after']
Path(sys.argv[1]).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
