"""Final protected metadata check after documentation and final browser verification."""
import json,sqlite3,subprocess
from pathlib import Path
from reconstructed19_protection import table_digest
from roll.research.models import code_fingerprint
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'.scratch/roll-p0/evidence/19-reconstruction-2026-10-10'
def main():
    initial=json.loads((OUT/'initial-state.json').read_text());state=json.loads((OUT/'v4/run-state.json').read_text());model=json.loads((OUT/'v4/real-model.json').read_text());tables=initial['source_tables_sha256']
    protected=[t for t in tables if t.startswith(('account_','funding_','valuation_','research_'))];source_checks={};copy_checks={}
    with sqlite3.connect((Path(initial['source'])/'roll.sqlite3').as_uri()+'?mode=ro',uri=True) as original,sqlite3.connect((Path(initial['target'])/'roll.sqlite3').as_uri()+'?mode=ro',uri=True) as copied:
        for table in protected:source_checks[table]=table_digest(original,table)==tables[table]
        for table in protected:
            if not table.startswith('research_') or table.startswith('research_risk_'):copy_checks[table]=table_digest(copied,table)==tables[table]
        protocols=[json.loads(r[0]) for r in copied.execute('SELECT value FROM research_protocols')]
        assert all(p['forward_started_at'] is None and p['capability']=='NOT_GRANTED' for p in protocols)
        assert not any(json.loads(r[0])['action'] in ['SEALED_INPUT_ACCESSED','SEALED_MARKET_INPUT_EXPOSED'] for r in copied.execute('SELECT value FROM research_events'))
    paths=subprocess.check_output(['git','diff','--name-only','--','.scratch/roll-p0/issues'],cwd=ROOT,text=True).splitlines()
    assert paths==['.scratch/roll-p0/issues/19-transparent-model-freeze.md']
    assert all(source_checks.values()) and all(copy_checks.values()) and code_fingerprint()==model['code_fingerprint']
    value={'passed':True,'protected_source_tables_unchanged':source_checks,'copied_account_and_authority_unchanged':copy_checks,'all_protocols_forward_start_null':True,'all_protocols_not_granted':True,
        'sealed_access_or_market_exposure_events':0,'changed_ticket_paths':paths,'numeric_code_matches_frozen_model':True,'model_run_id':model['model_run_id'],'code_sha256':model['code_fingerprint']}
    (OUT/'final-scope-verification.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');print(json.dumps({'passed':True,'protected_tables':len(protected),'changed_ticket_paths':paths,'numeric_code_matches_frozen_model':True}))
if __name__=='__main__':main()
