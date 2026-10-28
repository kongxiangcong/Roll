"""Deterministic diagnostic company calculator, with no authority to self-review."""
import copy
import json
import math
from datetime import date, datetime, time, timezone, timedelta

from .valuation_reference import fundamental_valuation as algorithm

SHANGHAI = timezone(timedelta(hours=8))


class CalculationError(ValueError):
    def __init__(self, code, reason):
        self.code, self.reason = code, reason
        super().__init__(reason)


def reject(code, reason):
    raise CalculationError(code, reason)


def valuation_cutoff(value):
    if len(value) == 10:
        return datetime.combine(date.fromisoformat(value), time.max, tzinfo=SHANGHAI)
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        raise ValueError('as_of timestamp requires timezone')
    return stamp


def market_equity(reverse, company, meta, shares):
    """Every listed share class has an independent dated share/price/FX basis."""
    listings = {i['listing_id']: i for i in company['listings']}
    basis = reverse.get('market_basis')
    if not isinstance(basis, list) or not basis or len(basis) != len(listings):
        reject('AH_BASIS_INCOMPLETE', 'Every frozen listing needs its own share count and same-day price/FX')
    if {'price', 'market_equity_value'} & set(reverse):
        reject('AH_BASIS_INCOMPLETE', 'Combined values and single price shortcuts are not accepted')
    seen, dates, total, total_shares, components = set(), set(), 0, 0, []
    try:
        cutoff = valuation_cutoff(meta['as_of'])
        for row in basis:
            lid = row['listing_id']
            if lid not in listings or lid in seen:
                raise ValueError('missing, duplicate or foreign listing')
            seen.add(lid)
            listing = listings[lid]
            stamp = datetime.fromisoformat(row['priced_at'])
            if stamp.tzinfo is None:
                raise ValueError('price must have timezone')
            if stamp > cutoff:
                raise ValueError('price is later than frozen valuation cutoff')
            day = stamp.astimezone(SHANGHAI).date().isoformat()
            dates.add(day)
            if row['shares_as_of'] != day or day > cutoff.astimezone(SHANGHAI).date().isoformat():
                raise ValueError('share count must be dated with the price and no later than valuation')
            if row['shares_unit'] != meta['shares_unit'] or row['currency'] != listing['currency']:
                raise ValueError('share units or listing currency mismatch')
            if not row['share_refs'] or not row['price_refs']:
                raise ValueError('share and price references required')
            count = algorithm.number(row['shares'], 'class shares', 0, True)
            price = algorithm.number(row['price'], 'class price', 0, True)
            fx = row.get('fx')
            rate = 1
            if row['currency'] != meta['currency'] or fx is not None:
                if not fx or fx['from_currency'] != row['currency'] or fx['to_currency'] != meta['currency'] or fx['as_of'] != day or not fx['source_refs']:
                    raise ValueError('same-day direct FX and provenance required')
                rate = algorithm.number(fx['rate'], 'fx', 0, True)
                if row['currency'] == meta['currency'] and rate != 1:
                    raise ValueError('same-currency conversion must be exactly one')
            value = count * price * rate
            components.append({**copy.deepcopy(row), 'fx_to_model': rate, 'market_equity_value': value,
                               'formula': 'class_shares * class_price * fx_to_model'})
            total += value
            total_shares += count
        if seen != set(listings) or len(dates) != 1 or not math.isclose(total_shares, shares, rel_tol=1e-9):
            raise ValueError('listing coverage, dates or total share count mismatch')
        algorithm.number(total, 'combined market equity', 0, True)
    except (KeyError, ValueError, TypeError) as exc:
        reject('AH_BASIS_INCOMPLETE', str(exc))
    return total, components


def perpetuity(normalized_fcff, discount_rate):
    """Separate closed form (no finite forecast years or terminal splice)."""
    value = algorithm.number(normalized_fcff, 'normalized_fcff', 0, True) / algorithm.number(discount_rate, 'discount_rate', 0, True)
    return algorithm.number(value, 'perpetuity value')


def calculate(config, company):
    cfg = copy.deepcopy(config)
    if company['industry'].upper() in {'BANK', 'BANKING', 'INSURANCE', 'FINANCIAL', '银行', '保险'}:
        return {'applicability': 'NOT_APPLICABLE', 'reason': 'FCFF/WACC executor does not apply to financial companies',
                'review': {'status': 'unreviewed', 'limitations': ['Use a separately supported financial-company method']},
                'usable_range': False, 'scenarios': []}
    scenarios = cfg.get('scenarios', [])
    if not isinstance(scenarios, list) or not 1 <= len(scenarios) <= 10:
        reject('VALUATION_INPUT_TOO_LARGE', 'Use one to ten full-path scenarios')
    if any(len(algorithm.cashflows(sc)) > 50 for sc in scenarios):
        reject('VALUATION_INPUT_TOO_LARGE', 'Annual forecast horizon is bounded to fifty years')
    seen = set()
    components = set()
    original_bridge = copy.deepcopy(cfg.get('equity_bridge'))
    for row in cfg.get('equity_bridge', []):
        name = row['name'].strip().casefold()
        if name in seen:
            reject('DUPLICATE_BRIDGE_COMPONENT', 'The same bridge component must not be counted twice')
        seen.add(name)
        component = row.pop('component_id', name)
        if not isinstance(component, str) or not component.strip() or component.strip().casefold() in components:
            reject('DUPLICATE_BRIDGE_COMPONENT', 'Bridge component IDs must be unique')
        components.add(component.strip().casefold())
        amount = algorithm.number(row['amount'], 'bridge amount')
        if row['treatment'] not in {'deduct', 'add', 'excluded'} or (row['treatment'] == 'deduct' and amount < 0) or (row['treatment'] == 'add' and amount > 0) or (row['treatment'] == 'excluded' and amount != 0):
            reject('BRIDGE_SIGN_INVALID', 'Bridge deductions are positive, additions negative, exclusions zero')
    if cfg.get('review', {}).get('status', 'unreviewed') != 'unreviewed':
        reject('ECONOMIC_REVIEW_BLOCKED', 'Caller cannot set economic review status')
    cfg['review'] = {'status': 'unreviewed', 'limitations': [
        'Diagnostic only: operating drivers and economic suitability require controlled review']}
    reverse = cfg.pop('reverse', None)
    epv = cfg.pop('epv', None)
    sensitivity = cfg.pop('sensitivity', None)
    cfg['metadata']['listing_structure'] = '+'.join(sorted({i['share_class'] for i in company['listings']}))
    result = algorithm.run(cfg)
    if original_bridge is not None:
        result['equity_bridge'] = original_bridge
    result['usable_range'] = False
    result['applicability'] = 'CONDITIONAL'
    if sensitivity is not None:
        result['sensitivity'] = []
        try:
            if set(sensitivity) != {'scenario', 'wacc', 'terminal_g'}:
                raise ValueError('Sensitivity needs scenario, wacc and terminal_g only')
            if len(sensitivity['wacc']) * len(sensitivity['terminal_g']) > 400:
                raise ValueError('Sensitivity grid is bounded to four hundred cells')
            path = next(row['fcff'] for row in result['scenarios'] if row['name'] == sensitivity['scenario'])
            for wacc in algorithm.vector(sensitivity['wacc'], 'sensitivity.wacc'):
                for growth in algorithm.vector(sensitivity['terminal_g'], 'sensitivity.terminal_g'):
                    cell = {'wacc': wacc, 'terminal_g': growth}
                    try:
                        cell.update(algorithm.dcf(path, wacc, growth, cfg['shares'], result['equity_adjustment']))
                        cell['status'] = 'CONDITIONAL'
                    except ValueError as exc:
                        cell.update(status='NOT_APPLICABLE', error={'code': 'WACC_NOT_ABOVE_G', 'reason': str(exc)})
                    result['sensitivity'].append(cell)
        except (KeyError, ValueError, TypeError, StopIteration) as exc:
            result['sensitivity'] = [{'status': 'NOT_APPLICABLE', 'error': {'code': 'SENSITIVITY_INPUT_INVALID', 'reason': str(exc)}}]
    if epv is not None:
        if epv.get('applicability') != 'APPLICABLE' or not epv.get('normalization_basis'):
            result['epv'] = {'status': 'NOT_APPLICABLE', 'reason': 'EPV needs explicit applicability and normalized FCFF after maintenance reinvestment'}
        else:
            if set(epv) != {'normalized_fcff', 'applicability', 'normalization_basis'}:
                reject('EPV_INPUT_INVALID', 'Unsupported EPV fields')
            ev = perpetuity(epv['normalized_fcff'], cfg['wacc'])
            debt = result['equity_adjustment']
            result['epv'] = {'status': 'CONDITIONAL', 'enterprise_value': ev, 'equity_value': ev - debt,
                'per_share': (ev - debt) / cfg['shares'], 'growth': 0, 'wacc': cfg['wacc'],
                'normalization_basis': epv['normalization_basis'], 'independent_validation': False,
                'normalization_verification': 'UNREVIEWED_INPUT_DECLARATION'}
    result['bridge_conservation'] = [{'name': r['name'], 'enterprise_value': r['enterprise_value'],
        'deductions_net': result['equity_adjustment'], 'parent_equity_value': r['equity_value'],
        'formula': 'enterprise_value - sum(signed_bridge_amounts)'} for r in result['scenarios']]
    result['weight_meaning'] = 'RESEARCH_ASSUMPTIONS_NOT_EVENT_PROBABILITIES'
    if reverse is not None:
        try:
            allowed = {'scenario', 'market_basis', 'steady_margins', 'base_revenue', 'comparable_margin_basis'}
            if set(reverse) - allowed:
                reject('AH_BASIS_INCOMPLETE', 'Reverse requires each frozen class; shortcuts are forbidden')
            market, components = market_equity(reverse, company, cfg['metadata'], cfg['shares'])
            margins = reverse.get('steady_margins', [])
            if ('steady_margins' in reverse) != ('base_revenue' in reverse) or margins and not reverse.get('comparable_margin_basis'):
                reject('REVERSE_MARGIN_NOT_COMPARABLE', 'Revenue conversion requires same-scope steady FCFF margin evidence')
            margins = algorithm.vector(margins, 'steady_margins') if margins else []
            for margin in margins:
                algorithm.number(margin, 'steady_margin', 0, True)
            base = algorithm.number(reverse.get('base_revenue', 1), 'base_revenue', 0, True)
            path = next(r['fcff'] for r in result['scenarios'] if r['name'] == reverse['scenario'])
            value = algorithm.reverse(1, cfg['shares'], result['equity_adjustment'], cfg['wacc'], cfg['terminal_g'], path, margins, base, market)
            result['reverse'] = {**value, 'market_equity_value': market, 'market_basis': components,
                'fixed_explicit_fcff': path, 'comparable_margin_basis': reverse.get('comparable_margin_basis')}
        except CalculationError as exc:
            result['reverse'] = {'status': 'NOT_APPLICABLE', 'error': {'code': exc.code, 'reason': exc.reason}}
        except (KeyError, ValueError, TypeError, StopIteration) as exc:
            result['reverse'] = {'status': 'NOT_APPLICABLE', 'error': {'code': 'REVERSE_INPUT_INVALID', 'reason': str(exc)}}
    json.dumps(result, allow_nan=False)
    return result
