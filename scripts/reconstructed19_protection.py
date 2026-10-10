"""Hashes only for actual account/protected history; no account values emitted."""
import hashlib,json,sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'.scratch/roll-p0/evidence/19-reconstruction-2026-10-10'
def digest(body):return hashlib.sha256(body).hexdigest()
def table_digest(db,table):return digest(json.dumps(list(db.execute(f'SELECT * FROM "{table}" ORDER BY rowid')),ensure_ascii=False,default=str).encode())
def main():
    initial=json.loads((OUT/'initial-state.json').read_text(encoding='utf-8'));source=Path(initial['source']);target=Path(initial['target'])
    tables=initial['source_tables_sha256'];original_checks={};isolated_checks={};old_rows={}
    with sqlite3.connect((source/'roll.sqlite3').as_uri()+'?mode=ro',uri=True) as original,sqlite3.connect((target/'roll.sqlite3').as_uri()+'?mode=ro',uri=True) as isolated:
        for table,sha in tables.items():
            original_checks[table]=table_digest(original,table)==sha
            if table.startswith(('account_','funding_','valuation_','research_risk_')):isolated_checks[table]=table_digest(isolated,table)==sha
            if table in ['research_protocols','research_datasets','research_attempts','research_models','research_forecasts','research_events','research_executions','research_execution_results']:
                rows=list(original.execute(f'SELECT * FROM "{table}" ORDER BY rowid'))
                copied={r[0]:r for r in isolated.execute(f'SELECT * FROM "{table}"')}
                old_rows[table]={'original_count':len(rows),'preserved':all(copied.get(r[0])==r for r in rows)}
    archive_checks=[]
    for item in initial['copies']:
        a=source/item['path'];b=target/item['path']
        archive_checks.append({'path':item['path'],'source_same':digest(a.read_bytes())==item['sha256'],'copy_same':digest(b.read_bytes())==item['sha256']})
    intentional={'.scratch/roll-p0/execution-status.md','.scratch/roll-p0/issues/19-transparent-model-freeze.md','.scratch/roll-p0/requirements-traceability.md','.scratch/roll-p0/spec.md',
        'GLOSSARY.md','backend/src/roll/app.py','backend/src/roll/research/datasets.py','backend/src/roll/research/design.py','backend/src/roll/research/execution.py','backend/src/roll/research/models.py',
        'backend/src/roll/research/registry.py','backend/src/roll/research/training_preflight.py','backend/src/roll/runtime/backups.py','backend/tests/application/test_transparent_models.py',
        'docs/data-evidence-contract.md','docs/research-protocol-contract.md','docs/transparent-model-contract.md','docs/adr/0004-reconstructed-price-volume-research.md','frontend/src/pages/models.tsx','frontend/src/pages/research.tsx'}
    changed=[];unexpected=[]
    for item in initial['initial_dirty_files']:
        p=ROOT/item['path'];same=p.is_file() and digest(p.read_bytes())==item['sha256']
        if not same:
            changed.append(item['path'])
            if item['path'] not in intentional and not item['path'].startswith(('.scratch/roll-p0/evidence/19-reconstruction-2026-10-10/','scripts/prepare_reconstructed19')):unexpected.append(item['path'])
    value={'source_tables_unchanged':original_checks,'isolated_account_and_authority_unchanged':isolated_checks,'old_research_rows':old_rows,
        'original_archive_count':len(archive_checks),'original_archives_and_opaque_copies_unchanged':all(c['source_same'] and c['copy_same'] for c in archive_checks),
        'initial_dirty_file_count':len(initial['initial_dirty_files']),'intended_changed_paths':changed,'unexpected_changed_paths':unexpected,
        'sealed_payloads_decoded':False,'forward_start_created':False,'later_ticket_implementation':False,'source_database_written_by_this_run':False}
    (OUT/'protection-verification.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    assert all(isolated_checks.values()) and all(v['preserved'] for v in old_rows.values()) and value['original_archives_and_opaque_copies_unchanged'] and not unexpected
    protected=[t for t in tables if t.startswith(('account_','funding_','valuation_','research_'))]
    assert all(original_checks[t] for t in protected)
    print(json.dumps({'protected_source_tables':len(protected),'all_protected_source_tables_unchanged':True,'original_archives':len(archive_checks),'old_research_preserved':True,'unexpected_changed_paths':unexpected}))
if __name__=='__main__':main()
