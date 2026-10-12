"""Host-clock, append-only collection. Acquisition time is never a backdated PIT claim."""
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pyarrow.parquet as pq
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from roll.accounts.ledger import encode, now
from roll.market.evidence import DataRequest
from roll.market.rules import SHANGHAI
from roll.market.collection_sources import CollectionSources


class CollectionCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    instrument: str = Field(pattern=r'^(SSE|SZSE):\d{6}$')
    basis: str = Field(min_length=1, max_length=2000)


class ProspectiveEvidence:
    def __init__(self, evidence, registry):
        self.evidence = evidence
        self.registry = registry
        self.ledger = evidence.ledger
        self.sources = CollectionSources(evidence)
        from roll.market.post_close_packet import PostClosePackets
        self.post_close = PostClosePackets(self)
        with self.ledger.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS pit_collection_plans(id TEXT PRIMARY KEY, instrument TEXT UNIQUE, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS pit_collection_batches(id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, run_id TEXT UNIQUE, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS pit_fact_versions(ordinal INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id TEXT NOT NULL, batch_id TEXT NOT NULL, fact_key TEXT NOT NULL,
                    known_at TEXT NOT NULL, value TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS pit_asof ON pit_fact_versions(plan_id, known_at, ordinal);
            ''')
            pending = [r[0] for r in db.execute('SELECT r.id FROM retrieval_runs r LEFT JOIN pit_collection_batches b ON b.run_id=r.id WHERE b.id IS NULL')]
        # Resume only host-associated prospective runs, conservatively known from recovery now.
        # No re-fetch, backdated availability or rewriting already registered batches.
        for run_id in pending:
            run = evidence.get('retrieval_runs', run_id)
            request = evidence.get('data_requests', run['request_id'])
            plan_id = request.get('collection_plan_id')
            if plan_id and run['status'] in {'COMPLETE', 'PARTIAL', 'FAILED', 'INTERRUPTED'}:
                self.record(plan_id, run_id)

    def plans(self):
        with self.ledger.connection() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT value FROM pit_collection_plans ORDER BY rowid')]

    def plan(self, identifier):
        with self.ledger.connection() as db:
            row = db.execute('SELECT value FROM pit_collection_plans WHERE id=?', (identifier,)).fetchone()
        if row is None:
            raise HTTPException(404, '采集计划不存在')
        return json.loads(row[0])

    def start(self, command):
        # No client-supplied start/availability clock, retrospective proof, or readiness override.
        value = {'plan_id': str(uuid4()), 'instrument': command.instrument, 'started_at': now(),
                 'basis': command.basis, 'namespace': 'PROSPECTIVE',
                 'source_policy': {'daily': 'SOHU', 'quote': 'SINA', 'adjustments': 'EASTMONEY',
                                   'lookback_calendar_days': 45, 'historical_pit_search': False},
                 'capability': 'NOT_GRANTED', 'forward_started_at': None}
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT value FROM pit_collection_plans WHERE instrument=?', (command.instrument,)).fetchone()
            if row is not None:
                return json.loads(row[0])
            db.execute('INSERT INTO pit_collection_plans VALUES(?,?,?)',
                       (value['plan_id'], command.instrument, encode(value)))
            db.commit()
        return value

    def batches(self, identifier):
        self.plan(identifier)
        with self.ledger.connection() as db:
            return [json.loads(r[0]) for r in db.execute(
                'SELECT value FROM pit_collection_batches WHERE plan_id=? ORDER BY rowid', (identifier,))]

    def collect(self, identifier):
        plan = self.plan(identifier)
        today = datetime.fromisoformat(now()).astimezone(SHANGHAI).date()
        # Earlier bars are current-known feature context only, never past prediction evidence.
        request = self.evidence.request(DataRequest(instruments=[plan['instrument']],
            groups=['DAILY', 'QUOTE', 'STATUS', 'ADJUSTMENTS', 'ANNOUNCEMENTS'], purpose='RESEARCH',
            start_date=today-timedelta(days=45), end_date=today, daily_source='SOHU', quote_source='SINA',
            timeout_seconds=15, max_calls=12))
        request['collection_plan_id'] = identifier
        with self.ledger.connection() as db:
            db.execute('UPDATE data_requests SET value=? WHERE id=?', (encode(request), request['request_id']))
        run = self.evidence.retrieve(request['request_id'], collection_source_policy=self.sources)
        primary = self.record(identifier, run['run_id'])
        from roll.market.cnequity import CNEquityCollection
        supplements = CNEquityCollection(self.evidence, self.sources).collect(plan)
        batches = [self.record(identifier, item['run_id']) for item in supplements]
        comparison = self.sources.compare_daily(identifier, self.as_of(identifier, datetime.fromisoformat(now()))['versions'])
        return {**primary, 'supplemental_batches': batches, 'comparison_id': comparison['comparison_id'],
                'unresolved_comparisons': len(comparison['differences'])}

    def record(self, identifier, run_id):
        plan = self.plan(identifier)
        run = self.evidence.get('retrieval_runs', run_id)
        request = self.evidence.get('data_requests', run['request_id'])
        if request['purpose'] != 'RESEARCH' or request['instruments'] != [plan['instrument']]:
            raise HTTPException(409, '采集证券/用途与计划不同')
        if datetime.fromisoformat(run['started_at']) < datetime.fromisoformat(plan['started_at']):
            raise HTTPException(409, '旧采集不能补写为新计划的前向证据')
        if run['status'] not in {'COMPLETE', 'PARTIAL', 'FAILED', 'INTERRUPTED'}:
            raise HTTPException(409, '只登记已经结束的宿主采集')
        snapshot = self.evidence.get('market_evidence_snapshots', run['snapshot_id']) if run.get('snapshot_id') else None
        facts = []
        if snapshot:
            if snapshot['run_id'] != run_id or snapshot['request_id'] != request['request_id']:
                raise HTTPException(409, '采集快照关联损坏')
            for archive in snapshot['archives']+[snapshot['parquet']]:
                self.evidence.raw(archive['sha256'])
            facts = [json.loads(r['payload']) for r in pq.read_table(
                self.evidence.raw(snapshot['parquet']['sha256'])).to_pylist()]
            if facts != snapshot['facts']:
                raise HTTPException(409, '采集快照与Parquet不同')
            if any(f.get('raw_hash') not in {a['sha256'] for a in snapshot['archives']} for f in facts):
                raise HTTPException(409, '采集事实缺少原件绑定')
        # Conservatively use completed host snapshot time, including normalization/commit latency.
        recorded_at = now()
        known_at = max([plan['started_at'], run['finished_at'], recorded_at,
                        *([snapshot['created_at']] if snapshot else []),
                        *[f['available_at'] for f in facts]], key=lambda v: datetime.fromisoformat(v))
        versions = []
        for fact in facts:
            if fact['instrument'] != plan['instrument']:
                raise HTTPException(409, '采集快照混入其他证券')
            identity = {k: fact.get(k) for k in ['instrument', 'group', 'source_id', 'trade_date', 'adjustment']}
            # Non-daily event identities must never collapse multiple disclosures into one event.
            if fact['group'] not in {'DAILY', 'QUOTE', 'STATUS'}:
                if fact.get('event_identity'):
                    identity['event_identity'] = fact['event_identity']
                else:
                    identity['event_content'] = fact
            versions.append({'fact': fact, 'fact_key': hashlib.sha256(encode(identity).encode()).hexdigest(),
                             'known_at': known_at, 'raw_hash': fact['raw_hash'],
                             'evidence_kind': snapshot['evidence_kind'], 'namespace': 'PROSPECTIVE',
                             'historical_pit_claim': False})
        batch = {'batch_id': str(uuid4()), 'plan_id': identifier, 'run_id': run_id,
                 'snapshot_id': snapshot['snapshot_id'] if snapshot else None, 'recorded_at': recorded_at,
                 'collection_code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 'source_adapter_version': snapshot.get('adapter_version') if snapshot else None,
                 'known_at': known_at, 'status': run['status'], 'fact_count': len(versions),
                 'evidence_kind': snapshot['evidence_kind'] if snapshot else run.get('evidence_kind'),
                 'gaps': run.get('gaps', []), 'capability': 'NOT_GRANTED'}
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT value FROM pit_collection_batches WHERE run_id=?', (run_id,)).fetchone()
            if old:
                if json.loads(old[0])['plan_id'] != identifier:
                    raise HTTPException(409, '该采集已绑定其他计划')
                return json.loads(old[0])
            db.execute('INSERT INTO pit_collection_batches VALUES(?,?,?,?)', (batch['batch_id'], identifier, run_id, encode(batch)))
            db.executemany('INSERT INTO pit_fact_versions(plan_id,batch_id,fact_key,known_at,value) VALUES(?,?,?,?,?)',
                          [(identifier, batch['batch_id'], v['fact_key'], known_at, encode(v)) for v in versions])
            db.commit()
        return batch

    def as_of(self, identifier, cutoff):
        plan = self.plan(identifier)
        if cutoff.tzinfo is None or cutoff > datetime.fromisoformat(now()):
            raise HTTPException(422, '查询时点须带时区且不是未来')
        selected = {}
        with self.ledger.connection() as db:
            rows = db.execute('SELECT value,batch_id,ordinal FROM pit_fact_versions WHERE plan_id=? ORDER BY ordinal', (identifier,))
            for row in rows:
                value = json.loads(row[0])
                previous = selected.get(value['fact_key'])
                if datetime.fromisoformat(value['known_at']) <= cutoff and (previous is None or
                        datetime.fromisoformat(value['known_at']) >= datetime.fromisoformat(previous['known_at'])):
                    selected[value['fact_key']] = {**value, 'batch_id': row[1], 'ordinal': row[2]}
        self.replay_versions(identifier, list(selected.values()), cutoff)
        return {'plan_id': identifier, 'started_at': plan['started_at'], 'cutoff': cutoff.isoformat(),
                'namespace': 'PROSPECTIVE', 'versions': list(selected.values()), 'network_calls': 0,
                'capability': 'NOT_GRANTED', 'historical_pit_claim': False}

    def replay_versions(self, identifier, versions, cutoff):
        """Verify the exact append-only versions selected by an archived consumer packet."""
        self.plan(identifier)
        if cutoff.tzinfo is None or cutoff > datetime.fromisoformat(now()):
            raise HTTPException(422, '查询时点须带时区且不是未来')
        ordinals = set()
        with self.ledger.connection() as db:
            for value in versions:
                ordinal = value.get('ordinal')
                row = db.execute('SELECT value,batch_id,fact_key,known_at FROM pit_fact_versions WHERE plan_id=? AND ordinal=?',
                                 (identifier, ordinal)).fetchone()
                if (row is None or ordinal in ordinals or
                        value != {**json.loads(row[0]), 'batch_id': row[1], 'ordinal': ordinal} or
                        value['fact_key'] != row[2] or value['known_at'] != row[3] or
                        datetime.fromisoformat(value['known_at']) > cutoff):
                    raise HTTPException(409, 'PIT_PACKET_ORIGINAL_VERSION_BINDING_MISMATCH')
                ordinals.add(ordinal)
        # Verify archives during offline replay; metadata presence is insufficient.
        replayed = {}
        batches = {b['batch_id']: b for b in self.batches(identifier)}
        for value in versions:
            batch = batches.get(value['batch_id'])
            if batch is None:
                raise HTTPException(409, 'PIT_PACKET_ORIGINAL_BATCH_MISSING')
            if batch['run_id'] not in replayed:
                replayed[batch['run_id']] = {encode(f) for f in self.evidence.replay(batch['run_id'])['facts']}
            if encode(value['fact']) not in replayed[batch['run_id']] or value['known_at'] != batch['known_at']:
                raise HTTPException(409, 'PIT事实版本与原采集快照不同')
            self.evidence.raw(value['raw_hash'])
            for sha in value['fact'].get('basis_raw_hashes', []):
                self.evidence.raw(sha)
        return versions

    def readiness(self, identifier):
        plan = self.plan(identifier)
        versions = self.as_of(identifier, datetime.fromisoformat(now()))['versions']
        first_day = datetime.fromisoformat(plan['started_at']).astimezone(SHANGHAI).date().isoformat()
        daily = [v for v in versions if v['evidence_kind'] == 'REAL_ACQUISITION'
                 and v['fact']['group'] == 'DAILY' and v['fact'].get('adjustment') == 'RAW'
                 and not v['fact'].get('errors') and v['fact'].get('volume_unit') == 'SHARE'
                 and v['fact'].get('model_daily_input_allowed', True)
                 and v['fact'].get('completion_state') == 'COMPLETE_REPORTED_HISTORICAL']
        days = sorted({v['fact']['trade_date'] for v in daily if v['fact']['trade_date'] >= first_day})
        return {'plan_id': identifier, 'started_at': plan['started_at'], 'state': 'COLLECTING',
                'real_recorded_sessions': len(days), 'real_context_sessions': len({v['fact']['trade_date'] for v in daily}),
                'batches': len(self.batches(identifier)), 'system_usable': False, 'capability': 'NOT_GRANTED',
                'minimum_calibration_examples_per_class': 20, 'minimum_effective_time_blocks': 30,
                'requirements': ['CONTIGUOUS_ASOF_FEATURE_LOOKBACK_21', 'COMPLETE_STATUS_ACTIONS_AND_RULES',
                    'PREREGISTERED_DEV_CAL_WINDOWS_AND_MATURE_LABELS', 'REAL_CALIBRATION_SUPPORT_BOTH_CLASSES_20',
                    'REAL_MODEL_AND_CALIBRATOR_FREEZE', 'CONFIRMATORY_AND_FORWARD_VALIDATION',
                    'MODEL_REVIEW_AND_CAPABILITY_GRANT'],
                'readiness_basis': '行数只说明采集覆盖；资料、成熟支持、验证和资格全部满足后方可用。'}
