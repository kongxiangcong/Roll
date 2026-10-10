"""Conservative cleaning of already acquired CNEquity rows. Rejections keep raw evidence."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from roll.market.rules import SHANGHAI


def numeric(value, *, positive=False):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite() or number < 0 or (positive and number == 0):
        return None
    return format(number, 'f')


def clean_rows(rows, source, instrument, archives, received_at, start, end, calendar):
    facts, quarantine, seen = [], [], {}
    symbol = instrument.split(':')[1]+('.SH' if instrument.startswith('SSE:') else '.SZ')
    group = source['group']
    raw_hashes = [a['sha256'] for a in archives]
    for ordinal, row in enumerate(rows):
        errors = []
        if row.get('symbol') != symbol:
            errors.append('SOURCE_OBJECT_MISMATCH')
        day = str(row.get('trade_date') or row.get('ex_date') or row.get('announce_date') or '')[:10]
        try:
            parsed_day = date.fromisoformat(day)
            if not start <= day <= end:
                errors.append('OUTSIDE_REQUEST_WINDOW')
        except ValueError:
            parsed_day = None
            errors.append('INVALID_EVENT_DATE')
        fact = {'instrument': instrument, 'group': group, 'source_id': source['id'],
                'upstream_source': source['upstream'], 'source_adapter': 'CNEQUITY',
                'source_commit': source['commit'], 'source_policy_revision': source['revision'],
                'trade_date': day, 'time_precision': 'DATE', 'raw_hash': raw_hashes[0] if raw_hashes else None,
                'basis_raw_hashes': raw_hashes, 'revision_id': raw_hashes[0] if raw_hashes else None,
                'source_url': next((a.get('source_url') for a in archives if a.get('source_url')), None),
                'received_at': received_at, 'available_at': received_at, 'published_at': None,
                'available_basis': 'FIRST_ACTUAL_HOST_RECEIPT', 'cleaning_version': source['cleaning_version'],
                'historical_pit_claim': False, 'historical_limitations': ['CURRENT_ACQUISITION_NOT_OLD_PIT'],
                'source_row': row, 'errors': errors, 'limitations': [], 'model_daily_input_allowed': False}
        if not raw_hashes:
            errors.append('SOURCE_ARCHIVE_MISSING')
        if group == 'DAILY':
            values = {k: numeric(row.get(k), positive=True) for k in ('open', 'high', 'low', 'close')}
            volume, amount = numeric(row.get('volume')), numeric(row.get('amount'))
            fact.update(**values, volume_shares=volume, amount_yuan=amount, volume_reported=volume,
                        volume_unit='SHARE', source_volume_unit='SHARE', adjustment='RAW',
                        conversion_basis='CNEquity adapter output in SHARE; upstream lot conversion retained in pinned code',
                        volume_state='ZERO_REPORTED' if volume == '0' else 'REPORTED',
                        completion_state='COMPLETE_REPORTED_HISTORICAL')
            if any(v is None for v in values.values()) or volume is None or amount is None:
                errors.append('MISSING_OR_INVALID_OHLCVA')
            else:
                o, h, l, c = [Decimal(values[k]) for k in ('open', 'high', 'low', 'close')]
                v, a = Decimal(volume), Decimal(amount)
                if not l <= min(o, c) <= max(o, c) <= h:
                    errors.append('INVALID_OHLC_RANGE')
                if v != v.to_integral_value():
                    errors.append('NON_INTEGER_SHARE_VOLUME')
                if v <= 0 or a <= 0:
                    errors.append('ZERO_TURNOVER_NOT_TRADING_PROOF')
                elif not l-Decimal('.02') <= a/v <= h+Decimal('.02'):
                    errors.append('UNIT_AMOUNT_OHLC_MISMATCH')
            current = datetime.fromisoformat(received_at).astimezone(SHANGHAI)
            if parsed_day == current.date():
                fact['completion_state'] = 'UNCONFIRMED_CURRENT_DAY'
                fact['limitations'].append('CURRENT_DAY_COMPLETENESS_NOT_VERIFIED')
            fact['model_daily_input_allowed'] = not errors and not fact['limitations']
        elif group == 'STATUS':
            # A current board snapshot cannot create earlier daily status, weekend trading,
            # listing-stage, ex-rights, or exchange-specific ST subtype evidence.
            if parsed_day != datetime.fromisoformat(received_at).astimezone(SHANGHAI).date() or calendar['is_trading_day'] is not True:
                errors.append('CURRENT_STATUS_DATE_NOT_VERIFIED_SESSION')
            if row.get('status') not in {'normal', 'suspended'} or not isinstance(row.get('is_trading'), bool):
                errors.append('INVALID_TRADING_STATUS')
            if row.get('risk_warning') is not None and not isinstance(row['risk_warning'], bool):
                errors.append('INVALID_RISK_WARNING')
            if row.get('is_trading') != (row.get('status') == 'normal'):
                errors.append('INCONSISTENT_TRADING_STATUS')
            fact.update(state='SUSPENDED' if row.get('status') == 'suspended' else 'NORMAL',
                        is_trading=row.get('is_trading'), suspension=row.get('status') == 'suspended',
                        risk_warning=row.get('risk_warning'), st_subtype=None, listing_stage=None, ex_rights=None)
            fact['limitations'] = ['LISTING_STAGE_AND_EX_RIGHTS_UNKNOWN', 'ST_SUBTYPE_UNKNOWN',
                                   'CURRENT_BOARD_SNAPSHOT_NOT_EXCHANGE_STATUS_CERTIFICATE']
        elif group == 'ADJUSTMENTS':
            action = row.get('action_type')
            if action not in {'cash_dividend', 'bonus', 'transfer', 'allotment', 'unit_split'}:
                errors.append('UNKNOWN_ACTION_TYPE')
            fields = ('cash_dividend', 'bonus_ratio', 'transfer_ratio', 'allotment_ratio', 'allotment_price', 'split_factor')
            for field in fields:
                value = numeric(row.get(field))
                if row.get(field) is not None and value is None:
                    errors.append('INVALID_'+field.upper())
                fact[field] = value
            required = {'cash_dividend': 'cash_dividend', 'bonus': 'bonus_ratio', 'transfer': 'transfer_ratio',
                        'allotment': 'allotment_ratio', 'unit_split': 'split_factor'}.get(action)
            if required and (fact.get(required) is None or Decimal(fact[required]) <= 0):
                errors.append('MISSING_ACTION_QUANTITY')
            fact.update(action_type=action, ex_date=day, event_identity=f'{symbol}:{day}:{action}',
                        payment_date=row.get('payment_date'), registration_date=None, account_receipt=None)
            fact['limitations'] = ['RIGHTS_LIFECYCLE_AND_TAX_NOT_COMPLETE', 'NO_ACCOUNT_LEDGER_AUTHORITY']
        elif group == 'ANNOUNCEMENTS':
            identifier = str(row.get('announcement_id') or row.get('id') or '')
            if not identifier or not row.get('title'):
                errors.append('MISSING_ANNOUNCEMENT_ID_OR_TITLE')
            fact.update(event_identity=f'{symbol}:{identifier}', title=row.get('title'),
                        disclosure_date=day, document_url=row.get('url'), document_hash=None)
            fact['limitations'] = ['ANNOUNCEMENT_INDEX_ONLY_ORIGINAL_NOT_ACQUIRED']
        key = (day, fact.get('event_identity'))
        if key in seen:
            # Identical rows may be deduplicated; conflicting duplicates are all quarantined.
            if row == seen[key]['source_row']:
                continue
            errors.append('CONFLICTING_DUPLICATE_KEY')
            if seen[key] in facts:
                facts.remove(seen[key])
                quarantine.append({'source_row': seen[key]['source_row'], 'errors': ['CONFLICTING_DUPLICATE_KEY']})
        seen[key] = fact
        fact['quality'] = 'INVALID' if errors else 'BASIC_CHECKED_SINGLE_SOURCE'
        if errors:
            quarantine.append({'ordinal': ordinal, 'source_row': row, 'errors': errors})
        else:
            facts.append(fact)
    return facts, quarantine
