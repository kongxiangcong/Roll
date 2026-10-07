"""Finite account holdings and explicitly added watch members, never a stock screener."""
import json
import re
import hashlib
from datetime import datetime
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from roll.accounts.ledger import encode, now, timestamp
from roll.market.rules import BACKGROUND_INDICES, RuleCalendar, SHANGHAI


class WatchCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    operation: str
    instrument: str
    expected_list_version: int = Field(ge=0)


class IdentityCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    instrument: str = Field(pattern=r'^(SSE|SZSE|BSE):\d{6}$')
    exchange: Literal['SSE', 'SZSE', 'BSE']
    board: str = Field(min_length=1, max_length=40)
    instrument_type: Literal['STOCK', 'OTHER']
    name: str = Field(min_length=1, max_length=80)
    basis: str = Field(min_length=1, max_length=1000)
    effective_at: str


class ScopeCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    instruments: list[str] = Field(min_length=1)
    purpose: Literal['OBSERVATION', 'RESEARCH', 'BACKGROUND']


class MarketDirectory:
    def __init__(self, ledger):
        self.ledger = ledger
        self.rules = RuleCalendar(ledger)
        with ledger.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS market_watch(instrument TEXT PRIMARY KEY, added_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS market_versions(version INTEGER PRIMARY KEY, snapshot TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS market_watch_events(id INTEGER PRIMARY KEY, event TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS market_identities(revision INTEGER PRIMARY KEY, instrument TEXT NOT NULL, identity TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS market_account_memberships(account_version INTEGER PRIMARY KEY, snapshot TEXT NOT NULL);
            ''')

    def _record_account_memberships(self, db):
        """Catch up unseen confirmations once; never backfill later identity knowledge."""
        seen = db.execute('SELECT COALESCE(MAX(account_version),0) FROM market_account_memberships').fetchone()[0]
        accounts = self.ledger.versions(after=seen, db=db)
        if not accounts:
            return
        events = [json.loads(r[0]) for r in db.execute('SELECT event FROM market_watch_events ORDER BY id')]
        identities = [json.loads(r[0]) for r in db.execute('SELECT identity FROM market_identities ORDER BY revision')]
        for account in accounts:
            known_at = datetime.fromisoformat(account['confirmed_at'])
            watch = set()
            for event in events:
                if datetime.fromisoformat(event['recorded_at']) <= known_at:
                    if event['operation'] == 'ADD':
                        watch.add(event['instrument'])
                    else:
                        watch.discard(event['instrument'])
            known = {f"{i['exchange']}:{i['code']}": i for i in identities
                     if datetime.fromisoformat(i['confirmed_at']) <= known_at}
            held = {p['instrument'] for p in account['positions']}
            snapshot = {'account_version': account['version'], 'confirmed_at': account['confirmed_at'],
                'effective_at': account['effective_at'], 'materialized_at': now(),
                'basis': 'CONFIRMED_ACCOUNT_VERSION',
                'members': [{'instrument': instrument, 'held': instrument in held,
                             'watched': instrument in watch, 'identity': known.get(instrument)}
                            for instrument in sorted(held | watch)]}
            db.execute('INSERT INTO market_account_memberships VALUES(?,?)', (account['version'], encode(snapshot)))

    def _publish(self, db):
        self._record_account_memberships(db)
        account = self.ledger.account(db=db)
        holdings = {p['instrument']: p for p in account['positions']}
        watch = {r['instrument']: r['added_at'] for r in db.execute('SELECT * FROM market_watch')}
        instruments = sorted(holdings.keys() | watch.keys())
        on = datetime.now(SHANGHAI).date()
        identities = {r['instrument']: json.loads(r['identity']) for r in db.execute(
            'SELECT * FROM market_identities ORDER BY revision')}
        members = []
        for instrument in instruments:
            exchange, code = instrument.split(':')
            identity = identities.get(instrument, {'exchange': exchange, 'code': code,
                'board': 'UNKNOWN', 'instrument_type': 'UNKNOWN', 'name': None, 'source': None})
            rule = self.rules.rule(exchange, identity['board'], identity['instrument_type'], on)
            permission = next((p for p in account['permission_profile'] if
                p['market'] == exchange and p['board'] == identity['board']), {'status': 'UNKNOWN', 'basis': '账户未确认该范围'})
            limitations = ['CURRENT_STATUS_UNKNOWN', 'MODEL_QUALIFICATION_NOT_GRANTED']
            if identity['board'] == 'UNKNOWN':
                limitations.append('IDENTITY_UNKNOWN')
            if rule['implementation_status'] != 'ADAPTED':
                limitations.append('RULE_UNSUPPORTED')
            if permission['status'] != 'OPEN':
                limitations.append('ACCOUNT_PERMISSION_' + permission['status'])
            members.append({'instrument': instrument, 'holding': holdings.get(instrument),
                'watched': instrument in watch, 'watch_added_at': watch.get(instrument),
                'identity': identity, 'rule': rule, 'account_permission': permission,
                'current_status': {'state': 'UNKNOWN', 'source': None, 'as_of': None,
                    'reason': '尚未取得该证券当前停牌、风险警示、上市阶段与除权证据'},
                'model_qualification': 'NOT_GRANTED', 'new_trade_use': 'RESTRICTED', 'limitations': limitations})
        content = {'account_version': account['version'], 'as_of_date': on.isoformat(), 'members': members,
            'limit': 20, 'over_limit': len(instruments) > 20,
            'background_indices': BACKGROUND_INDICES,
            'formal_judgment': 'DISABLED'}
        row = db.execute('SELECT snapshot FROM market_versions ORDER BY version DESC LIMIT 1').fetchone()
        old = json.loads(row[0]) if row else None
        if old and {k: v for k, v in old.items() if k not in {'version', 'recorded_at'}} == content:
            return old
        result = {**content, 'version': old['version'] + 1 if old else 1, 'recorded_at': now()}
        db.execute('INSERT INTO market_versions VALUES(?,?)', (result['version'], encode(result)))
        return result

    def listing(self, version=None):
        with self.ledger.connection() as db:
            if version is not None:
                row = db.execute('SELECT snapshot FROM market_versions WHERE version=?', (version,)).fetchone()
                if row is None:
                    raise HTTPException(404, '名单版本不存在')
                return json.loads(row[0])
            db.execute('BEGIN IMMEDIATE')
            try:
                result = self._publish(db)
                db.commit()
                return result
            except BaseException:
                db.rollback()
                raise

    def watch(self, command: WatchCommand):
        if command.operation not in {'ADD', 'REMOVE'} or not re.fullmatch(r'(?:SSE|SZSE|BSE):\d{6}', command.instrument):
            raise HTTPException(422, '关注需明确交易所:六位代码，操作为 ADD 或 REMOVE')
        if command.instrument in {i['instrument'] for i in BACKGROUND_INDICES}:
            raise HTTPException(422, '指数只作固定背景/基准，不加入个股关注或取得交易能力')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                current = self._publish(db)
                if current['version'] != command.expected_list_version:
                    raise HTTPException(409, {'code': 'LIST_VERSION_CONFLICT', 'current_list_version': current['version']})
                if command.operation == 'ADD':
                    if command.instrument not in {m['instrument'] for m in current['members']} and len(current['members']) >= 20:
                        raise HTTPException(409, {'code': 'WATCH_LIMIT', 'limit': 20, 'message': '名单达到20只，已有资产仍完整展示'})
                    db.execute('INSERT OR IGNORE INTO market_watch VALUES(?,?)', (command.instrument, now()))
                else:
                    db.execute('DELETE FROM market_watch WHERE instrument=?', (command.instrument,))
                result = self._publish(db)
                db.execute('INSERT INTO market_watch_events(event) VALUES(?)', (encode({
                    'operation': command.operation, 'instrument': command.instrument,
                    'list_version': result['version'], 'recorded_at': now()}),))
                db.commit()
                return result
            except BaseException:
                db.rollback()
                raise

    def identify(self, command: IdentityCommand):
        if command.instrument in {i['instrument'] for i in BACKGROUND_INDICES}:
            raise HTTPException(422, '固定背景指数不取得普通股票身份或交易能力')
        if command.instrument.split(':')[0] != command.exchange:
            raise HTTPException(422, '身份交易所必须与明确证券标识一致')
        if not command.basis.strip() or not command.name.strip() or not command.board.strip():
            raise HTTPException(422, '证券身份与确认依据不能为空')
        effective_at = timestamp(command.effective_at)
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                current = self._publish(db)
                if command.instrument not in {m['instrument'] for m in current['members']}:
                    raise HTTPException(403, {'code': 'OUTSIDE_FINITE_LIST'})
                identity = {'exchange': command.exchange, 'code': command.instrument.split(':')[1],
                    'board': command.board.strip(), 'instrument_type': command.instrument_type,
                    'name': command.name.strip(), 'effective_at': effective_at, 'confirmed_at': now(),
                    'source': {'kind': 'USER_CONFIRMED', 'basis': command.basis.strip(),
                               'sha256': hashlib.sha256(encode(command.model_dump()).encode()).hexdigest()}}
                cursor = db.execute('INSERT INTO market_identities(instrument,identity) VALUES(?,?)', (command.instrument, encode(identity)))
                identity['revision'] = cursor.lastrowid
                db.execute('UPDATE market_identities SET identity=? WHERE revision=?', (encode(identity), identity['revision']))
                result = self._publish(db)
                db.commit()
                return result
            except BaseException:
                db.rollback()
                raise

    def check_scope(self, command: ScopeCommand):
        current = self.listing()
        available = ({i['instrument'] for i in BACKGROUND_INDICES} if command.purpose == 'BACKGROUND'
                     else {m['instrument'] for m in current['members']} - {i['instrument'] for i in BACKGROUND_INDICES})
        rejected = sorted(set(command.instruments) - available)
        if rejected:
            raise HTTPException(403, {'code': 'OUTSIDE_FINITE_LIST', 'instruments': rejected,
                                     'message': '只允许当前持仓/关注或明确预定的背景指数，不扩大全市场'})
        return {'allowed': True, 'instruments': command.instruments, 'purpose': command.purpose,
                'list_version': current['version'], 'account_version': current['account_version'],
                'model_qualification': 'NOT_GRANTED', 'trading_capability': 'NONE'}

    def history(self):
        self.listing()
        with self.ledger.connection() as db:
            return {'versions': [json.loads(r[0]) for r in db.execute('SELECT snapshot FROM market_versions ORDER BY version DESC')],
                    'watch_events': [json.loads(r[0]) for r in db.execute('SELECT event FROM market_watch_events ORDER BY id DESC')],
                    'account_membership_history': [json.loads(r[0]) for r in db.execute(
                        'SELECT snapshot FROM market_account_memberships ORDER BY account_version DESC')]}
