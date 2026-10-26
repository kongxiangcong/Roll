"""Append-only company research records using the existing ledger and archive."""
from contextlib import contextmanager
import hashlib
import json
import os
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from uuid import uuid4
from urllib.parse import urlsplit

from fastapi import HTTPException

from roll.accounts.ledger import encode, now


def fail(code, reason, status=422, **context):
    raise HTTPException(status, {'code': code, 'reason': reason, 'context': context, 'retryable': False})


def fingerprint(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def record(value):
    payload = {'schema_version': 1, 'created_at': now(), **value}
    return {**payload, 'content_sha256': fingerprint(payload)}


def verified(value):
    if not isinstance(value, dict) or fingerprint({k: v for k, v in value.items() if k != 'content_sha256'}) != value.get('content_sha256'):
        fail('RESEARCH_RECORD_CORRUPT', 'Stored record hash does not match', 409)
    return value


def page_bounds(limit, offset, maximum=1000):
    if not isinstance(limit, int) or not isinstance(offset, int) or not 1 <= limit <= maximum or offset < 0:
        fail('INVALID_PAGE', 'Page limit or offset is outside allowed bounds')


class CompanyResearch:
    def __init__(self, evidence, analysis_worker=None):
        self.evidence, self.ledger = evidence, evidence.ledger
        self.analysis_worker = analysis_worker
        with self.ledger.connection() as db:
            db.executescript('''
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS company_research_companies(
                    version_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, revision INTEGER NOT NULL,
                    value TEXT NOT NULL, UNIQUE(company_id,revision));
                CREATE TABLE IF NOT EXISTS company_research_listings(
                    version_id TEXT PRIMARY KEY, listing_id TEXT NOT NULL, company_id TEXT NOT NULL,
                    value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS company_research_commands(
                    scope TEXT NOT NULL, key TEXT NOT NULL, request_hash TEXT NOT NULL,
                    result TEXT NOT NULL, PRIMARY KEY(scope,key));
                CREATE TABLE IF NOT EXISTS company_research_materials(
                    material_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, raw_sha256 TEXT NOT NULL,
                    value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS company_research_facts(
                    version_id TEXT PRIMARY KEY, fact_id TEXT NOT NULL, company_id TEXT NOT NULL,
                    revision INTEGER NOT NULL, value TEXT NOT NULL, UNIQUE(fact_id,revision));
                CREATE TABLE IF NOT EXISTS company_research_conflict_resolutions(
                    resolution_id TEXT PRIMARY KEY, fact_id TEXT NOT NULL, company_id TEXT NOT NULL,
                    value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS company_research_checks(
                    check_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, source_id TEXT NOT NULL,
                    key TEXT NOT NULL, request_hash TEXT NOT NULL, value TEXT NOT NULL,
                    UNIQUE(company_id,source_id,key));
                COMMIT;
            ''')
            from roll.agents.codex_process import owner_alive
            for row in db.execute("SELECT check_id,value FROM company_research_checks WHERE json_extract(value,'$.status')='RUNNING'").fetchall():
                value = verified(json.loads(row[1]))
                if not owner_alive(value):
                    value.pop('content_sha256', None)
                    value.update(status='FAILED', finished_at=now(), failed_scopes=value['requested_scopes'],
                                 errors=[{'code': 'HOST_INTERRUPTED', 'scope': s} for s in value['requested_scopes']],
                                 meaning='本次未完成核查；重启保留已有材料，不补写成功', retry_state='EXPLICIT_NEW_ATTEMPT_REQUIRED')
                    db.execute('UPDATE company_research_checks SET value=? WHERE check_id=?', (encode(record(value)), row[0]))

        from .analysis import AnalysisState
        self.analysis = AnalysisState(self)
        from .valuation import ValuationState
        self.valuations = ValuationState(self)
        from .economics import EconomicState
        self.economics = EconomicState(self)
        from .changes import ChangeState
        self.changes = ChangeState(self)
        from .financial_facts import initialize
        initialize(self)
        from .reports import ReportState
        self.reports = ReportState(self)

    @contextmanager
    def transaction(self):
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def prior_command(self, db, scope, key, request):
        prior = db.execute('SELECT request_hash,result FROM company_research_commands WHERE scope=? AND key=?',
                           (scope, key)).fetchone()
        if prior:
            if prior[0] != fingerprint(request):
                fail('IDEMPOTENCY_CONFLICT', 'The key was used for different input', 409)
            result = verified(json.loads(prior[1]))
            table, field = {'identity': ('company_research_companies', 'version_id'),
                            'material': ('company_research_materials', 'material_id'),
                            'fact': ('company_research_facts', 'version_id'),
                            'resolution': ('company_research_conflict_resolutions', 'resolution_id')}[scope.split(':')[0]]
            registered = db.execute(f'SELECT value FROM {table} WHERE {field}=?', (result[field],)).fetchone()
            if not registered or verified(json.loads(registered[0])) != result:
                fail('RESEARCH_RECORD_CORRUPT', 'Idempotent result differs from registered immutable record', 409)
            return result

    def save_command(self, db, scope, key, request, result):
        db.execute('INSERT INTO company_research_commands VALUES(?,?,?,?)',
                   (scope, key, fingerprint(request), encode(result)))
        return result

    def company(self, identifier, db=None):
        if db is None:
            with self.ledger.connection() as connection:
                return self.company(identifier, connection)
        row = db.execute('SELECT value FROM company_research_companies WHERE company_id=? ORDER BY revision DESC LIMIT 1',
                         (identifier,)).fetchone()
        if not row:
            fail('IDENTITY_NOT_FOUND', 'Company is not registered', 404)
        value = verified(json.loads(row[0]))
        for listing in value['listings']:
            verified(listing)
        return value

    def companies(self, limit=100, offset=0):
        page_bounds(limit, offset, 200)
        with self.ledger.connection() as db:
            total = db.execute('SELECT COUNT(DISTINCT company_id) FROM company_research_companies').fetchone()[0]
            identifiers = [r[0] for r in db.execute('SELECT DISTINCT company_id FROM company_research_companies ORDER BY company_id LIMIT ? OFFSET ?', (limit, offset))]
            return {'companies': [self.company(identifier, db) for identifier in identifiers],
                    'total': total, 'limit': limit, 'offset': offset, 'has_more': offset + limit < total}

    def register(self, command):
        request = command.model_dump()
        key = command.idempotency_key or fingerprint(request)
        listings = command.listings
        names = {n.casefold() for n in [command.legal_name, *command.aliases]}
        if any(not n.strip() or len(n) > 160 for n in command.aliases):
            fail('INVALID_IDENTITY', 'Aliases must be nonempty bounded names')
        try:
            if command.year_end:
                date.fromisoformat('2000-' + command.year_end)
            for listing in listings:
                if listing.valid_from:
                    date.fromisoformat(listing.valid_from)
        except ValueError:
            fail('INVALID_IDENTITY', 'Year end and listing validity dates must be valid calendar dates')
        if any((i.exchange == 'HKEX') != (len(i.code) == 5) for i in listings):
            fail('INVALID_LISTING', 'HKEX requires five digits; mainland exchanges require six')
        if any(i.currency != ('HKD' if i.exchange == 'HKEX' else 'CNY') or
               (i.share_class == 'H' and i.exchange != 'HKEX') or
               (i.share_class == 'A' and i.exchange == 'HKEX') for i in listings):
            fail('INVALID_LISTING', 'Listing currency or share class does not match the exchange')
        ids = [f'{i.exchange}:{i.code}' for i in listings]
        if len(ids) != len(set(ids)):
            fail('INVALID_LISTING', 'Duplicate listing')
        with self.transaction() as db:
            prior = self.prior_command(db, 'identity', key, request)
            if prior:
                return prior
            parent = self.company(command.company_id, db) if command.company_id else None
            company_id = parent['company_id'] if parent else str(uuid4())
            mapped = []
            for item, listing_id in zip(listings, ids):
                existing = db.execute('SELECT company_id FROM company_research_listings WHERE listing_id=? LIMIT 1', (listing_id,)).fetchone()
                if existing and existing[0] != company_id:
                    fail('LISTING_ALREADY_MAPPED', 'A listing cannot be reassigned to another company', 409)
                identity_ref = None
                if item.exchange != 'HKEX':
                    identity = db.execute('SELECT identity FROM market_identities WHERE instrument=? ORDER BY revision DESC LIMIT 1',
                                          (listing_id,)).fetchone()
                    identity_ref = json.loads(identity[0]) if identity else None
                    if identity_ref and identity_ref.get('name', '').strip().casefold() not in names:
                        fail('SOURCE_IDENTITY_MISMATCH', 'Registered market identity differs from selected company', listing_id=listing_id)
                listing = record({**item.model_dump(), 'listing_id': listing_id, 'company_id': company_id,
                                  'version_id': str(uuid4()), 'identity_basis': command.identity_basis,
                                  'market_identity_reference': identity_ref})
                mapped.append(listing)
                db.execute('INSERT INTO company_research_listings VALUES(?,?,?,?)',
                           (listing['version_id'], listing_id, company_id, encode(listing)))
            if parent and not {i['listing_id'] for i in parent['listings']} <= set(ids):
                fail('LISTING_HISTORY_REQUIRED', 'Registration updates must retain prior listings')
            value = record({**{k: v for k, v in request.items() if k not in {'listings', 'idempotency_key'}},
                            'company_id': company_id, 'version_id': str(uuid4()),
                            'revision': parent['revision'] + 1 if parent else 1,
                            'parent_version_id': parent['version_id'] if parent else None, 'listings': mapped})
            db.execute('INSERT INTO company_research_companies VALUES(?,?,?,?)',
                       (value['version_id'], company_id, value['revision'], encode(value)))
            return self.save_command(db, 'identity', key, request, value)

    def resolve(self, text):
        query = text.strip().casefold()
        if not query or len(query) > 160:
            fail('INVALID_IDENTITY_QUERY', 'Supply a company name or exchange-qualified code')
        candidates = []
        with self.ledger.connection() as db:
            rows = db.execute('SELECT c.value FROM company_research_companies c WHERE revision=(SELECT MAX(revision) FROM company_research_companies WHERE company_id=c.company_id) ORDER BY company_id')
            for row in rows:
                company = verified(json.loads(row[0]))
                names = {n.casefold() for n in [company['legal_name'], *company['aliases']]}
                listing_matches = [i for i in company['listings'] if query in {i['listing_id'].casefold(), i['code']}]
                if query in names or listing_matches:
                    candidates.append({'company_id': company['company_id'], 'legal_name': company['legal_name'],
                                       'listings': listing_matches or company['listings'], 'identity_basis': company['identity_basis']})
                    if len(candidates) > 50:
                        break
        if len(candidates) == 1:
            return {'input': text, 'status': 'RESOLVED', 'company': self.company(candidates[0]['company_id']),
                    'listings': candidates[0]['listings']}
        return {'input': text, 'status': 'AMBIGUOUS' if candidates else 'NOT_FOUND',
                'candidates': candidates[:50], 'has_more': len(candidates) > 50}

    def import_material(self, command, content):
        """Import explicit user bytes, never a caller-chosen filesystem path."""
        return self._material(command, content, 'USER_IMPORT')

    def import_existing(self, command):
        from .existing_sources import material_source
        material, content, kind, upstream = material_source(self.evidence, self.company(command.company_id), command)
        return self._material(material, content, kind, upstream)

    def _material(self, command, content, source_kind, upstream=None):
        company = self.company(command.company_id)
        parsed = urlsplit(command.source_url)
        allowed_schemes = {'http', 'https', 'user-import', 'registered-source'}
        if source_kind != 'USER_IMPORT':
            allowed_schemes.add('tcp')
        if parsed.scheme not in allowed_schemes or parsed.username or parsed.password or (parsed.scheme in {'http', 'https', 'tcp'} and not parsed.netloc):
            fail('SOURCE_URL_INVALID', 'Source reference must use an allowed scheme and contain no credentials')
        if command.subject_name.casefold() not in {n.casefold() for n in [company['legal_name'], *company['aliases']]}:
            fail('SOURCE_IDENTITY_MISMATCH', 'Source subject must match the selected company')
        if not isinstance(content, bytes) or not 0 < len(content) <= 16 * 1024 * 1024:
            fail('MATERIAL_SIZE_LIMIT', 'Material must contain 1 to 16 MiB of bytes')
        try:
            if command.media_type == 'application/pdf':
                if not content.startswith(b'%PDF-'):
                    raise ValueError()
            elif command.media_type == 'application/json':
                json.loads(content.decode('utf-8-sig'))
            elif command.media_type != 'application/octet-stream':
                content.decode('utf-8-sig')
            elif source_kind == 'USER_IMPORT':
                raise ValueError()
        except (ValueError, UnicodeDecodeError):
            fail('MATERIAL_TYPE_INVALID', 'Bytes do not match the declared supported media type')
        stamp = now()
        try:
            if command.disclosed_at:
                disclosed = datetime.fromisoformat(command.disclosed_at)
                if disclosed.tzinfo is None or disclosed > datetime.fromisoformat(stamp):
                    raise ValueError()
            dates = [date.fromisoformat(v) if v else None for v in [command.period_start, command.period_end]]
            if all(dates) and dates[0] > dates[1]:
                raise ValueError()
        except ValueError:
            fail('MATERIAL_TIME_INVALID', 'Disclosure must be aware and not future; report dates must be ordered')
        raw_sha = hashlib.sha256(content).hexdigest()
        request = {**command.model_dump(exclude={'idempotency_key'}), 'raw_sha256': raw_sha,
                   'source_kind': source_kind, 'upstream': upstream}
        key = command.idempotency_key or fingerprint(request)
        with self.transaction() as db:
            prior = self.prior_command(db, 'material:' + company['company_id'], key, request)
            if prior:
                self.evidence.raw(prior['archive']['sha256'])
                return prior
            # Existing raw authority is reused, including when another workflow registered it.
            archive = db.execute('SELECT value FROM evidence_archives WHERE sha256=?', (raw_sha,)).fetchone()
            if archive:
                archive = json.loads(archive[0])
                self.evidence.raw(raw_sha)
            else:
                archive = self.evidence.archive(content, 'COMPANY_RESEARCH_ORIGINAL', db=db)
            same = db.execute('SELECT value FROM company_research_materials WHERE company_id=? AND raw_sha256=? LIMIT 1',
                              (company['company_id'], raw_sha)).fetchone()
            # New acquisition receipts do not create new evidence when source
            # bytes and declared economic/identity basis are unchanged.
            for row in db.execute('SELECT value FROM company_research_materials WHERE company_id=? AND raw_sha256=?', (company['company_id'], raw_sha)):
                existing = verified(json.loads(row[0]))
                comparable = command.model_dump(exclude={'idempotency_key'})
                if existing['source_kind'] == source_kind and all(existing.get(k) == v for k, v in comparable.items()):
                    return self.save_command(db, 'material:' + company['company_id'], key, request, existing)
            root = json.loads(same[0])['origin_root_id'] if same else command.origin_root_id
            value = record({**request, 'material_id': str(uuid4()), 'archive': archive,
                            'origin_root_id': root, 'declared_origin_root_id': command.origin_root_id,
                            'received_at': stamp, 'consumable_at': now(), 'historical_pit_eligible': False,
                            'verification': 'IDENTITY_METADATA_AND_BYTES_CHECKED_NOT_FACTUAL_ENDORSEMENT',
                            'unknown_fields': [field for field in ['disclosed_at', 'period_start', 'period_end',
                                'unit', 'currency', 'scope', 'page', 'table'] if getattr(command, field) is None]})
            db.execute('INSERT INTO company_research_materials VALUES(?,?,?,?)',
                       (value['material_id'], company['company_id'], raw_sha, encode(value)))
            return self.save_command(db, 'material:' + company['company_id'], key, request, value)

    def material(self, identifier, company_id=None):
        with self.ledger.connection() as db:
            row = db.execute('SELECT value FROM company_research_materials WHERE material_id=?', (identifier,)).fetchone()
        if not row:
            fail('MATERIAL_NOT_FOUND', 'Material does not exist', 404)
        value = verified(json.loads(row[0]))
        if company_id is not None and value['company_id'] != company_id:
            fail('CROSS_COMPANY_REFERENCE', 'Material belongs to another company')
        self.evidence.raw(value['archive']['sha256'])
        return value

    def material_bytes(self, identifier):
        material = self.material(identifier)
        return self.evidence.raw(material['archive']['sha256']).read_bytes()

    def materials(self, company_id, purpose='CURRENT_RESEARCH', limit=200, offset=0):
        self.company(company_id)
        page_bounds(limit, offset, 200)
        if purpose not in {'DAILY', 'REPORT', 'CURRENT_RESEARCH'}:
            fail('PURPOSE_NOT_SUPPORTED', 'Material imports do not establish strict historical availability')
        with self.ledger.connection() as db:
            total = db.execute('SELECT COUNT(*) FROM company_research_materials WHERE company_id=?', (company_id,)).fetchone()[0]
            ids = [r[0] for r in db.execute('SELECT material_id FROM company_research_materials WHERE company_id=? ORDER BY rowid LIMIT ? OFFSET ?', (company_id, limit, offset))]
        materials = [self.material(identifier, company_id) for identifier in ids]
        return {'company_id': company_id, 'purpose': purpose, 'materials': materials,
                'total': total, 'limit': limit, 'offset': offset, 'has_more': offset + limit < total,
                'independent_origin_roots': sorted({m['origin_root_id'] for m in materials}),
                'verification': 'RECORDED_PROVENANCE_NOT_INDEPENDENT_FACT_VERIFICATION'}

    def add_fact(self, command):
        material = self.material(command.material_id, command.company_id)
        mismatches = [field for field in ['unit', 'currency', 'scope']
                      if material[field] is not None and getattr(command, field) != material[field]]
        if material['period_start'] and command.period_start < material['period_start']:
            mismatches.append('period_start')
        if mismatches and (command.kind == 'DISCLOSED' or not command.derivation):
            fail('FACT_BASIS_MISMATCH', 'Fact differs from declared material basis; explicit derived basis required', fields=mismatches)
        try:
            if date.fromisoformat(command.period_start) > date.fromisoformat(command.period_end):
                raise ValueError()
            if material['period_end'] and command.period_end > material['period_end']:
                raise ValueError()
        except ValueError:
            fail('FACT_PERIOD_INVALID', 'Fact period must be ordered and within source reporting end')
        if command.value is not None and command.value_type == 'NUMBER':
            try:
                if not Decimal(command.value).is_finite():
                    raise InvalidOperation()
            except InvalidOperation:
                fail('INVALID_NUMBER', 'Fact numbers must be finite decimal strings')
        if command.kind != 'DISCLOSED' and not command.derivation:
            fail('DERIVATION_REQUIRED', 'Derived values and assumptions must describe their basis')
        request = command.model_dump(exclude={'idempotency_key'})
        key = command.idempotency_key or fingerprint(request)
        fact_id = fingerprint({k: request[k] for k in ['company_id', 'metric', 'business', 'period_start', 'period_end', 'scope']})
        with self.transaction() as db:
            prior = self.prior_command(db, 'fact:' + command.company_id, key, request)
            if prior:
                return prior
            versions = [json.loads(r[0]) for r in db.execute('SELECT value FROM company_research_facts WHERE fact_id=? ORDER BY revision', (fact_id,))]
            if command.supersedes:
                previous = db.execute('SELECT value FROM company_research_facts WHERE version_id=?', (command.supersedes,)).fetchone()
                previous = json.loads(previous[0]) if previous else None
                if not previous or previous['fact_id'] != fact_id:
                    fail('FACT_REVISION_MISMATCH', 'Restatement must reference the same company and fact series')
            value = record({**request, 'fact_id': fact_id, 'version_id': str(uuid4()), 'entity_id': fact_id,
                            'revision': len(versions) + 1, 'parent_version_id': versions[-1]['version_id'] if versions else None,
                            'conflict_group_id': fact_id, 'source_disclosed_at': material['disclosed_at'],
                            'received_at': material['received_at'], 'consumable_at': now(),
                            'origin_root_id': material['origin_root_id'], 'archive_sha256': material['archive']['sha256'],
                            'verification': 'SOURCE_REFERENCE_AND_STRUCTURE_CHECKED_NOT_FACTUAL_ENDORSEMENT',
                            'unknown_fields': [k for k in ['value', 'unit', 'currency', 'scope', 'page', 'table'] if getattr(command, k) is None]})
            db.execute('INSERT INTO company_research_facts VALUES(?,?,?,?,?)',
                       (value['version_id'], fact_id, command.company_id, value['revision'], encode(value)))
            return self.save_command(db, 'fact:' + command.company_id, key, request, value)

    def fact(self, version_id, company_id=None):
        with self.ledger.connection() as db:
            row = db.execute('SELECT value FROM company_research_facts WHERE version_id=?', (version_id,)).fetchone()
        if not row:
            fail('FACT_NOT_FOUND', 'Fact version is not registered', 404)
        value = verified(json.loads(row[0]))
        self.material(value['material_id'], company_id or value['company_id'])
        if company_id and value['company_id'] != company_id:
            fail('CROSS_COMPANY_REFERENCE', 'Fact belongs to another company')
        return value

    def facts(self, company_id, limit=1000, offset=0, fact_id=None):
        self.company(company_id)
        page_bounds(limit, offset)
        with self.ledger.connection() as db:
            identifiers = [r[0] for r in db.execute('SELECT version_id FROM company_research_facts WHERE company_id=? AND (? IS NULL OR fact_id=?) ORDER BY rowid', (company_id, fact_id, fact_id))]
            resolutions = [verified(json.loads(r[0])) for r in db.execute('SELECT value FROM company_research_conflict_resolutions WHERE company_id=? ORDER BY rowid', (company_id,))]
        versions = [self.fact(identifier, company_id) for identifier in identifiers]
        conflicts = []
        for fact_id in sorted({v['fact_id'] for v in versions}):
            series = [v for v in versions if v['fact_id'] == fact_id]
            replaced = {v['supersedes'] for v in series if v['supersedes']}
            heads = [v for v in series if v['version_id'] not in replaced]
            signatures = {encode({k: v[k] for k in ['value', 'value_type', 'unit', 'currency', 'kind']}) for v in heads}
            if len(signatures) < 2:
                continue
            head_ids = {v['version_id'] for v in heads}
            choices = [r for r in resolutions if r['fact_id'] == fact_id and set(r['version_ids']) == head_ids]
            conflicts.append({'fact_id': fact_id, 'version_ids': sorted(head_ids),
                              'status': 'RESOLVED' if choices else 'UNRESOLVED',
                              'resolution': choices[-1] if choices else None})
        return {'company_id': company_id, 'versions': versions[offset:offset + limit],
                'conflicts': conflicts[offset:offset + limit], 'resolutions': resolutions[offset:offset + limit],
                'total': len(versions), 'limit': limit, 'offset': offset, 'has_more': offset + limit < len(versions),
                'conflict_total': len(conflicts), 'conflict_has_more': offset + limit < len(conflicts),
                'resolution_total': len(resolutions), 'resolution_has_more': offset + limit < len(resolutions)}

    def resolve_conflict(self, command):
        state = self.facts(command.company_id, fact_id=command.fact_id)
        conflict = next((c for c in state['conflicts'] if c['fact_id'] == command.fact_id), None)
        if not conflict or set(command.version_ids) != set(conflict['version_ids']) or len(set(command.version_ids)) != len(command.version_ids):
            fail('CONFLICT_REFERENCES_INVALID', 'Resolution must retain every conflicting active version')
        if command.selected_version_id is not None and command.selected_version_id not in command.version_ids:
            fail('CONFLICT_REFERENCES_INVALID', 'Selected value must reference a retained version')
        request = command.model_dump(exclude={'idempotency_key'})
        key = command.idempotency_key or fingerprint(request)
        with self.transaction() as db:
            prior = self.prior_command(db, 'resolution:' + command.company_id, key, request)
            if prior:
                return prior
            value = record({**request, 'resolution_id': str(uuid4())})
            db.execute('INSERT INTO company_research_conflict_resolutions VALUES(?,?,?,?)',
                       (value['resolution_id'], command.fact_id, command.company_id, encode(value)))
            return self.save_command(db, 'resolution:' + command.company_id, key, request, value)

    def check_source(self, command, supplier):
        """Run a host supplier once per scope; fixture suppliers remain METHOD_CASE.

        Supplier returns bounded (MaterialCommand, bytes) pairs. Existing-source
        adapters below retain their own acquisition receipts and provenance.
        """
        self.company(command.company_id)
        from .models import ExistingSourceCommand
        if len(set(command.requested_scopes)) != len(command.requested_scopes) or any(not s.strip() or len(s) > 300 for s in command.requested_scopes):
            fail('CHECK_SCOPE_INVALID', 'Requested scopes must be distinct bounded names')
        request = command.model_dump()
        from roll.agents.codex_process import process_creation
        with self.transaction() as db:
            prior = db.execute('SELECT request_hash,value FROM company_research_checks WHERE company_id=? AND source_id=? AND key=?',
                               (command.company_id, command.source_id, command.idempotency_key)).fetchone()
            if prior:
                if prior[0] != fingerprint(request):
                    fail('IDEMPOTENCY_CONFLICT', 'Check key was used for another scope', 409)
                return verified(json.loads(prior[1]))
            previous = [verified(json.loads(r[0])) for r in db.execute('SELECT value FROM company_research_checks WHERE company_id=? AND source_id=? ORDER BY rowid DESC', (command.company_id, command.source_id))]
            success = next((r for r in previous if r['status'] == 'SUCCESS' and set(r['requested_scopes']) == set(command.requested_scopes)), None)
            value = record({**request, 'check_id': str(uuid4()), 'attempt_id': str(uuid4()),
                            'status': 'RUNNING', 'started_at': now(), 'finished_at': None,
                            'host_owner': {'pid': os.getpid(), 'creation_ticks': process_creation(os.getpid())},
                            'last_success_check_id': success['check_id'] if success else None,
                            'last_success_at': success['finished_at'] if success else None,
                            'completed_scopes': [], 'failed_scopes': [], 'material_ids': [], 'new_material_count': 0,
                            'source_receipts': [],
                            'errors': [], 'retry_state': 'NO_AUTOMATIC_RETRY'})
            db.execute('INSERT INTO company_research_checks VALUES(?,?,?,?,?,?)',
                       (value['check_id'], command.company_id, command.source_id, command.idempotency_key, fingerprint(request), encode(value)))
        with self.ledger.connection() as db:
            before = {r[0] for r in db.execute('SELECT material_id FROM company_research_materials WHERE company_id=?', (command.company_id,))}
        for scope in command.requested_scopes:
            try:
                entries = supplier(scope)
                if not isinstance(entries, list) or len(entries) > 20:
                    raise ValueError('SOURCE_RESULT_LIMIT')
                completed = 0
                for entry in entries:
                    try:
                        material_command = entry if isinstance(entry, ExistingSourceCommand) else entry[0]
                        if material_command.company_id != command.company_id:
                            fail('CROSS_COMPANY_REFERENCE', 'Supplier material belongs to another company')
                        if isinstance(entry, ExistingSourceCommand):
                            material = self.import_existing(entry)
                            value['source_receipts'].append({**entry.model_dump(), 'scope': scope, 'material_id': material['material_id']})
                        else:
                            material_command, content = entry
                            material = self._material(material_command, content, 'METHOD_CASE')
                        value['material_ids'].append(material['material_id'])
                        completed += 1
                    except Exception as error:
                        if scope not in value['failed_scopes']:
                            value['failed_scopes'].append(scope)
                        code = error.detail.get('code') if isinstance(error, HTTPException) and isinstance(error.detail, dict) else 'SOURCE_TIMEOUT' if isinstance(error, TimeoutError) else 'SOURCE_UNAVAILABLE'
                        identity = {'record_id':entry.record_id, 'source_type':entry.source_type} if isinstance(entry, ExistingSourceCommand) else {}
                        value['errors'].append({'scope':scope, 'code':code, 'error_type':type(error).__name__, **identity})
                if completed or not entries:
                    value['completed_scopes'].append(scope)
            except Exception as error:
                value['failed_scopes'].append(scope)
                code = error.detail.get('code') if isinstance(error, HTTPException) and isinstance(error.detail, dict) else 'SOURCE_TIMEOUT' if isinstance(error, TimeoutError) else 'SOURCE_UNAVAILABLE'
                value['errors'].append({'scope': scope, 'code': code, 'error_type': type(error).__name__})
        value['status'] = 'PARTIAL' if value['failed_scopes'] and value['completed_scopes'] else 'FAILED' if value['failed_scopes'] else 'SUCCESS'
        value['new_material_count'] = len(set(value['material_ids']) - before)
        value['finished_at'] = now()
        value['meaning'] = ('本次已核查范围未取得新证据；不代表经营未变' if not value['new_material_count'] else '已取得材料，经营含义需另行分析') if value['status'] == 'SUCCESS' else '本次未完成核查' if value['status'] == 'FAILED' else '本次部分范围未完成核查，已完成范围单列'
        if value['status'] == 'SUCCESS':
            value.update(last_success_check_id=value['check_id'], last_success_at=value['finished_at'])
        value.pop('content_sha256', None)
        value = record(value)
        with self.transaction() as db:
            db.execute('UPDATE company_research_checks SET value=? WHERE check_id=?', (encode(value), value['check_id']))
        return value

    def checks(self, company_id, limit=100, offset=0):
        self.company(company_id)
        page_bounds(limit, offset, 500)
        with self.ledger.connection() as db:
            total = db.execute('SELECT COUNT(*) FROM company_research_checks WHERE company_id=?', (company_id,)).fetchone()[0]
            attempts = [verified(json.loads(r[0])) for r in db.execute('SELECT value FROM company_research_checks WHERE company_id=? ORDER BY rowid LIMIT ? OFFSET ?', (company_id, limit, offset))]
            last = db.execute("SELECT value FROM company_research_checks WHERE company_id=? AND json_extract(value,'$.finished_at') IS NOT NULL ORDER BY rowid DESC LIMIT 1", (company_id,)).fetchone()
            last = verified(json.loads(last[0])) if last else None
        return {'company_id': company_id, 'attempts': attempts,
                'total': total, 'limit': limit, 'offset': offset, 'has_more': offset + limit < total,
                'last_checked_at': last['finished_at'] if last else None,
                'meaning': '核查状态独立于经营判断；最后成功按来源与请求范围分别保存'}

    def freeze_analysis(self, command):
        return self.analysis.freeze(command)

    def daily_view(self, company_id, snapshot_id=None):
        from .daily import daily_view
        return daily_view(self, company_id, snapshot_id)

    def refresh_daily(self, company_id, key, supplier=None, retry_rejected=False):
        from .daily import refresh_daily
        return refresh_daily(self, company_id, key, supplier, retry_rejected)

    def analysis_input(self, identifier):
        return self.analysis.read('inputs', 'input_id', identifier)

    def apply_analysis_candidate(self, input_id, candidate):
        return self.analysis.apply(input_id, candidate)

    def analysis_snapshot(self, identifier, purpose='DAILY'):
        return self.analysis.snapshot(identifier, purpose)

    def analysis_snapshots(self, company_id, limit=100, offset=0):
        return self.analysis.snapshots(company_id, limit, offset)

    def operating_hypothesis(self, version_id):
        return self.analysis.read('hypotheses', 'version_id', version_id)

    def run_analysis(self, input_id):
        from .model_runtime import AnalysisRuntime
        return AnalysisRuntime(self).execute(input_id)

    def analysis_run(self, run_id):
        return self.analysis.read('analysis_runs', 'run_id', run_id)

    def analysis_candidates(self, input_id, limit=100, offset=0):
        return self.analysis.candidates(input_id, limit, offset)

    def calculate_valuation(self, command):
        return self.valuations.calculate(command)

    def valuation_input(self, identifier):
        return self.valuations.read('valuation_inputs', 'version_id', identifier)

    def valuation(self, identifier):
        return self.valuations.result(identifier)

    def replay_valuation(self, identifier):
        return self.valuations.replay(identifier)

    def valuation_bundle(self, identifier):
        return self.valuations.bundle(identifier)

    def calculate_operating_valuation(self, command):
        return self.economics.calculate(command)

    def operating_model(self, identifier):
        return self.economics.read('operating_models', 'operating_model_id', identifier)

    def economic_review(self, identifier):
        return self.economics.read('economic_reviews', 'review_id', identifier)

    def valuation_presentation(self, identifier, purpose='CURRENT_PRICING'):
        return self.economics.presentation(identifier, purpose)

    def compare_snapshots(self, command):
        return self.changes.compare(command)

    def change_set(self, identifier):
        return self.changes.read(identifier)

    def freeze_research_context(self, command):
        return self.changes.freeze_context(command)

    def replay_change_set(self, identifier):
        return self.changes.replay(identifier)
