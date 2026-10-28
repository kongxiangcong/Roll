"""One durable stock + market + assessment + exploratory result. No account writes."""
import hashlib
import json
import os
import re
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from roll.accounts.ledger import encode, now
from roll.market.baostock import acquire, rows, FIELDS
from roll.research.exploratory import backtest


class AssistanceCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    end_date: str | None = None
    instrument: str = 'SSE:600362'
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator('instrument')
    @classmethod
    def supported(cls, value):
        # Existing exploratory execution assumptions support ordinary main-board A shares.
        if not re.fullmatch(r'(SSE:60[0135][0-9]{3}|SZSE:00[0-3][0-9]{3})', value):
            raise ValueError('SUPPORTED_MAIN_BOARD_A_SHARE_REQUIRED')
        return value



class ReflectionCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str = Field(min_length=1, max_length=4000)


class Assistance:
    worker = None

    def __init__(self, ledger):
        self.ledger = ledger
        self.lock = threading.Lock()
        self.active = {}
        with ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS assistance_runs(id TEXT PRIMARY KEY,value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS assistance_reflections(id TEXT PRIMARY KEY,run_id TEXT NOT NULL,value TEXT NOT NULL)')
            from roll.agents.codex_process import owner_alive, recover_directory
            for row in db.execute('SELECT value FROM assistance_runs').fetchall():
                run = json.loads(row[0])
                if run['status'] in {'RUNNING', 'CANCEL_REQUESTED'} and not owner_alive(run):
                    run.update(status='INTERRUPTED', finished_at=now())
                    if run.get('process', {}).get('task_root'):
                        run['recovery_cleanup'] = recover_directory(run)
                    db.execute('UPDATE assistance_runs SET value=? WHERE id=?', (encode(run), run['run_id']))

    def save(self, run):
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior = db.execute('SELECT value FROM assistance_runs WHERE id=?', (run['run_id'],)).fetchone()
            if prior and json.loads(prior[0]).get('cancel_requested'):
                run['cancel_requested'] = True
                run['status'] = 'CANCELLED' if run.get('finished_at') else 'CANCEL_REQUESTED'
                run.pop('assessment', None)
            db.execute('INSERT OR REPLACE INTO assistance_runs VALUES(?,?)', (run['run_id'], encode(run)))
            db.commit()

    def history(self):
        with self.ledger.connection() as db:
            result = [json.loads(r[0]) for r in db.execute('SELECT value FROM assistance_runs ORDER BY rowid DESC LIMIT 30')]
        return [{k: r.get(k) for k in ['run_id', 'instrument', 'started_at', 'finished_at', 'status', 'phase', 'as_of', 'error']} for r in result]

    def get(self, identifier):
        with self.ledger.connection() as db:
            r = db.execute('SELECT value FROM assistance_runs WHERE id=?', (identifier,)).fetchone()
            if not r:
                raise HTTPException(404, 'ASSISTANCE_NOT_FOUND')
            result = json.loads(r[0])
            result['reflections'] = [json.loads(v[0]) for v in db.execute('SELECT value FROM assistance_reflections WHERE run_id=? ORDER BY rowid', (identifier,))]
        return result

    def reflect(self, identifier, text):
        self.get(identifier)
        result = {'id': str(uuid4()), 'run_id': identifier, 'text': text, 'created_at': now()}
        with self.ledger.connection() as db:
            db.execute('INSERT INTO assistance_reflections VALUES(?,?,?)', (result['id'], identifier, encode(result)))
        return result

    def cancel(self, identifier):
        with self.lock, self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT value FROM assistance_runs WHERE id=?', (identifier,)).fetchone()
            if not row:
                raise HTTPException(404, 'ASSISTANCE_NOT_FOUND')
            run = json.loads(row[0])
            if run['status'] in {'RUNNING', 'CANCEL_REQUESTED'}:
                run.update(cancel_requested=True, status='CANCEL_REQUESTED')
                db.execute('UPDATE assistance_runs SET value=? WHERE id=?', (encode(run), identifier))
            db.commit()
            if run.get('cancel_requested') and identifier in self.active:
                self.active[identifier][0].set()
        return self.get(identifier)

    def start(self, command):
        local_now = datetime.now(ZoneInfo('Asia/Shanghai'))
        today = local_now.date()
        latest = today if local_now.hour >= 18 else today-timedelta(days=1)
        try:
            end = datetime.strptime(command.end_date, '%Y-%m-%d').date() if command.end_date else latest
        except ValueError:
            raise HTTPException(422, 'INVALID_END_DATE')
        if end > latest or end < today-timedelta(days=365):
            raise HTTPException(422, 'END_DATE_MUST_BE_COMPLETED_SESSION_WITHIN_ONE_YEAR')
        from roll.agents.codex_process import process_creation, owner_alive
        with self.lock, self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            request_hash = hashlib.sha256(encode({'instrument': command.instrument, 'end_date': command.end_date}).encode()).hexdigest()
            for row in db.execute('SELECT value FROM assistance_runs').fetchall():
                old = json.loads(row[0])
                if command.idempotency_key and old.get('idempotency_key') == command.idempotency_key:
                    if old.get('request_hash') != request_hash:
                        raise HTTPException(409, 'ASSISTANCE_IDEMPOTENCY_CONFLICT')
                    return old
            for row in db.execute('SELECT value FROM assistance_runs').fetchall():
                old = json.loads(row[0])
                if old['status'] in {'RUNNING', 'CANCEL_REQUESTED'}:
                    if owner_alive(old):
                        raise HTTPException(409, 'ASSISTANCE_ALREADY_RUNNING')
                    old.update(status='INTERRUPTED', finished_at=now())
                    db.execute('UPDATE assistance_runs SET value=? WHERE id=?', (encode(old), old['run_id']))
            run = {'run_id': str(uuid4()), 'kind': 'RESEARCH_ASSISTANCE', 'task_kind': 'RESEARCH_ASSESSMENT',
                'instrument': command.instrument, 'idempotency_key': command.idempotency_key, 'request_hash': request_hash,
                'status': 'RUNNING', 'phase': 'SOURCES', 'started_at': now(), 'as_of': end.isoformat(),
                'start_date': (end-timedelta(days=120)).isoformat(), 'sources': [], 'gaps': [], 'archives': [], 'tools': [],
                'host_owner': {'pid': os.getpid(), 'creation_ticks': process_creation(os.getpid())},
                'model': os.environ.get('ROLL_CODEX_MODEL', 'gpt-6.1-sol'), 'backend': 'CODEX',
                'limits': {'timeout_seconds': 150, 'runtime_operations': 8, 'tool_calls': 0},
                'account_context': 'UNKNOWN', 'formal_authority': False}
            root = Path(__file__).parents[1]
            run['code_hashes'] = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in
                ['runtime/assistance.py', 'research/exploratory.py', 'agents/assistance_runtime.py', 'agents/codex_process.py', 'agents/codex_worker.py', 'market/baostock.py', 'market/baostock_process.py']}
            db.execute('INSERT INTO assistance_runs VALUES(?,?)', (run['run_id'], encode(run)))
            db.commit()
            cancel = threading.Event()
            thread = threading.Thread(target=self.execute, args=(run, cancel), daemon=True)
            self.active[run['run_id']] = (cancel, thread)
        thread.start()
        return self.get(run['run_id'])

    @staticmethod
    def stock_symbol(run):
        instrument = run.get('instrument', 'SSE:600362')
        return ('sh.' if instrument.startswith('SSE:') else 'sz.') + instrument.split(':')[1]

    def source(self, run, symbol, cancel):
        stock = symbol == self.stock_symbol(run)
        fields = FIELDS if stock else 'date,code,open,high,low,close,preclose,volume,amount,pctChg'
        wire, result = acquire({'auth_mode': 'PUBLIC', 'group': 'DAILY', 'symbol': symbol, 'fields': fields,
            'start_date': run['start_date'], 'end_date': run['as_of']}, time.monotonic()+30, cancel, 2*1024*1024, 5)
        mapped = rows(result)
        if not mapped or any(r['code'] != symbol or not run['start_date'] <= r['date'] <= run['as_of'] for r in mapped):
            raise ValueError('SOURCE_IDENTITY_OR_DATE_RANGE_INVALID')
        days = [r['date'] for r in mapped]
        if days != sorted(set(days)):
            raise ValueError('SOURCE_DUPLICATE_OR_UNORDERED_DAYS')
        digest = hashlib.sha256(wire).hexdigest()
        directory = self.ledger.path.parent/'assistance-raw'
        directory.mkdir(exist_ok=True)
        (directory/(digest+'.bin')).write_bytes(wire)
        return {'source_id': symbol, 'provider': 'BaoStock PUBLIC', 'received_at': result['received_at'],
                'sha256': digest, 'sdk_version': result['sdk_distribution_version'], 'rows': mapped,
                'first_date': days[0], 'last_date': days[-1], 'row_count': len(mapped),
                'adjustment': 'RAW', 'price_unit': 'CNY' if stock else 'INDEX_POINT', 'volume_unit': 'SHARE',
                'historical_pit': False, 'request_start': run['start_date'], 'request_end': run['as_of']}

    def execute(self, run, cancel):
        try:
            for symbol in [self.stock_symbol(run), 'sh.000001', 'sh.000300', 'sz.399006']:
                if cancel.is_set():
                    raise ValueError('CANCELLED')
                try:
                    run['sources'].append(self.source(run, symbol, cancel))
                except Exception:
                    run['gaps'].append({'source_id': symbol, 'code': 'SOURCE_UNAVAILABLE'})
                self.save(run)
            stock = next((s for s in run['sources'] if s['source_id'] == self.stock_symbol(run)), None)
            if not stock:
                raise ValueError('CRITICAL_STOCK_PRICE_UNAVAILABLE')
            market = next((s for s in run['sources'] if s['source_id'] == 'sh.000001'), None)
            if cancel.is_set() or run.get('cancel_requested'):
                raise ValueError('CANCELLED')
            run['phase'] = 'BACKTEST'
            self.save(run)
            if market and [r['date'] for r in stock['rows']] == [r['date'] for r in market['rows']]:
                try:
                    run['backtest'] = backtest(stock['rows'])
                except ValueError as exc:
                    run['gaps'].append({'code': str(exc)})
            else:
                run['gaps'].append({'code': 'PRICE_CALENDAR_COVERAGE_UNVERIFIED_BACKTEST_REFUSED'})
            valid_until = (datetime.fromisoformat(stock['last_date'])+timedelta(days=1, hours=15)).isoformat()+'+08:00'
            material = {'instrument': run.get('instrument', 'SSE:600362'), 'as_of': stock['last_date'], 'valid_until': valid_until, 'account_context': 'UNKNOWN',
                'sources': [{**s, 'rows': s['rows'][-25:]} for s in run['sources']], 'gaps': run['gaps'],
                'backtest': {'source_id': 'backtest', **{k: v for k, v in run.get('backtest', {}).items() if k not in {'strategy', 'buy_hold'}}}}
            material['display_scope'] = '模型仅接收每源最后25行及回测摘要；完整日线、成交和净值另存于同一记录，不代表模型复核了全部历史。'
            if 'backtest' in run:
                material['backtest'].update({k: {a: b for a, b in run['backtest'][k].items() if a != 'nav'} for k in ['strategy', 'buy_hold']})
            run['material'] = material
            run['phase'] = 'MODEL'
            self.save(run)
            if cancel.is_set() or run.get('cancel_requested'):
                raise ValueError('CANCELLED')
            configured = os.environ.get('ROLL_CODEX_AUTH_FILE')
            if not configured:
                raise ValueError('CODEX_AUTH_NOT_CONFIGURED')
            auth = json.loads(Path(configured).read_text(encoding='utf-8'))
            if auth.get('auth_mode') != 'chatgpt' or not auth.get('tokens'):
                raise ValueError('CHATGPT_AUTH_REQUIRED')
            from roll.agents.codex_process import execute
            execute(self, run, material, cancel, auth)
            if run['status'] == 'COMPLETE' and (run['gaps'] or not run.get('backtest')):
                run['status'] = 'PARTIAL'
        except Exception as exc:
            run.update(status='PARTIAL' if run['sources'] else 'FAILED', error={'code': str(exc) if isinstance(exc, ValueError) and str(exc).replace('_', '').isalnum() else 'ASSISTANCE_EXECUTION_FAILED', 'type': type(exc).__name__})
        finally:
            if cancel.is_set() or run.get('cancel_requested'):
                run['status'] = 'CANCELLED'
                run.pop('assessment', None)
            run.update(finished_at=now(), phase='FINISHED')
            self.save(run)
            with self.lock:
                self.active.pop(run['run_id'], None)

    def close(self):
        with self.lock:
            active = list(self.active.values())
        for cancel, thread in active:
            cancel.set()
        for cancel, thread in active:
            thread.join(timeout=35)
