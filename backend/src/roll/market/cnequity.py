"""Bounded pinned CNEquity subprocess → archived candidate facts → Roll PIT ledger."""
import base64
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from datetime import datetime, timedelta
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq

from roll.accounts.ledger import encode, now
from roll.market.collection_cleaning import clean_rows
from roll.market.collection_sources import CNE_COMMIT, CLEANING_VERSION
from roll.market.evidence import DataRequest
from roll.market.rules import SHANGHAI
from roll.agents.codex_process import process_creation

ROOT = Path(__file__).resolve().parents[4]
RUNTIME = ROOT/'.roll-data/cnequity-runtime'


def acquire(command):
    marker = RUNTIME/'runtime.json'
    python = RUNTIME/'.venv'/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not marker.exists() or not python.exists():
        raise ValueError('CNEQUITY_RUNTIME_NOT_INSTALLED')
    manifest = json.loads(marker.read_text(encoding='utf-8'))
    if manifest['commit'] != CNE_COMMIT:
        raise ValueError('CNEQUITY_RUNTIME_COMMIT_MISMATCH')
    # No arbitrary executable, endpoint, credentials or commands from HTTP clients.
    environment = {k: v for k, v in os.environ.items() if k.upper() in {
        'SYSTEMROOT', 'WINDIR', 'PATH', 'TEMP', 'TMP', 'USERPROFILE', 'LOCALAPPDATA',
        'APPDATA', 'HTTP_PROXY', 'HTTPS_PROXY', 'NO_PROXY', 'SSL_CERT_FILE'}}
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        process = subprocess.Popen([str(python), '-B', '-X', 'utf8', str(Path(__file__).with_name('cnequity_process.py'))],
            stdin=subprocess.PIPE, stdout=output, stderr=errors, env=environment)
        try:
            process.communicate(encode({**command, 'runtime_manifest': manifest}).encode(),
                                timeout=command['timeout_seconds']+2)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait()
            raise ValueError('CNEQUITY_HOST_DEADLINE')
        if process.returncode:
            raise ValueError('CNEQUITY_PROCESS_FAILED')
        if output.tell() > 24*1024*1024:
            raise ValueError('CNEQUITY_OUTPUT_LIMIT')
        output.seek(0)
        payload = json.loads(output.read())
    if payload.get('commit') != CNE_COMMIT or payload.get('source_id') != command['source_id']:
        raise ValueError('CNEQUITY_RESULT_BINDING_MISMATCH')
    return payload


class CNEquityCollection:
    def __init__(self, evidence, sources):
        self.evidence, self.sources = evidence, sources

    def collect(self, plan):
        # Independent views, no source winner and no fallback mislabeled as TDX.
        deadline = time.monotonic()+100
        results = []
        for source in self.sources.listing():
            if source['engine'] != 'CNEQUITY':
                continue
            results.append(self.one(plan, source, deadline))
        return results

    def one(self, plan, source, deadline):
        evidence = self.evidence
        instant = datetime.fromisoformat(now()).astimezone(SHANGHAI)
        start, end = (instant.date()-timedelta(days=45)).isoformat(), instant.date().isoformat()
        request = evidence.request(DataRequest(instruments=[plan['instrument']], groups=[source['group']],
            purpose='RESEARCH', start_date=start, end_date=end, timeout_seconds=source['timeout_seconds'],
            max_calls=source['max_calls']))
        request.update(collection_plan_id=plan['plan_id'], collection_source_id=source['id'],
                       collection_engine='CNEQUITY', source_policy_revision=source['revision'])
        for field in ['daily_source', 'status_source', 'adjustment_source']:
            request[field] = source['id']
        run = {'run_id': str(uuid4()), 'request_id': request['request_id'], 'backend': 'CNEQUITY',
               'status': 'RUNNING', 'started_at': now(), 'evidence_kind': evidence.evidence_kind,
               'commit': CNE_COMMIT, 'tools': [], 'gaps': [], 'source_policy': source,
               'host_owner': {'pid': os.getpid(), 'creation_ticks': process_creation(os.getpid()), 'nonce': str(uuid4())},
               'config_fingerprint': hashlib.sha256(encode(source).encode()).hexdigest()}
        run['roll_code_sha256'] = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                  for name in ['cnequity.py', 'cnequity_process.py', 'collection_cleaning.py']}
        with evidence.ledger.connection() as db:
            db.execute('UPDATE data_requests SET value=? WHERE id=?', (encode(request), request['request_id']))
            db.execute('INSERT INTO retrieval_runs VALUES(?,?,?)', (run['run_id'], request['request_id'], encode(run)))
        archives, facts, quarantine, payload = [], [], [], {}
        calendar = evidence.market.rules.calendar(plan['instrument'].split(':')[0], instant.date(), instant)
        blocked = self.sources.access(source['id'], plan['instrument'])
        if source['group'] == 'STATUS' and calendar['is_trading_day'] is not True:
            blocked = 'STATUS_NOT_A_VERIFIED_SESSION'
        if time.monotonic() >= deadline:
            blocked = 'COLLECTION_TIME_LIMIT'
        if blocked:
            run['gaps'].append({'source_id': source['id'], 'group': source['group'], 'code': blocked})
        else:
            try:
                command = {'source_id': source['id'], 'symbol': plan['instrument'].split(':')[1]+'.SH',
                           'start_date': start, 'end_date': end, 'max_calls': source['max_calls'],
                           'max_bytes': source['max_bytes'], 'timeout_seconds': min(source['timeout_seconds'], max(1, deadline-time.monotonic()))}
                payload = acquire(command)
                received_at = now()  # Host reception dominates all upstream clocks.
                for captured in payload.get('captures', []):
                    body = base64.b64decode(captured['body_b64'], validate=True)
                    if len(body) > source['max_bytes']:
                        raise ValueError('CNEQUITY_ARCHIVE_BYTE_LIMIT')
                    archives.append(evidence.archive(body, captured['kind'],
                        source_id=source['id'], source_url=captured['url'], received_at=received_at,
                        evidence_kind=evidence.evidence_kind, upstream_source=source['upstream'],
                        source_commit=CNE_COMMIT, request_id=request['request_id'],
                        parameters=captured.get('parameters'), wire_semantics=captured.get('wire_semantics')))
                # Persist the exact adapter export too, including any diagnostics/rows later rejected.
                export = evidence.archive(encode(payload).encode(), 'CNEQUITY_ADAPTER_EXPORT',
                    source_id=source['id'], received_at=received_at, source_commit=CNE_COMMIT,
                    evidence_kind=evidence.evidence_kind)
                archives.append(export)
                facts, quarantine = clean_rows(payload.get('rows', []), source, plan['instrument'],
                    archives, received_at, start, end, calendar)
                if payload.get('error_code'):
                    run['gaps'].append({'source_id': source['id'], 'group': source['group'], 'code': payload['error_code']})
                if not payload.get('captures'):
                    # A normalized export is useful for audit, but is not a supplier original.
                    for fact in facts:
                        fact['limitations'].append('SOURCE_RESPONSE_ORIGINAL_MISSING')
                        fact['model_daily_input_allowed'] = False
                    run['gaps'].append({'source_id': source['id'], 'group': source['group'], 'code': 'SOURCE_RESPONSE_ORIGINAL_MISSING'})
                if quarantine:
                    run['gaps'].append({'source_id': source['id'], 'group': source['group'], 'code': 'ROWS_QUARANTINED', 'count': len(quarantine)})
                valid_empty = (not payload.get('rows') and not payload.get('error_code') and bool(payload.get('captures'))
                               and source['group'] in {'ADJUSTMENTS', 'ANNOUNCEMENTS'})
                if not facts and not valid_empty:
                    run['gaps'].append({'source_id': source['id'], 'group': source['group'], 'code': 'NO_ACCEPTED_ROWS_IN_BOUNDED_QUERY'})
                success = not payload.get('error_code') and not quarantine and (bool(facts) or valid_empty)
                self.sources.outcome(source['id'], success, 'ACQUIRED' if success else 'ACQUISITION_OR_CLEANING_FAILED', run['run_id'])
            except (ValueError, OSError, KeyError, TypeError) as error:
                run['gaps'].append({'source_id': source['id'], 'group': source['group'], 'code': str(error)[:160]})
                self.sources.outcome(source['id'], False, type(error).__name__, run['run_id'])
        report = {'run_id': run['run_id'], 'source_id': source['id'], 'source_commit': CNE_COMMIT,
                  'roll_code_sha256': run['roll_code_sha256'],
                  'cleaning_version': CLEANING_VERSION, 'created_at': now(), 'input_rows': len(payload.get('rows', [])),
                  'accepted_rows': len(facts), 'quarantined_rows': quarantine, 'gaps': run['gaps'],
                  'raw_hashes': [a['sha256'] for a in archives], 'evidence_kind': evidence.evidence_kind}
        report_archive = evidence.archive(encode(report).encode(), 'CLEANING_REPORT', source_id=source['id'], received_at=now())
        archives.append(report_archive)
        buffer = BytesIO()
        pq.write_table(pa.Table.from_pylist([{'payload': encode(f)} for f in facts],
                       schema=pa.schema([pa.field('payload', pa.string())])), buffer)
        parquet = evidence.archive(buffer.getvalue(), 'NORMALIZED_PARQUET', 'parquet', adapter_version=CLEANING_VERSION)
        snapshot = {'snapshot_id': str(uuid4()), 'run_id': run['run_id'], 'request_id': request['request_id'],
                    'facts': facts, 'archives': archives, 'parquet': parquet, 'coverage': [{
                        'instrument': plan['instrument'], 'group': source['group'], 'source_id': source['id'],
                        'returned_rows': len(facts), 'request_start': start, 'request_end': end, 'full_history_verified': False}],
                    'observations': [], 'gaps': run['gaps'], 'created_at': now(), 'requested_cutoff': request['cutoff'],
                    'namespace': 'PROSPECTIVE', 'evidence_kind': evidence.evidence_kind,
                    'formal_judgment': 'DISABLED', 'adapter_version': CLEANING_VERSION,
                    'source_commit': CNE_COMMIT, 'cleaning_report_hash': report_archive['sha256']}
        snapshot['roll_code_sha256'] = run['roll_code_sha256']
        run.update(status='PARTIAL' if blocked or run['gaps'] and facts else 'FAILED' if run['gaps'] else 'COMPLETE',
                   snapshot_id=snapshot['snapshot_id'], finished_at=now(), network_calls=payload.get('calls', 0),
                   runtime_provenance=payload.get('runtime_provenance'), cleaning_report_hash=report_archive['sha256'])
        with evidence.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO market_evidence_snapshots VALUES(?,?,?)', (snapshot['snapshot_id'], run['run_id'], encode(snapshot)))
            db.execute('INSERT INTO collection_cleaning_reports VALUES(?,?)', (run['run_id'], encode(report)))
            db.execute('UPDATE retrieval_runs SET value=? WHERE id=?', (encode(run), run['run_id']))
            db.commit()
        return run
