"""Persistent access policy for prospective collectors; upstream identity is explicit."""
import json
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from itertools import combinations
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from roll.accounts.ledger import encode, now

CNE_COMMIT = 'c118038ea82b5bb78783c0c17a1d9251b36de71d'
CLEANING_VERSION = 'prospective-cleaning-v1'
SOURCES = [
    {'id': 'sse-company-client-contract', 'name': '上交所公司行情字段原件', 'upstream': 'SSE', 'group': 'STATUS', 'engine': 'ROLL'},
    {'id': 'sse-closing-board', 'name': '上交所盘后原始快照', 'upstream': 'SSE', 'group': 'DAILY', 'engine': 'ROLL'},
    {'id': 'sse-suspension-date', 'name': '上交所指定日期停牌观察', 'upstream': 'SSE', 'group': 'STATUS', 'engine': 'ROLL'},
    {'id': 'sse-stock-suspension-interval', 'name': '上交所证券停牌区间原件', 'upstream': 'SSE', 'group': 'STATUS', 'engine': 'ROLL'},
    {'id': 'sohu-daily', 'name': '搜狐日线', 'upstream': 'SOHU', 'group': 'DAILY', 'engine': 'ROLL'},
    {'id': 'sina-quote', 'name': '新浪报价与状态线索', 'upstream': 'SINA', 'group': 'QUOTE', 'engine': 'ROLL'},
    {'id': 'eastmoney-actions', 'name': '东财权益线索', 'upstream': 'EASTMONEY', 'group': 'ADJUSTMENTS', 'engine': 'ROLL'},
    {'id': 'eastmoney-announcements', 'name': '东财公告原件', 'upstream': 'EASTMONEY', 'group': 'ANNOUNCEMENTS', 'engine': 'ROLL'},
    {'id': 'cnequity-tdx-daily', 'name': 'CNEquity 通达信日线', 'upstream': 'TDX', 'group': 'DAILY', 'engine': 'CNEQUITY'},
    {'id': 'cnequity-eastmoney-daily', 'name': 'CNEquity 东财日线', 'upstream': 'EASTMONEY', 'group': 'DAILY', 'engine': 'CNEQUITY'},
    {'id': 'cnequity-eastmoney-status', 'name': 'CNEquity 东财交易状态', 'upstream': 'EASTMONEY', 'group': 'STATUS', 'engine': 'CNEQUITY'},
    {'id': 'cnequity-eastmoney-actions', 'name': 'CNEquity 东财公司行为', 'upstream': 'EASTMONEY', 'group': 'ADJUSTMENTS', 'engine': 'CNEQUITY'},
    {'id': 'cnequity-cninfo-announcements', 'name': 'CNEquity 巨潮公告索引', 'upstream': 'CNINFO', 'group': 'ANNOUNCEMENTS', 'engine': 'CNEQUITY'},
]


class SourcePolicyCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool
    expected_revision: int = Field(ge=1)
    basis: str = Field(min_length=1, max_length=2000)


class CollectionSources:
    def __init__(self, evidence):
        self.evidence, self.ledger = evidence, evidence.ledger
        with self.ledger.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS collection_source_policies(id TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS collection_source_changes(ordinal INTEGER PRIMARY KEY, source_id TEXT NOT NULL, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS collection_source_health(id TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS collection_cleaning_reports(run_id TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS collection_comparison_reports(id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, value TEXT NOT NULL);
            ''')
            for spec in SOURCES:
                policy = {**spec, 'enabled': True, 'revision': 1, 'changed_at': now(),
                          'basis': '2026-10-10用户授权持续采集与CNEquity补充接入',
                          'authentication': 'PUBLIC_NO_CREDENTIAL', 'scope': ['SSE:600362'],
                          'max_calls': 8, 'timeout_seconds': 18, 'max_bytes': 8*1024*1024,
                          'failure_threshold': 3, 'cooldown_seconds': 3600, 'retries': 0,
                          'commit': CNE_COMMIT if spec['engine'] == 'CNEQUITY' else None,
                          'adapter_version': 'cnequity-'+CNE_COMMIT[:12] if spec['engine'] == 'CNEQUITY' else 'ROLL_PROSPECTIVE',
                          'source_selection': 'EXPLICIT_SUPPLEMENT; NO_SOURCE_WINNER',
                          'historical_revision_proof': 'PROSPECTIVE_HOST_RECEIPTS_ONLY',
                          'unit_scope': 'Pinned adapter contract plus row-level quantity/amount checks; complete source coverage not asserted',
                          'license': 'Apache-2.0 code; upstream data rights separate',
                          'cleaning_version': CLEANING_VERSION, 'qualification': 'NOT_GRANTED'}
                if spec['id']=='sse-closing-board':
                    policy.update(basis='2026-10-11授权继续30宿主producer工程与公开来源核验',max_calls=1,
                        timeout_seconds=15,adapter_version='source-bound-post-close-v1',
                        license='Roll adaptation; upstream data rights separate',
                        unit_scope='SSE board original units/session turnover scope UNVERIFIED; not model-admissible')
                if spec['id']=='sse-company-client-contract':
                    policy.update(basis='2026-10-11授权同官方company客户端有限两源合同',max_calls=2,
                        timeout_seconds=15,adapter_version='source-bound-sse-company-client-v1',
                        license='Roll adaptation; upstream data rights separate',
                        historical_revision_proof='RECEIVED_ORIGINAL_NOT_HISTORICAL_PIT',
                        unit_scope='Official client display transforms only; sessions/full listing-risk/effective coverage UNKNOWN')
                if spec['id']=='sse-suspension-date':
                    policy.update(basis='2026-10-11授权有限指定日期官方SSE source assessment',max_calls=2,
                        timeout_seconds=15,adapter_version='source-bound-sse-suspension-date-v1',
                        license='Roll adaptation; upstream data rights separate',
                        historical_revision_proof='RECEIVED_ORIGINAL_ONLY_NOT_HISTORICAL_PIT',
                        unit_scope='Returned suspension schedules only; absence/resumption/full status UNKNOWN')
                if spec['id']=='sse-stock-suspension-interval':
                    policy.update(basis='2026-10-11授权新stock SSE有限独立来源评估',max_calls=3,
                        timeout_seconds=15,adapter_version='source-bound-sse-stock-interval-v1',
                        license='Roll adaptation; upstream data rights separate',
                        historical_revision_proof='CURRENT_RECEIVED_ORIGINAL_NOT_HISTORICAL_PIT',
                        unit_scope='Reported date/interval schedules; latest trade day and actual resumption UNKNOWN')
                db.execute('INSERT OR IGNORE INTO collection_source_policies VALUES(?,?)', (spec['id'], encode(policy)))

    def listing(self):
        with self.ledger.connection() as db:
            health = {r[0]: json.loads(r[1]) for r in db.execute('SELECT id,value FROM collection_source_health')}
            return [{**json.loads(r[1]), 'health': health.get(r[0], {'state': 'NOT_YET_ACQUIRED', 'consecutive_failures': 0})}
                    for r in db.execute('SELECT id,value FROM collection_source_policies ORDER BY rowid')]

    def policy(self, source_id):
        # Originals are fetched by the announcement policy, rather than a hidden switch.
        if source_id == 'eastmoney-original':
            source_id = 'eastmoney-announcements'
        return next((p for p in self.listing() if p['id'] == source_id), None)

    def change(self, source_id, command):
        if not command.basis.strip():
            raise HTTPException(422, '来源配置变更需明确依据')
        if source_id not in {s['id'] for s in SOURCES}:
            raise HTTPException(404, '采集来源不存在')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            old = json.loads(db.execute('SELECT value FROM collection_source_policies WHERE id=?', (source_id,)).fetchone()[0])
            if command.expected_revision != old['revision']:
                raise HTTPException(409, '来源配置已变化，请刷新')
            value = {**old, 'enabled': command.enabled, 'revision': old['revision']+1,
                     'basis': command.basis, 'changed_at': now()}
            db.execute('UPDATE collection_source_policies SET value=? WHERE id=?', (encode(value), source_id))
            db.execute('INSERT INTO collection_source_changes(source_id,value) VALUES(?,?)',
                       (source_id, encode({'before': old, 'after': value})))
            db.commit()
        return self.policy(source_id)

    def access(self, source_id, instrument):
        policy = self.policy(source_id)
        if policy is None:
            return None
        if instrument not in policy['scope']:
            return 'SOURCE_SCOPE_NOT_ALLOWED'
        if not policy['enabled']:
            return 'SOURCE_DISABLED'
        until = policy['health'].get('retry_after')
        if until and datetime.fromisoformat(until) > datetime.fromisoformat(now()):
            return 'SOURCE_COOLDOWN'
        return None

    def outcome(self, source_id, success, code, run_id):
        policy = self.policy(source_id)
        if policy is None:
            return
        source_id = policy['id']
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT value FROM collection_source_health WHERE id=?', (source_id,)).fetchone()
            old = json.loads(row[0]) if row else {}
            failures = 0 if success else old.get('consecutive_failures', 0)+1
            value = {**old, 'state': 'ACQUIRED' if success else 'FAILED', 'last_attempt_at': now(),
                     'last_run_id': run_id, 'last_code': code, 'consecutive_failures': failures,
                     'retry_after': (datetime.fromisoformat(now())+timedelta(seconds=policy['cooldown_seconds'])).isoformat()
                         if failures >= policy['failure_threshold'] else None}
            if success:
                value['last_success_at'] = value['last_attempt_at']
            db.execute('INSERT INTO collection_source_health VALUES(?,?) ON CONFLICT(id) DO UPDATE SET value=excluded.value',
                       (source_id, encode(value)))
            db.commit()

    def reports(self, limit=30):
        with self.ledger.connection() as db:
            return [json.loads(r[0]) for r in db.execute(
                'SELECT value FROM collection_cleaning_reports ORDER BY rowid DESC LIMIT ?', (limit,))]

    def compare_daily(self, plan_id, versions):
        days = {}
        for version in versions:
            fact = version['fact']
            if fact['group'] == 'DAILY' and fact.get('adjustment') == 'RAW' and not fact.get('errors'):
                days.setdefault(fact['trade_date'], []).append(fact)
        differences = []
        for day, facts in days.items():
            for left, right in combinations(facts, 2):
                changed = {}
                for field in ['open', 'close', 'high', 'low', 'volume_shares', 'amount_yuan']:
                    a, b = left.get(field), right.get(field)
                    if a is None or b is None:
                        continue
                    try:
                        differs = Decimal(str(a)) != Decimal(str(b))
                    except InvalidOperation:
                        differs = a != b
                    if differs:
                        changed[field] = {'left': a, 'right': b}
                if changed:
                    differences.append({'trade_date': day, 'left_source': left['source_id'],
                        'right_source': right['source_id'], 'left_raw_hash': left['raw_hash'],
                        'right_raw_hash': right['raw_hash'], 'fields': changed,
                        'resolution': 'UNRESOLVED; BOTH_SOURCE_VALUES_RETAINED', 'independence': 'NOT_ASSERTED'})
        value = {'comparison_id': str(uuid4()), 'plan_id': plan_id, 'created_at': now(),
                 'comparison_basis': 'EXACT_DECIMAL_SOURCE_VALUES; DISPLAY_PRECISION_NOT_SILENTLY_NORMALIZED',
                 'differences': differences, 'source_winner': None}
        with self.ledger.connection() as db:
            db.execute('INSERT INTO collection_comparison_reports VALUES(?,?,?)', (value['comparison_id'], plan_id, encode(value)))
        return value

    def comparisons(self, plan_id):
        with self.ledger.connection() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT value FROM collection_comparison_reports WHERE plan_id=? ORDER BY rowid DESC LIMIT 10', (plan_id,))]

    def integrity(self):
        """Read-only database and archive verification; never delete or repair evidence."""
        with self.ledger.connection() as db:
            result = db.execute('PRAGMA integrity_check').fetchone()[0]
            archives = [r[0] for r in db.execute('SELECT sha256 FROM evidence_archives')]
            plans = {r[0]: json.loads(r[1]) for r in db.execute('SELECT id,value FROM pit_collection_plans')}
            batches = {r[0]: json.loads(r[1]) for r in db.execute('SELECT id,value FROM pit_collection_batches')}
            versions = list(db.execute('SELECT plan_id,batch_id,value,fact_key,known_at FROM pit_fact_versions'))
        failures = []
        for sha in archives:
            try:
                self.evidence.raw(sha)
            except (HTTPException, OSError):
                failures.append(sha)
        references = []
        snapshot_facts = {}
        for batch in batches.values():
            if batch.get('snapshot_id'):
                try:
                    replay = self.evidence.replay(batch['run_id'])
                    snapshot_facts[batch['batch_id']] = {encode(f) for f in replay['facts']}
                except (HTTPException, OSError, ValueError, KeyError):
                    references.append({'batch_id': batch['batch_id'], 'code': 'SNAPSHOT_REPLAY_FAILED'})
        for row in versions:
            value = json.loads(row[2])
            if row[0] not in plans or row[1] not in batches or value.get('raw_hash') not in archives:
                references.append({'batch_id': row[1], 'code': 'MISSING_FACT_REFERENCE'})
                continue
            if (batches[row[1]]['plan_id'] != row[0] or encode(value['fact']) not in snapshot_facts.get(row[1], set())
                    or row[3] != value['fact_key'] or row[4] != value['known_at']
                    or value['known_at'] != batches[row[1]]['known_at'] or value['raw_hash'] != value['fact']['raw_hash']):
                references.append({'batch_id': row[1], 'code': 'FACT_SNAPSHOT_OR_VERSION_MISMATCH'})
            if datetime.fromisoformat(value['known_at']) < datetime.fromisoformat(plans[row[0]]['started_at']):
                references.append({'batch_id': row[1], 'code': 'FACT_KNOWN_BEFORE_PLAN'})
        return {'checked_at': now(), 'sqlite': result, 'archives_checked': len(archives),
                'archive_failures': failures, 'ok': result == 'ok' and not failures and not references,
                'reference_failures': references, 'facts_checked': len(versions),
                'network_calls': 0, 'system_usable': False, 'consistent': result == 'ok' and not failures and not references}
