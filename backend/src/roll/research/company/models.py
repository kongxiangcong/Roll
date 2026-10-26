from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Command(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class ListingInput(Command):
    exchange: Literal['SSE', 'SZSE', 'BSE', 'HKEX']
    code: str = Field(min_length=5, max_length=6, pattern=r'^\d+$')
    share_class: Literal['A', 'H', 'ORDINARY']
    currency: Literal['CNY', 'HKD']
    valid_from: str | None = None


class CompanyCommand(Command):
    company_id: str | None = None
    legal_name: str = Field(min_length=1, max_length=160)
    aliases: list[str] = Field(default_factory=list, max_length=30)
    jurisdiction: str = Field(min_length=1, max_length=80)
    accounting_standard: str | None = Field(default=None, max_length=80)
    year_end: str | None = Field(default=None, pattern=r'^\d{2}-\d{2}$')
    industry: str = Field(min_length=1, max_length=80)
    identity_basis: str = Field(min_length=1, max_length=2000)
    listings: list[ListingInput] = Field(min_length=1, max_length=20)
    change_reason: str = Field(default='Initial registration', min_length=1, max_length=2000)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)


class MaterialCommand(Command):
    company_id: str = Field(min_length=1, max_length=128)
    source_id: str = Field(min_length=1, max_length=160)
    origin_root_id: str = Field(min_length=1, max_length=300)
    source_url: str = Field(min_length=1, max_length=2000)
    subject_name: str = Field(min_length=1, max_length=160)
    media_type: Literal['text/plain', 'application/pdf', 'application/json', 'application/octet-stream']
    disclosed_at: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    unit: str | None = Field(default=None, max_length=80)
    currency: str | None = Field(default=None, max_length=10)
    scope: str | None = Field(default=None, max_length=300)
    page: str | None = Field(default=None, max_length=80)
    table: str | None = Field(default=None, max_length=160)
    license_note: str = Field(default='Source rights not established; private research use', max_length=1000)
    limitations: list[str] = Field(default_factory=list, max_length=30)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)


class FactCommand(Command):
    company_id: str = Field(min_length=1, max_length=128)
    material_id: str = Field(min_length=1, max_length=128)
    metric: str = Field(min_length=1, max_length=160)
    business: str = Field(min_length=1, max_length=160)
    value: str | None = Field(max_length=4000)
    value_type: Literal['NUMBER', 'TEXT'] = 'NUMBER'
    unit: str | None = Field(default=None, max_length=80)
    currency: str | None = Field(default=None, max_length=10)
    scope: str | None = Field(default=None, max_length=300)
    period_start: str
    period_end: str
    page: str | None = Field(default=None, max_length=80)
    table: str | None = Field(default=None, max_length=160)
    kind: Literal['DISCLOSED', 'DERIVED', 'ASSUMED'] = 'DISCLOSED'
    derivation: str | None = Field(default=None, max_length=2000)
    supersedes: str | None = None
    change_reason: str = Field(min_length=1, max_length=2000)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)


class ConflictResolution(Command):
    company_id: str
    fact_id: str
    version_ids: list[str] = Field(min_length=2, max_length=100)
    selected_version_id: str | None
    reason: str = Field(min_length=1, max_length=2000)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)


class CheckCommand(Command):
    company_id: str
    source_id: str = Field(min_length=1, max_length=160)
    requested_scopes: list[str] = Field(min_length=1, max_length=8)
    idempotency_key: str = Field(min_length=1, max_length=128)


class ExistingSourceCommand(Command):
    company_id: str
    source_type: Literal['FINANCIAL_FACT', 'NEWS_FACT', 'MARKET_SNAPSHOT']
    record_id: str = Field(min_length=1, max_length=128)
    fact_index: int = Field(default=0, ge=0, le=1000)
