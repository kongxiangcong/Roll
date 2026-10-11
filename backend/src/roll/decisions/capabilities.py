"""Host capability admission. Research/model workers have no issuance tool."""
import hashlib
import json
import os
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from roll.accounts.ledger import encode, now, timestamp
from roll.accounts.reconcile import use_check, UseCheck
from roll.decisions.funding import LossFacts, evaluate_loss
from roll.research.technical_review import LABEL
from roll.decisions.lifecycle_journal import LifecycleJournal
from roll.runtime.backups import persist

PROFIT_GATES = {f'G{i}' for i in range(1, 8)}
RISK_GATES = {'DATA', 'RULE_QUANTITY', 'AUTHORIZATION', 'STRESS_EXECUTION', 'ONLINE_CONSISTENCY'}
ACTIONS = {'BUY', 'ADD', 'HOLD', 'REDUCE', 'EXIT', 'WAIT'}


def source_inventory():
    root = Path(__file__).parents[1]
    return {str(p.relative_to(root)).replace('\\', '/'): hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
            for p in sorted(root.rglob('*.py'))}


def moment(value):
    try:
        result = datetime.fromisoformat(value)
        if result.tzinfo is None: raise ValueError('timezone required')
        return result.astimezone(timezone.utc)
    except (ValueError, TypeError): raise HTTPException(422, 'CAPABILITY_TIME_REQUIRES_TIMEZONE')


class GrantCommand(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    material_id: str
    review_run_id: str
    expected_material_fingerprint: str
    deployment_fingerprints: dict[str, str]
    scope: dict
    allowed_actions: list[str]
    expected_account_version: int = Field(ge=0)
    expected_funding_version: int = Field(ge=0)
    required_as_of: str
    effective_at: str
    expires_at: str
    idempotency_key: str = Field(min_length=1, max_length=128)
    basis: str = Field(min_length=1, max_length=2000)
    predecessor_grant_id: str | None = None

    @field_validator('scope')
    @classmethod
    def valid_scope(cls, value):
        if set(value) != {'instruments', 'market', 'board', 'frequency', 'horizon'} or not isinstance(value['instruments'], list) or not value['instruments'] or any(not isinstance(i, str) or not i for i in value['instruments']) or len(set(value['instruments'])) != len(value['instruments']):
            raise ValueError('需要明确且不重复的证券、市场、板块、频率和期限')
        if any(not isinstance(value[k], str) or not value[k] for k in ['market', 'board', 'frequency']) or type(value['horizon']) is not int or value['horizon'] <= 0:
            raise ValueError('适用范围字段无效')
        return value

    @field_validator('required_as_of', 'effective_at', 'expires_at')
    @classmethod
    def valid_time(cls, value):
        try: moment(value)
        except HTTPException as error: raise ValueError(str(error.detail)) from error
        return value


class LifecycleCommand(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    scope: Literal['NEW_RISK', 'MODEL', 'ALL_MONITOR']
    state: Literal['SUSPENDED', 'REVOKED', 'ACTIVE']
    reason_code: Literal['USER_PAUSE', 'USER_REVOKE', 'DATA_DRIFT', 'EXECUTION_MISMATCH', 'MATURE_EVIDENCE_DETERIORATION', 'LOSS_BOUNDARY']
    grant_id: str | None = None
    resume_event_id: str | None = None
    recovery_check_id: str | None = None
    reason: str = Field(min_length=1, max_length=2000)
    expected_version: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=128)

    @model_validator(mode='after')
    def user_command(self):
        if self.state != 'ACTIVE' and self.reason_code not in {'USER_PAUSE', 'USER_REVOKE'}:
            raise ValueError('自动受限原因由受控监测或损失服务登记')
        return self


class Capabilities:
    def __init__(self, ledger, funding, reviews, valuations, method_file=None, recovery=None):
        self.ledger, self.funding, self.reviews, self.valuations = ledger, funding, reviews, valuations
        self.recovery = recovery
        self.actions = None
        self.observation_reviews = None
        self.monitoring = None
        self.journal = LifecycleJournal(ledger)
        self.method_package = None
        self.method_fingerprint = None
        if method_file is not None:
            if os.environ.get('ROLL_ENV') != 'test': raise ValueError('CAPABILITY_METHOD_HOST_TEST_ONLY')
            envelope = json.loads(Path(method_file).read_text(encoding='utf-8'))
            raw = encode(envelope['package']).encode()
            if hashlib.sha256(raw).hexdigest() != envelope['sha256'] or envelope['package']['namespace'] != 'METHOD_ENGINEERING':
                raise ValueError('CAPABILITY_METHOD_PACKAGE_INVALID')
            self.method_package = envelope['package']
            self.method_fingerprint = envelope['sha256']
        with ledger.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS capability_grants(id TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS capability_events(id TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS capability_receipts(key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, status INTEGER NOT NULL, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS capability_method_basis(id INTEGER PRIMARY KEY, fingerprint TEXT NOT NULL, archive TEXT NOT NULL, sources TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS capability_proofs(id TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS capability_lifecycle_receipts(key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, value TEXT NOT NULL);
            ''')
            if self.method_package is not None:
                prior = db.execute('SELECT fingerprint FROM capability_method_basis WHERE id=1').fetchone()
                if prior and prior[0] != self.method_fingerprint: raise ValueError('CAPABILITY_METHOD_BASIS_CHANGED')
                if not prior:
                    archive = reviews.evidence.archive(encode(self.method_package).encode(), 'CAPABILITY_METHOD_QUALIFICATION')
                    db.execute('INSERT INTO capability_method_basis VALUES(1,?,?,?)', (self.method_fingerprint, encode(archive), encode(source_inventory())))
        self.journal.initialize()
        self.refresh_journal()

    def refresh_journal(self):
        with self.ledger.connection() as db:
            # Wait for a live controlled writer to commit or roll back before
            # classifying its durable PENDING file. A concurrent read must not
            # permanently lock a normal operation still being committed.
            db.execute('BEGIN IMMEDIATE')
            self.journal.reconcile_committed(db)
            status = self.journal.status()
            missing = [e for e in status['confirmed_events'] if not db.execute('SELECT 1 FROM capability_events WHERE id=?', (e['event_id'],)).fetchone()]
            if status['unknown'] or missing or not status['history_known']:
                path = Path(self.ledger.path).parent / 'backups/recovery-lock.json'
                prior = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
                value = {**prior, 'state': 'RECOVERY_LOCK', 'locked_at': prior.get('locked_at') or now(),
                    'formal_actions_allowed': False, 'old_notifications_allowed': False, 'observation_allowed': True,
                    'old_active_records': 'HISTORY_ONLY', 'possibly_missing_revocations': 'UNVERIFIED' if status['unknown'] or not status['history_known'] else 'CONFIRMED_LOCAL_JOURNAL_GAP',
                    'permission_consumer_27': 'CONNECTED', 'pending_permission_events': status['unknown'],
                    'missing_committed_event_ids': [e['event_id'] for e in missing]}
                persist(path, encode(value).encode())
            # Only a matching committed receipt may replay exact terminal
            # history. Rolled-back/crashed pending entries remain unknown.
            for event in missing:
                if event.get('state') in {'REVOKED', 'EXPIRED'}:
                    db.execute('INSERT OR IGNORE INTO capability_events VALUES(?,?)', (event['event_id'], encode(event)))
            db.commit()
        return status

    def grants(self):
        with self.ledger.connection() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT value FROM capability_grants ORDER BY rowid')]

    def proposal(self, material_id, review_run_id):
        # Frozen host evidence determines scope; React never chooses statistics or declares PASS.
        with self.ledger.connection() as db:
            row = self.method_package if self.method_package and self.method_package['material_id'] == material_id else None
            if row is None:
                material = self.reviews.get_material(material_id)
                row = {**material['basis_manifest'], 'material_fingerprint': material['material_fingerprint'],
                       'deployment_fingerprints': material['basis_manifest'].get('candidate_fingerprints', {})}
            if self.method_package and row is self.method_package and review_run_id != row['review_run_id']:
                raise HTTPException(409, 'REVIEW_BINDING_MISMATCH')
            if not row.get('review_due_at') or not row.get('allowed_actions') or not row.get('scope'):
                raise HTTPException(409, '最终资格证据、适用动作或到期边界未完成，不能登记资格')
            return {'material_id': material_id, 'review_run_id': review_run_id, 'expected_material_fingerprint': row['material_fingerprint'],
                    'deployment_fingerprints': row['deployment_fingerprints'], 'scope': row['scope'], 'allowed_actions': row['allowed_actions'],
                    'expected_account_version': self.ledger.account(db=db)['version'], 'expected_funding_version': self.funding.current(db=db)['version'],
                    'required_as_of': row['required_as_of'], 'effective_at': row['effective_at'], 'expires_at': row['review_due_at']}

    def _evidence(self, command, db, proof=None):
        if self.method_package is not None and command.material_id == self.method_package['material_id']:
            if os.environ.get('ROLL_ENV') != 'test': raise HTTPException(409, 'METHOD_PRODUCTION_REFUSED')
            row = db.execute('SELECT archive,sources FROM capability_method_basis WHERE id=1').fetchone()
            archive = json.loads(row[0])
            if self.reviews.evidence.raw(archive['sha256']).read_bytes() != encode(self.method_package).encode():
                raise HTTPException(409, 'METHOD_ARCHIVE_CHANGED')
            if json.loads(row[1]) != source_inventory(): raise HTTPException(409, 'DEPLOYMENT_SOURCE_CHANGED')
            if command.review_run_id != self.method_package['review_run_id']: raise HTTPException(409, 'REVIEW_BINDING_MISMATCH')
            package = dict(self.method_package)
            bindings = {'material_fingerprint': package['material_fingerprint'], 'review_run_id': command.review_run_id,
                        'basis_fingerprint': self.method_fingerprint, 'source_fingerprint': hashlib.sha256(encode(source_inventory()).encode()).hexdigest()}
            if proof is not None and any(proof.get(k) != v for k, v in bindings.items()): raise HTTPException(409, 'HOST_PROOF_BINDING_CHANGED')
            package['host_proof'] = {**bindings, 'reproduction': package['review']['reproduction']} if proof is None else proof
            return package, 'METHOD_ENGINEERING'
        material = self.reviews.get_material(command.material_id)
        run = self.reviews.get(command.review_run_id)
        basis = material['basis_manifest']
        sources = source_inventory()
        for item in material['local_code']:
            if sources.get(item['source_path']) != item['sha256']: raise HTTPException(409, 'DEPLOYMENT_SOURCE_CHANGED')
        record = run.get('review_record') or {}
        bindings = {'material_fingerprint': material['material_fingerprint'], 'review_run_id': command.review_run_id,
                    'basis_id': material['basis_id'], 'material_manifest_sha256': material['manifest_archive']['sha256'],
                    'review_record_sha256': (run.get('review_record_archive') or {}).get('sha256'),
                    'result_fingerprint': basis['result_fingerprint'], 'source_fingerprint': hashlib.sha256(encode(sources).encode()).hexdigest()}
        if proof is None:
            reproduction = self.reviews.reproduce(material)
            proof = {**bindings, 'reproduction': reproduction}
        else:
            if any(proof.get(k) != v for k, v in bindings.items()): raise HTTPException(409, 'HOST_PROOF_BINDING_CHANGED')
            reproduction = proof['reproduction']
        if reproduction.get('result_fingerprint') != basis['result_fingerprint']: raise HTTPException(409, 'HOST_PROOF_RESULT_CHANGED')
        p = {**basis, 'material_id': material['material_id'], 'material_fingerprint': material['material_fingerprint'],
             'candidate_kind': material['candidate_kind'], 'review': {**record, 'backend': run['backend'], 'status': run['status'],
                 'material_id': run['material_id'], 'material_fingerprint': run['material_fingerprint'], 'reproduction': reproduction},
             'host_proof': proof,
             'deployment_fingerprints': basis.get('candidate_fingerprints') or {
                 'policy': basis.get('policy_fingerprint'), 'code': basis.get('code_fingerprint'), **basis.get('dependency_fingerprints', {})}}
        # The final qualification producer owns these frozen fields. Diagnostic records do not acquire them here.
        return p, material['evidence_kind']

    def proofs(self):
        with self.ledger.connection() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT value FROM capability_proofs ORDER BY rowid')]

    def _prepare_proof(self, command):
        value = {'proof_id': str(uuid4()), 'status': 'RUNNING', 'started_at': now(),
                 'material_id': command.material_id, 'review_run_id': command.review_run_id, 'command': command.model_dump()}
        with self.ledger.connection() as db:
            db.execute('INSERT INTO capability_proofs VALUES(?,?)', (value['proof_id'], encode(value)))
        try:
            if self.method_package is not None and command.material_id == self.method_package['material_id']:
                delay = self.method_package.get('method_reproduction_delay_ms', 0)
                if type(delay) is not int or not 0 <= delay <= 5000: raise HTTPException(409, 'METHOD_REPRODUCTION_DELAY_INVALID')
                time.sleep(delay / 1000)
            # Numerical reproduction has no SQLite writer transaction. Only immutable evidence is read here.
            with self.ledger.connection() as db:
                package, kind = self._evidence(command, db)
            reproduction = package['host_proof']['reproduction']
            if reproduction.get('matches_original') is not True or reproduction.get('network_calls') != 0:
                raise HTTPException(409, 'HOST_REPRODUCTION_NOT_VERIFIED')
            value.update(status='VERIFIED', finished_at=now(), evidence_kind=kind, **package['host_proof'])
            value['archive'] = self.reviews.evidence.archive(encode(value).encode(), 'CAPABILITY_HOST_PROOF')
        except (HTTPException, ValueError, KeyError) as error:
            value.update(status='FAILED', finished_at=now(), error=str(error.detail) if isinstance(error, HTTPException) else type(error).__name__)
        with self.ledger.connection() as db:
            db.execute('UPDATE capability_proofs SET value=? WHERE id=?', (encode(value), value['proof_id']))
        return value

    def verify_proof(self, proof_id):
        with self.ledger.connection() as db:
            proof = self._checked_proof(proof_id, db)
            self._evidence(GrantCommand(**proof['command']), db, proof)
        return {'proof_id': proof_id, 'status': 'VERIFIED', 'reproduction_reused': True,
                'material_fingerprint': proof['material_fingerprint'], 'network_calls': 0}

    def _checked_proof(self, proof_id, db):
        row = db.execute('SELECT value FROM capability_proofs WHERE id=?', (proof_id,)).fetchone()
        if row is None: raise HTTPException(409, 'HOST_PROOF_MISSING')
        value = json.loads(row[0])
        if value['status'] != 'VERIFIED': raise HTTPException(409, value.get('error', 'HOST_PROOF_NOT_VERIFIED'))
        if self.reviews.shadow.checked_archive(value['archive']) != {k: v for k, v in value.items() if k != 'archive'}:
            raise HTTPException(409, 'HOST_PROOF_ARCHIVE_CHANGED')
        return value

    def _current_conditions(self, command, package, db, kind, recovery_check=False):
        reasons = []
        account, funding = self.ledger.account(db=db), self.funding.current(db=db)
        if account['version'] != command.expected_account_version: reasons.append('ACCOUNT_VERSION_CONFLICT')
        if funding['version'] != command.expected_funding_version: reasons.append('FUNDING_VERSION_CONFLICT')
        if funding['state'] != 'CONFIRMED' or not funding.get('enabled') or funding.get('pause_latched'): reasons.append('FUNDING_NOT_ENABLED')
        if package.get('scope_id') != funding.get('scope_id') or package.get('scope_kind') != funding.get('scope_kind'): reasons.append('FUNDING_SCOPE_MISMATCH')
        if funding.get('effective_at') and moment(funding['effective_at']) > moment(now()): reasons.append('FUNDING_NOT_EFFECTIVE')
        ids = [r[0] for r in db.execute("SELECT d.id FROM account_drafts d WHERE status IN ('READY','QUARANTINED') AND NOT EXISTS(SELECT 1 FROM account_receipts r WHERE json_extract(r.receipt,'$.draft_id')=d.id)")]
        pending = [self.ledger.get_draft(i, db) for i in ids]
        purpose = 'NEW_RISK' if set(command.allowed_actions) & {'BUY', 'ADD', 'HOLD', 'WAIT'} else 'REDUCTION'
        check = use_check(account, pending, UseCheck(purpose=purpose, required_as_of=command.required_as_of), timestamp, self.ledger.events(db=db))
        if not check['allowed']: reasons.append('ACCOUNT_FACTS_NOT_RECONCILED'); reasons.extend(check['reasons'])
        market, board = command.scope.get('market'), command.scope.get('board')
        if set(command.allowed_actions) & {'BUY', 'ADD'} and not any(p['market'] == market and p['board'] == board and p['status'] == 'OPEN' for p in account['permission_profile']): reasons.append('MARKET_PERMISSION_NOT_OPEN')
        if not recovery_check and self.recovery and self.recovery()['state'] == 'RECOVERY_LOCK': reasons.append('RECOVERY_LOCK')
        try:
            if kind == 'METHOD_ENGINEERING':
                if package.get('account_version') != account['version']: raise HTTPException(409, 'METHOD_ACCOUNT_BINDING_CHANGED')
                facts, data = package['loss_facts'], package['current_data']
                if data['status'] != 'COMPLETE' or moment(data['as_of']) < moment(command.required_as_of) or moment(data['as_of']).astimezone(timezone(timedelta(hours=8))).date() != moment(now()).astimezone(timezone(timedelta(hours=8))).date() or not set(command.scope['instruments']) <= set(data['instruments']): reasons.append('CURRENT_DATA_INCOMPLETE')
            else:
                valuation = self.valuations.get()
                if valuation['input_authority'] != 'CONFIRMED_ACCOUNT_AND_ARCHIVED_SOURCE' or valuation['account_version'] != account['version']: raise HTTPException(409, 'CURRENT_VALUATION_NOT_AUTHORITATIVE')
                if moment(valuation['facts']['as_of']) < moment(command.required_as_of) or moment(valuation['facts']['as_of']).astimezone(timezone(timedelta(hours=8))).date() != moment(now()).astimezone(timezone(timedelta(hours=8))).date(): raise HTTPException(409, 'CURRENT_VALUATION_STALE')
                facts = valuation['facts']
            if funding['version']:
                loss = evaluate_loss(funding, LossFacts(**facts))
                if loss['status'] != 'WITHIN_BOUNDARY': reasons.append('LOSS_BOUNDARY_UNAVAILABLE_OR_PAUSED')
        except (HTTPException, KeyError, ValueError): reasons.append('CURRENT_ACCOUNT_DATA_OR_LOSS_UNAVAILABLE')
        return reasons

    def _admit(self, command, db, proof_id, recovery_check=False):
        reasons = []
        try:
            proof = self._checked_proof(proof_id, db)
            package, kind = self._evidence(command, db, proof)
        except HTTPException as error:
            return ['EVIDENCE_UNAVAILABLE', str(error.detail)], None, None
        gates = PROFIT_GATES if package.get('candidate_kind') == 'PROFIT_MODEL' else RISK_GATES if package.get('candidate_kind') == 'RISK_POLICY' else set()
        protocol_fingerprint = package.get('complete_protocol_fingerprint')
        if not isinstance(protocol_fingerprint, str) or len(protocol_fingerprint) != 64 or any(c not in '0123456789abcdef' for c in protocol_fingerprint): reasons.append('COMPLETE_PROTOCOL_FINGERPRINT_MISSING')
        statuses = {k: v.get('status') if isinstance(v, dict) else v for k, v in package.get('gates', {}).items()}
        if not gates or set(statuses) != gates or any(s != 'PASS' for s in statuses.values()): reasons.append('REQUIRED_GATES_NOT_PASS')
        if package.get('validation_verdict') != 'PASS' or package.get('preliminary') is not False or package.get('experiment_status') not in {'CLOSED', 'ENDED'} or package.get('incomplete_checks') != []: reasons.append('QUALIFICATION_EVIDENCE_INCOMPLETE')
        review = package['review']
        if kind not in {'METHOD_ENGINEERING', 'REAL_ACQUISITION'}: reasons.append('SYNTHETIC_EVIDENCE_NOT_AUTHORIZED')
        if review.get('backend') != 'CODEX' or review.get('status') != 'COMPLETE': reasons.append('CODEX_REVIEW_INCOMPLETE')
        if review.get('material_id') != command.material_id or review.get('material_fingerprint') != command.expected_material_fingerprint or package['material_fingerprint'] != command.expected_material_fingerprint: reasons.append('REVIEW_MATERIAL_BINDING_MISMATCH')
        if review.get('blocking_issues_resolved') is not True or review.get('host_unresolved_gate_evidence') or any(i.get('severity') == 'BLOCKING' and not i.get('resolution') for i in review.get('issues', [])): reasons.append('REVIEW_BLOCKERS_UNRESOLVED')
        if review.get('reproduction', {}).get('matches_original') is not True or review.get('reproduction', {}).get('network_calls') != 0: reasons.append('HOST_REPRODUCTION_NOT_VERIFIED')
        if command.deployment_fingerprints != package.get('deployment_fingerprints'): reasons.append('DEPLOYMENT_FINGERPRINT_MISMATCH')
        scope = package.get('qualification_scope', package.get('scope', {}))
        if set(command.scope) != set(scope) or any(command.scope.get(k) != v for k, v in scope.items() if k != 'instruments') or not set(command.scope.get('instruments', [])) or not set(command.scope.get('instruments', [])) <= set(scope.get('instruments', [])): reasons.append('SCOPE_NOT_VALIDATED')
        if not command.allowed_actions or len(set(command.allowed_actions)) != len(command.allowed_actions) or not set(command.allowed_actions) <= ACTIONS or not set(command.allowed_actions) <= set(package.get('allowed_actions', [])): reasons.append('ACTIONS_NOT_VALIDATED')
        if package.get('candidate_kind') == 'RISK_POLICY' and not set(command.allowed_actions) <= {'REDUCE', 'EXIT'}: reasons.append('RISK_POLICY_CANNOT_AUTHORIZE_NEW_RISK')
        try:
            start, end, current = moment(command.effective_at), moment(command.expires_at), moment(now())
            if not start <= current < end or end > moment(package['review_due_at']) or start < moment(package['effective_at']) or moment(command.required_as_of) > current: reasons.append('GRANT_TIME_OUTSIDE_VALIDATED_BOUNDARY')
        except (KeyError, HTTPException): reasons.append('VALIDATED_EXPIRY_MISSING')
        reasons += self._current_conditions(command, package, db, kind, recovery_check)
        if command.required_as_of != package.get('required_as_of'): reasons.append('CURRENT_CUTOFF_NOT_BOUND')
        return list(dict.fromkeys(reasons)), package, kind

    def current(self, db=None, grant_id=None):
        if db is None:
            self.refresh_journal()
            with self.ledger.connection() as connection:
                connection.execute('BEGIN IMMEDIATE')
                expired = self.expire(connection)
                if expired and self.actions: self.actions.current(db=connection)
                result = self.current(connection, grant_id)
                connection.commit()
                self.journal.reconcile_committed()
                return result
        grants = [json.loads(r[0]) for r in db.execute('SELECT value FROM capability_grants ORDER BY rowid')]
        funding = self.funding.current(db=db)
        recovery = self.recovery() if self.recovery else {'state': 'NORMAL'}
        control = self.lifecycle(db)
        result = {'state': 'UNGRANTED', 'formal_judgment': 'DISABLED', 'allowed_actions': [], 'reason': '尚无通过验证及受控登记的技术能力',
                  'funding_state': funding['state'], 'runtime_state': recovery['state'], 'recovery': recovery, 'human_review_label': LABEL, 'reasons': [], 'grant_statuses': [], 'lifecycle': control}
        if grant_id is not None and not any(g['grant_id'] == grant_id for g in grants): raise HTTPException(404, '能力授权不存在')
        if not grants:
            event = db.execute('SELECT value FROM capability_events ORDER BY rowid DESC LIMIT 1').fetchone()
            if event:
                reasons = json.loads(event[0]).get('reasons', [])
                result.update(reasons=reasons, reason='；'.join(reasons) or result['reason'])
            return result
        statuses = []
        for grant in grants:
            own_control = self.lifecycle(db, grant['grant_id'])
            command = GrantCommand(**grant['command'])
            reasons, _, _ = self._admit(command, db, grant.get('proof_id'))
            if grant['evidence_kind'] == 'METHOD_ENGINEERING' and self.method_package is None: reasons.append('METHOD_PRODUCTION_REFUSED')
            revoked = any(s['state'] == 'REVOKED' for s in own_control['scopes'].values())
            expired = moment(now()) >= moment(grant['expires_at'])
            if revoked: reasons.append('CAPABILITY_REVOKED')
            if expired: reasons.append('CAPABILITY_EXPIRED')
            if not own_control['observations_allowed']: reasons.append('ALL_MONITOR_SUSPENDED')
            elif grant['candidate_kind'] == 'PROFIT_MODEL' and not own_control['model_judgments_allowed']: reasons.append('MODEL_SUSPENDED')
            allowed = [] if reasons else [a for a in grant['allowed_actions'] if own_control['new_risk_allowed'] or a not in {'BUY', 'ADD'}]
            statuses.append({'state': 'REVOKED' if revoked else 'EXPIRED' if expired else 'RESTRICTED' if reasons else 'METHOD_GRANTED' if grant['evidence_kind'] == 'METHOD_ENGINEERING' else 'GRANTED',
                'reason': '；'.join(reasons) if reasons else '资格范围与当前条件核验通过', 'reasons': reasons,
                'grant': grant, 'allowed_actions': allowed, 'lifecycle': own_control})
        if grant_id is not None:
            selected = next(s for s in statuses if s['grant']['grant_id'] == grant_id)
        else:
            usable = [s for s in statuses if not s['reasons']]
            selected = next((s for s in usable if s['grant']['candidate_kind'] == 'PROFIT_MODEL'), usable[-1] if usable else statuses[-1])
        result.update(selected, grant_statuses=statuses)
        if grant_id is None:
            result['allowed_actions'] = sorted({action for s in statuses for action in s['allowed_actions']})
        # Ticket25 owns formal action publication. METHOD authority is never usable in the actual system.
        return result

    def expire(self, db):
        """Append expiry once in the caller's controlled write transaction."""
        recorded = now()
        count = 0
        for row in db.execute('SELECT value FROM capability_grants ORDER BY rowid').fetchall():
            grant = json.loads(row[0])
            if moment(recorded) < moment(grant['expires_at']): continue
            if db.execute("SELECT 1 FROM capability_events WHERE json_extract(value,'$.grant_id')=? AND json_extract(value,'$.reason_code')='EXPIRY'", (grant['grant_id'],)).fetchone(): continue
            control = self.lifecycle(db, grant['grant_id'])
            if any(s['state'] == 'REVOKED' for s in control['scopes'].values()): continue
            value = {'event_id': str(uuid4()), 'event_type': 'CAPABILITY_SCOPE_CHANGED', 'scope': 'MODEL',
                     'grant_id': grant['grant_id'], 'state': 'EXPIRED', 'version': self.lifecycle(db)['version'] + 1,
                     'reason_code': 'EXPIRY', 'reason': '冻结资格已到期，须当前新资格和后继授权',
                     'effective_at': grant['expires_at'], 'recorded_at': recorded}
            db.execute('INSERT INTO capability_events VALUES(?,?)', (value['event_id'], encode(value)))
            self.journal.stage(value)
            count += 1
        return count

    def lifecycle(self, db=None, grant_id=None):
        if db is None:
            with self.ledger.connection() as connection:
                return self.lifecycle(connection, grant_id)
        scopes = {scope: {'state': 'ACTIVE', 'version': 0, 'reason_code': None, 'reason': None, 'effective_at': None}
                  for scope in ['NEW_RISK', 'MODEL', 'ALL_MONITOR']}
        local = {scope: dict(value) for scope, value in scopes.items()}
        version = 0
        for row in db.execute('SELECT value FROM capability_events ORDER BY rowid'):
            event = json.loads(row[0])
            if event['event_type'] != 'CAPABILITY_SCOPE_CHANGED': continue
            version = max(version, event['version'])
            if event.get('grant_id') not in {None, grant_id}: continue
            target = scopes if event.get('grant_id') is None else local
            # A global resume removes only its own pause. Per-grant controls and
            # terminal history cannot be overwritten by an unrelated command.
            target[event['scope']] = {k: event[k] for k in ['state', 'version', 'reason_code', 'reason', 'effective_at', 'event_id']}
        if grant_id is not None:
            scopes = {scope: local[scope] if local[scope]['state'] in {'REVOKED', 'EXPIRED'} or scopes[scope]['state'] == 'ACTIVE' else scopes[scope]
                      for scope in scopes}
        observations = scopes['ALL_MONITOR']['state'] == 'ACTIVE'
        model = observations and scopes['MODEL']['state'] == 'ACTIVE'
        return {'version': version, 'scopes': scopes, 'observations_allowed': observations,
                'independent_risk_observations_allowed': observations, 'model_judgments_allowed': model,
                'new_risk_allowed': model and scopes['NEW_RISK']['state'] == 'ACTIVE',
                'account_facts_allowed': True, 'audit_and_backup_allowed': True}

    def change_lifecycle(self, command):
        self.refresh_journal()
        prepared_recovery = None
        if command.state == 'ACTIVE' and command.reason_code not in {'USER_PAUSE', 'USER_REVOKE', 'LOSS_BOUNDARY'}:
            if not command.grant_id or not self.monitoring: raise HTTPException(409, 'REASON_BOUND_RECOVERY_EVIDENCE_REQUIRED')
            prepared_recovery = self.monitoring.prepare(command.grant_id)
        content = hashlib.sha256(encode(command.model_dump(exclude={'idempotency_key'})).encode()).hexdigest()
        if not command.reason.strip(): raise HTTPException(422, 'LIFECYCLE_REASON_REQUIRED')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior = db.execute('SELECT fingerprint,value FROM capability_lifecycle_receipts WHERE key=?', (command.idempotency_key,)).fetchone()
            if prior:
                if prior[0] != content: raise HTTPException(409, 'LIFECYCLE_IDEMPOTENCY_CONFLICT')
                return json.loads(prior[1])
            current = self.lifecycle(db)
            if command.expected_version != current['version']: raise HTTPException(409, 'LIFECYCLE_VERSION_CONFLICT')
            if command.grant_id:
                if not db.execute('SELECT 1 FROM capability_grants WHERE id=?', (command.grant_id,)).fetchone():
                    raise HTTPException(404, '能力授权不存在')
            elif command.state == 'REVOKED': raise HTTPException(422, 'REVOKE_REQUIRES_GRANT_ID')
            affected = self.lifecycle(db, command.grant_id)
            if any(s['state'] in {'REVOKED', 'EXPIRED'} for s in affected['scopes'].values()):
                raise HTTPException(409, 'REVOKED_REQUIRES_SUCCESSOR_GRANT')
            if command.state == 'ACTIVE':
                paused = affected['scopes'][command.scope]
                if paused['state'] != 'SUSPENDED' or paused.get('event_id') != command.resume_event_id or paused['reason_code'] != command.reason_code:
                    raise HTTPException(409, 'RESUME_PAUSE_REASON_BINDING_MISMATCH')
                if paused['reason_code'] != 'USER_PAUSE':
                    if prepared_recovery is None or not command.recovery_check_id:
                        raise HTTPException(409, 'REASON_BOUND_RECOVERY_EVIDENCE_REQUIRED')
                    self.monitoring.verify_resume(command.recovery_check_id, prepared_recovery, paused, db)
                if command.grant_id:
                    original = json.loads(db.execute('SELECT value FROM capability_grants WHERE id=?', (command.grant_id,)).fetchone()[0])
                    reasons, _, _ = self._admit(GrantCommand(**original['command']), db, original.get('proof_id'))
                    if reasons: raise HTTPException(409, {'code': 'RESUME_CURRENT_CONDITIONS_RESTRICTED', 'reasons': reasons})
            at = now()
            value = {'event_id': str(uuid4()), 'event_type': 'CAPABILITY_SCOPE_CHANGED', 'scope': command.scope,
                     'grant_id': command.grant_id,
                     'state': command.state, 'version': current['version'] + 1, 'reason_code': command.reason_code,
                     'resume_event_id': command.resume_event_id,
                     'recovery_check_id': command.recovery_check_id,
                     'reason': command.reason.strip(), 'effective_at': at, 'recorded_at': at}
            db.execute('INSERT INTO capability_events VALUES(?,?)', (value['event_id'], encode(value)))
            self.journal.stage(value)
            if command.grant_id is None and command.scope == 'ALL_MONITOR' and command.state != 'ACTIVE' and self.observation_reviews:
                self.observation_reviews.restrict_observations(db, value)
            if self.actions: self.actions.current(db=db)
            db.execute('INSERT INTO capability_lifecycle_receipts VALUES(?,?,?)', (command.idempotency_key, content, encode(value)))
            self.ledger.crash_point('capability_lifecycle_before_commit')
            db.commit()
            self.ledger.crash_point('capability_lifecycle_after_commit')
        self.journal.reconcile_committed()
        return value

    def events(self):
        with self.ledger.connection() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT value FROM capability_events ORDER BY rowid')]

    def restrict(self, db, grant_id, scope, reason_code, reason, monitoring_check_id):
        """A verified consumer restricts within the current caller transaction."""
        current = self.lifecycle(db, grant_id)
        prior = current['scopes'][scope]
        if prior['state'] in {'REVOKED', 'EXPIRED'} or prior['state'] == 'SUSPENDED' and prior['reason_code'] == reason_code:
            return prior
        at = now()
        value = {'event_id': str(uuid4()), 'event_type': 'CAPABILITY_SCOPE_CHANGED', 'scope': scope,
            'grant_id': grant_id, 'state': 'SUSPENDED', 'version': self.lifecycle(db)['version'] + 1,
            'reason_code': reason_code, 'reason': reason, 'effective_at': at, 'recorded_at': at,
            'monitoring_check_id': monitoring_check_id}
        db.execute('INSERT INTO capability_events VALUES(?,?)', (value['event_id'], encode(value)))
        self.journal.stage(value)
        return value

    def observe_loss(self, db, loss, evaluation_id):
        if not loss or not loss.get('triggered'): return
        current = self.lifecycle(db)
        prior = current['scopes']['NEW_RISK']
        if prior['state'] == 'SUSPENDED' and prior['reason_code'] == 'LOSS_BOUNDARY': return
        at = now()
        value = {'event_id': str(uuid4()), 'event_type': 'CAPABILITY_SCOPE_CHANGED', 'scope': 'NEW_RISK',
            'grant_id': None, 'state': 'SUSPENDED', 'version': current['version'] + 1,
            'reason_code': 'LOSS_BOUNDARY', 'reason': '资金损失边界已触发；反弹、扩容或时钟推进不自动恢复',
            'effective_at': at, 'recorded_at': at, 'evaluation_id': evaluation_id,
            'loss_scope': {k:loss[k] for k in ['scope_kind','scope_id','origin_at','baseline_account_version']},
            'peak_loss': loss['peak_loss'], 'facts_version': loss['facts_version']}
        db.execute('INSERT INTO capability_events VALUES(?,?)', (value['event_id'], encode(value)))
        self.journal.stage(value)

    def grant(self, command):
        self.refresh_journal()
        fingerprint = hashlib.sha256(encode(command.model_dump(exclude={'idempotency_key'})).encode()).hexdigest()
        with self.ledger.connection() as db:
            prior = db.execute('SELECT fingerprint,status,value FROM capability_receipts WHERE key=?', (command.idempotency_key,)).fetchone()
        if prior:
            if prior[0] != fingerprint: raise HTTPException(409, {'code': 'IDEMPOTENCY_CONTENT_CONFLICT'})
            if prior[1] >= 400: raise HTTPException(prior[1], json.loads(prior[2]))
            return json.loads(prior[2])
        proof = self._prepare_proof(command)
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior = db.execute('SELECT fingerprint,status,value FROM capability_receipts WHERE key=?', (command.idempotency_key,)).fetchone()
            if prior:
                db.rollback()
                if prior[0] != fingerprint: raise HTTPException(409, {'code': 'IDEMPOTENCY_CONTENT_CONFLICT'})
                if prior[1] >= 400: raise HTTPException(prior[1], json.loads(prior[2]))
                return json.loads(prior[2])
            reasons, package, kind = self._admit(command, db, proof['proof_id'])
            if command.predecessor_grant_id:
                row = db.execute('SELECT value FROM capability_grants WHERE id=?', (command.predecessor_grant_id,)).fetchone()
                if not row:
                    reasons.append('SUCCESSOR_PREDECESSOR_NOT_FOUND')
                elif self.current(db, command.predecessor_grant_id)['state'] not in {'REVOKED', 'EXPIRED'}:
                    reasons.append('SUCCESSOR_PREDECESSOR_NOT_TERMINAL')
            if reasons:
                value = {'code': 'CAPABILITY_ADMISSION_REFUSED', 'reasons': reasons}
                status, event_type = 409, 'GRANT_REFUSED'
            else:
                value = {'grant_id': str(uuid4()), 'version': 1, 'recorded_at': now(), 'evidence_kind': kind, 'proof_id': proof['proof_id'],
                    'predecessor_grant_id': command.predecessor_grant_id,
                    'system_usable': kind != 'METHOD_ENGINEERING', 'candidate_kind': package['candidate_kind'],
                    'protocol_id': package['protocol_id'], 'complete_protocol_fingerprint': package.get('complete_protocol_fingerprint'),
                    'validation_id': package['validation_id'], 'material_id': command.material_id,
                    'review_run_id': command.review_run_id, 'material_fingerprint': command.expected_material_fingerprint,
                    'scope': command.scope, 'allowed_actions': command.allowed_actions, 'execution': package.get('execution'),
                    'deployment_fingerprints': command.deployment_fingerprints, 'dependency_fingerprints': source_inventory(),
                    'account_version': command.expected_account_version, 'funding_version': command.expected_funding_version,
                    'funding_scope': {k: package[k] for k in ['scope_id', 'scope_kind']},
                    'effective_at': command.effective_at, 'expires_at': command.expires_at,
                    'revocation_conditions': ['EXPIRY', 'DEPLOYMENT_CHANGE', 'ACCOUNT_VERSION_CHANGE', 'FUNDING_CHANGE', 'RECOVERY_LOCK', 'DATA_OR_SCOPE_CHANGE'],
                    'human_review_label': LABEL, 'command': command.model_dump()}
                status, event_type = 201, 'CAPABILITY_GRANTED'
                db.execute('INSERT INTO capability_grants VALUES(?,?)', (value['grant_id'], encode(value)))
            event = {'event_id': str(uuid4()), 'event_type': event_type, 'recorded_at': now(), 'material_id': command.material_id,
                     'review_run_id': command.review_run_id, 'evidence_kind': kind, **value}
            db.execute('INSERT INTO capability_events VALUES(?,?)', (event['event_id'], encode(event)))
            db.execute('INSERT INTO capability_receipts VALUES(?,?,?,?)', (command.idempotency_key, fingerprint, status, encode(value)))
            db.commit()
        if status >= 400: raise HTTPException(status, value)
        return value
