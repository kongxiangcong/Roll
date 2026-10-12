"""Explicit offline price successor for the saved, exact SSE company snap contract.

This receipt type has its own fingerprint. Existing source receipts and daily packets
retain their original parser and meaning; quotes never establish complete daily input.
"""
import hashlib
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from roll.accounts.ledger import encode, now
from roll.market.rules import SHANGHAI
from roll.market.sse_company_contract import JS_SHA, SELECT, schema, quantity, display_divide

class PriceQuoteCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source_receipt_id: str = Field(min_length=1)
    basis: str = Field(min_length=8)

class PricePacketCommand(PriceQuoteCommand):
    predecessor_packet_id: str = Field(min_length=1)
    assessment_ids: list[str] = Field(min_length=1)

def fingerprint():
    from roll.market.post_close_packet import code
    return hashlib.sha256(b'SSE_PRICE_SUCCESSOR_V1\n' + Path(__file__).read_bytes().replace(b'\r\n', b'\n') + code().encode() + JS_SHA.encode()).hexdigest()

def prices(body, source, known_at):
    old = source['quote_fact']
    if not old: raise ValueError('SSE_PRICE_SOURCE_QUOTE_MISSING')
    contract = schema()
    js = contract['bodies']['company_js'].decode('utf-8')
    if not all(term in js for term in ['_turnover_ratio = data[13] / 100', '_turnover_ratio + "%"']):
        raise ValueError('SSE_PRICE_TURNOVER_DOCUMENT_UNPROVEN')
    value = json.loads(body, parse_float=Decimal)
    if not isinstance(value, dict) or value.get('code') != '600362' or not isinstance(value.get('snap'), list) or len(value['snap']) != 24:
        raise ValueError('SSE_PRICE_SECURITY_SELECT_UNPROVEN')
    fields = dict(zip(SELECT.split(','), value['snap']))
    result = {}
    for key in ['last', 'open', 'prev_close', 'high', 'low']:
        result[key] = quantity(fields[key])
        if Decimal(result[key]) <= 0: raise ValueError('SSE_PRICE_NONPOSITIVE:' + key)
    if Decimal(result['low']) > Decimal(result['high']) or any(
        not Decimal(result['low']) <= Decimal(result[key]) <= Decimal(result['high']) for key in ['last', 'open']):
        raise ValueError('SSE_PRICE_OHLC_INVALID')
    ratio = quantity(fields['turnover_ratio'])
    return {**old, **result, 'kind': 'QUOTE', 'known_at': known_at,
            'source_known_at': source['normalized_known_at'], 'source_receipt_id': source['receipt_id'],
            'turnover_ratio_raw': ratio, 'turnover_percent_document_exact': display_divide(ratio, 100),
            'turnover_unit_basis': 'OFFICIAL_CLIENT_DIVIDE_100_PERCENT',
            'session_scope': 'UNKNOWN', 'completion_state': 'UNKNOWN', 'price_semantics': 'SNAP_RAW_FIELDS',
            'daily_close_inferred': False, 'model_daily_input_allowed': False}

def current_state(quote, cutoff):
    day = cutoff.astimezone(SHANGHAI).date().isoformat()
    reasons = ['QUOTE_NOT_COMPLETE_DAILY_INPUT', 'SESSION_SCOPE_AND_COMPLETION_UNPROVEN']
    usable = True
    if quote['trade_date'] != day:
        usable = False; reasons.append('QUOTE_NOT_CURRENT_HOST_DATE')
    if quote['tradephase_compact'] == 'P1':
        usable = False; reasons.append('OFFICIAL_CLIENT_P1_PRICE_DISPLAY_WITHHELD')
    return {'quote_fact': quote, 'current_quote_available': usable, 'knowledge_cutoff': cutoff.isoformat(),
            'model_daily_input_allowed': False, 'system_usable': False, 'capability': 'NOT_GRANTED',
            'forward_started_at': None, 'gaps': reasons}

class PriceQuotes:
    def __init__(self, prospective):
        self.prospective = prospective
        self.ledger = prospective.ledger
        self.evidence = prospective.evidence
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS sse_price_quotes(id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS sse_price_packets(id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,value TEXT NOT NULL)')

    def assess(self, plan_id, command):
        stamp = now(); cutoff = datetime.fromisoformat(stamp)
        source = self.prospective.post_close.company_contracts.receipts(plan_id, cutoff, [command.source_receipt_id])[0]
        try:
            quote = prices(self.evidence.raw(source['responses']['snap']['archive']['sha256']).read_bytes(), source, stamp)
        except (ValueError, KeyError, TypeError) as error: raise HTTPException(409, str(error))
        value = {'assessment_id': str(uuid4()), 'plan_id': plan_id, 'source_receipt_id': source['receipt_id'],
                 'source_parser_fingerprint': source['parser_fingerprint'], 'parser_fingerprint': fingerprint(),
                 'basis': command.basis, 'normalized_known_at': stamp, 'quote_fact': quote,
                 'source_archive_hash': source['archive']['sha256'], 'mapping_hash': source['mapping_hash'],
                 'network_calls': 0, 'evidence_kind': source['evidence_kind'], 'system_usable': False,
                 'capability': 'NOT_GRANTED', 'forward_started_at': None}
        value['archive'] = self.evidence.archive(encode(value).encode(), 'SSE_PRICE_SUCCESSOR', evidence_kind=value['evidence_kind'])
        with self.ledger.connection() as db: db.execute('INSERT INTO sse_price_quotes VALUES(?,?,?)', (value['assessment_id'], plan_id, encode(value)))
        return value

    def assessments(self, plan_id, cutoff=None, ids=None):
        self.prospective.plan(plan_id); cutoff = cutoff or datetime.fromisoformat(now())
        with self.ledger.connection() as db:
            saved = [json.loads(row[0]) for row in db.execute('SELECT value FROM sse_price_quotes WHERE plan_id=? ORDER BY rowid', (plan_id,))]
        selected = [s for s in saved if datetime.fromisoformat(s['normalized_known_at']) <= cutoff]
        if ids is not None:
            available = {s['assessment_id']: s for s in selected}
            if len(set(ids)) != len(ids) or any(i not in available for i in ids): raise HTTPException(409, 'SSE_PRICE_ASSESSMENT_NOT_KNOWN')
            selected = [available[i] for i in ids]
        for value in selected:
            original = json.loads(self.evidence.raw(value['archive']['sha256']).read_bytes())
            if original != {k: v for k, v in value.items() if k != 'archive'}: raise HTTPException(409, 'SSE_PRICE_ARCHIVE_MISMATCH')
            if value['parser_fingerprint'] != fingerprint(): raise HTTPException(409, 'SSE_PRICE_PARSER_CHANGED_SUCCESSOR_REQUIRED')
            source = self.prospective.post_close.company_contracts.receipts(plan_id, cutoff, [value['source_receipt_id']])[0]
            if source['archive']['sha256'] != value['source_archive_hash'] or source['parser_fingerprint'] != value['source_parser_fingerprint'] or source['mapping_hash'] != value['mapping_hash']:
                raise HTTPException(409, 'SSE_PRICE_SOURCE_BINDING_MISMATCH')
            try: parsed = prices(self.evidence.raw(source['responses']['snap']['archive']['sha256']).read_bytes(), source, value['normalized_known_at'])
            except (ValueError, KeyError, TypeError) as error: raise HTTPException(409, str(error))
            if parsed != value['quote_fact']: raise HTTPException(409, 'SSE_PRICE_NORMALIZED_ORIGINAL_MISMATCH')
        return selected

    def current(self, plan_id):
        cutoff = datetime.fromisoformat(now()); values = self.assessments(plan_id, cutoff)
        if not values: return {'current_quote_available': False, 'system_usable': False, 'model_daily_input_allowed': False, 'gaps': ['EXPLICIT_PRICE_ASSESSMENT_MISSING'], 'assessments': []}
        return {**current_state(values[-1]['quote_fact'], cutoff), 'assessment_id': values[-1]['assessment_id'], 'assessments': values}

    def predecessor(self, plan_id, packet_id):
        self.prospective.plan(plan_id)
        with self.ledger.connection() as db:
            row = db.execute('SELECT value FROM post_close_packets WHERE id=? AND plan_id=?', (packet_id, plan_id)).fetchone()
        if not row: raise HTTPException(404, 'PRICE_PREDECESSOR_PACKET_MISSING')
        replay = self.prospective.post_close.replay(packet_id)
        if not replay['matches_original']: raise HTTPException(409, 'PRICE_PREDECESSOR_REPLAY_MISMATCH')
        return json.loads(row[0])

    def build(self, plan_id, command):
        cutoff = datetime.fromisoformat(now())
        predecessor = self.predecessor(plan_id, command.predecessor_packet_id)
        if datetime.fromisoformat(predecessor['knowledge_cutoff']) > cutoff:
            raise HTTPException(409, 'PRICE_PREDECESSOR_NOT_KNOWN')
        ids = [r['receipt_id'] for r in predecessor['company_contract_receipts']]
        if command.source_receipt_id not in ids: raise HTTPException(409, 'PRICE_PREDECESSOR_SOURCE_MISMATCH')
        assessments = self.assessments(plan_id, cutoff, command.assessment_ids)
        if any(a['source_receipt_id'] != command.source_receipt_id for a in assessments):
            raise HTTPException(409, 'PRICE_ASSESSMENT_SOURCE_MISMATCH')
        value = {'packet_type': 'PRICE_SUCCESSOR', 'packet_id': str(uuid4()), 'plan_id': plan_id,
                 'predecessor_packet_id': predecessor['packet_id'], 'predecessor': predecessor,
                 'source_receipt_id': command.source_receipt_id, 'assessment_ids': command.assessment_ids,
                 'assessments': assessments, 'quote_facts': [a['quote_fact'] for a in assessments],
                 'quote_states': [current_state(a['quote_fact'], cutoff) for a in assessments],
                 'knowledge_cutoff': cutoff.isoformat(), 'created_at': now(), 'basis': command.basis,
                 'parser_fingerprint': fingerprint(), 'network_calls': 0, 'system_usable': False,
                 'model_daily_input_allowed': False, 'forward_admissible': False, 'capability': 'NOT_GRANTED',
                 'forward_started_at': None, 'account_events_added': 0}
        value['archive'] = self.evidence.archive(encode(value).encode(), 'SSE_PRICE_SUCCESSOR_PACKET', evidence_kind='METHOD_CASE' if any(a['evidence_kind']=='METHOD_CASE' for a in assessments) else 'REAL_SOURCE_ASSESSMENT')
        with self.ledger.connection() as db: db.execute('INSERT INTO sse_price_packets VALUES(?,?,?)', (value['packet_id'], plan_id, encode(value)))
        return value

    def saved_packet(self, packet_id):
        with self.ledger.connection() as db:
            row = db.execute('SELECT value FROM sse_price_packets WHERE id=?', (packet_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def replay(self, packet_id):
        value = self.saved_packet(packet_id)
        if not value: raise HTTPException(404, 'PRICE_SUCCESSOR_PACKET_MISSING')
        original = json.loads(self.evidence.raw(value['archive']['sha256']).read_bytes())
        if original != {k: v for k, v in value.items() if k != 'archive'}: raise HTTPException(409, 'PRICE_PACKET_ARCHIVE_MISMATCH')
        if value['parser_fingerprint'] != fingerprint(): raise HTTPException(409, 'SSE_PRICE_PARSER_CHANGED_SUCCESSOR_REQUIRED')
        cutoff = datetime.fromisoformat(value['knowledge_cutoff'])
        predecessor = self.predecessor(value['plan_id'], value['predecessor_packet_id'])
        assessments = self.assessments(value['plan_id'], cutoff, value['assessment_ids'])
        if (datetime.fromisoformat(predecessor['knowledge_cutoff']) > cutoff or
            value['source_receipt_id'] not in [r['receipt_id'] for r in predecessor['company_contract_receipts']] or
            any(a['source_receipt_id'] != value['source_receipt_id'] for a in assessments)):
            raise HTTPException(409, 'PRICE_PACKET_SOURCE_BINDING_MISMATCH')
        matches = (predecessor == value['predecessor'] and assessments == value['assessments'] and
                   [a['quote_fact'] for a in assessments] == value['quote_facts'] and
                   [current_state(a['quote_fact'], cutoff) for a in assessments] == value['quote_states'])
        return {'packet_id': packet_id, 'packet_type': 'PRICE_SUCCESSOR', 'matches_original': matches,
                'network_calls': 0, 'forward_admissible': False, 'capability': 'NOT_GRANTED'}

    def packet(self, plan_id, packet_id):
        value = self.saved_packet(packet_id)
        if not value or value['plan_id'] != plan_id: raise HTTPException(404, 'PRICE_SUCCESSOR_PACKET_MISSING')
        if not self.replay(packet_id)['matches_original']: raise HTTPException(409, 'PRICE_PACKET_REPLAY_MISMATCH')
        return value
