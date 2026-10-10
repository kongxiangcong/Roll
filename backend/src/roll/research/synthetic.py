"""One fixed virtual development case; never consumes a real research family's budget."""
import hashlib
import json
import math
from datetime import date
from io import BytesIO
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from fastapi import HTTPException
from roll.accounts.ledger import encode, now
from roll.agents.codex_process import owner_alive
from roll.research.datasets import DatasetCommand, MethodWindows
from roll.research.execution import ExecutionCommand
from roll.research.models import ModelCommand, ForecastCommand
from roll.research.registry import ProtocolCommand
from roll.research.training_preflight import admit_model_training


def write_virtual_archive(directory, rules):
    source = directory/'research-inputs'/'ticket19-synthetic-v1'
    source.mkdir(parents=True, exist_ok=True)
    dates = ['2024-01-02']
    while len(dates) < 420:
        dates.append(rules.next_trading_day('SSE', date.fromisoformat(dates[-1])))
    rows = []
    acquired = now()
    for index, day in enumerate(dates):
        close = round(100+14*math.sin(index/13)+3*math.cos(index/5), 2)
        volume = 100000+index*37+round(15000*math.sin(index/9))
        rows.append({'instrument': 'SSE:600362', 'group': 'DAILY', 'adjustment': 'RAW', 'trade_date': day,
            'open': str(close), 'close': str(close), 'high': str(round(close+1, 2)), 'low': str(round(close-1, 2)),
            'volume_shares': str(volume), 'volume_unit': 'SHARE', 'amount_yuan': str(round(close*volume, 2)),
            'available_at': acquired, 'completion_state': 'COMPLETE_REPORTED_HISTORICAL',
            'method_completion_available_at': day+'T15:01:00+08:00', 'evidence_kind': 'METHOD_CASE',
            'namespace': 'HISTORICAL', 'errors': [],
            'execution_evidence': {'state': 'CONFIRMED_NORMAL', 'company_actions': 'CONFIRMED_NONE',
                'rule_scope': 'METHOD_CASE_ONLY', 'buy_minimum': '100', 'buy_increment': '100',
                'price_tick_yuan': '0.01', 'resale': 'NEXT_TRADING_DAY', 'close_time': '15:00:00',
                'normal_price_limit_percent': '10'}})
    raw = encode({'kind': 'METHOD_CASE', 'generator': 'ticket19-synthetic-v1',
                  'description': 'Virtual sinusoidal OHLC, volume and known execution state; no real market evidence', 'rows': rows}).encode()
    digest = hashlib.sha256(raw).hexdigest()
    (source/(digest+'.raw')).write_bytes(raw)
    for row in rows:
        row['raw_hash'] = digest
    buffer = BytesIO()
    pq.write_table(pa.Table.from_pylist([{'payload': encode(row)} for row in rows]), buffer)
    parquet = buffer.getvalue(); parquet_sha = hashlib.sha256(parquet).hexdigest()
    (source/(parquet_sha+'.parquet')).write_bytes(parquet)
    bundle = {'request': {'identity_context': {'SSE:600362': {'exchange': 'SSE', 'board': 'MAIN', 'instrument_type': 'STOCK'}}},
              'run': {'run_id': 'virtual19-source', 'evidence_kind': 'METHOD_CASE'},
              'snapshot': {'snapshot_id': 'virtual19-snapshot', 'adapter_version': 'VIRTUAL19_V1',
                'evidence_kind': 'METHOD_CASE', 'facts': rows,
                'archives': [{'sha256': digest, 'kind': 'RAW_RESPONSE', 'bytes': len(raw)}],
                'parquet': {'sha256': parquet_sha, 'kind': 'NORMALIZED_PARQUET', 'bytes': len(parquet)}}}
    (source/'browser-live.json').write_text(encode(bundle), encoding='utf-8')
    return dates


class SyntheticDevelopment:
    def __init__(self, registry, executions, models):
        self.registry, self.executions, self.models = registry, executions, models
        self.ledger = registry.ledger
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS research_development_runs(id TEXT PRIMARY KEY,value TEXT NOT NULL)')
            for row in db.execute('SELECT id,value FROM research_development_runs'):
                previous = json.loads(row['value'])
                if previous['status'] == 'RUNNING' and not owner_alive(previous):
                    previous.update(status='INTERRUPTED', finished_at=now(), reason='Previous virtual development host stopped; no automatic retry')
                    db.execute('UPDATE research_development_runs SET value=? WHERE id=?', (encode(previous), row['id']))

    def runs(self):
        with self.ledger.connection() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT value FROM research_development_runs ORDER BY rowid')]

    def create(self):
        # Single fixed case per database. Failed/interrupted work is retained, not silently retried/reset.
        run = {'development_run_id': 'ticket19-synthetic-v1', 'started_at': now(), 'status': 'RUNNING',
               'evidence_kind': 'METHOD_CASE', 'namespace': 'SYNTHETIC_DEVELOPMENT', 'system_usable': False,
               'host_owner': self.registry.owner,
               'capability': 'NOT_GRANTED', 'forward_started_at': None, 'real_attempt_budget_consumed': False}
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT value FROM research_development_runs WHERE id=?', (run['development_run_id'],)).fetchone()
            if old:
                return json.loads(old[0])
            # The engineering lab must be an isolated database; never create a new real family to evade budget.
            if db.execute('SELECT 1 FROM research_protocols LIMIT 1').fetchone() or self.ledger.account(db=db)['version'] != 0:
                raise HTTPException(409, '虚拟框架开发须使用独立空数据库，不混入已有真实账户/研究家族')
            db.execute('INSERT INTO research_development_runs VALUES(?,?)', (run['development_run_id'], encode(run)))
            db.commit()
        try:
            dates = write_virtual_archive(self.registry.evidence.directory, self.registry.evidence.market.rules)
            dataset = self.registry.register_dataset(DatasetCommand(archive_id='ticket19-synthetic-v1',
                method_windows=MethodWindows(), basis='Ticket19 isolated virtual development; no real PIT or qualification'))
            protocol = self.registry.register(ProtocolCommand(dataset_id=dataset['dataset_id'], basis='Fixed virtual DEV160/embargo20/CAL160/embargo20/SEALED60; no search'))
            pid = protocol['protocol_id']; run.update(dataset_id=dataset['dataset_id'], protocol_id=pid)
            for name, indices in [('DEVELOPMENT', range(20, 140)), ('CALIBRATION', range(180, 320))]:
                for index in indices:
                    self.executions.create(pid, ExecutionCommand(partition=name, observation_date=date.fromisoformat(dates[index]),
                        label_as_of=now(), quantity='200', basis='Explicit virtual fee-after20-session label'))
            admit_model_training(self.registry, pid, 'METHOD_VALIDATION')
            model = self.models.create(pid, ModelCommand(purpose='METHOD_VALIDATION', basis='Fixed virtual four-feature logit and intercept calibration'))
            run['model_run_id'] = model['model_run_id']
            if model['status'] != 'METHOD_ARTIFACT_ONLY':
                raise ValueError('VIRTUAL_MODEL_BUILD_FAILED')
            forecast = self.models.forecast(model['model_run_id'], ForecastCommand(observation_date=date.fromisoformat(dates[250]), basis='Virtual calibrated forecast; no published action'))
            replay = self.models.replay(forecast['forecast_id'])
            if not replay['matches_original']:
                raise ValueError('VIRTUAL_REPLAY_MISMATCH')
            frozen = {'evidence_kind': 'METHOD_CASE', 'namespace': 'SYNTHETIC_DEVELOPMENT',
                      'artifact_fingerprints': model['artifact_fingerprints'],
                      'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      'dataset_import_sha256': hashlib.sha256(Path(__file__).with_name('datasets.py').read_bytes()).hexdigest(),
                      'attempt_ids': self.registry.attempt_manifest(pid)['attempt_ids'],
                      'forecast_id': forecast['forecast_id'], 'system_usable': False, 'capability': 'NOT_GRANTED'}
            archive = self.registry.evidence.archive(encode(frozen).encode(), 'VIRTUAL_DEVELOPMENT_FREEZE')
            run.update(status='ENGINEERING_COMPLETE', forecast_id=forecast['forecast_id'], replay=replay,
                       statistical_support=model['statistical_support'], artifact_fingerprints=model['artifact_fingerprints'],
                       development_freeze=archive, real_model_frozen=False, complete_experiment_frozen=False,
                       validation_verdict=None, sealed_consumed=False)
        except Exception as error:
            run.update(status='FAILED', error=type(error).__name__, reason=str(error) if isinstance(error, ValueError) else 'Inspect persisted engineering attempt and host logs')
        run['finished_at'] = now()
        with self.ledger.connection() as db:
            db.execute('UPDATE research_development_runs SET value=? WHERE id=?', (encode(run), run['development_run_id']))
        return run
