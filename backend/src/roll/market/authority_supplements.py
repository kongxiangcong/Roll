"""Append-only, source-bound observations; never reinterpret frozen source packets."""
import hashlib
import json
import re
import unicodedata
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from pypdf import PdfReader
from roll.accounts.ledger import encode, now
from roll.market.rules import SHANGHAI
from roll.market import daily_sessions

REFERENCE = Path(__file__).parent / 'reference/authority-20261020'
MANIFEST = '6a81b945a9e782f7ff25cebc1faf905e0d88f72ee85cda2ac1b630445abb65e7'
ACTION_REFERENCE = Path(__file__).parent / 'reference/action-older-20261020'
ACTION_MANIFEST = '9963f062c418c07e2e905c9cf3c720e77750392b88223023615837dac816a483'
PHASES = dict(zip('IAHDF', ['开市前', '集中撮合', '连续交易', '闭市', '停牌']))


class AuthorityCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['DAILY', 'STATUS_PHASE', 'ACTION_DOCUMENTS', 'DAILY_SESSION']
    snapshot_id: str | None = None
    instrument: Literal['SSE:600362'] = 'SSE:600362'
    idempotency_key: str = Field(min_length=1, max_length=120)


def reference():
    return checked_reference(REFERENCE, MANIFEST)


def checked_reference(directory, manifest):
    try:
        body = (directory / 'sources.json').read_bytes()
    except OSError as exc:
        raise HTTPException(409, 'AUTHORITY_MANIFEST_UNAVAILABLE') from exc
    if hashlib.sha256(body).hexdigest() != manifest:
        raise HTTPException(409, 'AUTHORITY_MANIFEST_CORRUPT')
    catalog = json.loads(body); bodies = {}
    for role, item in catalog['sources'].items():
        try:
            raw = (directory / item['path']).read_bytes()
        except OSError as exc:
            raise HTTPException(409, 'AUTHORITY_ORIGINAL_UNAVAILABLE:' + role) from exc
        if len(raw) != item['bytes'] or hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise HTTPException(409, 'AUTHORITY_ORIGINAL_CORRUPT:' + role)
        bodies[role] = raw
    return catalog, bodies, body


def daily_use(fact):
    """Stricter successor consumer; legacy parser/flags and archives stay intact."""
    gaps = list(fact.get('errors', []))
    if fact.get('source_id') != 'baostock-daily': gaps.append('DAILY_SOURCE_NOT_ADAPTED')
    if fact.get('instrument') != 'SSE:600362': gaps.append('DAILY_SECURITY_NOT_ADAPTED')
    if fact.get('adjustment') != 'RAW': gaps.append('RAW_BASIS_REQUIRED')
    if fact.get('completion_state') != 'COMPLETE_REPORTED_HISTORICAL': gaps.append('COMPLETED_PRIOR_DAY_REQUIRED')
    if fact.get('reported_tradestatus') != '1': gaps.append('SUSPENSION_OR_UNKNOWN_NOT_SCORABLE')
    for field in ['volume_shares', 'amount_yuan']:
        value = fact.get(field)
        if value is None or not Decimal(value).is_finite() or Decimal(value) <= 0:
            gaps.append('POSITIVE_' + field.upper() + '_REQUIRED')
    return {'provider_daily_allowed': not gaps, 'rejections': sorted(set(gaps)),
            'strict_historical_as_of_allowed': False, 'revision_state': 'CURRENT_RECEIVED_VERSION_HISTORY_UNKNOWN',
            'turnover_scope': 'PROVIDER_DAILY_ACCUMULATION_NOT_EXCHANGE_ALL_PHASE_EQUIVALENCE',
            'model_daily_input_allowed': False,
            'model_gaps': ['JOINT_STATUS_ACTION_RULE_AND_CONFLICT_ADMISSION_REQUIRED']}


def compact_pdf(body):
    if not body.startswith(b'%PDF-'): raise HTTPException(409, 'AUTHORITY_PDF_REQUIRED')
    reader = PdfReader(BytesIO(body))
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', ''.join(page.extract_text() or '' for page in reader.pages[:3])))


def action_documents(bodies):
    pages = [json.loads(bodies['dividend_' + str(i)]) for i in [1, 2]]
    rows = [row for p in pages for row in p['result']]
    for number, page in enumerate(pages, 1):
        info = page['pageHelp']
        if (page['sqlId'] != 'COMMON_SSE_CP_GPJCTPZ_GPLB_LRFP_FH_L' or info['pageNo'] != number or
                info['total'] != 6 or info['pageCount'] != 2 or info['pageSize'] != 5 or info['data'] != page['result']):
            raise HTTPException(409, 'DIVIDEND_PAGE_BINDING_MISMATCH')
    if len(rows) != 6 or len({r['NUM'] for r in rows}) != 6 or any(r['A_STOCK_CODE'] != '600362' for r in rows):
        raise HTTPException(409, 'DIVIDEND_INVENTORY_CONFLICT')
    announcements = [json.loads(bodies['announcements_' + str(i)]) for i in [1, 2]]
    titles = [r for p in announcements for r in p['result']]
    if (len(titles) != 181 or len({r['URL'] for r in titles}) != 181 or
            any(p['pageHelp']['total'] != 181 or p['pageHelp']['pageNo'] != i for i, p in enumerate(announcements, 1)) or
            any(r['SECURITY_CODE'] != '600362' or not '2025-01-01' <= r['SSEDATE'] <= '2026-10-20' for r in titles)):
        raise HTTPException(409, 'ANNOUNCEMENT_WINDOW_CONFLICT')
    annual = compact_pdf(bodies['annual_notice']); interim = compact_pdf(bodies['interim_notice'])
    report = compact_pdf(bodies['annual_report'])
    for text, anchors in [(annual, ['600362', '2026-027', '2026/7/16', '2026/7/17', '每股现金红利0.6元']),
                          (interim, ['600362', '2025-037', '2025/11/27', '2025/11/28', '每股现金红利0.4元']),
                          (report, ['600362', '2025年半年度已实施完毕', '末期拟每股派发现金红利0.6元'])]:
        if not all(term in text for term in anchors): raise HTTPException(409, 'ISSUER_NOTICE_ANCHOR_MISMATCH')
    notices = [{'notice_number': '2025-037', 'period': '2025_INTERIM', 'role': 'interim_notice',
                'record_date': '2025-11-27', 'ex_date': '2025-11-28', 'scheduled_payment_date': '2025-11-28', 'cash_cny_per_share': '0.4'},
               {'notice_number': '2026-027', 'period': '2025_ANNUAL_FINAL', 'role': 'annual_notice',
                'record_date': '2026-07-16', 'ex_date': '2026-07-17', 'scheduled_payment_date': '2026-07-17', 'cash_cny_per_share': '0.6'}]
    if 'annual_2024_notice' in bodies:
        older = compact_pdf(bodies['annual_2024_notice'])
        anchors = ['600362', '2025-026', '2024年年度权益分派实施公告', '2025/7/21', '2025/7/22',
                   '每股现金红利0.70元', '0.6965', '不实施资本公积金转增股本,也不送股']
        if not all(term in older for term in anchors):
            raise HTTPException(409, 'ISSUER_NOTICE_ANCHOR_MISMATCH')
        if not any(r['SSEDATE'] == '2025-07-15' and '2024年年度权益分派实施公告' in r['TITLE'] for r in titles):
            raise HTTPException(409, 'NOTICE_ANNOUNCEMENT_INDEX_MISMATCH')
        notices.append({'notice_number': '2025-026', 'period': '2024_ANNUAL_FINAL', 'role': 'annual_2024_notice',
                        'record_date': '2025-07-21', 'ex_date': '2025-07-22',
                        'scheduled_payment_date': '2025-07-22', 'cash_cny_per_share': '0.70',
                        'ex_reference_cash_cny_per_share': '0.6965',
                        'ex_reference_cash_basis': 'ISSUER_REPORTED_DILUTED_REFERENCE_NOT_ACCOUNT_DIVIDEND',
                        'original_pdf_pages': [2, 3]})
    for n in notices:
        if not any(r['A_REG_DATE'] == n['record_date'].replace('-', '') and r['A_DIV_DATE'] == n['ex_date'].replace('-', '') and
                   Decimal(r['A_BEFR_TAX_DIV']) == Decimal(n['cash_cny_per_share']) for r in rows):
            raise HTTPException(409, 'NOTICE_LIST_AMOUNT_DATE_CONFLICT')
        n.update(payment_fulfilled=None, cancelled=None, authoritative_event_id=None,
                 document_version_sha256=hashlib.sha256(bodies[n['role']]).hexdigest(),
                 lifecycle='IMPLEMENTATION_ANNOUNCED_NOT_ACCOUNT_PAYMENT')
    return {'dividend_rows': rows, 'returned_count': 6, 'source_total': 6, 'missing_reported_rows': 0,
            'query_date_scope': 'UNKNOWN_NOT_ALL_HISTORY', 'announcement_window': ['2025-01-01', '2026-10-20'],
            'announcement_count': 181, 'notices': notices,
            'economic_links': [{'period': '2025_ANNUAL_FINAL', 'from_role': 'annual_report', 'to_role': 'annual_notice',
                                'relationship': 'PROPOSAL_TO_IMPLEMENTATION_SAME_ISSUER_PERIOD_NOT_REVISION_ID'}],
            'reported_fulfillment': [{'period': '2025_INTERIM', 'role': 'annual_report',
                                     'claim': 'ISSUER_REPORTED_IMPLEMENTED', 'actual_account_payment_verified': False}],
            'complete_action_coverage': False, 'pending_older_obligations_complete': False,
            'revision_cancellation_inventory_complete': False,
            'gaps': ['ALL_CATEGORY_EFFECTIVE_WINDOW_AND_REVISION_CANCELLATION_COVERAGE_UNPROVEN',
                     'ALL_OLDER_OBLIGATIONS_UNPROVEN', 'ACTUAL_PAYMENT_REQUIRES_ACCOUNT_FACT']}


class AuthoritySupplements:
    def __init__(self, evidence):
        self.evidence = evidence; self.ledger = evidence.ledger
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS source_authority_supplements(id TEXT PRIMARY KEY, idem TEXT UNIQUE, value TEXT NOT NULL)')

    def daily_options(self):
        # Query only observation metadata. Never enumerate/expose research facts or SEALED inputs.
        with self.ledger.connection() as db:
            rows = db.execute("""SELECT s.id, json_extract(s.value,'$.created_at'), json_extract(s.value,'$.evidence_kind')
                FROM market_evidence_snapshots s JOIN data_requests r ON r.id=json_extract(s.value,'$.request_id')
                WHERE json_extract(r.value,'$.purpose')='OBSERVATION'
                AND EXISTS (SELECT 1 FROM json_each(s.value,'$.requested_instruments') WHERE value='SSE:600362')
                AND EXISTS (SELECT 1 FROM json_each(s.value,'$.requested_groups') WHERE value='DAILY')
                ORDER BY s.rowid DESC LIMIT 100""").fetchall()
        return [{'snapshot_id': r[0], 'created_at': r[1], 'evidence_kind': r[2]} for r in rows]

    def get(self, identifier):
        with self.ledger.connection() as db:
            row = db.execute('SELECT value FROM source_authority_supplements WHERE id=?', (identifier,)).fetchone()
        if not row: raise HTTPException(404, 'AUTHORITY_ASSESSMENT_MISSING')
        value = json.loads(row[0])
        if json.loads(self.evidence.raw(value['archive']['sha256']).read_bytes()) != {k:v for k,v in value.items() if k != 'archive'}:
            raise HTTPException(409, 'AUTHORITY_ASSESSMENT_ARCHIVE_MISMATCH')
        for sha in value['dependency_hashes']: self.evidence.raw(sha)
        return value

    def listing(self, instrument, known_by=None):
        cutoff = known_by or datetime.fromisoformat(now())
        if cutoff.tzinfo is None or cutoff > datetime.fromisoformat(now()): raise HTTPException(422, 'AUTHORITY_CUTOFF_INVALID')
        with self.ledger.connection() as db:
            values = [json.loads(r[0]) for r in db.execute('SELECT value FROM source_authority_supplements ORDER BY rowid')]
        return [self.get(v['assessment_id']) for v in values if v['instrument'] == instrument and datetime.fromisoformat(v['created_at']) <= cutoff]

    def create(self, command):
        request = command.model_dump()
        needs_snapshot = command.kind in {'DAILY', 'DAILY_SESSION'}
        if needs_snapshot != bool(command.snapshot_id): raise HTTPException(422, 'DAILY_SNAPSHOT_REQUIRED_OTHER_KINDS_FORBIDDEN')
        with self.ledger.connection() as db:
            row = db.execute('SELECT id,value FROM source_authority_supplements WHERE idem=?', (command.idempotency_key,)).fetchone()
        if row:
            if json.loads(row[1])['request'] != request: raise HTTPException(409, 'AUTHORITY_IDEMPOTENCY_CONFLICT')
            return self.get(row[0])
        if command.kind == 'DAILY_SESSION':
            catalog, bodies, mapping = checked_reference(daily_sessions.REFERENCE, daily_sessions.MANIFEST)
        elif command.kind == 'ACTION_DOCUMENTS':
            catalog, bodies, mapping = checked_reference(ACTION_REFERENCE, ACTION_MANIFEST)
        else:
            catalog, bodies, mapping = reference()
        stamp = now()
        if any(datetime.fromisoformat(r['received_at']) > datetime.fromisoformat(stamp) for r in catalog['sources'].values()):
            raise HTTPException(409, 'AUTHORITY_REFERENCE_NOT_YET_KNOWN')
        dependencies = []; kind = 'REAL_SAVED_SOURCE_OBSERVATION'
        if needs_snapshot:
            with self.ledger.connection() as db:
                purpose = db.execute("""SELECT json_extract(r.value,'$.purpose') FROM market_evidence_snapshots s
                    JOIN data_requests r ON r.id=json_extract(s.value,'$.request_id') WHERE s.id=?""", (command.snapshot_id,)).fetchone()
            if not purpose or purpose[0] != 'OBSERVATION': raise HTTPException(403, 'OBSERVATION_SOURCE_ONLY_NO_RESEARCH_INPUT_ACCESS')
            snapshot = self.evidence.get('market_evidence_snapshots', command.snapshot_id)
            replay = self.evidence.replay(snapshot['run_id'])
            if replay['facts'] != snapshot['facts']: raise HTTPException(409, 'AUTHORITY_SOURCE_REPLAY_MISMATCH')
            rows = [f for f in snapshot['facts'] if f['group'] == 'DAILY' and f['instrument'] == command.instrument]
            if not rows: raise HTTPException(409, 'AUTHORITY_DAILY_SOURCE_MISSING')
            dependencies = [a['sha256'] for a in snapshot['archives']] + [snapshot['parquet']['sha256']]
            if snapshot['evidence_kind'] != 'REAL_ACQUISITION': kind = 'METHOD_CASE'
            details = {'rows': [{**f, 'successor_use': daily_use(f)} for f in rows], 'source_snapshot_id': command.snapshot_id,
                       'gaps': ['PROVIDER_REVISION_HISTORY_UNKNOWN', 'STRICT_HISTORICAL_PIT_NOT_GRANTED'],
                       'source_independence': 'UNPROVEN', 'cross_source_comparison': 'NOT_INDEPENDENT_VERIFICATION'}
            if command.kind == 'DAILY_SESSION':
                details = daily_sessions.assess(rows, bodies, catalog)
            else:
                comparison = json.loads(bodies['sse_daily_comparison'])['result'][0]
                details['sse_reported_comparison'] = comparison
                details['comparison_policy'] = 'DIFFERENT_PROVIDER_VALUES_RETAINED_NO_SELECTION_AVERAGING_OR_MODEL_ADMISSION'
        elif command.kind == 'STATUS_PHASE':
            snap = json.loads(bodies['phase_snap']); phase = snap['snap'][23]
            if snap['code'] != '600362' or not isinstance(phase, str): raise HTTPException(409, 'AUTHORITY_PHASE_OBJECT_MISMATCH')
            day = datetime.strptime(str(snap['date']), '%Y%m%d').date().isoformat()
            details = {'source_reported_date': day, 'source_reported_time': snap['time'], 'fp_phase_original': phase,
                       'fp_phase_display': PHASES.get(phase[:1], '未知'), 'source_current_for_host_date': day == datetime.fromisoformat(stamp).astimezone(SHANGHAI).date().isoformat(),
                       'complete_status_verified': False, 'negative_coverage_verified': False,
                       'gaps': ['DISPLAY_FIRST_CHARACTER_ONLY_NOT_COMPLETE_STATUS', 'STATUS_EFFECTIVE_TIME_AND_NEGATIVE_COVERAGE_UNPROVEN']}
        else: details = action_documents(bodies)
        refs = []
        for role, item in catalog['sources'].items():
            archive = self.evidence.archive(bodies[role], 'SOURCE_AUTHORITY_ORIGINAL', source_url=item['url'], received_at=item['received_at'], evidence_kind='REAL_PUBLIC_AUTHORITY_SOURCE')
            refs.append({'role': role, **item, 'archive_sha256': archive['sha256']}); dependencies.append(archive['sha256'])
        dependencies.append(self.evidence.archive(mapping, 'SOURCE_AUTHORITY_MAPPING')['sha256'])
        value = {'assessment_id': str(uuid4()), 'request': request, 'instrument': command.instrument, 'kind': command.kind,
                 'created_at': stamp, 'reference_version': catalog['version'], 'reference_manifest_sha256': hashlib.sha256(mapping).hexdigest(),
                 'evidence_kind': kind, 'details': details, 'references': refs, 'dependency_hashes': sorted(set(dependencies)),
                 'network_calls': 0, 'account_events_added': 0, 'system_usable': False, 'capability': 'NOT_GRANTED',
                 'historical_pit_claim': False}
        value['archive'] = self.evidence.archive(encode(value).encode(), 'SOURCE_AUTHORITY_ASSESSMENT', evidence_kind=kind)
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT id,value FROM source_authority_supplements WHERE idem=?', (command.idempotency_key,)).fetchone()
            if old:
                db.rollback()
                if json.loads(old[1])['request'] != request: raise HTTPException(409, 'AUTHORITY_IDEMPOTENCY_CONFLICT')
                return self.get(old[0])
            db.execute('INSERT INTO source_authority_supplements VALUES(?,?,?)', (value['assessment_id'], command.idempotency_key, encode(value))); db.commit()
        return value
