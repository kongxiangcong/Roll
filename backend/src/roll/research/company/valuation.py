"""Immutable diagnostic valuations and canonical offline source bundles."""
import base64
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from roll.accounts.ledger import encode
from .service import fail, record, verified, fingerprint
from .calculator import calculate, CalculationError, valuation_cutoff

METHOD_ID = 'fcff-wacc-year-end'
METHOD_VERSION = 'roll-diagnostic-1'


def numeric_leaves(value, path=''):
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        yield path, value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from numeric_leaves(child, (path + '/' + key).lstrip('/'))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from numeric_leaves(child, path + '/' + str(index))


def validate_provenance(command, snapshot, frozen_facts):
    facts = set(snapshot['fact_version_ids'])
    hypotheses = set(snapshot['hypothesis_version_ids'])
    assumptions = {}
    for item in command.assumptions:
        if set(item) != {'assumption_id', 'statement', 'anchor_fact_version_ids', 'hypothesis_version_ids'} or not item['statement'].strip():
            fail('ASSUMPTION_INVALID', 'Explicit assumptions need statement, fact anchors and hypothesis references')
        aid = item['assumption_id']
        if not isinstance(aid, str) or not aid.strip() or aid in assumptions or aid in facts | hypotheses:
            fail('ASSUMPTION_INVALID', 'Assumption IDs must be unique and separate from frozen references')
        if not item['anchor_fact_version_ids'] or not set(item['anchor_fact_version_ids']) <= facts or not set(item['hypothesis_version_ids']) <= hypotheses:
            fail('UNKNOWN_CITATION', 'Assumption anchors must be frozen in this snapshot')
        assumptions[aid] = item
    known = facts | hypotheses | set(assumptions)
    meta = command.config['metadata']
    if not set(meta['sources']) <= facts or not set(meta['assumptions']) <= set(assumptions):
        fail('UNKNOWN_CITATION', 'Metadata must reference frozen facts and explicit assumptions')
    leaves = dict(numeric_leaves(command.config))
    if set(command.provenance) != set(leaves):
        fail('PROVENANCE_REQUIRED', 'Every numeric leaf needs unit, currency, scope, period and references')
    for path, numeric_value in leaves.items():
        p = command.provenance[path]
        if not isinstance(p, dict) or set(p) != {'kind', 'references', 'unit', 'currency', 'scope', 'period'} or p['kind'] not in {'DISCLOSED', 'DERIVED', 'ASSUMED'} or not p['scope'] or not p['period']:
            fail('PROVENANCE_REQUIRED', 'Incomplete numeric provenance', path=path)
        if not p['references'] or not set(p['references']) <= known:
            fail('UNKNOWN_CITATION', 'Numeric references must be frozen facts/hypotheses or explicit assumptions', path=path)
        if p['kind'] == 'ASSUMED' and not set(p['references']) & set(assumptions):
            fail('ASSUMPTION_INVALID', 'Assumed inputs must reference an explicit assumption', path=path)
        if p['kind'] in {'DISCLOSED', 'DERIVED'}:
            origin = frozen_facts.get(p['references'][0]) if len(p['references']) == 1 else None
            period = origin['period_start'] + '/' + origin['period_end'] if origin else None
            if not origin or origin['value_type'] != 'NUMBER' or origin['kind'] != p['kind'] or origin['value'] is None or (p['kind'] == 'DERIVED' and not origin.get('derivation')):
                fail('FACT_VALUE_MISMATCH', 'Disclosed/derived values need one matching frozen numeric fact of that kind', path=path)
            if Decimal(str(numeric_value)) != Decimal(origin['value']) or any(p[k] != origin[k] for k in ['unit', 'currency', 'scope']) or p['period'] != period:
                fail('FACT_VALUE_MISMATCH', 'Numeric value, unit, currency, scope or period differs from frozen fact', path=path)
        ratio = path in {'wacc', 'terminal_g'} or any(x in path for x in ['/fcf_margin/', '/probability', 'sensitivity/wacc/', 'sensitivity/terminal_g/', 'steady_margins/', '/fx/rate'])
        unit = 'ratio' if ratio else meta['shares_unit'] if path == 'shares' or path.endswith('/shares') else 'price_per_share' if path.endswith('/price') else meta['amount_unit']
        currency = None if ratio or unit == meta['shares_unit'] else meta['currency']
        if '/market_basis/' in path and path.endswith('/price'):
            currency = command.config['reverse']['market_basis'][int(path.split('/')[2])]['currency']
        if p['unit'] != unit:
            fail('UNIT_MISMATCH', 'Numeric input unit differs from model convention', path=path)
        if p['currency'] != currency:
            fail('CURRENCY_MISMATCH', 'Numeric currency differs from model convention', path=path)
    for index, row in enumerate(command.config.get('reverse', {}).get('market_basis', [])):
        refs = row.get('price_refs', []) + row.get('share_refs', []) + row.get('fx', {}).get('source_refs', [])
        if not refs or not set(refs) <= facts:
            fail('UNKNOWN_CITATION', 'Market prices, shares and FX require frozen fact references')
        for field, reference_field in [('shares', 'share_refs'), ('price', 'price_refs')]:
            p = command.provenance[f'reverse/market_basis/{index}/{field}']
            if p['kind'] == 'ASSUMED' or p['references'] != row.get(reference_field) or p['scope'] != row['listing_id']:
                fail('MARKET_BASIS_PROVENANCE_INVALID', 'Each class market datum must match a frozen numeric fact and listing scope')
            day = row['shares_as_of']
            if p['period'] != day + '/' + day:
                fail('MARKET_BASIS_PROVENANCE_INVALID', 'Market fact period must equal the dated share/price basis')
        if row.get('fx'):
            p = command.provenance[f'reverse/market_basis/{index}/fx/rate']
            fx = row['fx']
            if p['kind'] == 'ASSUMED' or p['references'] != fx['source_refs'] or p['scope'] != fx['from_currency'] + '->' + fx['to_currency'] or p['period'] != fx['as_of'] + '/' + fx['as_of']:
                fail('MARKET_BASIS_PROVENANCE_INVALID', 'FX fact must match pair direction, date and numeric source')


def source_files():
    root = Path(__file__).parent
    paths = ['calculator.py', 'valuation.py', 'valuation_replay.py', 'valuation_reference/fundamental_valuation.py',
             'valuation_reference/original_fundamental_valuation.py',
             'valuation_reference/LICENSE', 'valuation_reference/equity-research-LICENSE.txt',
             'valuation_reference/THIRD_PARTY_NOTICES.md']
    return [(name, (root / name).read_bytes()) for name in paths]


def replay_bundle(bundle):
    """Standalone offline verification; never executes caller supplied source code."""
    frozen, saved = verified(bundle['input']), verified(bundle['valuation'])
    if frozen['version_id'] != saved['input_version_id'] or frozen['content_sha256'] != saved['input_sha256']:
        fail('RESEARCH_REFERENCE_INVALID', 'Replay input/result binding differs', 409)
    snapshot, packet = verified(bundle['snapshot']), verified(bundle['analysis_input'])
    if snapshot['content_sha256'] != frozen['snapshot_sha256'] or snapshot['snapshot_id'] != frozen['snapshot_id'] or snapshot['input_id'] != packet['input_id'] or packet['payload']['company'] != frozen['company_identity']:
        fail('RESEARCH_REFERENCE_INVALID', 'Standalone snapshot/evidence binding differs', 409)
    if fingerprint(packet['payload']) != packet['packet_sha256'] or packet['fact_version_ids'] != frozen['fact_version_ids']:
        fail('RESEARCH_REFERENCE_INVALID', 'Frozen evidence packet hash or fact set differs', 409)
    for fact in packet['payload']['facts']:
        verified(fact)
    for material in packet['payload']['materials']:
        verified(material)
        raw = base64.b64decode(bundle['originals'][material['archive']['sha256']], validate=True)
        if hashlib.sha256(raw).hexdigest() != material['archive']['sha256']:
            fail('ARTIFACT_CORRUPT', 'Standalone evidence original differs', 409)
    local = dict(source_files())
    for entry in frozen['algorithm']['files']:
        raw = base64.b64decode(bundle['sources'][entry['path']], validate=True)
        if hashlib.sha256(raw).hexdigest() != entry['archive']['sha256']:
            fail('ARTIFACT_CORRUPT', 'Frozen calculator source hash differs', 409)
        if local.get(entry['path']) != raw:
            fail('CALCULATOR_VERSION_UNAVAILABLE', 'Install the frozen method version; never silently use new code', 409)
    result = calculate(frozen['config'], frozen['company_identity'])
    return {'matches_saved_result': result == saved['result'], 'result_sha256': fingerprint(result),
            'saved_result_sha256': fingerprint(saved['result']), 'network_calls': 0, 'model_calls': 0,
            'method_id': frozen['algorithm']['method_id'], 'method_version': frozen['algorithm']['version']}


class ValuationState:
    def __init__(self, research):
        self.research = research
        with research.transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS company_research_valuation_inputs(version_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS company_research_valuations(valuation_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, value TEXT NOT NULL)')

    def archive(self, raw, kind, db):
        descriptor = self.research.evidence.archive(raw, kind, db=db)
        return json.loads(db.execute('SELECT value FROM evidence_archives WHERE sha256=?', (descriptor['sha256'],)).fetchone()[0])

    def read(self, table, key, identifier):
        with self.research.ledger.connection() as db:
            row = db.execute(f'SELECT value FROM company_research_{table} WHERE {key}=?', (identifier,)).fetchone()
        if not row:
            fail('VALUATION_NOT_FOUND', 'Valuation version not registered', 404)
        value = verified(json.loads(row[0]))
        field = 'input_archive' if table == 'valuation_inputs' else 'result_archive'
        raw = self.research.evidence.raw(value[field]['sha256']).read_bytes()
        expected = {k: v for k, v in value.items() if k not in {field, 'content_sha256'}}
        if json.loads(raw) != expected:
            fail('ARTIFACT_CORRUPT', 'Stored valuation and archived payload differ', 409)
        return value

    def result(self, identifier):
        value = self.read('valuations', 'valuation_id', identifier)
        frozen = self.read('valuation_inputs', 'version_id', value['input_version_id'])
        if frozen['content_sha256'] != value['input_sha256'] or frozen['snapshot_id'] != value['snapshot_id'] or frozen['company_id'] != value['company_id']:
            fail('RESEARCH_REFERENCE_INVALID', 'Valuation input/result binding differs', 409)
        return value

    def calculate(self, command):
        request = command.model_dump()
        try:
            wire = json.dumps(request, allow_nan=False)
        except ValueError:
            fail('INVALID_NUMBER', 'Inputs must contain only finite numbers')
        if len(wire.encode()) > 131072:
            fail('VALUATION_INPUT_TOO_LARGE', 'Valuation input exceeds 128 KiB')
        snapshot = self.research.analysis_snapshot(command.snapshot_id)
        packet = self.research.analysis_input(snapshot['input_id'])
        company = packet['payload']['company']
        try:
            if valuation_cutoff(command.config['metadata']['as_of']) > valuation_cutoff(snapshot['as_of']):
                fail('INPUT_CHANGED', 'Valuation cutoff cannot exceed the bound snapshot')
            if command.config['metadata']['company'] != company['legal_name']:
                fail('SOURCE_IDENTITY_MISMATCH', 'Calculator company label must match frozen company identity')
            validate_provenance(command, snapshot, {f['version_id']: f for f in packet['payload']['facts']})
            output = calculate(command.config, company)
        except CalculationError as exc:
            fail(exc.code, exc.reason)
        except (ValueError, TypeError, KeyError, AttributeError, IndexError, OverflowError, ZeroDivisionError) as exc:
            message = str(exc)
            code = 'WACC_NOT_ABOVE_G' if 'wacc must exceed' in message else 'TERMINAL_NOT_APPLICABLE' if 'terminal base' in message else 'INVALID_VALUATION_INPUT'
            fail(code, message)
        with self.research.transaction() as db:
            prior = db.execute('SELECT request_hash,result FROM company_research_commands WHERE scope=? AND key=?',
                               ('valuation:' + snapshot['company_id'], command.idempotency_key)).fetchone()
            if prior:
                if prior[0] != fingerprint(request):
                    fail('IDEMPOTENCY_CONFLICT', 'Valuation key was already used for another request', 409)
                return self.result(verified(json.loads(prior[1]))['valuation_id'])
            parent = self.read('valuation_inputs', 'version_id', command.parent_version_id) if command.parent_version_id else None
            if parent and parent['company_id'] != snapshot['company_id']:
                fail('CROSS_COMPANY_REFERENCE', 'Parent valuation belongs to another company')
            files = [{'path': name, 'archive': self.archive(raw, 'COMPANY_VALUATION_ALGORITHM', db)} for name, raw in source_files()]
            hashes = {item['path']: item['archive']['sha256'] for item in files}
            algorithm = {'method_id': METHOD_ID, 'version': METHOD_VERSION, 'files': files,
                'original_sha256': hashes['valuation_reference/original_fundamental_valuation.py'],
                'adapted_sha256': hashes['valuation_reference/fundamental_valuation.py'],
                'calculator_sha256': hashes['calculator.py']}
            payload = record({'schema_version': 1, **request, 'company_id': snapshot['company_id'],
                'version_id': str(uuid4()), 'entity_id': parent['entity_id'] if parent else str(uuid4()),
                'revision': parent['revision'] + 1 if parent else 1, 'snapshot_sha256': snapshot['content_sha256'],
                'company_identity': company, 'fact_version_ids': snapshot['fact_version_ids'],
                'hypothesis_version_ids': snapshot['hypothesis_version_ids'], 'algorithm': algorithm,
                'economic_status': 'unreviewed', 'usable_range': False})
            payload.pop('content_sha256')
            input_archive = self.archive(encode(payload).encode(), 'COMPANY_VALUATION_INPUT', db)
            frozen = record({**payload, 'input_archive': input_archive})
            result_payload = record({'valuation_id': str(uuid4()), 'company_id': snapshot['company_id'],
                'snapshot_id': snapshot['snapshot_id'], 'input_version_id': frozen['version_id'],
                'input_sha256': frozen['content_sha256'], 'result': output, 'algorithm': algorithm})
            result_payload.pop('content_sha256')
            result_archive = self.archive(encode(result_payload).encode(), 'COMPANY_VALUATION_RESULT', db)
            value = record({**result_payload, 'result_archive': result_archive})
            db.execute('INSERT INTO company_research_valuation_inputs VALUES(?,?,?)', (frozen['version_id'], frozen['company_id'], encode(frozen)))
            db.execute('INSERT INTO company_research_valuations VALUES(?,?,?)', (value['valuation_id'], value['company_id'], encode(value)))
            self.research.save_command(db, 'valuation:' + snapshot['company_id'], command.idempotency_key, request, value)
            return value

    def bundle(self, identifier):
        result = self.result(identifier)
        frozen = self.research.valuation_input(result['input_version_id'])
        snapshot = self.research.analysis_snapshot(frozen['snapshot_id'])
        packet = self.research.analysis_input(snapshot['input_id'])
        if sum(m['archive']['bytes'] for m in packet['payload']['materials']) > 36 * 1024 * 1024:
            fail('VALUATION_BUNDLE_TOO_LARGE', 'Standalone bundle originals exceed 36 MiB; use full offline backup')
        originals = {m['archive']['sha256']: base64.b64encode(self.research.evidence.raw(m['archive']['sha256']).read_bytes()).decode()
                     for m in packet['payload']['materials']}
        if sum(len(v) for v in originals.values()) > 48 * 1024 * 1024:
            fail('VALUATION_BUNDLE_TOO_LARGE', 'Standalone bundle originals exceed 36 MiB; use full offline backup')
        return {'input': frozen, 'valuation': result, 'snapshot': snapshot, 'analysis_input': packet, 'originals': originals,
                'sources': {f['path']: base64.b64encode(self.research.evidence.raw(f['archive']['sha256']).read_bytes()).decode() for f in frozen['algorithm']['files']}}

    def replay(self, identifier):
        return replay_bundle(self.bundle(identifier))
