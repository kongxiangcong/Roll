"""Source-bound retrospective cash rights for one fresh domestic individual study lot.

No complete action/status coverage or account receipt is inferred from this inventory.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
from pathlib import Path
from typing import Literal
import json

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

REFERENCE = Path(__file__).parent / 'reference' / 'cash-rights'
MANIFEST_SHA256 = '721b2c153ea08354bdc9a0fdd71069703190777488f69186a49b853ad4414680'


class CashRightsCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    instrument: str
    entry_date: date
    exit_date: date
    quantity: StrictInt = Field(gt=0)
    consumer_cutoff: datetime
    lot_scenario: Literal['FRESH_DOMESTIC_INDIVIDUAL_NEXT_OPEN'] = 'FRESH_DOMESTIC_INDIVIDUAL_NEXT_OPEN'

    @model_validator(mode='after')
    def timeline(self):
        if self.entry_date >= self.exit_date:
            raise ValueError('Exit must follow entry for the fresh single-lot study')
        if self.consumer_cutoff.utcoffset() is None:
            raise ValueError('Consumer cutoff requires timezone')
        if self.consumer_cutoff.astimezone(timezone(timedelta(hours=8))).date() < self.exit_date:
            raise ValueError('Retrospective calculation cannot precede disposal')
        return self


def cash_rights_manifest():
    try:
        raw = (REFERENCE / 'sources.json').read_bytes()
    except OSError:
        raise HTTPException(409, {'code': 'CASH_RIGHTS_SOURCE_INTEGRITY_FAILED'}) from None
    if sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise HTTPException(409, {'code': 'CASH_RIGHTS_SOURCE_INTEGRITY_FAILED'})
    manifest = json.loads(raw)
    for source in [e['source'] for e in manifest['events']] + manifest['tax_sources']:
        try:
            raw = (REFERENCE / source['file']).read_bytes()
        except OSError:
            raise HTTPException(409, {'code': 'CASH_RIGHTS_SOURCE_INTEGRITY_FAILED'}) from None
        if len(raw) != source['bytes'] or sha256(raw).hexdigest() != source['sha256']:
            raise HTTPException(409, {'code': 'CASH_RIGHTS_SOURCE_INTEGRITY_FAILED'})
    return manifest


def _holding_tax(entry, exit, new_regime):
    # Official2012 Q&A: natural month/year, acquisition through disposal's prior day.
    # Unspecified nonexistent anniversaries (Jan31/Feb29) are never silently clamped.
    try:
        year = entry.replace(year=entry.year + 1)
        month = entry.replace(year=entry.year + (entry.month == 12), month=entry.month % 12 + 1)
    except ValueError:
        return None
    if exit <= month:
        return Decimal('0.20')
    if exit <= year:
        return Decimal('0.10')
    return Decimal('0') if new_regime else Decimal('0.05')


def _money(value):
    return str(value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def assess_cash_rights(command: CashRightsCommand):
    manifest = cash_rights_manifest()
    blockers = ['COMPLETE_CORPORATE_ACTION_COVERAGE_NOT_ESTABLISHED']
    if command.instrument != manifest['instrument']:
        return {'instrument': command.instrument, 'coverage': 'UNKNOWN', 'scorable': False,
                'events': [], 'blockers': ['INSTRUMENT_OUTSIDE_CASH_RIGHTS_REFERENCE'], 'account_authority': 'NONE'}
    results = []
    for event in manifest['events']:
        record = date.fromisoformat(event['record_date'])
        # NEXT_OPEN entry participates at record close; NEXT_OPEN record-date exit does not.
        if not (command.entry_date <= record < command.exit_date):
            continue
        source = event['source']
        if datetime.fromisoformat(source['received_at']) > command.consumer_cutoff:
            blockers.append('SOURCE_NOT_RECEIVED_AT_CONSUMER_CUTOFF')
            continue
        if any(datetime.fromisoformat(s['received_at']) > command.consumer_cutoff for s in manifest['tax_sources']):
            blockers.append('TAX_SOURCE_NOT_RECEIVED_AT_CONSUMER_CUTOFF')
            continue
        #101: record dates after2015-09-08; earlier registration retains the old regime.
        new_regime = record > date(2015, 9, 8)
        rate = _holding_tax(command.entry_date, command.exit_date, new_regime)
        gross = Decimal(event['gross_cash_yuan_per_eligible_share']) * command.quantity
        initial = (gross * Decimal(event['tax_withholding_at_payment_pct']) / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        payment = date.fromisoformat(event['cash_payment_date'])
        item = dict(event)
        item.pop('extracted_pages', None)
        item.update(quantity=command.quantity, gross_entitlement_yuan=_money(gross),
                    holding_period_basis='ACQUISITION_THROUGH_DAY_BEFORE_DISPOSAL_NATURAL_MONTH_YEAR',
                    historical_prediction_admissibility='NOT_ESTABLISHED',
                    tax_regime='2015_101' if new_regime else '2012_85',
                    payment_date_precision='DATE', cash_payment_at_exit_open='INTRADAY_UNKNOWN' if payment == command.exit_date else None,
                    initial_payment_withholding_yuan=_money(initial),
                    known_event_treatment='CALCULATED' if rate is not None else 'UNSCORABLE',
                    cash_receipt_for_user_account='NOT_ESTABLISHED')
        if rate is None:
            blockers.append('TAX_CALENDAR_ANNIVERSARY_UNDEFINED')
            item.update(final_tax_rate=None, final_tax_yuan=None, net_entitlement_yuan=None,
                        cash_paid_by_exit_yuan=None, net_receivable_at_exit_yuan=None)
        else:
            tax = (gross * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            net = gross - tax
            # Calendar-date payment is not proof of spendable cash at that day's open.
            paid = payment < command.exit_date
            item.update(final_tax_rate=str(rate), final_tax_yuan=_money(tax),
                        net_entitlement_yuan=_money(net), supplementary_tax_liability_yuan=_money(tax - initial),
                        cash_paid_by_exit_yuan=_money(gross - initial) if paid else '0.00',
                        net_receivable_at_exit_yuan='0.00' if paid else _money(net),
                        tax_collection_clock='NOT_ESTABLISHED', net_economic_entitlement_yuan=_money(net))
        results.append(item)
    return {'instrument': command.instrument, 'lot_scenario': command.lot_scenario,
            'entry_date': command.entry_date.isoformat(), 'exit_date': command.exit_date.isoformat(),
            'consumer_cutoff': command.consumer_cutoff.isoformat(),
            'purpose': 'RETROSPECTIVE_KNOWN_CASH_RIGHTS_TREATMENT',
            'rounding_scenario': 'PER_LOT_FEN_HALF_UP_NOT_ACTUAL_BROKER_SETTLEMENT',
            'events': results, 'coverage': 'INCOMPLETE', 'scorable': False,
            'blockers': sorted(set(blockers)), 'account_authority': 'NONE',
            'source_manifest_sha256': MANIFEST_SHA256,
            'tax_sources': manifest['tax_sources'],
            'code_sha256': sha256(Path(__file__).read_bytes()).hexdigest()}
