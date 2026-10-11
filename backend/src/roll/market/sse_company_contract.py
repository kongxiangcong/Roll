"""Two exact official company-client sources; document transforms do not prove complete status."""
import hashlib
import json
import os
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from uuid import uuid4
import httpx
from fastapi import HTTPException
from roll.accounts.ledger import encode, now
from roll.market.rules import SHANGHAI
from roll.agents.codex_process import owner_alive, process_creation

SOURCE = 'sse-company-client-contract'
REFERENCE = Path(__file__).parent / 'reference/sse-company-contract'
HTML_SHA = '72bdf9f924465e3c848577fa4ec5285c163474a79be9bee4a0500a2ecb53f55b'
JS_SHA = '478fb2a72fc5a3725088adb208756e88171f79628956a9f5ca67c900d37def2f'
SQL = 'COMMON_SSE_CP_GPJCTPZ_GPLB_GPGK_GSGK_C'
SELECT = 'name,last,chg_rate,change,amount,volume,open,prev_close,ask,bid,high,low,tradephase,turnover_ratio,totalValue,amp_rate,circulating,up_limit,down_limit,fp_volume,fp_amount,cpxxprodusta,cpxxlmttype,fp_phase'
URLS = {'snap': 'https://yunhq.sse.com.cn:32042/v1/sh1/snap/600362',
        'company': 'https://query.sse.com.cn/sseQuery/commonQuery.do'}
PARAMS = {'snap': {'select': SELECT},
          'company': {'sqlId': SQL, 'COMPANY_CODE': '600362', 'isPagination': 'false'}}
PHASES = dict(zip('SCDTBEPMNU', ['开市前', '集合竞价', '集合竞价结束', '连续竞价', '午间休市', '闭市', '停牌', '熔断(可恢复)', '熔断(至闭市)', '收盘集合竞价']))
GAPS = ['SSE_CLIENT_UNITS_DOCUMENT_BOUND_SESSION_COMPLETION_UNPROVEN',
        'SSE_CLIENT_PHASE_NOT_COMPLETE_SUSPENSION_OR_RESUMPTION',
        'SSE_COMPANY_LISTING_RISK_ENUM_EFFECTIVE_AND_NEGATIVE_COVERAGE_UNPROVEN']

def fingerprint():
    from roll.market.post_close_packet import code
    return code()

def schema():
    mapping = (REFERENCE / 'sources.json').read_bytes()
    sources = {s['role']: s for s in json.loads(mapping)['sources']}
    bodies = {}
    for role, sha, size in [('company_html', HTML_SHA, 39826), ('company_js', JS_SHA, 277193)]:
        source = sources[role]
        if source['sha256'] != sha or source['bytes'] != size or source['path'] != sha + '.raw':
            raise ValueError('SSE_CLIENT_DOCUMENT_MAPPING_UNPROVEN')
        body = (REFERENCE / source['path']).read_bytes()
        if len(body) != size or hashlib.sha256(body).hexdigest() != sha:
            raise ValueError('SSE_CLIENT_DOCUMENT_ORIGINAL_CORRUPT')
        bodies[role] = body
    html = bodies['company_html'].decode('utf-8')
    js = bodies['company_js'].decode('utf-8')
    if not all(term in html for term in ['//query.sse.com.cn/', '//yunhq.sse.com.cn:32042/', 'search_stocksDepositoryReceipts_2021.js']):
        raise ValueError('SSE_CLIENT_HTML_HOST_BINDING_UNPROVEN')
    if not all(term in js for term in [SELECT, SQL, 'hq_queryUrl + "v1/sh1/snap/"',
        '(data[4] / 10000).toFixed(2)', '(data[5] / 100).toFixed(0)', 'data[12]',
        'tradephase.substr(0, 1)', 'data.STATE_CODE_A_DESC', 'data.A_LIST_DATE',
        'data.A_STOCK_CODE', 'resultData.COMPANY_CODE']):
        raise ValueError('SSE_CLIENT_RENDERER_CONTRACT_UNPROVEN')
    return {'sources': sources, 'bodies': bodies, 'mapping': mapping,
            'mapping_hash': hashlib.sha256(mapping).hexdigest()}

def quantity(value):
    if isinstance(value, bool) or not isinstance(value, (int, Decimal, str)):
        raise ValueError('SSE_CLIENT_NUMERIC_VALUE_UNPROVEN')
    try:
        n = Decimal(str(value))
        if not n.is_finite() or n < 0: raise ValueError('SSE_CLIENT_NUMERIC_VALUE_INVALID')
        return format(n, 'f')
    except InvalidOperation as error:
        raise ValueError('SSE_CLIENT_NUMERIC_VALUE_INVALID') from error

def display_divide(value, divisor):
    with localcontext() as context:
        context.prec = max(28, len(Decimal(value).as_tuple().digits) + 8)
        return format(Decimal(value) / divisor, 'f')

def reported_date(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError('SSE_CLIENT_DATE_UNPROVEN')
    text = str(value)
    if not re.fullmatch(r'\d{8}|\d{4}-\d{2}-\d{2}', text):
        raise ValueError('SSE_CLIENT_DATE_UNPROVEN')
    return date.fromisoformat(text).isoformat()

def parse(role, content, receipt, archive):
    value = json.loads(content, parse_float=Decimal)
    if not isinstance(value, dict): raise ValueError('SSE_CLIENT_RESPONSE_OBJECT_UNPROVEN')
    base = {'instrument': 'SSE:600362', 'source_id': SOURCE, 'raw_hash': archive['sha256'],
            'source_url': archive['source_url'], 'document_html_hash': HTML_SHA, 'document_js_hash': JS_SHA,
            'received_at': archive['received_at'], 'available_at': archive['received_at'],
            'known_at': receipt['normalized_known_at'], 'published_at': None, 'effective_at': None,
            'historical_pit_claim': False, 'system_usable': False, 'model_daily_input_allowed': False,
            'basis_raw_hashes': [archive['sha256'], HTML_SHA, JS_SHA]}
    if role == 'snap':
        if value.get('code') != '600362': raise ValueError('SSE_CLIENT_SNAP_SECURITY_UNPROVEN')
        fields = value.get('snap')
        if not isinstance(fields, list) or len(fields) != len(SELECT.split(',')):
            raise ValueError('SSE_CLIENT_SNAP_SELECT_ALIGNMENT_UNPROVEN')
        day = reported_date(value.get('date'))
        if date.fromisoformat(day) > date.fromisoformat(receipt['host_date']):
            raise ValueError('SSE_CLIENT_SNAP_DATE_AFTER_HOST')
        raw_time = value.get('time')
        if isinstance(raw_time, bool) or not isinstance(raw_time, (int, str)):
            raise ValueError('SSE_CLIENT_TIME_UNPROVEN')
        clock = str(raw_time)
        if not re.fullmatch(r'\d{5,6}', clock): raise ValueError('SSE_CLIENT_TIME_UNPROVEN')
        clock = clock.zfill(6)
        if int(clock[:2]) > 23 or int(clock[2:4]) > 59 or int(clock[4:]) > 59:
            raise ValueError('SSE_CLIENT_TIME_UNPROVEN')
        volume, amount = quantity(fields[5]), quantity(fields[4])
        phase = fields[12]
        if not isinstance(phase, str): raise ValueError('SSE_CLIENT_PHASE_UNPROVEN')
        compact = re.sub(r'\s', '', phase)
        first = compact[:1]
        return {**base, 'group': 'QUOTE', 'trade_date': day, 'date_original': value['date'],
            'time_original': raw_time, 'time_display': clock[:2] + ':' + clock[2:4] + ':' + clock[4:],
            'source_timezone': 'UNKNOWN', 'reported_date_precision': 'DATE',
            'volume_raw': volume, 'amount_raw': amount,
            'display_volume_hands_exact': display_divide(volume, 100),
            'display_amount_10000_cny_exact': display_divide(amount, 10000),
            'volume_transform_divisor': 100, 'amount_transform_divisor': 10000,
            'unit_basis': 'OFFICIAL_CLIENT_TRANSFORM_DOCUMENT_BOUND',
            'unit_source_locator': 'company.getMarketIndex exact select data[4]/10000,data[5]/100',
            'turnover_scope': 'UNKNOWN', 'completion_state': 'UNKNOWN',
            'tradephase_original': phase, 'tradephase_compact': compact, 'tradephase_first': first,
            'tradephase_display': PHASES.get(first, first), 'tradephase_full_semantics': 'UNKNOWN',
            'fp_volume_raw': quantity(fields[19]) if fields[19] is not None else None,
            'fp_amount_raw': quantity(fields[20]) if fields[20] is not None else None,
            'fp_phase_original': fields[23], 'fp_phase_semantics': 'UNKNOWN',
            'cpxxprodusta_original': fields[21], 'cpxxlmttype_original': fields[22],
            'current_complete_daily_authority': False}
    if value.get('sqlId') != SQL or value.get('actionErrors') or value.get('fieldErrors'):
        raise ValueError('SSE_COMPANY_SQL_OR_ERRORS_UNPROVEN')
    rows = value.get('result')
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise ValueError('SSE_COMPANY_ROW_MISSING_OR_AMBIGUOUS')
    row = rows[0]
    if row.get('COMPANY_CODE') != '600362' or row.get('A_STOCK_CODE') != '600362':
        raise ValueError('SSE_COMPANY_RESPONSE_SECURITY_UNPROVEN')
    if row.get('SEC_TYPE') != '主板A': raise ValueError('SSE_COMPANY_A_BRANCH_UNPROVEN')
    state = row.get('STATE_CODE_A_DESC')
    if not isinstance(state, str): raise ValueError('SSE_COMPANY_STATE_FIELD_UNPROVEN')
    listing_original = row.get('A_LIST_DATE')
    listing = reported_date(listing_original) if listing_original not in {None, '', '-'} else None
    if listing and date.fromisoformat(listing) > date.fromisoformat(receipt['host_date']):
        raise ValueError('SSE_COMPANY_LIST_DATE_AFTER_HOST')
    return {**base, 'group': 'STATUS', 'trade_date': receipt['host_date'], 'source_reported_date': None,
            'source_reported_date_precision': 'UNKNOWN', 'company_state_reported': state,
            'listing_date_original': listing_original, 'listing_date_reported': listing,
            'listing_date_precision': 'DATE' if listing else 'UNKNOWN', 'status_a_original': row.get('STATUS_A'),
            'sec_type_reported': row['SEC_TYPE'], 'state': 'REPORTED_COMPANY_DESCRIPTION_FULL_STATUS_UNKNOWN',
            'listing_stage': None, 'risk_warning': None, 'st_subtype': None, 'suspension': None,
            'resume_date': None, 'ex_rights': None, 'complete_status_verified': False,
            'negative_coverage_verified': False}

def capture_plan(contract, receipt):
    return {'capture_id': receipt['receipt_id'], 'collection_plan_id': receipt['plan_id'],
            'created_at': receipt['started_at'], 'host_date': receipt['host_date'],
            'source_id': SOURCE, 'html_hash': HTML_SHA, 'js_hash': JS_SHA,
            'mapping_hash': contract['mapping_hash'], 'parser_fingerprint': receipt['parser_fingerprint'],
            'requests': [{'role': role, 'url': URLS[role], 'parameters': PARAMS[role]} for role in ['snap', 'company']],
            'request_budget_calls': 2, 'method': 'GET', 'response_variant': 'JSON_WITHOUT_CALLBACK',
            'declared_client_transport': 'POST_JSONP_CALLBACK', 'client_transport_equivalence_claim': False,
            'timeout_seconds': 15, 'max_decoded_bytes': 8 * 1024 * 1024,
            'follow_redirects': False, 'retries': 0, 'fallbacks': 0, 'system_usable': False}

class CompanyContracts:
    def __init__(self, prospective):
        self.prospective, self.ledger, self.evidence = prospective, prospective.ledger, prospective.evidence
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS company_contract_receipts(id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS company_contract_jobs(plan_id TEXT NOT NULL,day TEXT NOT NULL,value TEXT NOT NULL,PRIMARY KEY(plan_id,day))')
            for saved in db.execute('SELECT plan_id,day,value FROM company_contract_jobs'):
                job = json.loads(saved[2])
                if job['state'] == 'CLAIMED' and not owner_alive(job):
                    job.update(state='INTERRUPTED', finished_at=now(), gaps=['SSE_CLIENT_WORKER_INTERRUPTED_NO_RETRY'])
                    db.execute('UPDATE company_contract_jobs SET value=? WHERE plan_id=? AND day=?', (encode(job), saved[0], saved[1]))

    def fetch(self, client, role, receipt):
        receipt['network_calls'] += 1
        with client.stream('GET', URLS[role], params=PARAMS[role], headers={'Referer': 'https://www.sse.com.cn/'}) as response:
            body = bytearray(); error = None; truncated = False
            try:
                for part in response.iter_bytes():
                    remaining = 8 * 1024 * 1024 - len(body)
                    body.extend(part[:remaining])
                    if len(part) > remaining: truncated = True; break
            except httpx.HTTPError as caught: error = caught
            archive = self.evidence.archive(bytes(body), 'SSE_CLIENT_RAW_RESPONSE', source_id=SOURCE,
                source_url=str(response.url), received_at=now(), status_code=response.status_code,
                parameters=PARAMS[role], evidence_kind=receipt['evidence_kind'],
                original_complete=not truncated and error is None, content_type=response.headers.get('content-type'),
                stream_error=type(error).__name__ if error else None)
            receipt['responses'][role] = {'archive': archive, 'parameters': PARAMS[role],
                'original_complete': not truncated and error is None}
            if error: raise error
            if truncated: raise ValueError('SSE_CLIENT_BYTE_LIMIT_PREFIX_ONLY')
            response.raise_for_status()
            return bytes(body), archive

    def capture(self, plan_id, basis):
        plan = self.prospective.plan(plan_id)
        if plan['instrument'] != 'SSE:600362': raise HTTPException(403, 'SSE company contract only adapts SSE:600362')
        try: contract = schema()
        except (ValueError, KeyError, TypeError, IndexError) as error: raise HTTPException(409, str(error))
        started = now()
        if datetime.fromisoformat(started) < datetime.fromisoformat(plan['started_at']):
            raise HTTPException(409, 'SSE_CLIENT_CAPTURE_BEFORE_COLLECTION_PLAN')
        if any(datetime.fromisoformat(s['received_at']) > datetime.fromisoformat(started) for s in contract['sources'].values()):
            raise HTTPException(409, 'SSE_CLIENT_DOCUMENT_AFTER_CAPTURE')
        for role, body in contract['bodies'].items(): self.evidence.archive(body, 'SSE_CLIENT_' + role.upper())
        self.evidence.archive(contract['mapping'], 'SSE_CLIENT_DOCUMENT_MAPPING')
        receipt = {'receipt_id': str(uuid4()), 'plan_id': plan_id, 'instrument': plan['instrument'],
            'source_id': SOURCE, 'basis': basis, 'started_at': started,
            'host_date': datetime.fromisoformat(started).astimezone(SHANGHAI).date().isoformat(),
            'parser_fingerprint': fingerprint(), 'mapping_hash': contract['mapping_hash'],
            'document_sources': contract['sources'], 'request_budget_calls': 2, 'network_calls': 0,
            'evidence_kind': 'METHOD_CASE' if self.evidence.transport is not None else 'REAL_SOURCE_ASSESSMENT',
            'responses': {}, 'errors': {}, 'quote_fact': None, 'company_fact': None,
            'system_usable': False, 'complete_status_verified': False, 'no_event_authority': False,
            'actual_forward_start': False, 'forward_started_at': None, 'capability': 'NOT_GRANTED'}
        receipt['capture_plan'] = capture_plan(contract, receipt)
        receipt['capture_plan_archive'] = self.evidence.archive(encode(receipt['capture_plan']).encode(),
            'SSE_CLIENT_FINITE_PLAN', created_at=started, evidence_kind=receipt['evidence_kind'])
        blocked = self.prospective.sources.access(SOURCE, plan['instrument'])
        if blocked: receipt['errors']['access'] = blocked
        else:
            with httpx.Client(transport=self.evidence.transport, follow_redirects=False, timeout=15) as client:
                for role in ['snap', 'company']:
                    try:
                        body, archive = self.fetch(client, role, receipt)
                        receipt['normalized_known_at'] = now()
                        receipt['quote_fact' if role == 'snap' else 'company_fact'] = parse(role, body, receipt, archive)
                    except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
                        receipt['errors'][role] = str(error)[:160] if isinstance(error, ValueError) else type(error).__name__
        receipt.update(finished_at=now(), normalized_known_at=now(), status='REPORTED_PARTIAL' if not receipt['errors'] else 'REFUSED_PARTIAL',
                       gaps=sorted(set(GAPS + ['SSE_CLIENT_' + role.upper() + '_REFUSED:' + reason for role, reason in receipt['errors'].items()])))
        receipt['archive'] = self.evidence.archive(encode(receipt).encode(), 'SSE_CLIENT_RECEIPT', evidence_kind=receipt['evidence_kind'])
        with self.ledger.connection() as db: db.execute('INSERT INTO company_contract_receipts VALUES(?,?,?)', (receipt['receipt_id'], plan_id, encode(receipt)))
        self.prospective.sources.outcome(SOURCE, not receipt['errors'], receipt['status'], receipt['receipt_id'])
        return receipt

    def receipts(self, plan_id, cutoff=None, ids=None):
        self.prospective.plan(plan_id); cutoff = cutoff or datetime.fromisoformat(now())
        with self.ledger.connection() as db:
            saved = [json.loads(r[0]) for r in db.execute('SELECT value FROM company_contract_receipts WHERE plan_id=? ORDER BY rowid', (plan_id,))]
        selected = [s for s in saved if datetime.fromisoformat(s['normalized_known_at']) <= cutoff]
        if ids is not None:
            available = {s['receipt_id']: s for s in selected}
            if len(set(ids)) != len(ids) or any(i not in available for i in ids): raise HTTPException(409, 'SSE_CLIENT_RECEIPT_MISSING')
            selected = [available[i] for i in ids]
        try: contract = schema()
        except (ValueError, KeyError, TypeError, IndexError) as error: raise HTTPException(409, str(error))
        for receipt in selected:
            original = json.loads(self.evidence.raw(receipt['archive']['sha256']).read_bytes())
            if original != {k: v for k, v in receipt.items() if k != 'archive'}: raise HTTPException(409, 'SSE_CLIENT_RECEIPT_ORIGINAL_MISMATCH')
            if receipt['parser_fingerprint'] != fingerprint(): raise HTTPException(409, 'POST_CLOSE_PARSER_CHANGED_SUCCESSOR_REQUIRED')
            for sha in [HTML_SHA, JS_SHA, receipt['mapping_hash']]: self.evidence.raw(sha)
            if receipt['mapping_hash'] != contract['mapping_hash'] or receipt['document_sources'] != contract['sources']:
                raise HTTPException(409, 'SSE_CLIENT_DOCUMENT_BINDING_MISMATCH')
            plan = json.loads(self.evidence.raw(receipt['capture_plan_archive']['sha256']).read_bytes())
            if plan != receipt['capture_plan'] or plan != capture_plan(contract, receipt): raise HTTPException(409, 'SSE_CLIENT_FINITE_PLAN_MISMATCH')
            for role, saved_response in receipt['responses'].items():
                archive = saved_response['archive']; body = self.evidence.raw(archive['sha256']).read_bytes()
                expected_url = str(httpx.URL(URLS[role], params=PARAMS[role]))
                if archive['source_url'] != expected_url or saved_response['parameters'] != PARAMS[role]:
                    raise HTTPException(409, 'SSE_CLIENT_REQUEST_BINDING_MISMATCH')
                fact = receipt['quote_fact' if role == 'snap' else 'company_fact']
                if fact:
                    context = {**receipt, 'normalized_known_at': fact['known_at']}
                    try: parsed = parse(role, body, context, archive)
                    except (ValueError, KeyError, TypeError) as error: raise HTTPException(409, str(error))
                    if parsed != fact: raise HTTPException(409, 'SSE_CLIENT_NORMALIZED_ORIGINAL_MISMATCH')
        return selected

    def jobs(self, plan_id):
        self.prospective.plan(plan_id)
        with self.ledger.connection() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT value FROM company_contract_jobs WHERE plan_id=? ORDER BY rowid', (plan_id,))]

    def capture_once(self, plan_id, basis):
        self.prospective.plan(plan_id); day = datetime.fromisoformat(now()).astimezone(SHANGHAI).date().isoformat()
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT value FROM company_contract_jobs WHERE plan_id=? AND day=?', (plan_id, day)).fetchone()
            if old: return json.loads(old[0])
            job = {'plan_id': plan_id, 'day': day, 'source_id': SOURCE, 'state': 'CLAIMED', 'basis': basis,
                   'started_at': now(), 'request_budget_calls': 2, 'actual_forward_start': False,
                   'host_owner': {'pid': os.getpid(), 'creation_ticks': process_creation(os.getpid())}}
            db.execute('INSERT INTO company_contract_jobs VALUES(?,?,?)', (plan_id, day, encode(job))); db.commit()
        try:
            receipt = self.capture(plan_id, basis)
            job.update(state='RECORDED', receipt_id=receipt['receipt_id'], gaps=receipt['gaps'], finished_at=now())
        except HTTPException as error: job.update(state='REFUSED', gaps=[str(error.detail)], finished_at=now())
        with self.ledger.connection() as db: db.execute('UPDATE company_contract_jobs SET value=? WHERE plan_id=? AND day=?', (encode(job), plan_id, day))
        return job
