"""Bounded observation work on the existing review worker and its durable lease."""
import asyncio
import hashlib
import json
import time
import threading
from datetime import datetime, timedelta, time as wall_time
from typing import Literal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from roll.accounts.ledger import encode, now
from roll.agents.codex_process import owner_alive
from roll.market.rules import SHANGHAI
from roll.market.observation_symbols import symbols
from roll.market.directory import ScopeCommand
from roll.market.news_ingestion import NewsCommand
from roll.market.financial_income import IncomeCommand
from roll.market.evidence import DataRequest
from roll.market.sentiment import SentimentCommand
from roll.market.sentiment_series import SeriesCommand, VERSION as SERIES_VERSION

VERSION = 'observation-worker-v1'
TIMEOUT = 45
MODEL_TIMEOUT = 30
MAX_DAILY_ATTEMPTS = 3
RETRY_MINUTES = 15
RETRY_END = wall_time(21, 0)


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


class UpdateSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: int = Field(ge=1)
    basis: str = Field(min_length=1, max_length=2000)
    enabled: bool
    news_postclose: bool = False
    financial_postclose: bool = False
    market_postclose: bool = False
    news_refresh: bool = False
    classify: bool = False
    profile: Literal['legacy', 'finbert-adaptation-01'] = 'legacy'


class UpdateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    idempotency_key: str = Field(min_length=1, max_length=128)
    basis: str = Field(min_length=1, max_length=2000)
    kind: Literal['FINANCIAL', 'NEWS', 'MARKET']
    refresh_sources: bool = False


class ObservationUpdates:
    def __init__(self, reviews, financial, supplement, observations, news, sentiment, series, sources, notifications):
        self.reviews, self.ledger = reviews, reviews.ledger
        self.financial, self.supplement, self.observations = financial, supplement, observations
        self.news, self.sentiment, self.series = news, sentiment, series
        self.sources, self.notifications = sources, notifications
        with self.ledger.connection() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS observation_update_settings(instrument TEXT PRIMARY KEY,value TEXT);
                CREATE TABLE IF NOT EXISTS observation_update_jobs(id TEXT PRIMARY KEY,instrument TEXT,key TEXT,command_hash TEXT,value TEXT,UNIQUE(instrument,key));
                CREATE TABLE IF NOT EXISTS background_observations(id TEXT PRIMARY KEY,instrument TEXT,input_sha256 TEXT,value TEXT,UNIQUE(instrument,input_sha256));
                CREATE TABLE IF NOT EXISTS observation_update_health(id TEXT PRIMARY KEY,value TEXT);''')
            for row in db.execute('SELECT id,value FROM observation_update_jobs').fetchall():
                job = json.loads(row[1])
                if job['status'] == 'RUNNING' and not owner_alive(job):
                    job.update(status='INTERRUPTED', finished_at=now(), error='HOST_INTERRUPTED_NO_AUTOMATIC_RETRY')
                    db.execute('UPDATE observation_update_jobs SET value=? WHERE id=?', (encode(job), row[0]))

    def settings(self, instrument):
        try: symbols(instrument)
        except ValueError as error: raise HTTPException(409, str(error))
        with self.ledger.connection() as db:
            row = db.execute('SELECT value FROM observation_update_settings WHERE instrument=?', (instrument,)).fetchone()
        return {'financial_postclose': False, 'market_postclose': False, **json.loads(row[0])} if row else {'instrument': instrument, 'revision': 1, 'enabled': False,
            'financial_postclose': False, 'market_postclose': False,
            'news_postclose': False, 'news_refresh': False, 'classify': False, 'profile': 'legacy',
            'basis': '新增观察默认暂停，需显式配置；不改变来源开关或外部通知渠道', 'changed_at': None}

    def configure(self, instrument, command):
        self.settings(instrument)
        if not command.basis.strip():
            raise HTTPException(422, 'OBSERVATION_SETTINGS_BASIS_REQUIRED')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT value FROM observation_update_settings WHERE instrument=?', (instrument,)).fetchone()
            old = json.loads(row[0]) if row else self.settings(instrument)
            if old['revision'] != command.expected_revision:
                raise HTTPException(409, 'OBSERVATION_SETTINGS_REVISION_CONFLICT')
            value = {**command.model_dump(exclude={'expected_revision'}), 'instrument': instrument,
                'revision': old['revision']+1, 'changed_at': now()}
            db.execute('INSERT OR REPLACE INTO observation_update_settings VALUES(?,?)', (instrument, encode(value)))
            db.commit()
        return value

    def submit(self, instrument, command, scheduled=None, attempt=1, retry_of=None):
        settings = self.settings(instrument)
        self.reviews.market.check_scope(ScopeCommand(instruments=[instrument], purpose='OBSERVATION'))
        hashed = digest(command.model_dump())
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT command_hash,value FROM observation_update_jobs WHERE instrument=? AND key=?', (instrument, command.idempotency_key)).fetchone()
            if row:
                if row[0] != hashed:
                    raise HTTPException(409, 'OBSERVATION_UPDATE_IDEMPOTENCY_CONFLICT')
                return json.loads(row[1])
            if not settings['enabled']:
                raise HTTPException(409, 'OBSERVATION_UPDATES_PAUSED')
            if db.execute("SELECT count(*) FROM observation_update_jobs WHERE json_extract(value,'$.status') IN ('QUEUED','RUNNING')").fetchone()[0] >= 100:
                raise HTTPException(409, 'OBSERVATION_UPDATE_QUEUE_BOUND_EXCEEDED')
            job = {'job_id': str(uuid4()), 'instrument': instrument, 'command': command.model_dump(),
                'settings': settings, 'status': 'QUEUED', 'created_at': now(), 'started_at': None, 'finished_at': None,
                'scheduled_checkpoint': scheduled, 'scheduled_attempt': attempt, 'retry_of': retry_of, 'observation_id': None, 'error': None,
                'namespace': 'OBSERVATION_ONLY', 'forecast_archive_created': False, 'external_notification_enabled': False}
            db.execute('INSERT INTO observation_update_jobs VALUES(?,?,?,?,?)', (job['job_id'], instrument, command.idempotency_key, hashed, encode(job)))
            db.commit()
        return job

    def get(self, identifier):
        with self.ledger.connection() as db:
            row = db.execute('SELECT value FROM observation_update_jobs WHERE id=?', (identifier,)).fetchone()
        if not row:
            raise HTTPException(404, 'OBSERVATION_UPDATE_NOT_FOUND')
        return json.loads(row[0])

    def cancel(self, identifier):
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT value FROM observation_update_jobs WHERE id=?', (identifier,)).fetchone()
            if not row:
                raise HTTPException(404, 'OBSERVATION_UPDATE_NOT_FOUND')
            job = json.loads(row[0])
            if job['status'] in ('QUEUED', 'RUNNING'):
                job.update(status='CANCELLED', error='USER_CANCELLED', finished_at=now())
                db.execute('UPDATE observation_update_jobs SET value=? WHERE id=?', (encode(job), identifier))
            db.commit()
        return job

    def listing(self, instrument):
        settings = self.settings(instrument)
        with self.ledger.connection() as db:
            jobs = [json.loads(row[0]) for row in db.execute('SELECT value FROM observation_update_jobs WHERE instrument=? ORDER BY rowid DESC LIMIT 100', (instrument,))]
            observations = [json.loads(row[0]) for row in db.execute('SELECT value FROM background_observations WHERE instrument=? ORDER BY rowid DESC LIMIT 30', (instrument,))]
            health = {row[0].removeprefix(instrument+':'): json.loads(row[1]) for row in db.execute('SELECT id,value FROM observation_update_health') if row[0].startswith(instrument+':') or row[0] in ('MODULE','REPORT')}
        return {'settings': settings, 'jobs': jobs, 'observations': observations, 'health': health,
            'sources': [source for source in self.sources.listing() if source['id'] in ('akshare-news-em', 'akshare-financial-em', 'sohu-daily', 'sina-quote')],
            'checkpoint': 'Asia/Shanghai 15:05–21:00; current session only',
            'retry_policy': {'max_daily_attempts': MAX_DAILY_ATTEMPTS, 'minimum_minutes': RETRY_MINUTES, 'until': '21:00 Asia/Shanghai'}, 'timeout_seconds': TIMEOUT,
            'offline_coverage': self.reviews.coverage(), 'worker': self.reviews.health(),
            'forecast_backfill': False, 'external_notifications': 'IN_APP_ONLY_NO_CHANNEL_ACTIVATION'}

    def schedule(self, clock):
        local = clock.astimezone(SHANGHAI)
        if local.time().replace(tzinfo=None) < wall_time(15, 5) or local.time().replace(tzinfo=None) > RETRY_END:
            return
        day = local.date()
        for member in self.reviews.market.listing()['members']:
            instrument = member['instrument']
            try: settings = self.settings(instrument)
            except HTTPException: continue
            if not settings['enabled']: continue
            calendar = self.news.evidence.market.rules.calendar(instrument.split(':')[0], day, clock)
            if calendar['is_trading_day'] is not True: continue
            for kind, enabled, prefix in (
                ('NEWS', settings['news_postclose'], 'postclose:'),
                ('FINANCIAL', settings.get('financial_postclose', False), 'financial-postclose:'),
                ('MARKET', settings.get('market_postclose', False), 'market-postclose:'),
            ):
                if not enabled: continue
                base_key = prefix+day.isoformat()
                with self.ledger.connection() as db:
                    prior = [json.loads(row[0]) for row in db.execute(
                        'SELECT value FROM observation_update_jobs WHERE instrument=? AND (key=? OR key LIKE ?) ORDER BY rowid',
                        (instrument, base_key, base_key+':retry:%'))]
                attempt = len(prior)+1
                if attempt > MAX_DAILY_ATTEMPTS: continue
                if prior:
                    last = prior[-1]
                    if last['status'] in ('QUEUED','RUNNING'): continue
                    if last['status']=='CANCELLED' and last.get('error')!='RESOURCE_DEADLINE_EXCEEDED': continue
                    ready = last.get('source_ready', last['status']=='COMPLETE' and not any(r.get('status')=='PARTIAL' for r in last.get('result',[])))
                    if ready: continue
                    finished = last.get('finished_at')
                    if not finished or clock < datetime.fromisoformat(finished)+timedelta(minutes=RETRY_MINUTES): continue
                    # Respect provider pause/cooldown; a later worker tick can revisit.
                    sources = {'NEWS':['akshare-news-em'], 'FINANCIAL':['akshare-financial-em'], 'MARKET':['sohu-daily','sina-quote']}[kind]
                    if settings['news_refresh'] and any(self.sources.access(source,instrument) for source in sources): continue
                key = base_key if attempt==1 else base_key+':retry:'+str(attempt)
                try:
                    self.submit(instrument, UpdateRequest(idempotency_key=key, kind=kind,
                        refresh_sources=settings['news_refresh'], basis='已登记盘后观察检查点；当前在线观察，不补造离线预测'),
                        scheduled=datetime.combine(day, wall_time(15, 5), SHANGHAI).isoformat(),
                        attempt=attempt,retry_of=prior[-1]['job_id'] if prior else None)
                except HTTPException as error:
                    if error.status_code not in (403, 409): raise

    def health_write(self, key, value):
        with self.ledger.connection() as db:
            db.execute('INSERT OR REPLACE INTO observation_update_health VALUES(?,?)', (key, encode(value)))

    def consumption_epoch(self, instrument):
        instant = datetime.fromisoformat(now()).astimezone(SHANGHAI)
        day = instant.date() if instant.time().replace(tzinfo=None) >= wall_time(15, 5) else instant.date()-timedelta(days=1)
        basis = {}
        for _ in range(32):
            calendar = self.series.calendar(instrument.split(':')[0], day, basis)
            if calendar['is_trading_day'] is None:
                return 'CALENDAR_UNKNOWN:'+day.isoformat()
            if calendar['is_trading_day']:
                return datetime.combine(day, wall_time(15, 5), SHANGHAI).isoformat()
            day -= timedelta(days=1)
        return 'CHECKPOINT_LOOKBACK_LIMIT'

    def work(self, clock, stop):
        # Called only by the existing worker loop after it validates its lease.
        try:
            self.schedule(clock)
            members = {m['instrument'] for m in self.reviews.market.listing()['members']}
            with self.ledger.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                rows = db.execute("SELECT id,value FROM observation_update_jobs WHERE json_extract(value,'$.status')='QUEUED' ORDER BY rowid").fetchall()
                job = None
                for identifier, raw in rows:
                    value = json.loads(raw)
                    if value['instrument'] not in members or not self.settings(value['instrument'])['enabled']:
                        value.update(status='CANCELLED', finished_at=now(), error='OBSERVATION_UPDATES_PAUSED')
                        db.execute('UPDATE observation_update_jobs SET value=? WHERE id=?', (encode(value), identifier))
                        continue
                    health = db.execute('SELECT value FROM observation_update_health WHERE id=?', (value['instrument']+':'+value['command']['kind'],)).fetchone()
                    if health and datetime.fromisoformat(json.loads(health[0])['retry_after']) > clock:
                        continue
                    job = value
                    job.update(status='RUNNING', started_at=now(), host_owner=self.reviews.owner)
                    db.execute('UPDATE observation_update_jobs SET value=? WHERE id=?', (encode(job), identifier))
                    break
                db.commit()
            if job:
                asyncio.run(self.execute(job, stop))
            if getattr(self, 'daily_reports', None) and not stop.is_set():
                # Existing lease owns this loop. Snapshot only after a task, or
                # once a minute while enabled; unchanged inputs reuse the report.
                local=clock.astimezone(SHANGHAI)
                due=local.time().replace(tzinfo=None)>=wall_time(15,5)
                if job or due and time.monotonic()-getattr(self,'last_report_check',0)>=60:
                    self.last_report_check=time.monotonic()
                    with self.ledger.connection() as db:
                        enabled=db.execute("SELECT 1 FROM observation_update_settings WHERE json_extract(value,'$.enabled')=1 LIMIT 1").fetchone()
                    if enabled:
                        try: self.daily_reports.publish()
                        except Exception as error:
                            self.health_write('REPORT', {'error':str(getattr(error,'detail',type(error).__name__)), 'at':now(), 'retry_after':(clock+timedelta(minutes=1)).isoformat()})
        except Exception as error:
            # This optional module cannot stop market/account/forward task chains.
            self.health_write('MODULE', {'error': type(error).__name__, 'at': now(), 'retry_after': (clock+timedelta(minutes=5)).isoformat()})

    async def execute(self, job, stop):
        task = asyncio.create_task(self.prepare(job))
        started = time.monotonic()
        reason = None
        while not task.done():
            await asyncio.wait({task}, timeout=.1)
            if stop.is_set() or self.get(job['job_id'])['status'] == 'CANCELLED' or not self.settings(job['instrument'])['enabled']:
                reason = 'CANCELLED_OR_PAUSED'
            elif time.monotonic()-started > TIMEOUT:
                reason = 'RESOURCE_DEADLINE_EXCEEDED'
            if reason:
                task.cancel()
                break
        try:
            prepared = await task
            if reason:
                raise asyncio.CancelledError()
            with self.ledger.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                current = json.loads(db.execute('SELECT value FROM observation_update_jobs WHERE id=?', (job['job_id'],)).fetchone()[0])
                if current['status'] == 'CANCELLED':
                    return
                configured = db.execute('SELECT value FROM observation_update_settings WHERE instrument=?', (job['instrument'],)).fetchone()
                if not configured or not json.loads(configured[0])['enabled']:
                    current.update(status='CANCELLED', finished_at=now(), error='OBSERVATION_UPDATES_PAUSED')
                    db.execute('UPDATE observation_update_jobs SET value=? WHERE id=?', (encode(current), job['job_id']))
                    db.commit()
                    return
                row = db.execute('SELECT value FROM background_observations WHERE instrument=? AND input_sha256=?', (job['instrument'], prepared['input_sha256'])).fetchone()
                observation = json.loads(row[0]) if row else {'observation_id': str(uuid4()), 'created_at': now(), **prepared}
                if not row:
                    db.execute('INSERT INTO background_observations VALUES(?,?,?,?)', (observation['observation_id'], job['instrument'], observation['input_sha256'], encode(observation)))
                    if observation['meaningful']:
                        self.notifications.observation_updated(db, observation)
                job.update(status='PARTIAL' if prepared['errors'] else 'COMPLETE', finished_at=now(), observation_id=observation['observation_id'],
                    cache_reused=row is not None, result=prepared['receipts'], errors=prepared['errors'], source_ready=prepared.get('source_ready',False), readiness=prepared.get('readiness','UNKNOWN'))
                db.execute('UPDATE observation_update_jobs SET value=? WHERE id=?', (encode(job), job['job_id']))
                db.commit()
            if prepared['errors']:
                self.health_write(job['instrument']+':'+job['command']['kind'], {'error': prepared['errors'], 'at': now(), 'retry_after': (datetime.fromisoformat(now())+timedelta(minutes=5)).isoformat()})
        except (Exception, asyncio.CancelledError) as error:
            with self.ledger.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                current = json.loads(db.execute('SELECT value FROM observation_update_jobs WHERE id=?', (job['job_id'],)).fetchone()[0])
                # An explicit persisted cancellation wins over a concurrent failure.
                if current['status'] != 'RUNNING':
                    return
                configured = db.execute('SELECT value FROM observation_update_settings WHERE instrument=?', (job['instrument'],)).fetchone()
                paused = not configured or not json.loads(configured[0])['enabled']
                current.update(status='CANCELLED' if reason or paused else 'FAILED', finished_at=now(),
                    error='OBSERVATION_UPDATES_PAUSED' if paused else reason or str(getattr(error, 'detail', type(error).__name__))[:300])
                db.execute('UPDATE observation_update_jobs SET value=? WHERE id=?', (encode(current), job['job_id']))
                db.commit()
            if current['status'] == 'FAILED' or reason == 'RESOURCE_DEADLINE_EXCEEDED':
                self.health_write(job['instrument']+':'+job['command']['kind'], {'error': current['error'], 'at': now(), 'retry_after': (datetime.fromisoformat(now())+timedelta(minutes=5)).isoformat()})

    async def refresh(self, service, job, source_id, receipts, errors):
        if not job['command']['refresh_sources']:
            receipts.append({'source': source_id, 'refresh': 'NOT_REQUESTED_SAVED_FACTS_ONLY'})
            return
        denied = self.sources.access(source_id, job['instrument'])
        if denied:
            errors.append(source_id+':'+denied)
            return
        table = getattr(service, 'run_table', 'news_runs')
        with self.ledger.connection() as db:
            runs = [json.loads(row[0]) for row in db.execute(f'SELECT value FROM {table} WHERE instrument=? ORDER BY rowid DESC', (job['instrument'],))]
        complete = next((run for run in runs if run['status'] in ('COMPLETE', 'PARTIAL', 'EMPTY') and run.get('finished_at')), None)
        current = datetime.fromisoformat(now())
        completed = datetime.fromisoformat(complete['finished_at']) if complete else None
        fresh = completed and (
            current-completed < timedelta(minutes=15) if source_id == 'akshare-news-em'
            else current.astimezone(SHANGHAI).date() == completed.astimezone(SHANGHAI).date())
        retry_partial = job.get('scheduled_attempt',1)>1 and complete and complete['status']=='PARTIAL'
        if complete and fresh and not retry_partial:
            receipts.append({'source': source_id, 'run_id': complete['run_id'], 'status': complete['status'],
                'refresh': 'CACHE_FRESH_BY_ACTUAL_SOURCE_RUN', 'source_finished_at': complete['finished_at']})
            return
        try:
            command = {'idempotency_key': 'observation:'+job['job_id']+':'+table, 'basis': job['command']['basis']}
            run = await service.collect(job['instrument'], NewsCommand(**command) if table == 'news_runs' else IncomeCommand(**command))
            receipts.append({'source': source_id, 'run_id': run['run_id'], 'status': run['status'], 'network_calls': run.get('network_calls', 0), 'evidence_kind': run['evidence_kind']})
            if run['status'] not in ('COMPLETE', 'PARTIAL', 'EMPTY'):
                errors.append(source_id+':'+run['status'])
        except Exception as error:
            errors.append(source_id+':'+str(getattr(error, 'detail', type(error).__name__))[:200])

    async def prepare(self, job):
        instrument, kind = job['instrument'], job['command']['kind']
        self.reviews.market.check_scope(ScopeCommand(instruments=[instrument], purpose='OBSERVATION'))
        receipts, errors, payload = [], [], {}
        evidence = []
        if kind == 'MARKET':
            # Existing bounded source adapters; no model input admission required.
            if job['command']['refresh_sources']:
                cutoff = datetime.fromisoformat(now())
                day = cutoff.astimezone(SHANGHAI).date()
                request = self.reviews.evidence.request(DataRequest(
                    instruments=[instrument], groups=['DAILY', 'QUOTE'], purpose='OBSERVATION',
                    start_date=day-timedelta(days=90), end_date=day, cutoff=cutoff,
                    daily_source='SOHU', quote_source='SINA', max_calls=2, timeout_seconds=18,
                    max_decoded_bytes=1048576, max_total_decoded_bytes=2097152))
                cancelled = threading.Event()
                try:
                    run = await asyncio.to_thread(self.reviews.evidence.retrieve, request['request_id'],
                        collection_source_policy=self.sources, cancel_event=cancelled,
                        acquisition_limits={'max_response_bytes':1048576, 'max_total_bytes':2097152})
                finally:
                    cancelled.set()
                receipts.append({'source': 'SOHU_DAILY_SINA_QUOTE', 'run_id': run['run_id'], 'status': run['status']})
                errors.extend(str(gap.get('code', 'SOURCE_GAP')) for gap in run['gaps'])
            else:
                receipts.append({'source': 'SOHU_DAILY_SINA_QUOTE', 'refresh': 'NOT_REQUESTED_SAVED_FACTS_ONLY'})
            listing = self.reviews.market.listing()
            rows, _, gaps, _ = self.reviews.facts_at(listing, datetime.fromisoformat(now()))
            member = next((row for row in rows if row['instrument'] == instrument), None)
            payload = {'market': member, 'limitations': ['原价行情；公司行动覆盖不足时不推算总收益', '不生成买卖建议']}
            if member is None:
                errors.append('INSTRUMENT_NOT_IN_WATCHLIST')
            facts = [fact for fact in ((member or {}).get('quote'), (member or {}).get('last_complete_daily')) if fact]
            evidence = [fact.get('evidence_kind') for fact in facts]
            input_value = ['MARKET', facts]
            meaning = ['MARKET', [{key: fact.get(key) for key in
                ('group', 'trade_date', 'upstream_at', 'last', 'close', 'open', 'high', 'low', 'volume_shares')}
                for fact in facts]]
            meaningful = bool(facts)
        elif kind == 'FINANCIAL':
            for service in (self.financial, self.supplement):
                await self.refresh(service, job, 'akshare-financial-em', receipts, errors)
            observation = self.observations.listing(instrument)['current']
            payload = {'financial_observation_id': observation['observation_id'], 'source_known_by': observation['known_by'], 'status': observation['status']}
            facts = self.observations.facts(instrument, datetime.fromisoformat(now()))
            evidence = [fact.get('evidence_kind') for fact in facts]
            input_value = ['FINANCIAL', observation['input_sha256']]
            meaning = ['FINANCIAL', observation['latest_period'], [(period['report_period'], {name: {key: metric.get(key) for key in ('status', 'value')} for name, metric in period['metrics'].items()}) for period in observation['periods']]]
            meaningful = bool(facts)
        else:
            await self.refresh(self.news, job, 'akshare-news-em', receipts, errors)
            news = self.news.listing(instrument)
            facts = news['facts']
            evidence = [fact.get('evidence_kind') for fact in facts]
            profile = job['settings']['profile']
            reference_sha = None
            if job['settings']['classify'] and facts:
                try:
                    reference_sha, _ = self.sentiment.reference(profile)
                except Exception as error:
                    errors.append('SENTIMENT:'+str(getattr(error, 'detail', error))[:200])
            input_value = ['NEWS', SERIES_VERSION, profile, reference_sha, sorted(fact['fact_id'] for fact in facts)]
            payload = {'saved_fact_count': len(facts), 'unique_event_count': news['unique_event_count'], 'classification_run_id': None, 'series_id': None,
                'source_available_through': max((fact['available_at'] for fact in facts), key=datetime.fromisoformat, default=None)}
            meaning = ['NEWS', sorted({fact['event']['event_id'] for fact in facts})]
            if reference_sha:
                try:
                    # A newly reached consumer checkpoint is a new logical input,
                    # while unchanged source timestamps and semantics stay frozen.
                    epoch = self.consumption_epoch(instrument)
                    input_value.append(epoch)
                    payload['consumption_checkpoint'] = epoch
                    with self.ledger.connection() as db:
                        runs = [json.loads(row[0]) for row in db.execute('SELECT value FROM sentiment_runs WHERE instrument=? ORDER BY rowid DESC', (instrument,))]
                    run = next((run for run in runs if run['status'] == 'COMPLETE' and run['reference_sha256'] == reference_sha and {row['fact_id'] for row in run['facts']} == {fact['fact_id'] for fact in facts}), None)
                    if not run:
                        run = await asyncio.wait_for(self.sentiment.classify(instrument, SentimentCommand(idempotency_key='observation:'+job['job_id'], basis=job['command']['basis'], profile=profile)), timeout=MODEL_TIMEOUT)
                    if run['status'] != 'COMPLETE':
                        raise ValueError('MODEL_'+run['status'])
                    evidence.append(run.get('evidence_kind'))
                    day = datetime.fromisoformat(now()).astimezone(SHANGHAI).date()
                    series = self.series.build(instrument, SeriesCommand(idempotency_key='observation:'+digest(input_value), basis=job['command']['basis'], source_run_id=run['run_id'], start_date=day-timedelta(days=6), end_date=day))
                    payload.update(classification_run_id=run['run_id'], series_id=series['series_id'], quality_gate_passed=run['reference'].get('evaluation', {}).get('passed_frozen_gates', False))
                    meaning.append(sorted({(row['event_id'], row['label'], row['reject_reason']) for row in run['facts']}, key=encode))
                except Exception as error:
                    errors.append('SENTIMENT:'+str(getattr(error, 'detail', type(error).__name__))[:200])
            meaningful = bool(facts)
        input_value += [payload.get('classification_run_id') is not None] if kind == 'NEWS' else []
        source_ready=not errors and not any(r.get('status')=='PARTIAL' for r in receipts)
        if kind=='MARKET':
            target=datetime.fromisoformat(job.get('scheduled_checkpoint') or now()).astimezone(SHANGHAI).date().isoformat()
            last=(payload.get('market') or {}).get('last_complete_daily') or {}
            source_ready=source_ready and last.get('trade_date')==target
        elif kind=='FINANCIAL':
            source_ready=source_ready and payload.get('status') not in ('MISSING',None)
        elif not payload.get('saved_fact_count'):
            source_ready=source_ready and any(r.get('status')=='EMPTY' for r in receipts)
        return {'source_ready':source_ready,'readiness':'READY' if source_ready else 'SOURCE_INCOMPLETE_OR_NOT_CURRENT',
            'instrument': instrument, 'kind': kind, 'version': VERSION, 'known_by': now(), 'payload': payload,
            'input_sha256': digest(input_value), 'semantic_sha256': digest(meaning), 'meaningful': meaningful,
            'receipts': receipts, 'errors': errors, 'evidence_kind': 'METHOD_CASE' if 'METHOD_CASE' in evidence else 'REAL_SAVED_OBSERVATION' if evidence and all(value in ('REAL_ACQUISITION', 'REAL_ARCHIVE_IMPORT', 'REAL_LOCAL_CLASSIFICATION') for value in evidence) else 'SOURCE_PROVENANCE_UNVERIFIED',
            'forecast_archive_created': False, 'system_usable': False, 'capability': 'RESEARCH_LIMITED'}
