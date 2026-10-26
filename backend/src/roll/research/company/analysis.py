"""Frozen inputs, append-only hypotheses and shared published analysis.

Models return candidates only. This host owns references and revision authority.
"""
import json
from datetime import datetime, timezone
from uuid import uuid4, uuid5, NAMESPACE_URL

from roll.accounts.ledger import encode, now
from .service import fail, record, verified, fingerprint, page_bounds


class AnalysisState:
    def __init__(self, research):
        self.research = research
        with research.transaction() as db:
            for name, key in [('inputs', 'input_id'), ('snapshots', 'snapshot_id'),
                              ('hypotheses', 'version_id'), ('candidates', 'candidate_id'), ('analysis_runs', 'run_id')]:
                db.execute(f'CREATE TABLE IF NOT EXISTS company_research_{name}({key} TEXT PRIMARY KEY, company_id TEXT NOT NULL, value TEXT NOT NULL)')
            from roll.agents.codex_process import owner_alive, recover_directory
            for row in db.execute("SELECT value FROM company_research_analysis_runs WHERE json_extract(value,'$.status')='RUNNING'").fetchall():
                run = verified(json.loads(row[0]))
                if not owner_alive(run):
                    run.pop('content_sha256', None)
                    run.update(status='INTERRUPTED', finished_at=now(), error={'code': 'INTERRUPTED'})
                    if run.get('process', {}).get('task_root'):
                        run['recovery_cleanup'] = recover_directory(run)
                    db.execute('UPDATE company_research_analysis_runs SET value=? WHERE run_id=?', (encode(record(run)), run['run_id']))

    def read(self, table, key, identifier):
        with self.research.ledger.connection() as db:
            row = db.execute(f'SELECT value FROM company_research_{table} WHERE {key}=?', (identifier,)).fetchone()
        if not row:
            fail('ANALYSIS_NOT_FOUND', 'Analysis record is not registered', 404)
        result = verified(json.loads(row[0]))
        for field in ['input_archive', 'candidate_archive', 'raw_output_archive', 'candidate_output_archive']:
            if result.get(field):
                self.research.evidence.raw(result[field]['sha256'])
        return result

    def insert(self, db, table, key, value):
        db.execute(f'INSERT INTO company_research_{table} VALUES(?,?,?)',
                   (value[key], value['company_id'], encode(value)))

    def latest(self, company_id, db):
        row = db.execute('SELECT value FROM company_research_snapshots WHERE company_id=? ORDER BY rowid DESC LIMIT 1', (company_id,)).fetchone()
        return verified(json.loads(row[0])) if row else None

    def freeze(self, command):
        company = self.research.company(command.company_id)
        try:
            cutoff = datetime.fromisoformat(command.as_of)
            if cutoff.tzinfo is None or cutoff > datetime.now(timezone.utc):
                raise ValueError()
        except ValueError:
            fail('INVALID_AS_OF', 'as_of must be a timezone-aware timestamp no later than input freeze')
        facts = [self.research.fact(i, command.company_id) for i in dict.fromkeys(command.fact_version_ids)]
        if not facts and not command.evidence_gap_reason:
            fail('EVIDENCE_GAP_REQUIRED', 'An empty evidence packet must explain the evidence gap')
        materials = [self.research.material(i, command.company_id) for i in dict.fromkeys(f['material_id'] for f in facts)]
        for item in [*facts, *materials]:
            if datetime.fromisoformat(item['consumable_at']) > cutoff:
                fail('EVIDENCE_NOT_AVAILABLE', 'Selected evidence was not consumable at the requested cutoff')
        with self.research.transaction() as db:
            parent = self.latest(command.company_id, db)
            if (parent['snapshot_id'] if parent else None) != command.parent_snapshot_id:
                fail('INPUT_CHANGED', 'Specify the current parent snapshot before freezing a revision', 409)
            conflicts, resolutions = [], []
            for fact_id in dict.fromkeys(f['fact_id'] for f in facts):
                series = [verified(json.loads(r[0])) for r in db.execute('SELECT value FROM company_research_facts WHERE fact_id=? ORDER BY rowid', (fact_id,))]
                superseded = {f['supersedes'] for f in series if f['supersedes']}
                heads = [f for f in series if f['version_id'] not in superseded]
                signatures = {encode({k: f[k] for k in ['value', 'value_type', 'unit', 'currency', 'kind']}) for f in heads}
                if len(signatures) < 2:
                    continue
                heads_ids = {f['version_id'] for f in heads}
                choices = [verified(json.loads(r[0])) for r in db.execute('SELECT value FROM company_research_conflict_resolutions WHERE fact_id=? ORDER BY rowid', (fact_id,))]
                choices = [r for r in choices if set(r['version_ids']) == heads_ids]
                conflicts.append({'fact_id': fact_id, 'version_ids': sorted(heads_ids),
                                  'status': 'RESOLVED' if choices else 'UNRESOLVED', 'resolution': choices[-1] if choices else None})
                resolutions.extend(choices)
                for head in heads:
                    if head['version_id'] not in {f['version_id'] for f in facts}:
                        facts.append(self.research.fact(head['version_id'], command.company_id))
            if len(facts) > 80:
                fail('ANALYSIS_INPUT_TOO_LARGE', 'All conflict heads must fit the eighty-fact evidence limit')
            materials = [self.research.material(i, command.company_id) for i in dict.fromkeys(f['material_id'] for f in facts)]
            if any(datetime.fromisoformat(i['consumable_at']) > cutoff for i in [*facts, *materials]):
                fail('EVIDENCE_NOT_AVAILABLE', 'A known conflict cannot be silently omitted at the requested cutoff')
            prior_by_key = {}
            for row in db.execute('SELECT value FROM company_research_hypotheses WHERE company_id=? ORDER BY rowid', (command.company_id,)):
                hypothesis = verified(json.loads(row[0]))
                prior_by_key[hypothesis['key']] = hypothesis
            payload = {'company': company, 'as_of': command.as_of, 'facts': facts, 'materials': materials,
                       'conflicts': conflicts, 'conflict_resolutions': resolutions,
                       'prior_hypotheses': list(prior_by_key.values()),
                       'evidence_gap_reason': command.evidence_gap_reason,
                       'historical_pit_eligible': False, 'authority': 'RESEARCH_ONLY_NO_TOOLS_NO_ACCOUNT_WRITES'}
            wire = encode(payload).encode()
            if len(wire) > 98304:
                fail('ANALYSIS_INPUT_TOO_LARGE', 'Select a smaller evidence packet; limit is 96 KiB')
            archive = self.research.evidence.archive(wire, 'COMPANY_ANALYSIS_INPUT', db=db)
            value = record({**command.model_dump(), 'input_id': str(uuid4()), 'payload': payload,
                            'packet_sha256': fingerprint(payload), 'input_archive': archive,
                            'material_ids': [m['material_id'] for m in materials], 'fact_version_ids': [f['version_id'] for f in facts]})
            self.insert(db, 'inputs', 'input_id', value)
            return value

    def apply(self, input_id, candidate, model='EXTERNAL_CANDIDATE', prompt=None, raw_output_archive=None):
        packet = self.read('inputs', 'input_id', input_id)
        if not isinstance(candidate, dict) or len(encode(candidate).encode()) > 65536:
            fail('MODEL_OUTPUT_INVALID', 'Candidate must be an object of at most 64 KiB')
        candidate_hash = fingerprint(candidate)
        candidate_id = str(uuid5(NAMESPACE_URL, input_id + ':' + candidate_hash))
        with self.research.transaction() as db:
            if not db.execute('SELECT 1 FROM company_research_candidates WHERE candidate_id=?', (candidate_id,)).fetchone():
                archived = self.research.evidence.archive(encode(candidate).encode(), 'COMPANY_ANALYSIS_CANDIDATE', db=db)
                archived = json.loads(db.execute('SELECT value FROM evidence_archives WHERE sha256=?', (archived['sha256'],)).fetchone()[0])
                receipt = record({'candidate_id': candidate_id, 'company_id': packet['company_id'], 'input_id': input_id,
                                  'candidate_sha256': candidate_hash, 'candidate_archive': archived,
                                  'meaning': 'Archived provisional candidate; receipt does not authorize publication'})
                self.insert(db, 'candidates', 'candidate_id', receipt)
        if candidate.get('company_id') != packet['company_id']:
            fail('CROSS_COMPANY_REFERENCE', 'Candidate company differs from the frozen input')
        if candidate.get('input_sha256') != packet['packet_sha256']:
            fail('INPUT_CHANGED', 'Candidate does not bind the frozen input hash', 409)
        from .candidates import validate_candidate
        normalized, rejections = validate_candidate(self.research, packet, candidate)
        with self.research.transaction() as db:
            row = db.execute("SELECT value FROM company_research_snapshots WHERE json_extract(value,'$.input_id')=?", (input_id,)).fetchone()
            if row:
                saved = verified(json.loads(row[0]))
                if saved['candidate_sha256'] != fingerprint(candidate):
                    fail('IDEMPOTENCY_CONFLICT', 'Frozen input has already published another candidate', 409)
                return saved
            parent = self.latest(packet['company_id'], db)
            if (parent['snapshot_id'] if parent else None) != packet['parent_snapshot_id']:
                fail('INPUT_CHANGED', 'Another analysis was published after input freeze', 409)
            hypotheses = []
            for item in normalized['hypotheses']:
                hid = str(uuid5(NAMESPACE_URL, packet['company_id'] + ':' + item['key']))
                previous = next((h for h in packet['payload']['prior_hypotheses'] if h['hypothesis_id'] == hid), None)
                hypothesis = record({**item, 'hypothesis_id': hid, 'version_id': str(uuid4()),
                    'company_id': packet['company_id'], 'revision': previous['revision'] + 1 if previous else 1,
                    'parent_version_id': previous['version_id'] if previous else None,
                    'judgment_status': 'CONDITIONAL' if item['support_fact_version_ids'] else ('COUNTEREVIDENCE_ONLY' if item['counter_fact_version_ids'] else 'UNABLE_TO_JUDGE')})
                self.insert(db, 'hypotheses', 'version_id', hypothesis)
                hypotheses.append(hypothesis)
            archive = json.loads(db.execute('SELECT value FROM evidence_archives WHERE sha256=?', (candidate_hash,)).fetchone()[0])
            value = record({'snapshot_id': str(uuid4()), 'company_id': packet['company_id'],
                'input_id': input_id, 'as_of': packet['as_of'], 'generated_at': now(), 'status': 'PUBLISHED',
                'parent_snapshot_id': packet['parent_snapshot_id'], 'purposes': ['DAILY', 'REPORT'],
                'material_ids': packet['material_ids'], 'fact_version_ids': packet['fact_version_ids'],
                'independent_origin_root_ids': sorted({m['origin_root_id'] for m in packet['payload']['materials']}),
                'hypothesis_version_ids': [h['version_id'] for h in hypotheses], 'valuation_ids': [],
                'omitted_prior_hypothesis_version_ids': [h['version_id'] for h in packet['payload']['prior_hypotheses']
                    if h['key'] not in {item['key'] for item in hypotheses}],
                'quote_ids': [], 'check_ids': [], 'input_sha256': packet['packet_sha256'],
                'candidate_id': candidate_id, 'candidate_sha256': candidate_hash, 'candidate_archive': archive, 'rejections': rejections,
                'input_archive': packet['input_archive'], 'raw_output_archive': raw_output_archive, 'model_id': model, 'prompt': prompt,
                'verification': 'STRUCTURE_AND_REFERENCES_CHECKED_NOT_FACTUAL_ENDORSEMENT',
                'core': {**{k: normalized[k] for k in ['business_structure', 'attention_reasons', 'counterevidence',
                    'limitations', 'insufficient_hypotheses_reason', 'valuation_unavailable_reason']}, 'hypotheses': hypotheses}})
            value.pop('content_sha256')
            value = record({**value, 'core_sha256': fingerprint(value['core'])})
            self.insert(db, 'snapshots', 'snapshot_id', value)
            return value

    def snapshot(self, identifier, purpose='DAILY'):
        if purpose not in {'DAILY', 'REPORT'}:
            fail('INVALID_PURPOSE', 'Published analysis is shared by DAILY and REPORT')
        return self.read('snapshots', 'snapshot_id', identifier)

    def snapshots(self, company_id, limit=100, offset=0):
        self.research.company(company_id)
        page_bounds(limit, offset, 200)
        with self.research.ledger.connection() as db:
            total = db.execute('SELECT COUNT(*) FROM company_research_snapshots WHERE company_id=?', (company_id,)).fetchone()[0]
            ids = [r[0] for r in db.execute('SELECT snapshot_id FROM company_research_snapshots WHERE company_id=? ORDER BY rowid LIMIT ? OFFSET ?', (company_id, limit, offset))]
        return {'snapshots': [self.snapshot(i) for i in ids], 'total': total, 'limit': limit, 'offset': offset,
                'has_more': offset + limit < total}

    def candidates(self, input_id, limit=100, offset=0):
        self.read('inputs', 'input_id', input_id)
        page_bounds(limit, offset, 200)
        with self.research.ledger.connection() as db:
            total = db.execute("SELECT COUNT(*) FROM company_research_candidates WHERE json_extract(value,'$.input_id')=?", (input_id,)).fetchone()[0]
            rows = db.execute("SELECT value FROM company_research_candidates WHERE json_extract(value,'$.input_id')=? ORDER BY rowid LIMIT ? OFFSET ?", (input_id, limit, offset)).fetchall()
        return {'candidates': [verified(json.loads(r[0])) for r in rows], 'total': total,
                'limit': limit, 'offset': offset, 'has_more': offset + limit < total}
