"""One host-day SSE statistic, archived before parsing; no implicit retry/backfill.

Daily statistic authority and complete execution/status/action authority are separate.
This successor does not reinterpret any existing packet or frozen adapter.
"""
import asyncio
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import HTTPException

from roll.accounts.ledger import encode, now
from roll.agents.codex_process import owner_alive, process_creation
from roll.market.rules import SHANGHAI
from roll.market.post_close_packet import HISTORY_DAILY_SQL, HISTORY_REFERENCE, historical_daily, code as packet_code
from decimal import Decimal, localcontext
from pydantic import BaseModel, ConfigDict, Field

SOURCE = 'sse-dated-daily-statistic'
URL = 'https://query.sse.com.cn/commonQuery.do'
UNIT_SHA = '478fb2a72fc5a3725088adb208756e88171f79628956a9f5ca67c900d37def2f'
LIMIT = 1024 * 1024


class DailyPacketCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    predecessor_packet_id: str = Field(min_length=1)
    receipt_ids: list[str] = Field(min_length=1)
    basis: str = Field(min_length=1, max_length=2000)


def fingerprint():
    return hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n') +
                          UNIT_SHA.encode() + packet_code().encode()).hexdigest()


def unit_proof():
    manifest = (HISTORY_REFERENCE / 'sources.json').read_bytes()
    source = next(s for s in json.loads(manifest)['sources'] if s['role'] == 'daily_units')
    body = (HISTORY_REFERENCE / source['path']).read_bytes()
    if source['sha256'] != UNIT_SHA or hashlib.sha256(body).hexdigest() != UNIT_SHA or len(body) != source['bytes']:
        raise HTTPException(409, 'SSE_DAILY_UNIT_DOCUMENT_CORRUPT')
    return body, source


def parameters(day):
    return {'sqlId': HISTORY_DAILY_SQL, 'SEC_CODE': '600362', 'TX_DATE': day,
            'TX_DATE_MON': '', 'TX_DATE_YEAR': ''}


def normalize(body, archive, day, known_at, units, unit_source):
    value = json.loads(body)
    if not isinstance(value, dict): raise ValueError('SSE_DAILY_RESPONSE_NOT_OBJECT')
    rows = value.get('result')
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise ValueError('SSE_DAILY_ROW_MISSING_OR_DUPLICATED')
    # The pinned official statistic reports decimal strings. Never round JSON floats.
    if any(not isinstance(rows[0].get(k), str) for k in
           ['OPEN_PRICE', 'HIGH_PRICE', 'LOW_PRICE', 'CLOSE_PRICE', 'TRADE_VOL', 'TRADE_AMT']):
        raise ValueError('SSE_DAILY_LITERAL_DECIMAL_STRINGS_REQUIRED')
    source = {'url': archive['source_url'], 'sha256': archive['sha256'], 'received_at': archive['received_at']}
    with localcontext() as context:
        context.prec = max(28, *[len(rows[0][k]) + 20 for k in ['TRADE_VOL', 'TRADE_AMT']])
        fact = historical_daily(body, units, source, unit_source, known_at)
    if fact['trade_date'] != day: raise ValueError('SSE_DAILY_REQUEST_DATE_MISMATCH')
    return {**fact, 'source_id': SOURCE, 'group': 'DAILY_STATISTIC_ASSESSMENT',
            'known_at': known_at, 'adjustment': 'QUERY_STATISTIC_RAW_BASIS_NOT_QUALIFIED', 'volume_unit': 'SHARE',
            'completion_state': 'REPORTED_DATED_DAILY_STATISTIC',
            'turnover_scope': 'OFFICIAL_DAILY_STATISTIC_QUERY',
            'current_board_unit_authority': False, 'model_daily_input_allowed': False,
            'parser_fingerprint': fingerprint(), 'status_authority': False,
            'action_coverage_authority': False}


class DatedDaily:
    def __init__(self, prospective):
        self.prospective, self.ledger, self.evidence = prospective, prospective.ledger, prospective.evidence
        self.last_worker_check = None
        self.worker_gaps = []
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS sse_daily_jobs(plan_id TEXT, day TEXT, value TEXT NOT NULL, PRIMARY KEY(plan_id,day))')
            db.execute('CREATE TABLE IF NOT EXISTS sse_daily_receipts(id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS sse_daily_packets(id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,value TEXT NOT NULL)')
            for row in db.execute('SELECT plan_id,day,value FROM sse_daily_jobs'):
                job = json.loads(row[2])
                if job['state'] == 'CLAIMED' and not owner_alive(job):
                    job.update(state='INTERRUPTED_NO_RETRY', finished_at=now(),
                               gaps=['SSE_DAILY_INTERRUPTED_NO_IMPLICIT_RETRY'])
                    db.execute('UPDATE sse_daily_jobs SET value=? WHERE plan_id=? AND day=?', (encode(job), row[0], row[1]))

    async def fetch(self, receipt):
        body = bytearray(); finished = False; status = None; error = None
        async def consume():
            nonlocal finished, status
            async with httpx.AsyncClient(transport=self.evidence.transport, timeout=15, follow_redirects=False) as client:
                async with client.stream('GET', URL, params=receipt['parameters'], headers={'Referer': 'https://www.sse.com.cn/'}) as response:
                    status = response.status_code
                    async for part in response.aiter_bytes():
                        remaining = LIMIT - len(body); body.extend(part[:remaining])
                        if len(part) > remaining: raise ValueError('SSE_DAILY_PREFIX_BYTE_LIMIT')
                    finished = True
                    response.raise_for_status()
        receipt['network_calls'] = 1
        try: await asyncio.wait_for(consume(), timeout=15)
        except (TimeoutError, httpx.HTTPError, ValueError) as caught:
            error = str(caught) if isinstance(caught, ValueError) else type(caught).__name__
        receipt['response'] = {'archive': self.evidence.archive(bytes(body), 'SSE_DATED_DAILY_RAW',
            source_id=SOURCE, source_url=str(httpx.URL(URL, params=receipt['parameters'])),
            parameters=receipt['parameters'], received_at=now(), status_code=status,
            original_complete=finished, evidence_kind=receipt['evidence_kind']),
            'original_complete': finished, 'status_code': status, 'error': error}
        self.ledger.crash_point('sse_daily_after_raw')
        return bytes(body)

    def capture_once(self, plan_id, basis):
        plan = self.prospective.plan(plan_id); started = now(); local = datetime.fromisoformat(started).astimezone(SHANGHAI)
        day = local.date().isoformat()
        if plan['instrument'] != 'SSE:600362': raise HTTPException(403, 'SSE_DAILY_SECURITY_UNADAPTED')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT value FROM sse_daily_jobs WHERE plan_id=? AND day=?', (plan_id, day)).fetchone()
            if old:
                job = json.loads(old[0])
                return self.receipts(plan_id, ids=[job['receipt_id']])[0] if job['state'] == 'RECORDED' else job
            if local.time().replace(tzinfo=None).isoformat() < '15:05:00': raise HTTPException(409, 'SSE_DAILY_POST_CLOSE_NOT_REACHED')
            if self.evidence.market.rules.calendar('SSE', local.date(), local)['is_trading_day'] is not True:
                raise HTTPException(409, 'SSE_DAILY_KNOWN_TRADING_DAY_REQUIRED')
            units, unit_source = unit_proof()
            if any(datetime.fromisoformat(s) > datetime.fromisoformat(started) for s in [unit_source['received_at'], plan['started_at']]):
                raise HTTPException(409, 'SSE_DAILY_DOCUMENT_OR_PLAN_NOT_AVAILABLE')
            blocked = self.prospective.sources.access(SOURCE, plan['instrument'])
            if blocked: raise HTTPException(409, blocked)
            job = {'plan_id': plan_id, 'day': day, 'state': 'CLAIMED', 'started_at': started,
                   'request_budget_calls': 1, 'host_owner': {'pid': os.getpid(), 'creation_ticks': process_creation(os.getpid())}}
            db.execute('INSERT INTO sse_daily_jobs VALUES(?,?,?)', (plan_id, day, encode(job))); db.commit()
        self.evidence.archive(units, 'SSE_DAILY_UNIT_DOCUMENT', **{'source_url': unit_source['url'], 'received_at': unit_source['received_at']})
        kind = 'METHOD_CASE' if self.evidence.transport is not None else 'REAL_SOURCE_ASSESSMENT'
        receipt = {'receipt_id': str(uuid4()), 'plan_id': plan_id, 'instrument': plan['instrument'], 'source_id': SOURCE,
                   'host_date': day, 'started_at': started, 'basis': basis, 'parameters': parameters(day),
                   'parser_fingerprint': fingerprint(), 'unit_source': unit_source, 'evidence_kind': kind,
                   'request_budget_calls': 1, 'network_calls': 0, 'fact': None, 'gaps': [],
                   'system_usable': False, 'forward_started_at': None, 'capability': 'NOT_GRANTED'}
        capture_plan = {'source_id': SOURCE, 'plan_id': plan_id, 'host_date': day, 'created_at': started,
                        'url': URL, 'parameters': receipt['parameters'], 'unit_sha256': UNIT_SHA,
                        'parser_fingerprint': fingerprint(), 'request_budget_calls': 1, 'retries': 0,
                        'fallbacks': 0, 'follow_redirects': False, 'timeout_seconds': 15, 'max_bytes': LIMIT}
        receipt['capture_plan'] = capture_plan
        receipt['capture_plan_archive'] = self.evidence.archive(encode(capture_plan).encode(), 'SSE_DAILY_FINITE_PLAN', evidence_kind=kind)
        body = asyncio.run(self.fetch(receipt)); known = now()
        error = receipt['response']['error']
        if error: receipt['gaps'].append(error)
        else:
            try: receipt['fact'] = normalize(body, receipt['response']['archive'], day, known, units, unit_source)
            except (ValueError, KeyError, TypeError, IndexError) as caught: receipt['gaps'].append(str(caught))
        receipt.update(normalized_known_at=known, status='DAILY_STATISTIC_REPORTED' if receipt['fact'] else 'FAILED',
                       gaps=receipt['gaps'] + ['COMPLETE_STATUS_ACTIONS_AND_SESSION_AUTHORITY_REQUIRED'])
        receipt['archive'] = self.evidence.archive(encode(receipt).encode(), 'SSE_DAILY_RECEIPT', evidence_kind=kind)
        job.update(state='RECORDED', receipt_id=receipt['receipt_id'], finished_at=known)
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO sse_daily_receipts VALUES(?,?,?)', (receipt['receipt_id'], plan_id, encode(receipt)))
            db.execute('UPDATE sse_daily_jobs SET value=? WHERE plan_id=? AND day=?', (encode(job), plan_id, day))
            self.ledger.crash_point('sse_daily_before_commit'); db.commit()
        self.prospective.sources.outcome(SOURCE, bool(receipt['fact']), receipt['status'], receipt['receipt_id'])
        return receipt

    def receipts(self, plan_id, cutoff=None, ids=None):
        self.prospective.plan(plan_id); cutoff = cutoff or datetime.fromisoformat(now())
        with self.ledger.connection() as db:
            saved = [json.loads(r[0]) for r in db.execute('SELECT value FROM sse_daily_receipts WHERE plan_id=? ORDER BY rowid', (plan_id,))]
        selected = [s for s in saved if datetime.fromisoformat(s['normalized_known_at']) <= cutoff]
        if ids is not None:
            available = {s['receipt_id']: s for s in selected}
            if len(set(ids)) != len(ids) or any(i not in available for i in ids): raise HTTPException(409, 'SSE_DAILY_RECEIPT_NOT_KNOWN')
            selected = [available[i] for i in ids]
        units, unit_source = unit_proof()
        for value in selected:
            if json.loads(self.evidence.raw(value['archive']['sha256']).read_bytes()) != {k:v for k,v in value.items() if k != 'archive'}:
                raise HTTPException(409, 'SSE_DAILY_RECEIPT_ARCHIVE_MISMATCH')
            if value['parser_fingerprint'] != fingerprint() or value['unit_source'] != unit_source:
                raise HTTPException(409, 'SSE_DAILY_IMPLEMENTATION_CHANGED_SUCCESSOR_REQUIRED')
            self.evidence.raw(UNIT_SHA)
            if value['parameters'] != parameters(value['host_date']) or value['network_calls'] != 1:
                raise HTTPException(409, 'SSE_DAILY_REQUEST_BINDING_MISMATCH')
            if json.loads(self.evidence.raw(value['capture_plan_archive']['sha256']).read_bytes()) != value['capture_plan']:
                raise HTTPException(409, 'SSE_DAILY_CAPTURE_PLAN_MISMATCH')
            archive = value['response']['archive']; body = self.evidence.raw(archive['sha256']).read_bytes()
            original_url = httpx.URL(archive['source_url'])
            if (archive['parameters'] != value['parameters'] or original_url.copy_with(query=None) != httpx.URL(URL) or
                dict(original_url.params) != value['parameters']):
                raise HTTPException(409, 'SSE_DAILY_ORIGINAL_REQUEST_MISMATCH')
            if value['fact']:
                try: fact = normalize(body, archive, value['host_date'], value['normalized_known_at'], units, unit_source)
                except (ValueError, KeyError, TypeError, IndexError) as caught: raise HTTPException(409, str(caught))
                if fact != value['fact']: raise HTTPException(409, 'SSE_DAILY_NORMALIZED_ORIGINAL_MISMATCH')
        return selected

    def predecessor(self, plan_id, packet_id):
        with self.ledger.connection() as db:
            row = db.execute('SELECT value FROM post_close_packets WHERE id=? AND plan_id=?', (packet_id, plan_id)).fetchone()
        if not row: raise HTTPException(404, 'SSE_DAILY_PREDECESSOR_MISSING')
        if not self.prospective.post_close.replay(packet_id)['matches_original']:
            raise HTTPException(409, 'SSE_DAILY_PREDECESSOR_REPLAY_MISMATCH')
        return json.loads(row[0])

    def build(self, plan_id, command):
        cutoff = datetime.fromisoformat(now())
        predecessor = self.predecessor(plan_id, command.predecessor_packet_id)
        if datetime.fromisoformat(predecessor['knowledge_cutoff']) > cutoff:
            raise HTTPException(409, 'SSE_DAILY_PREDECESSOR_NOT_AVAILABLE')
        receipts = self.receipts(plan_id, cutoff, command.receipt_ids)
        value = {'packet_id': str(uuid4()), 'packet_type': 'DATED_DAILY_SUCCESSOR', 'plan_id': plan_id,
            'predecessor_packet_id': command.predecessor_packet_id, 'predecessor': predecessor,
            'receipt_ids': command.receipt_ids, 'receipts': receipts,
            'daily_statistic_facts': [r['fact'] for r in receipts if r['fact']],
            'gaps': sorted(set(predecessor['gaps'] + [g for r in receipts for g in r['gaps']])),
            'knowledge_cutoff': cutoff.isoformat(), 'basis': command.basis,
            'parser_fingerprint': fingerprint(), 'network_calls': 0, 'forward_admissible': False,
            'forward_started_at': None, 'system_usable': False, 'capability': 'NOT_GRANTED'}
        value['archive'] = self.evidence.archive(encode(value).encode(), 'SSE_DATED_DAILY_PACKET',
            evidence_kind='METHOD_CASE' if any(r['evidence_kind'] == 'METHOD_CASE' for r in receipts) else 'REAL_SOURCE_ASSESSMENT')
        with self.ledger.connection() as db:
            db.execute('INSERT INTO sse_daily_packets VALUES(?,?,?)', (value['packet_id'], plan_id, encode(value)))
        return value

    def saved_packet(self, packet_id):
        with self.ledger.connection() as db:
            row = db.execute('SELECT value FROM sse_daily_packets WHERE id=?', (packet_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def replay(self, packet_id):
        value = self.saved_packet(packet_id)
        if not value: raise HTTPException(404, 'SSE_DAILY_PACKET_MISSING')
        if json.loads(self.evidence.raw(value['archive']['sha256']).read_bytes()) != {k:v for k,v in value.items() if k != 'archive'}:
            raise HTTPException(409, 'SSE_DAILY_PACKET_ARCHIVE_MISMATCH')
        if value['parser_fingerprint'] != fingerprint(): raise HTTPException(409, 'SSE_DAILY_PACKET_IMPLEMENTATION_CHANGED')
        cutoff = datetime.fromisoformat(value['knowledge_cutoff'])
        predecessor = self.predecessor(value['plan_id'], value['predecessor_packet_id'])
        if datetime.fromisoformat(predecessor['knowledge_cutoff']) > cutoff:
            raise HTTPException(409, 'SSE_DAILY_PREDECESSOR_NOT_AVAILABLE')
        receipts = self.receipts(value['plan_id'], cutoff, value['receipt_ids'])
        matches = (predecessor == value['predecessor'] and receipts == value['receipts'] and
            [r['fact'] for r in receipts if r['fact']] == value['daily_statistic_facts'] and
            sorted(set(predecessor['gaps'] + [g for r in receipts for g in r['gaps']])) == value['gaps'])
        return {'packet_id': packet_id, 'packet_type': 'DATED_DAILY_SUCCESSOR', 'matches_original': matches,
                'network_calls': 0, 'forward_admissible': False, 'capability': 'NOT_GRANTED'}

    def packet(self, plan_id, packet_id):
        value = self.saved_packet(packet_id)
        if not value or value['plan_id'] != plan_id: raise HTTPException(404, 'SSE_DAILY_PACKET_MISSING')
        if not self.replay(packet_id)['matches_original']: raise HTTPException(409, 'SSE_DAILY_PACKET_REPLAY_MISMATCH')
        return value

    def work(self):
        checked = datetime.fromisoformat(now())
        if self.last_worker_check and (checked - self.last_worker_check).total_seconds() < 60: return
        self.last_worker_check = checked
        local = checked.astimezone(SHANGHAI)
        if (local.time().replace(tzinfo=None).isoformat() < '15:05:00' or
            self.evidence.market.rules.calendar('SSE', local.date(), local)['is_trading_day'] is not True): return
        self.worker_gaps = []
        for plan in self.prospective.plans():
            if plan['instrument'] != 'SSE:600362': continue
            try: self.capture_once(plan['plan_id'], 'Existing single worker host-day daily statistic')
            except HTTPException as error:
                self.worker_gaps.append({'plan_id': plan['plan_id'], 'checked_at': checked.isoformat(), 'code': error.detail})
