"""Read-only real-host receipt, accounting and restart verification; no network."""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'backend'/'src'))
from roll.research.exploratory import backtest

parser = argparse.ArgumentParser()
parser.add_argument('--data-directory', required=True)
parser.add_argument('--run-id', required=True)
parser.add_argument('--before', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args()
directory = Path(args.data_directory)
db = sqlite3.connect((directory/'roll.sqlite3').as_uri()+'?mode=ro', uri=True)
run = json.loads(db.execute('SELECT value FROM assistance_runs WHERE id=?', (args.run_id,)).fetchone()[0])
reflections = db.execute('SELECT count(*) FROM assistance_reflections WHERE run_id=?', (args.run_id,)).fetchone()[0]
hashes = {s['source_id']: hashlib.sha256((directory/'assistance-raw'/(s['sha256']+'.bin')).read_bytes()).hexdigest() == s['sha256'] for s in run['sources']}
stock = next(s for s in run['sources'] if s['source_id'] == 'sh.600362')
reproduced = backtest(stock['rows']) == run['backtest']
closes = {r['date']: Decimal(r['close']) for r in stock['rows']}
accounting = {}
for name in ['strategy', 'buy_hold']:
    result = run['backtest'][name]
    trades = {t['date']: t for t in result['trades']}
    cash, quantity = Decimal('100000'), 0
    matches = True
    for row in result['nav']:
        if t := trades.get(row['date']):
            assert t['signal_date'] < t['date'] and t['quantity'] % 100 == 0
            gross = Decimal(str(t['price']))*t['quantity']
            cash += (gross if t['side'] == 'SELL' else -gross)-Decimal(str(t['fee']))
            quantity += t['quantity'] if t['side'] == 'BUY' else -t['quantity']
            matches &= cash == Decimal(str(t['cash_after']))
        matches &= cash >= 0 and quantity >= 0
        matches &= (cash+quantity*closes[row['date']]).quantize(Decimal('.01')) == Decimal(str(row['nav']))
    accounting[name] = matches
before = json.loads(Path(args.before).read_text(encoding='utf-8-sig'))
after = {name: hashlib.sha256(json.dumps(db.execute('SELECT * FROM "'+name+'" ORDER BY rowid').fetchall(), sort_keys=True, default=str).encode()).hexdigest() for name in before}
changed = [name for name in before if before[name] != after[name]]
proof = {'run_id': args.run_id, 'status': run['status'], 'as_of': run['as_of'], 'source_raw_hashes_verified': hashes,
         'offline_backtest_reproduced': reproduced, 'independent_cash_and_nav_replay': accounting,
         'model': run.get('resolved_model'), 'model_turn_completed': run.get('runtime_completion', {}).get('status') == 'completed',
         'temporary_credentials_removed': run.get('process', {}).get('temporary_directory_removed'),
         'saved_reflections': reflections, 'protected_tables_compared': len(before), 'changed_protected_tables': changed,
         'scope': 'REAL source/model/host receipts plus deterministic replay; no claim of predictive advantage'}
Path(args.output).write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(proof, ensure_ascii=False, indent=2))
assert all(hashes.values()) and reproduced and all(accounting.values()) and not changed
assert proof['model_turn_completed'] and proof['temporary_credentials_removed'] and reflections > 0
