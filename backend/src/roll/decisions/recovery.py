"""Current authorization recovery; the physical legacy lock remains intact."""
import json
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from roll.accounts.ledger import encode, now
from roll.decisions.capabilities import GrantCommand, moment, source_inventory
from roll.decisions.lifecycle_journal import sha
from roll.runtime.backups import persist


class RecoveryCommand(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    proof_id: str
    expected_account_version: int = Field(ge=0)
    expected_funding_version: int = Field(ge=0)
    expected_journal_fingerprint: str
    basis: str = Field(min_length=1, max_length=2000)
    idempotency_key: str = Field(min_length=1, max_length=128)


class AuthorizationRecovery:
    def __init__(self, capabilities):
        self.capabilities = capabilities
        self.ledger = capabilities.ledger
        self.root = Path(self.ledger.path).parent / 'backups'
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS capability_recoveries(id TEXT PRIMARY KEY, key TEXT UNIQUE, fingerprint TEXT NOT NULL, value TEXT NOT NULL)')

    def physical(self):
        file = self.root / 'recovery-lock.json'
        return json.loads(file.read_text(encoding='utf-8')) if file.exists() else {'state': 'NOT_RESTORED'}

    def binding(self, db, proof_id):
        cap = self.capabilities
        journal = cap.journal.status()
        if journal['unknown'] or not journal['history_known']:
            raise HTTPException(409, 'LATEST_PERMISSION_HISTORY_UNVERIFIED')
        proof = cap._checked_proof(proof_id, db)
        command = GrantCommand(**proof['command'])
        reasons, package, kind = cap._admit(command, db, proof_id, recovery_check=True)
        if reasons: raise HTTPException(409, {'code': 'RECOVERY_CURRENT_CONDITIONS_RESTRICTED', 'reasons': reasons})
        lock = self.physical()
        if lock['state'] != 'RECOVERY_LOCK': raise HTTPException(409, 'RECOVERY_LOCK_REQUIRED')
        if lock.get('permission_journal_error'): raise HTTPException(409, 'LATEST_PERMISSION_HISTORY_UNVERIFIED')
        account = self.ledger.account(db=db)
        reconciliations = account.get('reconciliations', [])
        if not any(r.get('recorded_at') and moment(r['recorded_at']) > moment(lock['locked_at']) and
                   not r.get('unresolved') for r in reconciliations):
            raise HTTPException(409, 'CURRENT_BROKER_RECONCILIATION_REQUIRED')
        if moment(proof['finished_at']) <= moment(lock['locked_at']) or moment(command.required_as_of) < moment(lock['locked_at']):
            raise HTTPException(409, 'POST_RECOVERY_CURRENT_EVIDENCE_REQUIRED')
        return {'proof_id': proof_id, 'proof_archive_sha256': proof['archive']['sha256'],
            'account_version': account['version'], 'funding_version': cap.funding.current(db=db)['version'],
            'source_fingerprint': sha(source_inventory()), 'journal_fingerprint': journal['fingerprint'],
            'lifecycle_version': cap.lifecycle(db)['version'], 'lock_fingerprint': sha(lock),
            'scope': command.scope, 'deployment_fingerprints': command.deployment_fingerprints,
            'required_as_of': command.required_as_of, 'material_fingerprint': package['material_fingerprint'],
            'evidence_kind': kind}

    def status(self):
        physical = self.physical()
        journal = self.capabilities.journal.status()
        result = {**physical, 'journal_fingerprint': journal['fingerprint'],
            'permission_history_known': journal['history_known'], 'pending_permission_events': journal['unknown']}
        if physical['state'] != 'RECOVERY_LOCK': return result
        with self.ledger.connection() as db:
            rows = db.execute('SELECT value FROM capability_recoveries ORDER BY rowid DESC').fetchall()
            for row in rows:
                receipt = json.loads(row[0])
                try:
                    file = self.root / 'authorization-recovery' / (receipt['recovery_id'] + '.json')
                    if json.loads(file.read_text(encoding='utf-8')) != receipt: continue
                    if self.binding(db, receipt['binding']['proof_id']) != receipt['binding']: continue
                    return {**result, 'state': 'RECOVERED_VERIFIED', 'receipt': receipt,
                        'formal_actions_allowed': receipt['system_usable'], 'old_active_records': 'HISTORY_ONLY'}
                except (HTTPException, OSError, ValueError, KeyError): continue
        return {**result, 'recovery_conditions': '须当前部署、完整验证与CODEX审阅材料、资金与范围、恢复后券商核对及可核最新权限日志；旧动作不可复活'}

    def check(self, command):
        self.capabilities.refresh_journal()
        content = sha(command.model_dump(exclude={'idempotency_key'}))
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute('SELECT fingerprint,value FROM capability_recoveries WHERE key=?', (command.idempotency_key,)).fetchone()
            if previous:
                if previous[0] != content: raise HTTPException(409, 'RECOVERY_IDEMPOTENCY_CONFLICT')
                return json.loads(previous[1])
            binding = self.binding(db, command.proof_id)
            if (binding['account_version'], binding['funding_version'], binding['journal_fingerprint']) != (
                    command.expected_account_version, command.expected_funding_version, command.expected_journal_fingerprint):
                raise HTTPException(409, 'RECOVERY_VERSION_CONFLICT')
            # Before recording recovery, invalidate old cards under the still
            # physical lock. Recovery never supplies a new evaluation or grant.
            self.capabilities.actions.current(db=db)
            receipt = {'recovery_id': str(uuid4()), 'state': 'RECOVERED_VERIFIED', 'recorded_at': now(),
                'system_usable': binding['evidence_kind'] != 'METHOD_ENGINEERING',
                'binding': binding, 'basis': command.basis.strip(), 'old_active_records': 'HISTORY_ONLY'}
            persist(self.root / 'authorization-recovery' / (receipt['recovery_id'] + '.json'), encode(receipt).encode())
            db.execute('INSERT INTO capability_recoveries VALUES(?,?,?,?)',
                (receipt['recovery_id'], command.idempotency_key, content, encode(receipt)))
            db.commit()
        return receipt
