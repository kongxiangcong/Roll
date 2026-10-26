"""Host-owned operating cashflows, economic checks and immutable reviewed views.

Forecast computations are derived records, never historical disclosed facts.
The legacy calculator receives explicit forecast assumptions linked to this
frozen derivation; its source validation and unreviewed result remain intact.
"""
import copy
import json
import math
from datetime import datetime
from pathlib import Path
from decimal import Decimal
from uuid import uuid4, uuid5, NAMESPACE_URL

from roll.accounts.ledger import encode, now
from .service import fail, record, verified, fingerprint
from .models import ValuationCommand
from .valuation import numeric_leaves
from .calculator import SHANGHAI

FORMULA = 'NOPAT + depreciation - maintenance_capex - growth_capex - delta_working_capital'
RATIOS = {'revenue_growth', 'operating_margin', 'tax_rate'}
YEAR_FIELDS = RATIOS | {'depreciation', 'maintenance_capex', 'growth_capex', 'delta_working_capital', 'invested_capital'}


def close(a, b):
    return math.isclose(a, b, rel_tol=1e-8, abs_tol=1e-8)


def assumption_source_roles(path, config):
    field = path.rsplit('/', 1)[-1]
    if path == 'config/shares':
        return ['share']
    if path.startswith('config/equity_bridge/'):
        name = config['equity_bridge'][int(path.split('/')[2])]['name'].casefold()
        return ['cash'] if 'cash' in name else ['debt', 'loan', 'lease', 'liabilit', 'repurchase']
    if path == 'config/wacc':
        return ['risk_free', 'govt_yield', 'risk_premium', 'wacc']
    if field in {'revenue_growth', 'volume_growth', 'price_growth', 'terminal_g'}:
        return ['growth', 'volume', 'revenue', 'reinvestment']
    if field in {'equity_weight', 'debt_weight'}:
        return ['equity', 'debt', 'capital', 'financing']
    if field in {'roic'} or '/terminal/roic/' in path:
        return ['roic', 'capital', 'core_profit', 'operating_profit']
    return {'base_revenue': ['revenue'], 'operating_margin': ['margin', 'core_profit', 'operating_profit'],
            'tax_rate': ['tax'], 'depreciation': ['depreciation', 'da_'],
            'maintenance_capex': ['capex', 'depreciation', 'da_'], 'growth_capex': ['capex', 'capital'],
            'delta_working_capital': ['working_capital', 'cash_recon', 'nwc'], 'invested_capital': ['capital', 'equity', 'debt'],
            'risk_free': ['risk_free', 'govt_yield'], 'beta': ['beta'],
            'equity_risk_premium': ['risk_premium', 'erp'], 'cost_of_debt': ['debt_rate', 'loan_rate', 'borrowing_rate']}.get(field, [field])


def classification_sources(facts):
    return [f for f in facts if f['value_type'] == 'TEXT' and
            (any(marker in f['metric'].casefold() for marker in ['business', 'structure', 'scope']) or
             any(marker in f['business'].casefold() for marker in ['业务结构', '业务口径', '产量', '分部', 'business_structure', 'business_scope']))]


def input_provenance(value, p, facts, assumptions, unit, currency):
    if not isinstance(value, (float, int)) or isinstance(value, bool) or not math.isfinite(value):
        fail('INVALID_NUMBER', 'Operating inputs must be finite numbers')
    if not isinstance(p, dict) or set(p) != {'kind', 'references', 'unit', 'currency', 'scope', 'period'} or not p['scope'] or not p['period']:
        fail('PROVENANCE_REQUIRED', 'Every operating input needs kind, references, unit, currency, scope and period')
    if p['unit'] != unit or p['currency'] != currency:
        fail('UNIT_MISMATCH', 'Operating input scale or currency differs from model')
    if p['kind'] == 'ASSUMED':
        if not p['references'] or not set(p['references']) <= set(assumptions):
            fail('ASSUMPTION_INVALID', 'Operating assumptions must cite explicit frozen-anchored assumptions')
    elif p['kind'] in {'DISCLOSED', 'DERIVED'}:
        f = facts.get(p['references'][0]) if len(p['references']) == 1 else None
        if not f or f['kind'] != p['kind'] or f['value_type'] != 'NUMBER' or (p['kind'] == 'DERIVED' and not f.get('derivation')):
            fail('FACT_VALUE_MISMATCH', 'Disclosed/derived operating inputs require matching frozen facts')
        if Decimal(str(value)) != Decimal(f['value']) or any(p[k] != f[k] for k in ['unit', 'currency', 'scope']) or p['period'] != f['period_start'] + '/' + f['period_end']:
            fail('FACT_VALUE_MISMATCH', 'Operating value or basis differs from its fact')
    else:
        fail('PROVENANCE_REQUIRED', 'Unknown operating input kind')


def build_model(command, snapshot, packet):
    drivers, basis, cfg = copy.deepcopy(command.drivers), command.economic_basis, command.config
    facts = {f['version_id']: f for f in packet['payload']['facts']}
    if set(basis) - {'applicability', 'wacc', 'terminal', 'bridge', 'limitations', 'assumption_basis', 'valuation_basis'} or not {'applicability', 'wacc', 'terminal', 'bridge', 'limitations'} <= set(basis) or 'scenarios' in cfg or set(drivers) != {'scenarios', 'normalizations', 'provenance'}:
        fail('OPERATING_MODEL_INVALID', 'Only structured economic basis and host-generated FCFF are accepted')
    if set(basis['applicability']) - {'category', 'reason', 'references', 'cycle_normalization', 'segment_basis'} or basis['applicability']['category'] not in {'NON_FINANCIAL', 'CYCLICAL', 'GROUP', 'CYCLICAL_GROUP', 'FINANCIAL'}:
        fail('OPERATING_MODEL_INVALID', 'Unknown applicability category or caller review status')
    if set(basis['wacc']) != {'risk_free', 'beta', 'equity_risk_premium', 'cost_of_debt', 'equity_weight', 'debt_weight', 'tax_rate', 'currency', 'as_of', 'tax_shield_reason', 'references'} or set(basis['terminal']) != {'roic', 'maintenance_reason', 'references'}:
        fail('OPERATING_MODEL_INVALID', 'WACC constituents and terminal capital-return basis must be explicit')
    assumptions = {a['assumption_id']: a for a in command.assumptions}
    for a in command.assumptions:
        if not a.get('statement') or not a.get('anchor_fact_version_ids') or not set(a['anchor_fact_version_ids']) <= set(facts) or not set(a.get('hypothesis_version_ids', [])) <= set(snapshot['hypothesis_version_ids']):
            fail('ASSUMPTION_INVALID', 'Forecast assumption anchors must belong to the frozen snapshot')
    if set(drivers) != {'scenarios', 'normalizations', 'provenance'} or not 1 <= len(drivers['scenarios']) <= 10:
        fail('OPERATING_MODEL_INVALID', 'Supply bounded scenarios, normalization schedule and exact provenance')
    numeric = dict(numeric_leaves({'scenarios': drivers['scenarios'], 'basis': {'wacc': basis['wacc'], 'terminal': basis['terminal']}}))
    # Bridge amounts use the stricter existing calculator provenance. Economic
    # notes carry no independent numeric authority.
    if set(numeric) != set(drivers['provenance']):
        fail('PROVENANCE_REQUIRED', 'Every driver and WACC/terminal numeric constituent needs exact provenance')
    meta = cfg['metadata']
    for path, value in numeric.items():
        ratio = path.startswith('basis/') or path.rsplit('/', 1)[-1] in RATIOS | {'volume_growth', 'price_growth'}
        input_provenance(value, drivers['provenance'][path], facts, assumptions,
                         'ratio' if ratio else meta['amount_unit'], None if ratio else meta['currency'])
    normalizations = []
    targets, adjustments = set(), set()
    for adjustment in drivers['normalizations']:
        required = {'adjustment_id', 'target', 'before', 'delta', 'after', 'formula', 'reason', 'references', 'provenance'}
        if set(adjustment) != required:
            fail('NORMALIZATION_INVALID', 'Adjustments need before, delta, after, formula, reason, source and provenance')
        path = adjustment['target']
        p = drivers['provenance'].get(path)
        if not p or path.startswith('basis/'):
            fail('NORMALIZATION_INVALID', 'Normalization must target one operating input')
        for key in ['before', 'delta', 'after']:
            input_provenance(adjustment[key], adjustment['provenance'][key], facts, assumptions, p['unit'], p['currency'])
        ok = (path not in targets and adjustment['adjustment_id'] not in adjustments and
              bool(adjustment['reason']) and bool(adjustment['references']) and set(adjustment['references']) <= set(facts) and
              adjustment['formula'] == 'before + delta' and close(adjustment['before'], numeric[path]) and
              close(adjustment['before'] + adjustment['delta'], adjustment['after']))
        normalizations.append(dict(**adjustment, status='PASS' if ok else 'BLOCKED'))
        targets.add(path); adjustments.add(adjustment['adjustment_id'])
    if all(a['status'] == 'PASS' for a in normalizations):
        for a in normalizations:
            node = drivers
            parts = a['target'].split('/')
            for part in parts[:-1]:
                node = node[int(part)] if isinstance(node, list) else node[part]
            node[parts[-1]] = a['after']
    cashflows, derived = [], []
    names = set()
    for si, scenario in enumerate(drivers['scenarios']):
        if set(scenario) != {'name', 'base_revenue', 'years'} or scenario['name'] in names or not scenario['name'] or not 1 <= len(scenario['years']) <= 50:
            fail('OPERATING_MODEL_INVALID', 'Use named unique scenarios and one to fifty annual periods')
        names.add(scenario['name'])
        revenue, rows = scenario['base_revenue'], []
        if revenue <= 0:
            fail('INVALID_NUMBER', 'Base revenue must be positive')
        previous_end = None
        for yi, year in enumerate(scenario['years']):
            if set(year) not in [YEAR_FIELDS | {'period'}, YEAR_FIELDS - {'revenue_growth'} | {'period', 'revenue_driver'}]:
                fail('OPERATING_MODEL_INVALID', 'Annual rows require revenue growth, margin, tax, depreciation, capex, working capital and invested capital')
            if 'revenue_driver' in year:
                if set(year['revenue_driver']) != {'volume_growth', 'price_growth'} or any(v <= -1 for v in year['revenue_driver'].values()):
                    fail('OPERATING_MODEL_INVALID', 'Revenue drivers require volume and price growth above minus100%')
                year['revenue_growth'] = (1 + year['revenue_driver']['volume_growth']) * (1 + year['revenue_driver']['price_growth']) - 1
            from datetime import date
            start, end = [date.fromisoformat(v) for v in year['period'].split('/')]
            if start.month != 1 or start.day != 1 or end.month != 12 or end.day != 31 or start.year != end.year or (previous_end and start.year != previous_end.year + 1):
                fail('OPERATING_MODEL_INVALID', 'Forecasts require complete consecutive calendar years')
            previous_end = end
            if year['revenue_growth'] <= -1 or year['operating_margin'] > 1 or not 0 <= year['tax_rate'] <= 1 or any(year[k] < 0 for k in ['depreciation', 'maintenance_capex', 'growth_capex']) or year['invested_capital'] <= 0:
                fail('INVALID_NUMBER', 'Growth, taxes, depreciation, capex and invested capital exceed economic domain')
            for path in numeric:
                if path.startswith(f'scenarios/{si}/years/{yi}/') and drivers['provenance'][path]['period'] != year['period']:
                    fail('PROVENANCE_REQUIRED', 'Annual input provenance must match its forecast period')
            revenue *= 1 + year['revenue_growth']
            ebit = revenue * year['operating_margin']
            # Losses do not create cash refunds without a separately supported tax-loss model.
            tax = max(ebit, 0) * year['tax_rate']
            nopat = ebit - tax
            reinvestment = year['maintenance_capex'] + year['growth_capex'] + year['delta_working_capital'] - year['depreciation']
            fcff = nopat - reinvestment
            if not all(math.isfinite(v) for v in [revenue, ebit, tax, nopat, reinvestment, fcff]):
                fail('INVALID_NUMBER', 'Computed operating values must remain finite')
            refs = sorted([f'scenarios/{si}/base_revenue'] + [p for p in numeric if any(p.startswith(f'scenarios/{si}/years/{j}/') for j in range(yi + 1))])
            proof = dict(formula=FORMULA, revenue_formula='prior_revenue * (1 + volume_growth) * (1 + price_growth)' if 'revenue_driver' in year else 'prior_revenue * (1 + revenue_growth)',
                         operating_profit_formula='revenue * operating_margin', tax_formula='operating_profit * tax_rate',
                         input_paths=refs, inputs_sha256=fingerprint({p: dict(value=numeric[p], provenance=drivers['provenance'][p]) for p in refs}),
                         transitive_assumptions=sorted({a for p in refs for a in drivers['provenance'][p]['references'] if a in assumptions}),
                         normalization_sha256=fingerprint(normalizations))
            row = dict(period=year['period'], revenue=revenue, operating_profit=ebit, tax=tax, nopat=nopat,
                       reinvestment=reinvestment, fcff=fcff, roic=nopat / year['invested_capital'] if year['invested_capital'] else None,
                       derivation=proof, normalized_inputs=year)
            rows.append(row)
            derived.append(record(dict(kind='DERIVED', company_id=snapshot['company_id'], value=fcff,
                unit=meta['amount_unit'], currency=meta['currency'], scope='CONSOLIDATED', period=year['period'],
                scenario=scenario['name'], year_index=yi, derivation=proof)))
        cashflows.append(dict(name=scenario['name'], years=rows))
    return cashflows, derived, normalizations


def economic_checks(command, snapshot, packet, cashflows, normalizations, classification_context=None):
    """Checks return evidence and gaps, never caller-supplied status upgrades."""
    basis, cfg = command.economic_basis, command.config
    facts = set(snapshot['fact_version_ids'])
    checks = []

    def check(key, ok, reason, references=None):
        refs = references or []
        checks.append(dict(check_id=key, status='PASS' if ok else 'BLOCKED', reason=reason,
                           fact_version_ids=refs, missing_path=None if ok else 'Supply or reconcile ' + key))

    audits = basis.get('assumption_basis', {})
    fact_lookup = {f['version_id']: f for f in packet['payload']['facts']}
    assumed = {**{'config/' + p: v for p, v in command.provenance.items() if v['kind'] == 'ASSUMED'},
               **{'drivers/' + p: v for p, v in command.drivers['provenance'].items() if v['kind'] == 'ASSUMED'}}
    for path, p in assumed.items():
        audit = audits.get(path)
        evidence = bool(audit) and set(audit) == {'reason', 'support_fact_version_ids', 'counter_fact_version_ids', 'limitations'}
        if evidence:
            roles = assumption_source_roles(path, cfg)
            evidence = (bool(audit['reason']) and bool(audit['support_fact_version_ids']) and set(audit['support_fact_version_ids'] + audit['counter_fact_version_ids']) <= facts and
                        any(fact_lookup[i]['value_type'] == 'NUMBER' and any(role in fact_lookup[i]['metric'].casefold() for role in roles) for i in audit['support_fact_version_ids'] if i in facts))
        checks.append(dict(check_id='assumption/' + path, status='BLOCKED' if not evidence else 'PASS' if not audit['limitations'] else 'CONDITIONAL',
                           reason=audit['reason'] if evidence else 'Explicit forecast assumption retained; detailed economic evidence audit incomplete',
                           fact_version_ids=audit['support_fact_version_ids'] + audit['counter_fact_version_ids'] if evidence else [],
                           limitations=audit['limitations'] if evidence else [],
                           missing_path=None if evidence and not audit['limitations'] else 'Conditional use requires: ' + '; '.join(audit['limitations']) if evidence else 'Supply relevant sourced economic rationale for ' + path))

    app = basis['applicability']
    temporal = basis.get('valuation_basis')
    if temporal:
        from datetime import date
        expected = {'valuation_basis_date', 'financial_period_end', 'bridge_as_of', 'latest_known_financial_period_end', 'current_pricing_gaps'}
        if set(temporal) != expected or not isinstance(temporal['current_pricing_gaps'], list):
            fail('OPERATING_MODEL_INVALID', 'Temporal basis requires financial/bridge/latest-known dates and explicit current-pricing gaps')
        for key in expected - {'current_pricing_gaps'}:
            if date.fromisoformat(temporal[key]) > date.fromisoformat(snapshot['as_of'][:10]):
                fail('OPERATING_MODEL_INVALID', 'Financial basis cannot be later than frozen knowledge cutoff')
        anchor = date.fromisoformat(temporal['valuation_basis_date'])
        if anchor.month != 12 or anchor.day != 31 or any(int(s['years'][0]['period'][:4]) != anchor.year + 1 for s in command.drivers['scenarios']):
            fail('OPERATING_MODEL_INVALID', 'v1 requires a December31 value anchor and complete next-calendar-year first cashflow; stub periods unsupported')
        bridge_periods = [p['period'].split('/')[-1] for path, p in command.provenance.items() if path == 'shares' or path.startswith('equity_bridge/')]
        revenue_periods = [p['period'].split('/')[-1] for path, p in command.drivers['provenance'].items() if path.endswith('/base_revenue')]
        check('temporal_basis', temporal['financial_period_end'] in {f['period_end'] for f in packet['payload']['facts']} and
              bool(bridge_periods) and all(p == temporal['bridge_as_of'] for p in bridge_periods) and
              bool(revenue_periods) and all(p == temporal['financial_period_end'] for p in revenue_periods),
              'Financial baseline and declared bridge dates must match the frozen revenue/shares/bridge numeric-provenance periods')
    else:
        checks.append(dict(check_id='temporal_basis', status='BLOCKED', reason='Temporal scope incomplete; no usable price basis', fact_version_ids=[], missing_path='Supply valuation/financial/bridge/latest-known dates'))
    financial = packet['payload']['company']['industry'].upper() in {'BANK', 'BANKING', 'INSURANCE', 'FINANCIAL', '银行', '保险'} or app['category'] == 'FINANCIAL'
    check('applicability', not financial, 'FCFF/WACC unavailable for financial companies' if financial else app['reason'], app['references'])
    check('evidence_references', all(isinstance(c, str) and c in facts for c in app['references']) and bool(app['references']), 'Applicability must cite frozen evidence', app['references'])
    for key in ['wacc', 'terminal', 'bridge']:
        check(key + '_evidence', bool(basis[key].get('references')) and set(basis[key]['references']) <= facts,
              'Economic basis uses frozen evidence and explicit forecast assumptions', basis[key].get('references', []))
    w = basis['wacc']
    def sourced_rate(value):
        return any(fact_lookup[i]['value_type'] == 'NUMBER' and fact_lookup[i]['unit'] == 'ratio' and
                   close(float(fact_lookup[i]['value']), value) and fact_lookup[i]['period_end'] <= w['as_of']
                   for i in w['references'] if i in fact_lookup)
    check('wacc_source_values', sourced_rate(w['risk_free']) and (w['debt_weight'] == 0 or sourced_rate(w['cost_of_debt']) and sourced_rate(w['tax_rate'])),
          'Riskfree and any debt/tax-shield rate require matching dated numeric source facts; beta/ERP/target weights remain explicit assumptions', w['references'])
    expected_wacc = (w['risk_free'] + w['beta'] * w['equity_risk_premium']) * w['equity_weight'] + w['cost_of_debt'] * (1 - w['tax_rate']) * w['debt_weight']
    check('wacc_construction', all(0 <= w[k] <= 1 for k in ['equity_weight', 'debt_weight', 'tax_rate']) and all(w[k] >= 0 for k in ['risk_free', 'beta', 'equity_risk_premium', 'cost_of_debt']) and close(w['equity_weight'] + w['debt_weight'], 1) and close(expected_wacc, cfg['wacc']) and
          w['currency'] == cfg['metadata']['currency'] and w['as_of'] == cfg['metadata']['as_of'][:10] and bool(w['tax_shield_reason']),
          'WACC = (risk_free + beta * ERP) * equity_weight + pretax_debt_cost * (1-tax) * debt_weight', w['references'])
    for scenario, output in zip(command.drivers['scenarios'], cashflows):
        for yi, (year, row) in enumerate(zip(scenario['years'], output['years'])):
            year = row['normalized_inputs']
            previous = output['years'][yi - 1] if yi else None
            turnover_ok = (close(row['revenue'] / year['invested_capital'], previous['revenue'] / previous['normalized_inputs']['invested_capital']) if previous else close(year['revenue_growth'], 0))
            check(f'{scenario["name"]}/{yi}/growth_reinvestment', turnover_ok and (year['revenue_growth'] <= 0 or previous is not None and previous['reinvestment'] > 0),
                  'v1 stable capital turnover: year-end reinvestment funds next-year opening capital and revenue; first year uses unchanged baseline scale')
            if yi:
                check(f'{scenario["name"]}/{yi}/capital_rollforward', close(year['invested_capital'], previous['normalized_inputs']['invested_capital'] + previous['reinvestment']),
                      'Opening invested capital rolls forward by prior net reinvestment')
        row = output['years'][-1]
        last = row['normalized_inputs']
        roic = basis['terminal']['roic'].get(scenario['name']) if isinstance(basis['terminal']['roic'], dict) else basis['terminal']['roic']
        required = cfg['terminal_g'] / roic if roic > 0 else None
        check(scenario['name'] + '/terminal_reinvestment', required is not None and 0 <= required < 1 and row['nopat'] > 0 and
              close(row['reinvestment'] / row['nopat'], required) and close(row['roic'], roic) and close(last['revenue_growth'], cfg['terminal_g']) and bool(basis['terminal']['maintenance_reason']),
              'Final steady reinvestment/NOPAT = g/ROIC; terminal FCFF grows from an after-reinvestment base', basis['terminal']['references'])
    check('normalization', all(a['status'] == 'PASS' for a in normalizations),
          'Each adjustment is applied once; before + delta = after; original basis and evidence retained')
    classification_facts = classification_context if classification_context is not None else classification_sources(packet['payload']['facts'])
    evidence_text = ' '.join(str(f.get('value', '')) for f in classification_facts).casefold()
    needs_cycle = app['category'] in {'CYCLICAL', 'CYCLICAL_GROUP'} or any(v in evidence_text for v in ['lme', 'commodity', 'mining', '铜价', '铜周期', 'tc/rc', '采矿', '大宗商品'])
    needs_group = app['category'] in {'GROUP', 'CYCLICAL_GROUP'} or any(v in evidence_text for v in ['trading business', 'financial segment', 'associate scope', '贸易', '金融业务', '联营', '合营'])
    # Evidence markers are conservative safety guards, never a claim that
    # absence of a keyword independently proves a simple business model.
    if needs_cycle:
        c = app.get('cycle_normalization')
        lookup = {f['version_id']: f for f in packet['payload']['facts']}
        ok = isinstance(c, dict) and set(c) == {'period_start', 'period_end', 'peak_fact_version_ids', 'trough_fact_version_ids', 'complete_cycle_reason', 'adjustment_ids'}
        if ok:
            from datetime import date
            start, end = date.fromisoformat(c['period_start']), date.fromisoformat(c['period_end'])
            refs = c['peak_fact_version_ids'] + c['trough_fact_version_ids']
            ok = (end.year - start.year >= 4 and bool(c['complete_cycle_reason']) and bool(c['peak_fact_version_ids']) and bool(c['trough_fact_version_ids']) and
                  bool(c['adjustment_ids']) and set(c['adjustment_ids']) <= {a['adjustment_id'] for a in normalizations if a['status'] == 'PASS'} and
                  set(refs) <= facts and len(set(refs)) >= 2 and all(lookup[i]['value_type'] == 'NUMBER' and start.isoformat() <= lookup[i]['period_start'] <= lookup[i]['period_end'] <= end.isoformat() for i in refs))
        check('cycle_normalization', ok, 'Cyclicals need sourced peak/trough, multi-year complete-cycle rationale and applied normalizations; a two-year mean is insufficient', [f['version_id'] for f in classification_facts])
    if needs_group:
        group = app.get('segment_basis')
        lookup = {f['version_id']: f for f in packet['payload']['facts']}
        ok = isinstance(group, dict) and set(group) == {'reconciliations', 'financial_associate_treatment', 'reason'} and bool(group['reason']) and bool(group['financial_associate_treatment']) and len(group['reconciliations']) >= 3
        metrics = set()
        if ok:
            for reconciliation in group['reconciliations']:
                children = [lookup.get(i) for i in reconciliation['segment_fact_version_ids']]
                total = lookup.get(reconciliation['consolidated_fact_version_id'])
                valid = total and len(children) >= 2 and all(children) and total['scope'] == 'CONSOLIDATED' and total['value_type'] == 'NUMBER'
                if valid:
                    valid = (len({c['scope'] for c in children}) == len(children) and all(c['scope'] != 'CONSOLIDATED' and c['value_type'] == 'NUMBER' and all(c[k] == total[k] for k in ['unit', 'currency', 'period_start', 'period_end']) for c in children) and
                             close(sum(float(c['value']) for c in children), float(total['value'])))
                ok = ok and valid
                metrics.add(reconciliation['metric'])
        ok = ok and metrics >= {'revenue', 'operating_profit', 'invested_capital'}
        check('segment_basis', bool(ok), 'Complex groups need sourced segment revenue/profit/capital totals reconciled to consolidated scope and financial/associate treatment', [f['version_id'] for f in classification_facts])
    bridge = basis['bridge']
    components, exclusions = bridge['components'], bridge['exclusions']
    categories = {'DEBT', 'CASH', 'RESTRICTED_CASH', 'NCI', 'NONOPERATING_ASSETS', 'ASSOCIATES'}
    bridge_ok = (bool(bridge['shares_reason']) and bool(bridge['overlap_reason']) and len(components) == len(cfg['equity_bridge']) and
                 {c['category'] for c in components + exclusions} == categories and len(components + exclusions) == len(categories) and
                 len({c['economic_id'] for c in components}) == len(components))
    for item, numeric_row in zip(components, cfg['equity_bridge']):
        bridge_ok = bridge_ok and item['component_id'] == numeric_row.get('component_id', numeric_row['name'].strip().casefold()) and close(item['amount'], numeric_row['amount']) and bool(item['reason']) and bool(item['references']) and set(item['references']) <= facts and item['included_in_fcff'] is False
        if item['category'] == 'RESTRICTED_CASH':
            bridge_ok = bridge_ok and item['amount'] == 0 and numeric_row['treatment'] == 'excluded'
    for item in exclusions:
        bridge_ok = bridge_ok and bool(item['reason']) and bool(item['references']) and set(item['references']) <= facts
    check('equity_bridge', bridge_ok,
          'Diluted shares and mutually exclusive operating/nonoperating treatments need reconciliation', bridge['references'])
    return checks, financial


class EconomicState:
    def __init__(self, research):
        self.research = research
        with research.transaction() as db:
            for table, key in [('operating_models', 'operating_model_id'), ('economic_reviews', 'review_id')]:
                db.execute(f'CREATE TABLE IF NOT EXISTS company_research_{table}({key} TEXT PRIMARY KEY, company_id TEXT NOT NULL, value TEXT NOT NULL)')

    def read(self, table, key, identifier):
        with self.research.ledger.connection() as db:
            row = db.execute(f'SELECT value FROM company_research_{table} WHERE {key}=?', (identifier,)).fetchone()
        if not row:
            fail('ECONOMIC_REVIEW_NOT_FOUND', 'Operating model or review not registered', 404)
        value = verified(json.loads(row[0]))
        raw = self.research.evidence.raw(value['archive']['sha256']).read_bytes()
        if json.loads(raw) != {k: v for k, v in value.items() if k not in {'archive', 'content_sha256'}}:
            fail('ARTIFACT_CORRUPT', 'Economic record differs from canonical archive', 409)
        return value

    def save(self, db, table, key, payload):
        payload = record(payload)
        payload.pop('content_sha256')
        archive = self.research.valuations.archive(encode(payload).encode(), 'COMPANY_' + table.upper(), db)
        value = record({**payload, 'archive': archive})
        db.execute(f'INSERT INTO company_research_{table} VALUES(?,?,?)', (value[key], value['company_id'], encode(value)))
        return value

    def calculate(self, command):
        request = command.model_dump()
        try:
            if len(json.dumps(request, allow_nan=False).encode()) > 131072:
                fail('VALUATION_INPUT_TOO_LARGE', 'Operating model exceeds 128 KiB')
        except (ValueError, TypeError):
            fail('INVALID_NUMBER', 'Operating inputs must be finite')
        snapshot = self.research.analysis_snapshot(command.snapshot_id)
        scope = 'operating-valuation:' + snapshot['company_id']
        with self.research.ledger.connection() as db:
            prior = db.execute('SELECT request_hash,result FROM company_research_commands WHERE scope=? AND key=?', (scope, command.idempotency_key)).fetchone()
        if prior:
            if prior[0] != fingerprint(request):
                fail('IDEMPOTENCY_CONFLICT', 'Operating valuation key reused for changed input', 409)
            return verified(json.loads(prior[1]))
        packet = self.research.analysis_input(snapshot['input_id'])
        context = {f['version_id']: f for f in classification_sources(packet['payload']['facts'])}
        ancestor = snapshot
        for _ in range(1000):
            if not ancestor['parent_snapshot_id']:
                break
            ancestor = self.research.analysis_snapshot(ancestor['parent_snapshot_id'])
            if ancestor['company_id'] != snapshot['company_id']:
                fail('CROSS_COMPANY_REFERENCE', 'Classification ancestry belongs to another company')
            if ancestor.get('enrichment_kind') == 'ECONOMIC_REVIEW':
                prior_model = self.research.operating_model(ancestor['core']['valuation']['operating_model_id'])
                if 'classification_context' in prior_model:
                    context.update({f['version_id']: f for f in prior_model['classification_context']})
                    break
            prior_packet = self.research.analysis_input(ancestor['input_id'])
            context.update({f['version_id']: f for f in classification_sources(prior_packet['payload']['facts'])})
        else:
            fail('OPERATING_MODEL_INVALID', 'Classification ancestry exceeds controlled bounds')
        try:
            financial = packet['payload']['company']['industry'].upper() in {'BANK', 'BANKING', 'INSURANCE', 'FINANCIAL', '银行', '保险'} or command.economic_basis['applicability']['category'] == 'FINANCIAL'
            if financial:
                if not set(command.economic_basis['applicability']['references']) <= set(snapshot['fact_version_ids']):
                    fail('UNKNOWN_CITATION', 'Financial applicability must reference frozen evidence')
                cashflows, derived, normalizations = [], [], []
                checks = [dict(check_id='applicability', status='BLOCKED', reason='Financial company: FCFF executor not applicable; retain research and method gap', fact_version_ids=command.economic_basis['applicability']['references'], missing_path='Use a separately supported financial-company method')]
            else:
                cashflows, derived, normalizations = build_model(command, snapshot, packet)
                checks, financial = economic_checks(command, snapshot, packet, cashflows, normalizations, list(context.values()))
        except (KeyError, TypeError, ValueError, AttributeError, IndexError, OverflowError, ZeroDivisionError) as exc:
            fail('OPERATING_MODEL_INVALID', str(exc))
        mid = str(uuid5(NAMESPACE_URL, scope + ':' + fingerprint(request)))
        payload = dict(operating_model_id=mid, company_id=snapshot['company_id'], snapshot_id=snapshot['snapshot_id'],
            snapshot_sha256=snapshot['content_sha256'], request=request, cashflows=cashflows, derived_records=derived,
            normalization_schedule=normalizations,
            classification_context=list(context.values()),
            method_version='operating-fcff-1', generated_at=now())
        with self.research.transaction() as db:
            existing = db.execute('SELECT value FROM company_research_operating_models WHERE operating_model_id=?', (mid,)).fetchone()
            if existing:
                model = self.research.operating_model(mid)
                if model['request'] != request:
                    fail('INPUT_CHANGED', 'Frozen operating model differs', 409)
            else:
                payload['algorithm_archive'] = self.research.valuations.archive(Path(__file__).read_bytes(), 'COMPANY_ECONOMIC_ALGORITHM', db)
                model = self.save(db, 'operating_models', 'operating_model_id', payload)
        raw = None
        if not financial:
            raw_command = ValuationCommand(**command.model_dump(exclude={'drivers', 'economic_basis'}))
            raw_command.config = copy.deepcopy(command.config)
            raw_command.config['scenarios'] = []
            raw_command.provenance = copy.deepcopy(command.provenance)
            for si, scenario in enumerate(cashflows):
                raw_command.config['scenarios'].append(dict(name=scenario['name'], fcf=[r['fcff'] for r in scenario['years']]))
                for yi, row in enumerate(scenario['years']):
                    aid = 'operating:' + mid + ':' + str(si) + ':' + str(yi)
                    raw_command.assumptions.append(dict(assumption_id=aid, statement='Forecast FCFF computed by operating-fcff-1; model ' + mid + '; derived-record ' + derived[sum(len(s['years']) for s in cashflows[:si]) + yi]['content_sha256'],
                        anchor_fact_version_ids=snapshot['fact_version_ids'], hypothesis_version_ids=snapshot['hypothesis_version_ids']))
                    raw_command.config['metadata']['assumptions'].append(aid)
                    raw_command.provenance[f'scenarios/{si}/fcf/{yi}'] = dict(kind='ASSUMED', references=[aid],
                        unit=command.config['metadata']['amount_unit'], currency=command.config['metadata']['currency'],
                        scope='CONSOLIDATED', period=row['period'])
            raw_command.idempotency_key = 'operating:' + command.idempotency_key
            raw = self.research.calculate_valuation(raw_command)
        status = 'blocked' if any(c['status'] == 'BLOCKED' for c in checks) else 'conditional' if command.economic_basis['limitations'] or any(c['status'] == 'CONDITIONAL' for c in checks) else 'reviewed'
        with self.research.transaction() as db:
            prior = db.execute('SELECT request_hash,result FROM company_research_commands WHERE scope=? AND key=?', (scope, command.idempotency_key)).fetchone()
            if prior:
                if prior[0] != fingerprint(request):
                    fail('IDEMPOTENCY_CONFLICT', 'Operating valuation key reused', 409)
                return verified(json.loads(prior[1]))
            parent = self.research.analysis.latest(snapshot['company_id'], db)
            if parent['snapshot_id'] != snapshot['snapshot_id']:
                fail('INPUT_CHANGED', 'Another snapshot was published; rebind operating analysis', 409)
            review = self.save(db, 'economic_reviews', 'review_id', dict(review_id=str(uuid4()), company_id=snapshot['company_id'],
                source_snapshot_id=snapshot['snapshot_id'], valuation_id=raw['valuation_id'] if raw else None, valuation_sha256=raw['content_sha256'] if raw else None,
                operating_model_id=mid, operating_model_sha256=model['content_sha256'], status=status,
                applicability='NOT_APPLICABLE' if financial else 'CONDITIONAL', usable_range=status in {'conditional', 'reviewed'},
                checks=checks, limitations=command.economic_basis['limitations'], reviewed_at=now(),
                authority='HOST_DETERMINISTIC_CHECKS', policy_version='economic-review-2', policy_archive=model['algorithm_archive'],
                meaning='Economic consistency only; no return validation or trading authority'))
            enriched = {k: copy.deepcopy(v) for k, v in snapshot.items() if k != 'content_sha256'}
            enriched.update(snapshot_id=str(uuid4()), parent_snapshot_id=snapshot['snapshot_id'], generated_at=now(),
                enrichment_kind='ECONOMIC_REVIEW', economic_review_ids=[review['review_id']], valuation_ids=[raw['valuation_id']] if raw else [])
            enriched['core']['valuation_unavailable_reason'] = None if review['usable_range'] else 'Economic review blocked; inspect gaps'
            enriched['core']['valuation'] = dict(review_id=review['review_id'], valuation_id=raw['valuation_id'] if raw else None,
                operating_model_id=mid, status=status, usable_range=review['usable_range'])
            enriched['core_sha256'] = fingerprint(enriched['core'])
            enriched = record(enriched)
            self.research.analysis.insert(db, 'snapshots', 'snapshot_id', enriched)
            receipt = record(dict(company_id=snapshot['company_id'], operating_model_id=mid, valuation_id=raw['valuation_id'] if raw else None,
                                  review_id=review['review_id'], snapshot_id=enriched['snapshot_id']))
            self.research.save_command(db, scope, command.idempotency_key, request, receipt)
        return receipt

    def presentation(self, identifier, purpose='CURRENT_PRICING'):
        if purpose not in {'CURRENT_PRICING', 'BASELINE_RESEARCH'}:
            fail('INVALID_PURPOSE', 'Valuation presentation supports current pricing or explicit baseline research')
        with self.research.ledger.connection() as db:
            exists = db.execute('SELECT 1 FROM company_research_economic_reviews WHERE review_id=?', (identifier,)).fetchone()
        if not exists:
            raw = self.research.valuation(identifier)
            return dict(review=raw['result']['review'], status='unreviewed', usable_range=False, scenarios=[],
                        limitations=raw['result']['review']['limitations'], diagnostic_valuation_id=raw['valuation_id'])
        review = self.research.economic_review(identifier)
        if review['valuation_id'] is None:
            return dict(review=review, status='blocked', usable_range=False, scenarios=[], purpose=purpose, limitations=review['limitations'], diagnostic_valuation_id=None)
        raw = self.research.valuation(review['valuation_id'])
        model = self.research.operating_model(review['operating_model_id'])
        if raw['content_sha256'] != review['valuation_sha256']:
            fail('RESEARCH_REFERENCE_INVALID', 'Review and valuation hash differ', 409)
        basis = model['request']['economic_basis'].get('valuation_basis')
        current_gaps = []
        later_ids = []
        evaluated_at = now() if purpose == 'CURRENT_PRICING' else None
        if basis:
            current_gaps = list(basis['current_pricing_gaps'])
            if basis['financial_period_end'] < basis['latest_known_financial_period_end'] or basis['bridge_as_of'] < basis['latest_known_financial_period_end']:
                current_gaps.append('Latest known financial period and equity bridge not incorporated')
            from datetime import date
            knowledge_day = datetime.fromisoformat(evaluated_at).astimezone(SHANGHAI).date() if evaluated_at else date.fromisoformat(model['request']['config']['metadata']['as_of'][:10])
            if (knowledge_day - date.fromisoformat(basis['bridge_as_of'])).days > 180:
                current_gaps.append('Equity bridge older than180 days; refresh required for current pricing')
            packet = self.research.analysis_input(self.research.analysis_snapshot(model['snapshot_id'])['input_id'])
            known = [f['period_end'] for f in packet['payload']['facts'] if f['metric'] == 'latest_financial_disclosure']
            if known and max(known) > basis['financial_period_end']:
                current_gaps.append('A newer frozen financial disclosure is known but not incorporated')
            if purpose == 'CURRENT_PRICING':
                with self.research.ledger.connection() as db:
                    rows = db.execute("SELECT value FROM company_research_facts WHERE company_id=? AND json_extract(value,'$.period_end')>? AND (json_extract(value,'$.metric')='latest_financial_disclosure' OR json_extract(value,'$.business')='FINANCIAL_STATEMENT') AND json_extract(value,'$.kind') IN ('DISCLOSED','DERIVED') ORDER BY json_extract(value,'$.period_end') DESC LIMIT 80", (review['company_id'], basis['financial_period_end'])).fetchall()
                later = [verified(json.loads(row[0])) for row in rows]
                later_ids = [f['version_id'] for f in later if f['consumable_at'] <= evaluated_at]
                if later_ids:
                    current_gaps.append('Newer company financial disclosure acquired since baseline; refresh current applicability without changing the saved snapshot')
        else:
            current_gaps.append('Valuation, financial and equity bridge temporal basis not verified')
        policy_supported = review['policy_version'] == 'economic-review-2'
        if not policy_supported:
            current_gaps.append('Saved legacy review policy is diagnostic; rerun controlled review under the supported policy')
        usable = review['usable_range'] and policy_supported and not (purpose == 'CURRENT_PRICING' and current_gaps)
        return dict(review=review, status=review['status'] if usable else 'blocked', usable_range=usable, purpose=purpose,
                    scenarios=copy.deepcopy(raw['result']['scenarios']) if usable else [], valuation_basis=basis,
                    knowledge_as_of=self.research.analysis_snapshot(model['snapshot_id'])['as_of'],
                    current_pricing_gaps=current_gaps, conditions=model['request']['assumptions'],
                    evaluated_at=evaluated_at, later_disclosure_fact_version_ids=later_ids,
                    limitations=review['limitations'], diagnostic_valuation_id=raw['valuation_id'], operating_model_id=model['operating_model_id'])
