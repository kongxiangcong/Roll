"""Integration acceptance inventory; hash protected state without disclosing values."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'backend/src'))
from roll.accounts.ledger import encode

DIRECTORY = Path(__file__).parent


def inventory():
    result = {}
    for relative in ['.roll-data/pit/roll.sqlite3', '.roll-data/roll.sqlite3', '.roll-data/synthetic19/roll.sqlite3']:
        path = ROOT/relative
        if not path.exists():
            continue
        db = sqlite3.connect(f'file:{path.as_posix()}?mode=ro', uri=True)
        names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        state = {}
        for name in names:
            if any(part in name for part in ['account', 'research_', 'model', 'attempt', 'forecast', 'funding', 'decision', 'capability', 'execution', 'risk_policy']):
                rows = list(db.execute('SELECT * FROM "'+name.replace('"', '""')+'" ORDER BY rowid'))
                state[name] = {'rows': len(rows), 'sha256': hashlib.sha256(encode(rows).encode()).hexdigest()}
        if relative.startswith('.roll-data/pit/'):
            state['original_pit_facts'] = [r for r in db.execute('SELECT ordinal,plan_id,batch_id,fact_key,known_at,value FROM pit_fact_versions ORDER BY ordinal')]
        db.close()
        result[relative] = state
    result['model_code_sha256'] = hashlib.sha256((ROOT/'backend/src/roll/research/models.py').read_bytes()).hexdigest()
    return result


if sys.argv[1] == 'before':
    from roll.runtime.backups import Backups
    captured = inventory()
    backup = Backups(ROOT/'.roll-data/pit').create(reason='BEFORE_CNEQUITY_INTEGRATION')
    (DIRECTORY/'protected-before.json').write_text(json.dumps(captured, ensure_ascii=False, indent=2), encoding='utf-8')
    (DIRECTORY/'pre-integration-backup.json').write_text(json.dumps(backup, indent=2), encoding='utf-8')
    print(json.dumps({'protected_databases': len(captured)-1, 'backup': backup}, ensure_ascii=False))
else:
    before = json.loads((DIRECTORY/'protected-before.json').read_text(encoding='utf-8'))
    after = inventory()
    old = before['.roll-data/pit/roll.sqlite3'].pop('original_pit_facts')
    current = after['.roll-data/pit/roll.sqlite3'].pop('original_pit_facts')
    same = all(after[k] == v for k, v in before.items())
    original_unchanged = current[:len(old)] == [tuple(r) for r in old]
    from roll.app import create_app
    app = create_app(ROOT/'.roll-data/pit')
    integrity = app.state.collection_sources.integrity()
    result = {'protected_state_unchanged': same, 'original_pit_facts_unchanged': original_unchanged,
              'original_fact_versions': len(old), 'current_fact_versions': len(current), 'integrity': integrity,
              'sources': app.state.collection_sources.listing(), 'cleaning': app.state.collection_sources.reports(),
              'model_code_sha256': after['model_code_sha256']}
    (DIRECTORY/'persistence-check.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in {'sources','cleaning'}}, ensure_ascii=False, indent=2))
    assert same and original_unchanged and integrity['consistent']
