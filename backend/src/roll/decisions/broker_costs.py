"""Confirmed broker tariff facts; never a qualification or action validity policy."""
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from fastapi import HTTPException
from roll.accounts.ledger import encode, now, timestamp
from roll.research.execution import fees


VALIDITY_GAP = 'PRODUCTION_ACTION_VALIDITY_POLICY_NOT_FROZEN'


class BrokerCostConfirmation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=0)
    expected_account_version: int = Field(ge=1)
    expected_funding_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=128)
    market: Literal['SSE']
    board: Literal['MAIN']
    instrument_type: Literal['STOCK']
    effective_from: str
    effective_until: str
    commission_including_regulatory_rate: str
    minimum_commission_yuan: str
    transfer_each_side_rate: str
    source_name: str = Field(min_length=1, max_length=200)
    source_text: str = Field(min_length=1, max_length=20000)
    confirmed: Literal[True]

    @field_validator('effective_from', 'effective_until')
    @classmethod
    def instant(cls, value):
        try: parsed = datetime.fromisoformat(value)
        except ValueError: raise ValueError('适用区间需要ISO时间') from None
        if parsed.tzinfo is None: raise ValueError('适用区间需要时区')
        return parsed.astimezone(timezone.utc).isoformat()

    @field_validator('commission_including_regulatory_rate', 'transfer_each_side_rate', 'minimum_commission_yuan')
    @classmethod
    def amount(cls, value, info):
        try: number = Decimal(value)
        except InvalidOperation: raise ValueError('需要精确十进制字符串') from None
        maximum = Decimal('1000000') if info.field_name == 'minimum_commission_yuan' else Decimal('1')
        if not number.is_finite() or not 0 <= number <= maximum or number.as_tuple().exponent < (-2 if info.field_name == 'minimum_commission_yuan' else -10):
            raise ValueError('费用值超出可登记范围或精度')
        return value

    @model_validator(mode='after')
    def interval(self):
        if datetime.fromisoformat(self.effective_from) >= datetime.fromisoformat(self.effective_until):
            raise ValueError('费用适用区间必须为正')
        return self


class BrokerCostEstimate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    instrument: str = Field(min_length=1, max_length=40)
    price_upper_yuan: str
    quantity: str
    required_as_of: str

    @field_validator('required_as_of')
    @classmethod
    def instant(cls, value): return timestamp(value)

    @field_validator('price_upper_yuan', 'quantity')
    @classmethod
    def positive(cls, value, info):
        try: number = Decimal(value)
        except InvalidOperation: raise ValueError('需要正十进制字符串') from None
        if not number.is_finite() or not 0 < number <= 1000000 or number.as_tuple().exponent < -8:
            raise ValueError('价格或数量超出范围')
        if info.field_name == 'quantity' and number != number.to_integral_value(): raise ValueError('数量必须为整数股')
        return value


class BrokerCosts:
    def __init__(self, ledger, funding, evidence):
        self.ledger, self.funding, self.evidence = ledger, funding, evidence
        with ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS broker_cost_versions(version INTEGER PRIMARY KEY, idempotency_key TEXT UNIQUE, value TEXT NOT NULL)')

    def listing(self, db=None):
        if db is None:
            with self.ledger.connection() as connection: return self.listing(connection)
        records = [json.loads(r[0]) for r in db.execute('SELECT value FROM broker_cost_versions ORDER BY version')]
        reasons = []
        if records:
            command = records[-1]['command']
            account, funding = self.ledger.account(db=db), self.funding.current(db=db)
            if (command['expected_account_version'], command['expected_funding_version']) != (account['version'], funding['version']):
                reasons.append('BROKER_COST_ACCOUNT_OR_FUNDING_VERSION_CHANGED')
            if not datetime.fromisoformat(command['effective_from']) <= datetime.fromisoformat(now()) < datetime.fromisoformat(command['effective_until']):
                reasons.append('BROKER_COST_OUTSIDE_EFFECTIVE_INTERVAL')
            try: self.evidence.raw(records[-1]['source_archive']['sha256'])
            except (HTTPException, RuntimeError, OSError): reasons.append('BROKER_COST_SOURCE_UNAVAILABLE_OR_CORRUPT')
        return {'version': records[-1]['version'] if records else 0, 'current': records[-1] if records else None,
                'versions': records, 'current_status': 'NOT_REGISTERED' if not records else 'RESTRICTED' if reasons else 'CONFIRMED_COST_FACTS_ONLY',
                'current_reasons': reasons, 'limitations': [VALIDITY_GAP]}

    def get(self, version):
        with self.ledger.connection() as db:
            row = db.execute('SELECT value FROM broker_cost_versions WHERE version=?', (version,)).fetchone()
        if row is None: raise HTTPException(404, 'BROKER_COST_VERSION_NOT_FOUND')
        return json.loads(row[0])

    def confirm(self, command):
        value = command.model_dump()
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT value FROM broker_cost_versions WHERE idempotency_key=?', (command.idempotency_key,)).fetchone()
            if existing:
                record = json.loads(existing[0])
                if record['command'] != value: raise HTTPException(409, 'BROKER_COST_IDEMPOTENCY_CONFLICT')
                return record
            current = self.listing(db)
            account, funding = self.ledger.account(db=db), self.funding.current(db=db)
            if current['version'] != command.expected_version: raise HTTPException(409, 'BROKER_COST_VERSION_CONFLICT')
            if account['version'] != command.expected_account_version or funding['version'] != command.expected_funding_version or funding['state'] != 'CONFIRMED':
                raise HTTPException(409, 'BROKER_COST_ACCOUNT_OR_FUNDING_VERSION_CONFLICT')
            archive = self.evidence.archive(command.source_text.encode('utf-8'), 'CONFIRMED_BROKER_COST_BASIS', db=db, source_name=command.source_name)
            record = {'version': current['version'] + 1, 'command': value, 'confirmed_at': now(), 'source_archive': archive,
                      'contract_fingerprint': hashlib.sha256(encode(value).encode()).hexdigest(),
                      'system_usable': False, 'authority': 'USER_CONFIRMED_COST_FACT_NOT_CAPABILITY_GRANT'}
            db.execute('INSERT INTO broker_cost_versions VALUES(?,?,?)', (record['version'], command.idempotency_key, encode(record)))
            db.commit()
            return record

    def estimate(self, state, account, funding, identity, price_upper_yuan, quantity, required_as_of, checked_at):
        record = state['current']
        result = {'fees_yuan': None, 'cost_binding': None, 'limitations': []}
        if record is None: return {**result, 'limitations': ['ACTUAL_BROKER_COST_NOT_CONFIRMED']}
        command = record['command']
        if (command['expected_account_version'], command['expected_funding_version']) != (account['version'], funding['version']):
            result['limitations'].append('BROKER_COST_ACCOUNT_OR_FUNDING_VERSION_CHANGED')
        if any(identity.get(k) != command[v] for k, v in [('exchange', 'market'), ('board', 'board'), ('instrument_type', 'instrument_type')]):
            result['limitations'].append('BROKER_COST_SCOPE_MISMATCH')
        start, end = datetime.fromisoformat(command['effective_from']), datetime.fromisoformat(command['effective_until'])
        if not all(start <= datetime.fromisoformat(t) < end for t in [required_as_of, checked_at]):
            result['limitations'].append('BROKER_COST_OUTSIDE_EFFECTIVE_INTERVAL')
        # Verify the original bytes on every consumer path, including replay capture.
        try: raw = self.evidence.raw(record['source_archive']['sha256']).read_bytes()
        except (HTTPException, RuntimeError, OSError): raw = None
        if raw is None or hashlib.sha256(raw).hexdigest() != record['source_archive']['sha256']:
            result['limitations'].append('BROKER_COST_SOURCE_UNAVAILABLE_OR_CORRUPT')
        if price_upper_yuan is None: result['limitations'].append('BROKER_COST_PRICE_UNKNOWN')
        if result['limitations']: return result
        gross = Decimal(price_upper_yuan) * Decimal(quantity)
        costs = {'commission_scenario_rate': command['commission_including_regulatory_rate'],
                 'minimum_commission_yuan': command['minimum_commission_yuan'],
                 'transfer_each_side_rate': command['transfer_each_side_rate'], 'stamp_sell_rate': '0', 'extra_regulatory_charge': '0'}
        result.update(fees_yuan=fees(gross, costs, 'BUY')['total_yuan'],
            cost_binding={'version': record['version'], 'contract_fingerprint': record['contract_fingerprint'],
                          'source_sha256': record['source_archive']['sha256'], 'fee_basis': 'CONFIRMED_BUY_TARIFF_AT_UPPER_PRICE',
                          'effective_until': command['effective_until']})
        return result

    def preview(self, command):
        with self.ledger.connection() as db:
            state, account, funding = self.listing(db), self.ledger.account(db=db), self.funding.current(db=db)
        listing = self.evidence.market.listing()
        member = next((v for v in listing['members'] if v['instrument'] == command.instrument), {})
        result = self.estimate(state, account, funding, member.get('identity') or {}, command.price_upper_yuan,
                               command.quantity, command.required_as_of, now())
        return {**result, 'system_usable': False, 'limitations': [*result['limitations'], VALIDITY_GAP]}
