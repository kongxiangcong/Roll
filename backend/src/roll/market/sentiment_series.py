"""Immutable reconstruction of saved event observations; never a forecast archive."""
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from roll.accounts.ledger import encode, now
from roll.market.news_events import content_digest
from roll.market.rules import SHANGHAI

VERSION = 'sentiment-event-series-v1'
CHECKPOINT = {'id': 'POST_CLOSE_1505_V1', 'time': '15:05:00', 'timezone': 'Asia/Shanghai',
              'source_close_boundary': '15:00:00', 'namespace': 'SAVED_RESEARCH_OBSERVATION'}
LABELS = ('POSITIVE', 'NEGATIVE', 'NEUTRAL')


class SeriesCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    idempotency_key: str = Field(min_length=1, max_length=128)
    basis: str = Field(min_length=1, max_length=2000)
    source_run_id: str = Field(min_length=1, max_length=128)
    start_date: date
    end_date: date
    known_by: datetime | None = None


def aware(value):
    stamp = datetime.fromisoformat(value) if isinstance(value, str) else value
    if stamp.tzinfo is None:
        raise HTTPException(422, 'SENTIMENT_SERIES_AWARE_TIME_REQUIRED')
    return stamp


def semantics(run):
    # The accepted legacy producer used recorded v1 event IDs. Do not reinterpret
    # them through a later grouping implementation when reading archived runs.
    return {key: run.get(key, default) for key, default in (
        ('reference_sha256', None), ('classification_version', 'sentiment-classification-v1'),
        ('reject_layer', None), ('news_grouping_version', 1),
        ('news_association_version', 1))}


class SentimentSeries:
    def __init__(self, sentiment):
        self.sentiment = sentiment
        self.ledger = sentiment.ledger
        self.rules = sentiment.evidence.market.rules
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS sentiment_series(id TEXT PRIMARY KEY,instrument TEXT,key TEXT,command_hash TEXT,value TEXT,UNIQUE(instrument,key))')
            db.execute('CREATE TABLE IF NOT EXISTS sentiment_series_checkpoints(id TEXT PRIMARY KEY,value TEXT,registered_at TEXT)')

    def calendar(self, exchange, day, basis):
        key = day.isoformat()
        if key not in basis:
            value = self.rules.calendar(exchange, day, datetime.combine(day, time(16), SHANGHAI))
            source = value.get('source') or {}
            basis[key] = {name: value.get(name) for name in ('is_trading_day', 'coverage', 'calendar_version', 'historical_knowledge')}
            basis[key]['source_sha256'] = source.get('sha256')
            basis[key]['correction_sha256'] = [item['sha256'] for item in value.get('correction_sources', [])]
        return basis[key]

    def consumption(self, exchange, source_at, label_at, basis):
        source_at, label_at = aware(source_at).astimezone(SHANGHAI), aware(label_at).astimezone(SHANGHAI)
        day = source_at.date()
        # The intraday close boundary is supported only in the adapted rule era.
        if day < date(2026, 7, 6):
            return None, 'INTRADAY_RULE_COVERAGE_UNKNOWN'
        after_close = source_at.time().replace(tzinfo=None) >= time(15)
        if after_close:
            day += timedelta(days=1)
        day = max(day, label_at.date())
        for _ in range(32):
            calendar = self.calendar(exchange, day, basis)
            if calendar['is_trading_day'] is None:
                return None, 'CALENDAR_COVERAGE_UNKNOWN'
            checkpoint = datetime.combine(day, time(15, 5), SHANGHAI)
            if calendar['is_trading_day'] and checkpoint >= max(source_at, label_at):
                return checkpoint, None
            day += timedelta(days=1)
        return None, 'CONSUMPTION_LOOKAHEAD_LIMIT'

    def source_runs(self, instrument):
        with self.ledger.connection() as db:
            runs = [json.loads(row[0]) for row in db.execute('SELECT value FROM sentiment_runs WHERE instrument=? ORDER BY rowid DESC', (instrument,))]
        return [{'run_id': run['run_id'], 'finished_at': run.get('finished_at'),
                 'model': run['reference'].get('model'), 'profile': run.get('profile', 'legacy'),
                 'reference_sha256': run['reference_sha256'],
                 'quality_gate_passed': run['reference'].get('evaluation', {}).get('passed_frozen_gates', False)}
                for run in runs if run['status'] == 'COMPLETE']

    def build(self, instrument, command):
        command_hash = hashlib.sha256(encode(command.model_dump(mode='json')).encode()).hexdigest()
        with self.ledger.connection() as db:
            prior = db.execute('SELECT command_hash,value FROM sentiment_series WHERE instrument=? AND key=?', (instrument, command.idempotency_key)).fetchone()
        if prior:
            if prior[0] != command_hash:
                raise HTTPException(409, 'SENTIMENT_SERIES_IDEMPOTENCY_CONFLICT')
            return json.loads(prior[1])
        stamp = aware(command.known_by or now())
        if stamp > aware(now()) or not 0 <= (command.end_date-command.start_date).days < 92:
            raise HTTPException(422, 'SENTIMENT_SERIES_PAST_CUTOFF_AND_92_DAY_RANGE_REQUIRED')
        anchor = self.sentiment.get(command.source_run_id)
        if anchor['instrument'] != instrument or anchor['status'] != 'COMPLETE':
            raise HTTPException(409, 'SENTIMENT_SERIES_COMPLETE_MATCHING_RUN_REQUIRED')
        if aware(anchor['finished_at']) > stamp:
            raise HTTPException(409, 'SENTIMENT_CLASSIFICATION_NOT_KNOWN_AT_CUTOFF')
        contract = semantics(anchor)
        if not contract['reference_sha256']:
            raise HTTPException(409, 'SENTIMENT_SERIES_REFERENCE_MISSING')
        with self.ledger.connection() as db:
            runs = [json.loads(row[0]) for row in db.execute('SELECT value FROM sentiment_runs WHERE instrument=?', (instrument,))]
        lineage = sorted((run for run in runs if run['status'] == 'COMPLETE' and semantics(run) == contract and
                          aware(run['finished_at']) <= aware(anchor['finished_at'])), key=lambda run: (aware(run['finished_at']), run['run_id']))
        if len(lineage) > 366 or len({row['fact_id'] for run in lineage for row in run['facts']}) > 2000:
            raise HTTPException(409, 'SENTIMENT_SERIES_366_RUN_2000_UNIQUE_FACT_BOUND_EXCEEDED')
        anchor_members = {row['fact_id']: row['event_id'] for row in anchor['facts']}
        incompatible = [index for index, run in enumerate(lineage) if any(
            row['fact_id'] in anchor_members and anchor_members[row['fact_id']] != row['event_id'] for row in run['facts'])]
        excluded_runs = []
        if incompatible:
            # A later exact-link bridge may change an earlier event membership.
            # Start a successor epoch; do not retroactively merge historical counts.
            boundary = max(incompatible)+1
            excluded_runs = [run['run_id'] for run in lineage[:boundary]]
            lineage = lineage[boundary:]
        sources = {fact['fact_id']: fact for fact in self.sentiment.facts(instrument)}
        supported = LABELS if anchor['reference'].get('task') == 'CHINESE_FINANCIAL_SENTIMENT_3_CLASS' else LABELS[:2]
        events, seen, observations, basis, used = {}, {}, [], {}, {}
        raw_checked, digests = set(), {}
        exchange = instrument.split(':')[0]
        for run in lineage:
            groups = defaultdict(list)
            for prediction in run['facts']:
                source = sources.get(prediction['fact_id'])
                if not source or aware(source['available_at']) > aware(run['finished_at']):
                    raise HTTPException(409, 'SENTIMENT_SERIES_SOURCE_TIME_OR_VERSION_MISSING')
                if prediction.get('label') is not None and prediction['label'] not in supported:
                    raise HTTPException(409, 'SENTIMENT_SERIES_UNSUPPORTED_SAVED_LABEL')
                if not prediction.get('label') and not prediction.get('reject_reason'):
                    raise HTTPException(409, 'SENTIMENT_SERIES_SAVED_REJECTION_MISSING')
                try:
                    for digest in [source['list_sha256'], source.get('body_sha256')]:
                        if digest and digest not in raw_checked:
                            self.sentiment.evidence.raw(digest)
                            raw_checked.add(digest)
                except Exception as error:
                    raise HTTPException(409, 'SENTIMENT_SERIES_SOURCE_INTEGRITY_FAILED') from error
                used[source['fact_id']] = source
                if source['fact_id'] not in digests:
                    digests[source['fact_id']] = content_digest(source)
                groups[prediction['event_id']].append((source, prediction))
            for event_id, members in groups.items():
                source, prediction = max(members, key=lambda item: (aware(item[0]['available_at']), item[0]['fact_id']))
                signature = digests[source['fact_id']] + '|' + prediction['text_sha256']
                if seen.get(event_id) == signature:
                    continue
                checkpoint, gap = self.consumption(exchange, source['available_at'], run['finished_at'], basis)
                observation = {'event_id': event_id, 'fact_id': source['fact_id'], 'source_run_id': run['run_id'],
                    'source_available_at': source['available_at'], 'classification_available_at': run['finished_at'],
                    'first_source_available_at': min((item[0]['available_at'] for item in members), key=aware),
                    'input_sha256': prediction['text_sha256'], 'source_content_sha256': digests[source['fact_id']],
                    'label': prediction.get('label'), 'reject_reason': prediction.get('reject_reason'),
                    'is_revision_update': event_id in events, 'member_fact_ids': [item[0]['fact_id'] for item in members],
                    'checkpoint_at': checkpoint.isoformat() if checkpoint else None, 'gap': gap}
                events[event_id] = observation
                seen[event_id] = signature
                observations.append(observation)
        days, deferred = [], []
        first_checkpoints = {}
        for row in observations:
            if row['checkpoint_at']:
                checkpoint = aware(row['checkpoint_at'])
                first_checkpoints[row['event_id']] = min(checkpoint, first_checkpoints.get(row['event_id'], checkpoint))
        for offset in range((command.end_date-command.start_date).days+1):
            day = command.start_date + timedelta(days=offset)
            info = self.calendar(exchange, day, basis)
            checkpoint = datetime.combine(day, time(15, 5), SHANGHAI)
            consumed = [row for row in observations if row['checkpoint_at'] and aware(row['checkpoint_at']) == checkpoint and checkpoint <= stamp]
            # Several known versions can become consumable at the same checkpoint.
            # Count the event once using its last known version at that checkpoint.
            checkpoint_states = {row['event_id']: row for row in consumed}
            initial = [row for row in checkpoint_states.values() if first_checkpoints[row['event_id']] == checkpoint]
            updates = [row for row in checkpoint_states.values() if first_checkpoints[row['event_id']] < checkpoint]
            counts = Counter(row['label'] or row['reject_reason'] for row in initial)
            status = 'CALENDAR_UNKNOWN' if info['is_trading_day'] is None else 'CLOSED' if not info['is_trading_day'] else 'NOT_REACHED' if checkpoint > stamp else 'VERSION_NOT_AVAILABLE' if checkpoint < aware(lineage[0]['finished_at']) else 'OBSERVED' if consumed else 'NO_OBSERVATIONS'
            days.append({'trade_date': day.isoformat(), 'checkpoint_at': checkpoint.isoformat(), 'status': status,
                'unique_events': len(initial), 'source_fact_count': sum(len(row['member_fact_ids']) for row in initial),
                'counts': {label: counts[label] if initial and label in supported else None for label in LABELS},
                'proportions': {label: counts[label]/len(initial) if initial and label in supported else None for label in LABELS},
                'reject_count': sum(bool(row['reject_reason']) for row in initial),
                'reject_counts': dict(Counter(row['reject_reason'] for row in initial if row['reject_reason'])),
                'covered_events': sum(row['label'] is not None for row in initial),
                'coverage': sum(row['label'] is not None for row in initial)/len(initial) if initial else None,
                'denominator': 'UNIQUE_NEW_EVENTS_INCLUDING_REJECTED',
                'revision_event_count': len({row['event_id'] for row in updates}), 'revision_updates': updates,
                'events': initial, 'calendar': info})
        for observation in observations:
            if observation['gap'] or aware(observation['checkpoint_at']) > stamp:
                deferred.append({key: observation[key] for key in ('event_id', 'fact_id', 'checkpoint_at', 'gap', 'source_available_at', 'classification_available_at')})
        latest = {}
        for observation in observations:
            if observation['checkpoint_at'] and aware(observation['checkpoint_at']) <= stamp and command.start_date <= aware(observation['checkpoint_at']).astimezone(SHANGHAI).date() <= command.end_date:
                latest[observation['event_id']] = observation
        value = {'series_id': str(uuid4()), 'instrument': instrument, 'status': 'COMPLETE', 'version': VERSION,
            'created_at': now(), 'known_by': stamp.isoformat(), 'start_date': command.start_date.isoformat(),
            'end_date': command.end_date.isoformat(), 'basis': command.basis, 'checkpoint': dict(CHECKPOINT),
            'source_run_id': anchor['run_id'], 'source_run_ids': [run['run_id'] for run in lineage],
            'excluded_predecessor_runs': excluded_runs,
            'membership_epoch': lineage[0]['run_id'],
            'membership_boundary': 'LATER_LINK_REQUIRES_SUCCESSOR_NO_HISTORICAL_REMERGE' if excluded_runs else None,
            'source_run_sha256': {run['run_id']: hashlib.sha256(encode(run).encode()).hexdigest() for run in lineage},
            'semantics': contract, 'model': anchor['reference'].get('model'), 'labels_supported': list(supported),
            'quality_gate_passed': anchor['reference'].get('evaluation', {}).get('passed_frozen_gates', False),
            'days': days, 'deferred_events': deferred, 'latest_consumed_states': list(latest.values()),
            'source_coverage': {'archived_facts': len(used), 'unique_recorded_events': len(events),
                'source_ids': sorted({source.get('source_id', 'UNKNOWN') for source in used.values()}),
                'complete_news_flow': False, 'news_scope': 'ONLY_ACTUALLY_SAVED_CLASSIFIED_FACTS'},
            'evidence_kind': 'METHOD_CASE' if any(run.get('evidence_kind') == 'METHOD_CASE' for run in lineage) or any(source.get('evidence_kind') == 'METHOD_CASE' for source in used.values()) else 'REAL_SAVED_OBSERVATION_RECONSTRUCTION' if all(source.get('evidence_kind') in ('REAL_ACQUISITION','REAL_ARCHIVE_IMPORT') for source in used.values()) else 'SOURCE_PROVENANCE_UNVERIFIED',
            'historical_forecast_archive': False, 'reconstruction_created_after_cutoff': aware(now()) > stamp,
            'network_calls': 0, 'model_calls': 0, 'system_usable': False, 'capability': 'RESEARCH_LIMITED',
            'limitations': ['有限归档来源，缺席日不代表中性；不声称完整新闻覆盖', '同版本首次新事件只计一次，修订更新单列不增加新事件分母',
                           '实际创建时点的历史观察重建，不补造历史预测或授予交易资格', '模型评测限制与非独立标签结论继承原分类版本']}
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior = db.execute('SELECT command_hash,value FROM sentiment_series WHERE instrument=? AND key=?', (instrument, command.idempotency_key)).fetchone()
            if prior:
                if prior[0] != command_hash:
                    raise HTTPException(409, 'SENTIMENT_SERIES_IDEMPOTENCY_CONFLICT')
                return json.loads(prior[1])
            policy = db.execute('SELECT value,registered_at FROM sentiment_series_checkpoints WHERE id=?', (CHECKPOINT['id'],)).fetchone()
            if policy and policy[0] != encode(CHECKPOINT):
                raise HTTPException(409, 'SENTIMENT_SERIES_CHECKPOINT_VERSION_CONFLICT')
            value['checkpoint_registered_at'] = policy[1] if policy else now()
            if not policy:
                db.execute('INSERT INTO sentiment_series_checkpoints VALUES(?,?,?)', (CHECKPOINT['id'], encode(CHECKPOINT), value['checkpoint_registered_at']))
            db.execute('INSERT INTO sentiment_series VALUES(?,?,?,?,?)', (value['series_id'], instrument, command.idempotency_key, command_hash, encode(value)))
            db.commit()
        return value

    def get(self, identifier):
        with self.ledger.connection() as db:
            row = db.execute('SELECT value FROM sentiment_series WHERE id=?', (identifier,)).fetchone()
        if not row:
            raise HTTPException(404, 'SENTIMENT_SERIES_NOT_FOUND')
        return json.loads(row[0])

    def listing(self, instrument):
        with self.ledger.connection() as db:
            row = db.execute('SELECT value FROM sentiment_series WHERE instrument=? ORDER BY rowid DESC LIMIT 1', (instrument,)).fetchone()
        if not row:
            raise HTTPException(404, 'SENTIMENT_SERIES_NOT_FOUND')
        return json.loads(row[0])

    def history(self, instrument):
        with self.ledger.connection() as db:
            rows = db.execute('SELECT value FROM sentiment_series WHERE instrument=? ORDER BY rowid DESC LIMIT 100', (instrument,)).fetchall()
        return [{key: value[key] for key in ('series_id', 'created_at', 'known_by', 'model', 'source_run_id', 'start_date', 'end_date')}
                for row in rows for value in [json.loads(row[0])]]
