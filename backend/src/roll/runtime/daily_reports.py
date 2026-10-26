"""Append-only daily reports over frozen account and source versions; no model advice."""
import hashlib
import json
import math
import statistics
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from uuid import uuid4
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, AnyHttpUrl
from roll.accounts.ledger import encode, now
from roll.accounts.valuation import ValuationRequest, fees
from roll.market.rules import SHANGHAI

VERSION = 'daily-report-v1'


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def market_metrics(bars):
    """20 consecutive supplied daily observations, raw index price (not total return)."""
    ordered = sorted(bars, key=lambda b: b['trade_date'])
    usable = [b for b in ordered if number(b.get('close')) is not None and number(b['close']) > 0]
    empty = {'status': 'UNKNOWN', 'value': None, 'reason': 'NEED_20_COMPLETE_INDEX_BARS'}
    result = {'through': usable[-1]['trade_date'] if usable else None,
              'trend': dict(empty), 'activity': dict(empty), 'risk': dict(empty),
              'basis': 'RAW_INDEX_PRICE_NOT_TOTAL_RETURN', 'bar_count': len(usable),
              'source_refs': [{'snapshot_id': b.get('snapshot_id'), 'raw_hash': b.get('raw_hash'),
                               'trade_date': b['trade_date'], 'available_at': b.get('available_at')} for b in usable[-21:]]}
    if len(usable) < 20: return result
    prices = [float(b['close']) for b in usable[-20:]]
    result['trend'] = {'status': 'KNOWN', 'value': (prices[-1]/statistics.mean(prices)-1)*100,
                       'unit': 'PERCENT_VS_MA20'}
    # Same raw amount field/unit for every observation; volume is not turnover.
    amounts = [number(b.get('amount_yuan')) for b in usable[-21:]]
    if len(amounts) == 21 and all(v is not None and v >= 0 for v in amounts) and statistics.mean(amounts[:-1]) > 0:
        result['activity'] = {'status': 'KNOWN', 'value': amounts[-1]/statistics.mean(amounts[:-1]),
                              'unit': 'TURNOVER_VS_PREVIOUS_20_MEAN'}
    else: result['activity'] = {'status': 'UNKNOWN', 'value': None, 'reason': 'NEED_21_COMPARABLE_AMOUNT_YUAN_BARS'}
    if len(usable) >= 21:
        closes = [float(b['close']) for b in usable[-21:]]
        returns = [closes[i]/closes[i-1]-1 for i in range(1, len(closes))]
        peak = closes[0]; drawdown = 0
        for close in closes:
            peak = max(peak, close); drawdown = min(drawdown, close/peak-1)
        result['risk'] = {'status': 'KNOWN', 'value': statistics.stdev(returns)*math.sqrt(252)*100,
                          'unit': 'ANNUALIZED_VOLATILITY_PERCENT_20_RETURNS',
                          'max_drawdown_percent': drawdown*100}
    return result


class NoteCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    idempotency_key: str = Field(min_length=1, max_length=128)
    report_id: str
    instrument: str
    thesis: str = Field(min_length=1, max_length=2000)
    invalidation: str = Field(min_length=1, max_length=2000)
    outcome: Literal['WATCH', 'ACTED', 'NO_ACTION', 'REVIEWED'] = 'WATCH'
    comparator: Literal['ABOVE', 'BELOW'] | None = None
    threshold: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    due_date: date | None = None
    parent_note_id: str | None = None
    fill_record_id: str | None = None


class BreadthCommand(BaseModel):
    """Explicit imported market summary, never silently called an official acquisition."""
    model_config = ConfigDict(extra='forbid')
    source_url: AnyHttpUrl
    observed_at: datetime
    trade_date: date
    universe: Literal['SSE_SZSE_A']
    universe_count: int = Field(gt=0, le=20000)
    advancing: int = Field(ge=0)
    declining: int = Field(ge=0)
    unchanged: int = Field(ge=0)
    basis: str = Field(min_length=1, max_length=2000)


class DailyReports:
    def __init__(self, ledger, market, reviews, valuations, updates, financial, news):
        self.ledger, self.market, self.reviews = ledger, market, reviews
        self.valuations, self.updates, self.financial, self.news = valuations, updates, financial, news
        with ledger.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS daily_reports(id TEXT PRIMARY KEY,day TEXT,revision INTEGER,input_hash TEXT,value TEXT,UNIQUE(day,revision));
                CREATE TABLE IF NOT EXISTS daily_notes(id TEXT PRIMARY KEY,key TEXT UNIQUE,command_hash TEXT,value TEXT);
                CREATE TABLE IF NOT EXISTS daily_breadth(id TEXT PRIMARY KEY,value TEXT);
            ''')

    def history(self, limit=30):
        with self.ledger.connection() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT value FROM daily_reports ORDER BY rowid DESC LIMIT ?', (limit,))]

    def get(self, identifier):
        with self.ledger.connection() as db:
            row = db.execute('SELECT value FROM daily_reports WHERE id=?', (identifier,)).fetchone()
        if not row: raise HTTPException(404, 'DAILY_REPORT_NOT_FOUND')
        value = json.loads(row[0])
        if digest(value['inputs']) != value['input_sha256']: raise HTTPException(409, 'DAILY_REPORT_INPUT_CORRUPT')
        return value

    def notes(self):
        with self.ledger.connection() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT value FROM daily_notes ORDER BY rowid')]

    def note(self, command):
        value = command.model_dump(mode='json'); hashed = digest(value)
        report = self.get(command.report_id)
        if not command.thesis.strip() or not command.invalidation.strip(): raise HTTPException(422, 'NOTE_TEXT_REQUIRED')
        if command.instrument not in {m['instrument'] for m in report['inputs']['listing']['members']}:
            raise HTTPException(422, 'NOTE_INSTRUMENT_NOT_IN_REPORT')
        if (command.comparator is None) != (command.threshold is None): raise HTTPException(422, 'CONDITION_PAIR_REQUIRED')
        if command.fill_record_id and command.fill_record_id not in {f['record_id'] for f in self.ledger.account().get('fills', []) if f['instrument']==command.instrument}:
            raise HTTPException(422, 'CONFIRMED_FILL_NOT_FOUND')
        if command.outcome == 'ACTED' and not command.fill_record_id: raise HTTPException(422, 'ACTED_REQUIRES_CONFIRMED_FILL')
        if command.parent_note_id and not any(n['note_id']==command.parent_note_id and n['instrument']==command.instrument for n in self.notes()):
            raise HTTPException(422, 'PARENT_NOTE_NOT_FOUND')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior = db.execute('SELECT command_hash,value FROM daily_notes WHERE key=?', (command.idempotency_key,)).fetchone()
            if prior:
                if prior[0]!=hashed: raise HTTPException(409, 'NOTE_IDEMPOTENCY_CONFLICT')
                return json.loads(prior[1])
            result = {**value, 'note_id': str(uuid4()), 'recorded_at': now(), 'authority': 'USER_JUDGMENT_NOT_SYSTEM_ADVICE'}
            db.execute('INSERT INTO daily_notes VALUES(?,?,?,?)', (result['note_id'],command.idempotency_key,hashed,encode(result)))
            db.commit()
            return result

    def import_breadth(self, command):
        stamp = datetime.fromisoformat(now())
        if command.observed_at.tzinfo is None or command.observed_at > stamp or command.trade_date > command.observed_at.astimezone(SHANGHAI).date():
            raise HTTPException(422, 'BREADTH_TIME_INVALID')
        count = command.advancing+command.declining+command.unchanged
        if count > command.universe_count: raise HTTPException(422, 'BREADTH_COUNTS_EXCEED_UNIVERSE')
        value = command.model_dump(mode='json')
        identifier = digest(value)
        result = {**value, 'breadth_id': identifier, 'recorded_at': now(), 'source_kind': 'USER_IMPORTED_UNVERIFIED',
                  'covered_count': count, 'coverage_percent': count/command.universe_count*100,
                  'advancing_percent': command.advancing/count*100 if count else None,
                  'status': 'IMPORTED' if count==command.universe_count else 'PARTIAL', 'independent_verification': False}
        with self.ledger.connection() as db:
            db.execute('INSERT OR IGNORE INTO daily_breadth VALUES(?,?)', (identifier,encode(result)))
            return json.loads(db.execute('SELECT value FROM daily_breadth WHERE id=?',(identifier,)).fetchone()[0])

    def publish(self):
        stamp = datetime.fromisoformat(now()); day = stamp.astimezone(SHANGHAI).date().isoformat()
        listing = self.market.listing(); account = self.ledger.account(listing['account_version'])
        rows, observations, gaps, versions = self.reviews.facts_at(listing, stamp)
        news, financial, jobs, failures = {}, {}, {}, []
        for member in listing['members']:
            instrument = member['instrument']
            try:
                value = self.news.listing(instrument, known_by=stamp)
                news[instrument] = {k:value[k] for k in ['facts','events','unique_event_count','reprint_count','revision_count']}
            except Exception as error: failures.append({'instrument':instrument,'module':'NEWS','error':str(getattr(error,'detail',type(error).__name__))})
            try:
                content=self.financial.build(instrument, known_by=stamp)
                stable={k:v for k,v in content.items() if k not in {'known_by','created_at','input_sha256'}}
                content['input_sha256']=digest({'daily_report_day':day,'content':stable})
                financial[instrument]=self.financial.store(instrument,content)
            except Exception as error: failures.append({'instrument':instrument,'module':'FINANCIAL','error':str(getattr(error,'detail',type(error).__name__))})
            try:
                status = self.updates.listing(instrument)
                jobs[instrument] = {kind:next((j for j in status['jobs'] if j['command']['kind']==kind),None) for kind in ['MARKET','FINANCIAL','NEWS']}
            except HTTPException as error: failures.append({'instrument':instrument,'module':'UPDATES','error':str(error.detail)})
        backgrounds = {i['instrument'] for i in listing['background_indices'] if i['purpose']=='BROAD_BACKGROUND'}
        daily = {i:{} for i in backgrounds}
        for snapshot in reversed(self.reviews.evidence.snapshots(group='DAILY', available_before=stamp)):
            for bar in snapshot['facts']:
                if bar['instrument'] in daily and bar.get('trade_date','9999')<=day and bar.get('adjustment')=='RAW' and bar.get('completion_state','').startswith('COMPLETE') and not bar.get('errors'):
                    daily[bar['instrument']][bar['trade_date']] = {**bar,'snapshot_id':snapshot['snapshot_id'],'evidence_kind':snapshot['evidence_kind']}
        metrics = {i:market_metrics(list(bars.values())) for i,bars in sorted(daily.items())}
        # Do not conceal missing trading sessions inside a rolling window.
        for instrument, metric in metrics.items():
            bars=sorted(daily[instrument].values(), key=lambda b:b['trade_date'])[-21:]
            if len(bars)>=20:
                from datetime import timedelta
                cursor=date.fromisoformat(bars[0]['trade_date']);end=date.fromisoformat(bars[-1]['trade_date']);seen={b['trade_date'] for b in bars};missing=False
                while cursor<=end:
                    calendar=self.market.rules.calendar(instrument.split(':')[0],cursor)
                    if calendar['is_trading_day'] is None or calendar['is_trading_day'] and cursor.isoformat() not in seen:missing=True
                    cursor+=timedelta(days=1)
                if missing:
                    for name in ['trend','activity','risk']:metric[name]={'status':'UNKNOWN','value':None,'reason':'INDEX_SESSION_GAPS_OR_CALENDAR_UNKNOWN'}
        with self.ledger.connection() as db:
            breadths=[json.loads(r[0]) for r in db.execute('SELECT value FROM daily_breadth ORDER BY rowid DESC')]
        breadth=next((b for b in breadths if b['trade_date']==day),{'status':'UNKNOWN','advancing_percent':None,'coverage_percent':None,'reason':'NO_FULL_MARKET_SOURCE; WATCHLIST_IS_NOT_MARKET_BREADTH'})
        notes = self.notes()
        inputs={'version':VERSION,'day':day,'account':account,'listing':listing,'market_rows':rows,
                'market_versions':versions,'observations':observations,'gaps':gaps,'news':news,'financial':financial,
                'jobs':jobs,'indices':metrics,'breadth':breadth,'notes':notes,'module_errors':failures}
        # Financial observations have stable IDs and source cutoffs. No fresh wall time in the input hash.
        hashed=digest(inputs)
        previous=self.history(1)
        if previous and previous[0]['day']==day and previous[0]['input_sha256']==hashed:return self.get(previous[0]['report_id'])
        valuation=None
        report_errors=list(failures)
        if account['version']:
            try:
                basis=self.valuations.basis()
                valuation=self.valuations.publish(ValuationRequest(**{k:basis[k] for k in ['baseline_account_version','origin_at','scope_kind','scope_id']},as_of=stamp.isoformat(),known_by=stamp.isoformat()))
                if valuation['account_version']!=account['version']:raise HTTPException(409,'ACCOUNT_CHANGED_RETRY_REPORT')
            except HTTPException as error:
                if error.detail=='ACCOUNT_CHANGED_RETRY_REPORT':raise
                report_errors.append({'module':'VALUATION','error':str(error.detail)})
        conditions=[]
        reviewed={n['parent_note_id'] for n in notes if n.get('parent_note_id')}
        for note in notes:
            if note['note_id'] in reviewed:continue
            row=next((r for r in rows if r['instrument']==note['instrument']),{})
            fact=row.get('last_complete_daily') or {}
            close=number(fact.get('close'));state='MANUAL_REVIEW'
            if note.get('comparator'):
                state='UNKNOWN' if close is None or fact.get('trade_date')!=day else 'TRIGGERED' if (close>=note['threshold'] if note['comparator']=='ABOVE' else close<=note['threshold']) else 'NOT_TRIGGERED'
            if note.get('due_date') and note['due_date']<=day:state='DUE_FOR_REVIEW'
            conditions.append({'note_id':note['note_id'],'instrument':note['instrument'],'thesis':note['thesis'],
                'invalidation':note['invalidation'],'state':state,'price_basis':fact or None,'outcome':note['outcome']})
        event_ids={f['fact_id'] for n in (previous[0]['inputs']['news'].values() if previous else []) for f in n['facts']}
        new_events=[f for n in news.values() for f in n['facts'] if f['fact_id'] not in event_ids]
        change={'comparison_report_id':previous[0]['report_id'] if previous else None,'net_asset_change':None,'external_net_flow':None,'investment_change_after_flow':None}
        if previous:
            old=previous[0];before=(old.get('valuation') or {}).get('cash_plus_holdings');after=(valuation or {}).get('cash_plus_holdings')
            if before is not None and after is not None:
                delta=Decimal(after)-Decimal(before)
                flow=(Decimal(account.get('external_cash_in','0'))-Decimal(old['inputs']['account'].get('external_cash_in','0')))-(Decimal(account.get('external_cash_out','0'))-Decimal(old['inputs']['account'].get('external_cash_out','0')))
                change.update(net_asset_change=str(delta),external_net_flow=str(flow),investment_change_after_flow=str(delta-flow))
        result={'report_id':str(uuid4()),'day':day,'created_at':stamp.isoformat(),'known_by':stamp.isoformat(),
                'inputs':inputs,'input_sha256':digest(inputs),'valuation':valuation,'account_change':change,
                'new_events':new_events,'conditions':conditions,'module_errors':report_errors,
                'status':'PARTIAL' if gaps or failures or breadth['status']!='IMPORTED' else 'AVAILABLE',
                'authority':'OBSERVATION_ONLY','formal_advice':False,'previous_report_id':None}
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if self.ledger.account(db=db)['version']!=account['version']:raise HTTPException(409,'ACCOUNT_CHANGED_RETRY_REPORT')
            prior=db.execute('SELECT value FROM daily_reports ORDER BY rowid DESC LIMIT 1').fetchone()
            prior=json.loads(prior[0]) if prior else None
            if prior and prior['day']==day and prior['input_sha256']==result['input_sha256']:return prior
            if (prior or {}).get('report_id')!=(previous[0]['report_id'] if previous else None):raise HTTPException(409,'REPORT_CHANGED_RETRY')
            revision=db.execute('SELECT COALESCE(MAX(revision),0)+1 FROM daily_reports WHERE day=?',(day,)).fetchone()[0]
            result.update(revision=revision,edition='INITIAL' if revision==1 else 'UPDATE',previous_report_id=prior['report_id'] if prior else None)
            db.execute('INSERT INTO daily_reports VALUES(?,?,?,?,?)',(result['report_id'],day,revision,result['input_sha256'],encode(result)))
            db.commit()
        return result
