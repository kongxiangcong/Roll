"""Reproduce ticket05 dated real-source case and JCC negative case, offline.

Inputs are frozen official source bytes, never credentials or a model service.
Create a new isolated store for a new run; saved results are immutable.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from roll.accounts.ledger import Ledger
from roll.market.directory import MarketDirectory
from roll.market.evidence import EvidenceStore
from roll.research.company import (CompanyResearch, CompanyCommand, MaterialCommand, FactCommand,
                                  AnalysisCommand, OperatingValuationCommand)

HERE = Path(__file__).resolve().parent


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-directory', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--jcc-data-directory', default='D:/dsh-proj/Roll/.scratch/rv03-real-data')
    args = parser.parse_args()
    target = Path(args.data_directory)
    if target.exists():
        raise RuntimeError('Choose a new empty data directory; never replace saved real evidence')
    ledger = Ledger(target)
    research = CompanyResearch(EvidenceStore(ledger, MarketDirectory(ledger)))
    raw_notes = json.loads((HERE / 'source-data/lulu-source-facts.json').read_text(encoding='utf-8'))
    source_facts = {f['fact_key']: f for f in raw_notes['facts']}
    identity = research.register(CompanyCommand(legal_name=raw_notes['company'], jurisdiction='CN',
        accounting_standard='PRC_GAAP', year_end='12-31', industry='NON_FINANCIAL',
        identity_basis='Issuer annual report2025 pp1/50; manufacturer, not the related deposit-taking finance company',
        listings=[dict(exchange='SZSE', code='000848', share_class='A', currency='CNY')]))
    materials, facts = {}, {}

    def add(key, value, unit='unit', currency='CNY', start='2025-01-01', end='2025-12-31',
            page='68-69', kind='DISCLOSED', derivation=None, metric=None, source='LULU_2025', text=False, business='FINANCIAL_STATEMENT'):
        source_meta = raw_notes['sources'][source]
        group = (source, start, end, unit, currency)
        if group not in materials:
            raw = (HERE / 'source-data' / source_meta['filename']).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == source_meta['sha256']
            materials[group] = research.import_material(MaterialCommand(company_id=identity['company_id'],
                source_id=source, origin_root_id=source_meta['source_url'], source_url=source_meta['source_url'],
                subject_name=identity['legal_name'], media_type='application/pdf', disclosed_at=None,
                period_start=start, period_end=end, scope='CONSOLIDATED', unit=unit, currency=currency,
                limitations=['Actual import occurs now; source acquired2026-10-26 UTC; no historical PIT',
                              'unit=unit means whole CNY with unchanged numeric scale; share means individual shares']), raw)
        f = research.add_fact(FactCommand(company_id=identity['company_id'], material_id=materials[group]['material_id'],
            metric=metric or key, business=business, value=str(value), value_type='TEXT' if text else 'NUMBER',
            unit=unit, currency=currency, scope='CONSOLIDATED', period_start=start, period_end=end, page=page,
            kind=kind, derivation=derivation, change_reason='Read frozen issuer original at exact page; ' + (derivation or 'No numeric scaling')))
        facts[key] = f
        return f

    selected = [k + '_2025' for k in ['revenue', 'cost_of_goods', 'taxes_and_surcharges', 'selling_expenses', 'administrative_expenses', 'research_expenses',
        'reported_operating_profit', 'interest_income_accrual', 'cfo', 'cash_capex', 'fixed_asset_depreciation', 'rou_depreciation', 'intangible_amortization', 'deferred_expense_amortization',
        'cash_total', 'cash_at_related_finance_company', 'bank_loans_including_current', 'lease_liabilities_including_current', 'restricted_share_repurchase_obligation', 'share_count', 'restricted_cash_declared',
        'cash_recon_inventory_decrease', 'cash_recon_operating_receivables_decrease', 'cash_recon_operating_payables_increase', 'goods_payables', 'capital_project_payables']]
    selected += [k for k in source_facts if k.endswith('_2024') and k.startswith(('revenue_', 'cost_of_goods_', 'taxes_and_surcharges_', 'selling_expenses_', 'administrative_expenses_', 'research_expenses_', 'cfo_', 'cash_capex_'))]
    for key in selected:
        f = source_facts[key]
        add(key, f['value'], 'share' if key.startswith('share_count') else 'unit',
            None if key.startswith('share_count') else 'CNY', f['period_start'], f['period_end'],
            page=str(f['pdf_page_1based']), source=f['source_id'])
    add('business_structure', 'The issuer manufactures and sells plant protein beverages; beverage revenue and other revenue are separately disclosed. Related finance-company deposits are not a consolidated finance business.',
        unit=None, currency=None, page='10/16/148', text=True, business='BUSINESS_STRUCTURE')
    add('associate_boundary', '本公司对合营企业或联营企业投资已全额计提减值。No economic recovery value is independently established.',
        unit=None, currency=None, page='149', text=True, business='BALANCE_NOTE')
    add('noncash_asset_boundary', 'All reported nonblank current assets4232193507.86 plus noncurrent assets1078778070.07 equal total5310971577.93. Residual carrying amount for blank financial-investment rows is0, not an appraisal or proof of no recoverable economic value.',
        unit=None, currency=None, page='64-65', text=True, business='BALANCE_NOTE')
    external_materials = []
    owner_receipts = {r['filename']: r for r in json.loads((HERE / 'source-data/wacc-owner-acquisition.json').read_text(encoding='utf-8'))}
    def external_number(key, value, filename, source_url, period_start, period_end, scope, unit='ratio', currency=None, derivation=None):
        raw = (HERE / 'source-data' / filename).read_bytes()
        if filename in owner_receipts:
            assert hashlib.sha256(raw).hexdigest() == owner_receipts[filename]['sha256']
        m = research.import_material(MaterialCommand(company_id=identity['company_id'], source_id=filename,
            origin_root_id=source_url, source_url=source_url, subject_name=identity['legal_name'], media_type='text/plain',
            unit=unit, currency=currency, scope=scope, period_start=period_start, period_end=period_end,
            limitations=['Applied external macro/industry/provider source, not issuer disclosure; actual current import, no historical PIT']), raw)
        external_materials.append(m)
        facts[key] = research.add_fact(FactCommand(company_id=identity['company_id'], material_id=m['material_id'], metric=key,
            business='EXTERNAL_VALUATION_INPUT', value=str(value), unit=unit, currency=currency, scope=scope,
            period_start=period_start, period_end=period_end, page='Frozen source row documented in source-research.md',
            kind='DERIVED' if derivation else 'DISCLOSED', derivation=derivation, change_reason=derivation or 'Exact author table numeric input; applicability is a separate assumption'))
    external_number('cny_10y_govt_yield_20251231', '.018473', 'chinabond-20251231.html', owner_receipts['chinabond-20251231.html']['url'],
        '2025-12-31', '2025-12-31', 'CNY_GOVT_10Y', derivation='Disclosed1.8473 percent /100; dated2025-12-31, not a current quote')
    external_number('china_equity_risk_premium', '.0514', 'damodaran-country-premiums-jan2026.html', owner_receipts['damodaran-country-premiums-jan2026.html']['url'],
        '2026-01-05', '2026-01-05', 'CHINA_ERP', derivation='Author totalChinaERP5.14 percent /100 includes mature4.23 plus country0.91; no additional country premium')
    external_number('global_soft_beverage_cash_corrected_unlevered_beta', '.54', 'damodaran-global-betas-jan2026.html', owner_receipts['damodaran-global-betas-jan2026.html']['url'],
        '2026-01-01', '2026-01-31', 'GLOBAL_SOFT_BEVERAGES_JAN2026')
    external_number('approx_market_equity_value_20251231', '8670000000', 'provider-wacc-market-data.json', 'registered-source://CONNECTED_MX_FINANCE_DATA/000848/market-cap-20251231',
        '2025-12-31', '2025-12-31', 'CONSOLIDATED', unit='unit', currency='CNY', derivation='Provider reports86.7亿, multiply1e8; approximate rounded market equity, not a verified RAW-price reverse input')
    q3_raw = (HERE / 'source-data/lulu-2026-q3-issuer-mirror.pdf').read_bytes()
    assert hashlib.sha256(q3_raw).hexdigest() == '4ba56ec58824e6e7aa667ce3f2caa78e0834e51c57b470dad6b9433e66b6f464'
    q3_material = research.import_material(MaterialCommand(company_id=identity['company_id'], source_id='LULU_2026_Q3_MIRROR',
        origin_root_id='ISSUER_LULU_2026_038', source_url='https://pdf.dfcfw.com/pdf/H2_AN202610231830847933_1.PDF',
        subject_name=identity['legal_name'], media_type='application/pdf', scope='CONSOLIDATED', unit=None, currency=None,
        period_start='2026-01-01', period_end='2026-09-30', disclosed_at=None,
        limitations=['Issuer original hosted by mirror; authorship/announcement checked against statutory media, no claim of identical CNINFO bytes',
                      'Only exact report date known, actual current import, no historical PIT']), q3_raw)
    facts['latest_financial_disclosure'] = research.add_fact(FactCommand(company_id=identity['company_id'], material_id=q3_material['material_id'],
        metric='latest_financial_disclosure', business='DISCLOSURE_AVAILABILITY', value='承德露露股份公司2026年第三季度报告', value_type='TEXT', unit=None, currency=None,
        scope='CONSOLIDATED', period_start='2026-01-01', period_end='2026-09-30', page='1/9', change_reason='Read exact issuer report title and period; no Q3 numeric values substituted into FY2025 case'))
    from pypdf import PdfReader
    annual = PdfReader(HERE / 'source-data/lulu-2025-annual.pdf')
    assert '本公司对合营企业或联营企业投资已全额计提减值' in annual.pages[148].extract_text()
    for year in [2025, 2024]:
        amount = sum((Decimal(source_facts[f'{k}_{year}']['value']) * (-1 if k != 'revenue' else 1)
                      for k in ['revenue', 'cost_of_goods', 'taxes_and_surcharges', 'selling_expenses', 'administrative_expenses', 'research_expenses']), Decimal(0))
        add('core_profit_' + str(year), amount, start=f'{year}-01-01', end=f'{year}-12-31', kind='DERIVED',
            derivation='revenue - COGS - taxes/surcharges - selling - administration - research; excludes finance, other gains and impairments; references ' + ','.join(facts[f'{k}_{year}']['version_id'] for k in ['revenue', 'cost_of_goods', 'taxes_and_surcharges', 'selling_expenses', 'administrative_expenses', 'research_expenses']))
    da = sum(Decimal(source_facts[k]['value']) for k in ['fixed_asset_depreciation_2025', 'rou_depreciation_2025', 'intangible_amortization_2025', 'deferred_expense_amortization_2025'])
    add('da_2025', da, page='146', kind='DERIVED', derivation='Sum fixed depreciation + ROU depreciation + intangible amortization + disclosed deferred amortization; capitalized lease replacement included in forecast maintenance')
    interest_debt = sum(Decimal(source_facts[k]['value']) for k in ['bank_loans_including_current_2025', 'lease_liabilities_including_current_2025'])
    debt = interest_debt + Decimal(source_facts['restricted_share_repurchase_obligation_2025']['value']) + Decimal(source_facts['capital_project_payables_2025']['value'])
    add('bridge_debt_2025', debt, start='2025-12-31', end='2025-12-31', page='135/146', kind='DERIVED', derivation='Bank loans including current + lease liabilities including current + share repurchase obligation + recognized capital-project payables; the latter are excluded from operating NWC; no additional treasury-stock deduction or share netting')
    # Explicit disclosed equation and exhaustive balance reconciliation, not blank=0.
    add('total_equity_2025', '3490498161.46', start='2025-12-31', end='2025-12-31', page='66')
    add('no_disclosed_material_commitment_2025', '截至2025年12月31日，本公司无需要披露的重要承诺事项。', unit=None, currency=None, page='155', text=True, business='COMMITMENT_NOTE')
    add('nci_2025', '0', start='2025-12-31', end='2025-12-31', page='66/148', kind='DERIVED', derivation='3490498161.46 consolidated equity -3490498161.46 parent equity =0; three subsidiaries100% owned')
    add('statutory_tax_rate', '.25', unit='ratio', currency=None, page='119', kind='DERIVED', derivation='Disclosed corporate income tax25 percent /100; usable interest tax shield remains an assumption')
    add('guaranteed_debt_rate', '.0299', unit='ratio', currency=None, start='2025-12-31', end='2025-12-31', page='137', kind='DERIVED', derivation='Disclosed guaranteed-loan annual interest2.99 percent /100; current borrowing spread not observed')
    all_ids = [f['version_id'] for f in facts.values()]
    packet = research.freeze_analysis(AnalysisCommand(company_id=identity['company_id'], as_of=datetime.now(timezone.utc).isoformat(), fact_version_ids=all_ids))
    claim = dict(text='The issuer discloses plant beverage manufacturing and separately reports cash, debt and cash-flow information.', fact_version_ids=[facts['business_structure']['version_id']], gap_reason=None)
    candidate = dict(company_id=identity['company_id'], input_sha256=packet['packet_sha256'], business_structure=[claim], attention_reasons=[], counterevidence=[], hypotheses=[],
        insufficient_hypotheses_reason='This deterministic ticket05 case reuses public financial evidence; no new model-generated hypothesis set',
        limitations=['Dated financial baseline; see operating-model conditions and newer filing gap'], valuation_unavailable_reason='Operating model not yet evaluated')
    snapshot = research.apply_analysis_candidate(packet['input_id'], candidate)
    anchors = all_ids
    assumptions = [dict(assumption_id='dated-steady-state', statement='2025FY financial baseline, current knowledge; flat volume/price/mix, zero growth and working-capital change, normalized margins; no current-fair-price claim. Maintenance and lease renewals equal full D&A. Actual capex and WC cash release are not repeated. Operating cash reserve equals one quarter of the core operating-expense proxy including noncash costs, not actual cash expense; deposits assumed collectible. No new dilution; repurchase and capital AP obligations deducted once with gross reported shares.', anchor_fact_version_ids=anchors, hypothesis_version_ids=[])]
    revenue = float(source_facts['revenue_2025']['value'])
    margin25 = float(facts['core_profit_2025']['value']) / revenue
    margin24 = float(facts['core_profit_2024']['value']) / float(source_facts['revenue_2024']['value'])
    cash_cost = revenue - float(facts['core_profit_2025']['value'])
    reserve = cash_cost / 4
    excess_cash = float(source_facts['cash_total_2025']['value']) - reserve
    capital = 3490498161.46 + float(debt) - excess_cash
    as_of = snapshot['as_of']
    risk_free, erp, cost_debt, tax = .018473, .0514, .0299, .25
    market_equity = 8670000000
    ew, dw = market_equity / (market_equity + float(interest_debt)), float(interest_debt) / (market_equity + float(interest_debt))
    beta = .54 * (1 + (1 - tax) * float(interest_debt) / market_equity)
    wacc = (risk_free + beta * erp) * ew + cost_debt * (1 - tax) * dw
    cfg = dict(metadata=dict(company=identity['legal_name'], as_of=as_of, currency='CNY', amount_unit='unit', shares_unit='share', sources=all_ids, assumptions=['dated-steady-state']),
        cash_flow_basis='FCFF', shares=float(source_facts['share_count_2025']['value']), wacc=wacc, terminal_g=0,
        equity_bridge=[dict(name='Debt leases repurchase and capital-project payable', component_id='liabilities', amount=float(debt), source=facts['bridge_debt_2025']['version_id'], treatment='deduct'),
                       dict(name='Assumed collectible excess cash', component_id='excess-cash', amount=-excess_cash, source=facts['cash_total_2025']['version_id'], treatment='add')])

    def assumed(unit, period, currency=None):
        return dict(kind='ASSUMED', references=['dated-steady-state'], unit=unit, currency=currency, scope='CONSOLIDATED', period=period)

    period = '2025-01-01/2025-12-31'
    provenance = {'shares': dict(kind='DISCLOSED', references=[facts['share_count_2025']['version_id']], unit='share', currency=None, scope='CONSOLIDATED', period=facts['share_count_2025']['period_start'] + '/' + facts['share_count_2025']['period_end']),
                  'equity_bridge/0/amount': dict(kind='DERIVED', references=[facts['bridge_debt_2025']['version_id']], unit='unit', currency='CNY', scope='CONSOLIDATED', period='2025-12-31/2025-12-31'),
                  'equity_bridge/1/amount': assumed('unit', period, 'CNY'), 'wacc': assumed('ratio', as_of[:10]), 'terminal_g': assumed('ratio', 'STEADY_STATE')}
    scenarios, dp, adjustments, terminal_roics = [], {}, [], {}
    for si, (name, margin) in enumerate([('baseline', margin24), ('margin-stress', .22)]):
        rows = []
        dp[f'scenarios/{si}/base_revenue'] = assumed('unit', period, 'CNY')
        for yi, year in enumerate([2026, 2027, 2028, 2029, 2030]):
            yp = f'{year}-01-01/{year}-12-31'
            reported_margin = float(source_facts['reported_operating_profit_2025']['value']) / revenue
            row = dict(period=yp, revenue_driver=dict(volume_growth=0, price_growth=0), operating_margin=reported_margin, tax_rate=tax,
                depreciation=float(da), maintenance_capex=float(da), growth_capex=0, delta_working_capital=0, invested_capital=capital)
            rows.append(row)
            for key in ['operating_margin', 'tax_rate', 'depreciation', 'maintenance_capex', 'growth_capex', 'delta_working_capital', 'invested_capital']:
                ratio = key in {'operating_margin', 'tax_rate'}
                dp[f'scenarios/{si}/years/{yi}/{key}'] = assumed('ratio' if ratio else 'unit', yp, None if ratio else 'CNY')
            for key in ['volume_growth', 'price_growth']:
                dp[f'scenarios/{si}/years/{yi}/revenue_driver/{key}'] = assumed('ratio', yp)
            adjustments.append(dict(adjustment_id=f'{name}-{year}-margin', target=f'scenarios/{si}/years/{yi}/operating_margin', before=reported_margin, delta=margin - reported_margin, after=margin,
                formula='before + delta', reason='Reported operating profit832768950.67 -> core802208126.13 by revenue minus COGS/surcharges/selling/admin/research, excluding all finance/gains/impairments, then normalize to2024 observed core margin or explicit22% stress. One combined adjustment per target; no complete-cycle claim.',
                references=[facts['core_profit_2025']['version_id'], facts['core_profit_2024']['version_id']], provenance={k: assumed('ratio', yp) for k in ['before', 'delta', 'after']}))
        scenarios.append(dict(name=name, base_revenue=revenue, years=rows))
        terminal_roics[name] = revenue * margin * (1 - tax) / capital
        dp['basis/terminal/roic/' + name] = assumed('ratio', 'STEADY_STATE')
    for key in ['risk_free', 'beta', 'equity_risk_premium', 'cost_of_debt', 'equity_weight', 'debt_weight', 'tax_rate']:
        dp['basis/wacc/' + key] = assumed('ratio', as_of[:10])
    refs = [facts['cash_total_2025']['version_id'], facts['bridge_debt_2025']['version_id'], facts['nci_2025']['version_id'], facts['associate_boundary']['version_id']]
    limits = list(raw_notes['critical_boundaries']) + [
        'BASELINE_RESEARCH only:2025 financial/bridge basis, actual current acquisition and discount-rate assumptions. Current pricing is blocked pending2026Q3 reconciliation, commitments and post-quarter share cancellation verification; Q3 cash/investment assets differ materially from2025.',
        'Operating cash reserve and collectible related deposits are assumptions; no independent credit appraisal. Noncash financial investment book residual0 is not an appraised economic recovery value.',
        'Core margin excludes gains and impairments by explicit definition;2024-margin benchmark and22% stress are assumptions, not forecasts or full-cycle normalization.',
        'Capital employed includes explicitly retained operating cash and gross repurchase liability; stable capital-turnover/zero-growth model only. No price-implied reverse analysis, probabilities or expected-return assertion.']
    limits += ['WACC uses CNY government-yield riskfree proxy without sovereign-spread subtraction, China totalERP includes country risk once, Jan2026 global industry asset-beta proxy relevered by approximate2025 marketE and book interestD. These are justified proxies with model risk, not a measured issuer beta/current market WACC; simplified common beta scaling of totalERP is explicit.',
               'Reported2025 material commitment disclosure is none; recognized capital-project payables are deducted once. This does not imply no future replacement spending or optional project plans. Quarter operating-expense cash reserve is an assumption including noncash expenses.']
    basis = dict(applicability=dict(category='NON_FINANCIAL', reason='Manufacturing beverage subsidiaries; related finance-company deposits are counterparties, not consolidated financial operations', references=[facts['business_structure']['version_id']]),
        wacc=dict(risk_free=risk_free, beta=beta, equity_risk_premium=erp, cost_of_debt=cost_debt, equity_weight=ew, debt_weight=dw, tax_rate=tax,
            currency='CNY', as_of=as_of[:10], tax_shield_reason='Statutory25% usable shield assumed;2025 bank+lease interest debt592328455.05 and approximately8.67bn market equity imply weights. Repurchase/capital AP excluded from WACC D but bridge deducted. Beta=.54*(1+.75*D/E), asset industry proxyJan2026 not company measured beta. TotalChinaERP5.14% already includes country0.91%, simplified beta-scaled totalERP assumption. Riskfree2025-12-31=1.8473%; historical debt2.99% proxy, no current quote', references=[facts['bridge_debt_2025']['version_id'], facts['cny_10y_govt_yield_20251231']['version_id'], facts['statutory_tax_rate']['version_id'], facts['guaranteed_debt_rate']['version_id']]),
        terminal=dict(roic=terminal_roics, maintenance_reason='Zero growth and zero net reinvestment; maintenance including capitalized lease renewals equals full D&A by assumption, not disclosed maintenance spending', references=[facts['da_2025']['version_id']]),
        bridge=dict(shares_reason='Gross year-end shares used, no treasury-share netting; no new dilution assumed. Repurchase liability deducted once in debt.', references=refs,
            components=[dict(component_id='liabilities', economic_id='interest-and-repurchase-obligations', category='DEBT', amount=float(debt), reason='Loans + leases + restricted-share repurchase + recognized capital-project payable; the latter excluded from operating NWC and not deducted again in maintenance capex. No treasury-stock double deduction', references=[facts['bridge_debt_2025']['version_id']], included_in_fcff=False),
                        dict(component_id='excess-cash', economic_id='cash-after-operating-reserve', category='CASH', amount=-excess_cash, reason='Cash minus quarter-year core expense reserve; related deposits assumed collectible; all finance income excluded from EBIT', references=[facts['cash_total_2025']['version_id']], included_in_fcff=False)],
            exclusions=[dict(category='RESTRICTED_CASH', reason='Issuer explicitly reports no pledged/frozen cash; no separate addback', references=[facts['restricted_cash_declared_2025']['version_id']]),
                        dict(category='NCI', reason='Total-parent equity difference0, all subsidiaries100% owned', references=[facts['nci_2025']['version_id']]),
                        dict(category='NONOPERATING_ASSETS', reason='No addback beyond cash; exhaustive2025 balance-line residual0, no claim of economic value0; finance deposits already included once in cash', references=[facts['noncash_asset_boundary']['version_id']]),
                        dict(category='ASSOCIATES', reason='Fully impaired book value, conservative assumed no economic recovery addback; excluded from core profit', references=[facts['associate_boundary']['version_id']])],
            overlap_reason='Cash excluded from earnings before adding excess cash; all debt/lease/repurchase obligations deducted once; no separate inventory-share or associate addback'), limitations=limits,
        valuation_basis=dict(valuation_basis_date='2025-12-31', financial_period_end='2025-12-31', bridge_as_of='2025-12-31', latest_known_financial_period_end='2026-09-30', current_pricing_gaps=['2026Q3 bridge, investment assets and capital commitments not fully reconciled;2025 bridge is not current']))
    def audit(reason, keys, conditions):
        return dict(reason=reason, support_fact_version_ids=[facts[k]['version_id'] for k in keys], counter_fact_version_ids=[], limitations=conditions)
    wacc_audits = {
        'risk_free': audit('Use dated2025-12-31 CNY10Y government yield1.8473% as riskfree benchmark proxy; no additional default-spread subtraction under this convention.', ['cny_10y_govt_yield_20251231'], ['Government benchmark is a proxy; other defaultfree conventions change discount rate']),
        'beta': audit(f'Cash-corrected unlevered global soft-beverage beta0.54 * (1+(1-25%)*{float(interest_debt)}/{market_equity}) = {beta}; industry business-risk proxy relevered using issuer debt/equity proxy.', ['global_soft_beverage_cash_corrected_unlevered_beta', 'approx_market_equity_value_20251231', 'bank_loans_including_current_2025', 'lease_liabilities_including_current_2025'], ['Jan2026 global94-firm industry proxy is not a measured000848 equity beta; marketE rounded and bookD proxies market debt']),
        'equity_risk_premium': audit('Author Jan5 2026 China rating-based totalERP5.14%=mature4.23%+country0.91%; use total once with beta-scaled common country exposure.', ['china_equity_risk_premium'], ['After-anchor public source, current acquisition, not2025 historical PIT; country exposure scaling is a simplifying convention']),
        'cost_of_debt': audit('Use disclosed2025 guaranteed-loan2.99% as conservative upper historical borrowing-cost proxy; credit-loan range2.44%-2.88%.', ['guaranteed_debt_rate'], ['Proxy for forward debt cost, not a current quote or duration-matched bond yield']),
        'equity_weight': audit(f'E/(D+E)={market_equity}/({float(interest_debt)}+{market_equity})={ew}; excludes repurchase and capital AP from interest-bearing WACC D.', ['approx_market_equity_value_20251231', 'bank_loans_including_current_2025', 'lease_liabilities_including_current_2025'], ['Rounded marketE and book interestD approximation; not arbitrary target weights']),
        'debt_weight': audit(f'D/(D+E)={float(interest_debt)}/({float(interest_debt)}+{market_equity})={dw}; only bank+capitalized-lease debt receives shield.', ['bank_loans_including_current_2025', 'lease_liabilities_including_current_2025', 'approx_market_equity_value_20251231'], ['BookD proxies nontraded market debt; repurchase/capital AP only in bridge']),
        'tax_rate': audit('Disclosed statutory25% rate applied to positive operating profit and assumed usable interest tax shield; current cash tax need not equal this accrual proxy.', ['statutory_tax_rate'], ['No automatic tax refund on losses; future shield usability is conditional'])}
    ab = {'config/wacc': audit(f'WACC=(RF+relevered beta*China totalERP)*wE + historical debt cost*(1-tax)*wD = {wacc}; no duplicate country premium.',
              ['cny_10y_govt_yield_20251231', 'china_equity_risk_premium', 'global_soft_beverage_cash_corrected_unlevered_beta', 'approx_market_equity_value_20251231'], ['Industry/country/rounded-capital proxies; see each constituent audit']),
          'config/terminal_g': audit('Zero nominal steady growth is a conservative no-expansion scenario, not extrapolation of2025 CFO release or a statement of actual future demand.', ['revenue_2025', 'revenue_2024', 'cash_capex_2025'], ['Flat volume, price and mix must hold; optional expansion benefits excluded']),
          'config/equity_bridge/1/amount': audit(f'Collectible cash4032137003.56 minus reserve({revenue}-{facts["core_profit_2025"]["value"]})/4={reserve}; excess cash={excess_cash}. Finance income excluded from EBIT.',
              ['cash_total_2025', 'cash_at_related_finance_company_2025', 'core_profit_2025'], ['Quarter operating-expense proxy includes noncash costs; reserve adequacy and counterparty recovery not independently appraised'])}
    for path in dp:
        if path.startswith('basis/wacc/'):
            ab['drivers/' + path] = wacc_audits[path.rsplit('/', 1)[-1]]
        elif path.startswith('basis/terminal/roic/'):
            name = path.rsplit('/', 1)[-1]
            ab['drivers/' + path] = audit(f'Endogenous steady NOPAT/normalized capital proxy={terminal_roics[name]}; capital=parent equity+bridge obligations-excess cash, no growth net reinvestment required.',
                ['core_profit_2025', 'total_equity_2025', 'bridge_debt_2025', 'cash_total_2025'], ['Steady capital-turnover and retained operating-cash reserve are assumptions; ROIC not independent validation'])
        elif path.endswith('base_revenue'):
            ab['drivers/' + path] = audit('Base revenue equals actual2025 consolidated revenue without scale conversion; flat fixed mix links volume/price growth to whole-group revenue.', ['revenue_2025'], ['Model uses full consolidated revenue, not group profit divided by partial product tonnage'])
        else:
            field = path.rsplit('/', 1)[-1]
            data = {
                'volume_growth': ('Flat aggregate sales-activity volume index with fixed product mix; actual2025/24 consolidated revenues are the demand anchors.', ['revenue_2025', 'revenue_2024'], ['Scenario assumption, not a reported physical group volume series']),
                'price_growth': ('Flat nominal price/mix index; primary beverage source separately gives revenue/ton and other revenue, no group unit-profit inference.', ['revenue_2025', 'revenue_2024'], ['Price/mix and seasonality may change; no retail per-can price claim']),
                'operating_margin': ('Begin at reported2025 operating-profit/revenue, apply single explicit normalization: remove finance/other gains/impairments, then2024 core-margin benchmark or22% margin stress.', ['reported_operating_profit_2025', 'core_profit_2025', 'core_profit_2024', 'revenue_2025'], ['Core-profit definition, benchmark and stress are research choices; recurring impairments may differ']),
                'tax_rate': ('Use disclosed statutory25% operating-tax proxy; accrued statutory tax differs from actual cash tax.', ['statutory_tax_rate'], ['No tax-loss refund credited; future tax policy and deductions may differ']),
                'depreciation': ('Carry full2025 fixed+ROU+intangible+deferred amortization total47326934.25 into stable asset base.', ['da_2025'], ['Not a projection of future expansion commissioning or accelerated depreciation']),
                'maintenance_capex': ('Assume maintenance and capitalized lease renewals equal full D&A47326934.25; actual cashcapex184906387.79 shown separately and not called maintenance.', ['da_2025', 'cash_capex_2025'], ['Replacement spending can exceed D&A; optional expansion excluded; recognized capital AP deducted separately once']),
                'growth_capex': ('Zero incremental growth capex in the no-growth scenario;2025 actualcapex and material-commitment disclosure retained, recognized capital AP bridge deducted once.', ['cash_capex_2025', 'capital_project_payables_2025'], ['No unearned expansion benefit; no-disclosed-important-commitment is not a forecast of zero future spending']),
                'delta_working_capital': ('Steady-state delta operating NWC0; do not repeat2025 CFO inventory/receivable/payable release276916417.60. Goods AP and capital AP remain separated.', ['cash_recon_inventory_decrease_2025', 'cash_recon_operating_receivables_decrease_2025', 'cash_recon_operating_payables_increase_2025'], ['Flat steady balances assumed; actual full operating NWC classification requires further future reconciliation']),
                'invested_capital': (f'Normalized capital proxy={capital}=parent equity3490498161.46 + bridge obligations{debt} - assumed excess cash{excess_cash}; cash reserve remains operational.', ['total_equity_2025', 'bridge_debt_2025', 'cash_total_2025'], ['Capital/ROIC proxy depends on explicit reserve/obligation treatment, stable turnover only'])}
            ab['drivers/' + path] = audit(*data[field])
    basis['assumption_basis'] = ab
    command = OperatingValuationCommand(snapshot_id=snapshot['snapshot_id'], config=cfg, assumptions=assumptions, provenance=provenance,
        drivers=dict(scenarios=scenarios, normalizations=adjustments, provenance=dp), economic_basis=basis,
        change_reason='Real-source2025 financial baseline conditional model; preserve current-pricing gaps', idempotency_key='real-lulu-baseline-v1')
    result = research.calculate_operating_valuation(command)
    view = research.valuation_presentation(result['review_id'], 'BASELINE_RESEARCH')
    current = research.valuation_presentation(result['review_id'])
    assert view['review']['status'] == 'conditional', view['review']['checks']
    assert current['usable_range'] is False and current['scenarios'] == []
    receipt = dict(kind='REAL_SOURCE_DATED_CONDITIONAL_VALUATION', data_directory=str(target), company=identity,
        result=result, baseline_view=view, current_view=current, financial_facts=facts,
        actual_cfo_2025=source_facts['cfo_2025']['value'], actual_cash_capex_2025=source_facts['cash_capex_2025']['value'],
        cfo_less_capex_label='MECHANICAL_NOT_NORMALIZED_FCFF', source_hashes={k: v['sha256'] for k, v in raw_notes['sources'].items()},
        import_received_at=[m['received_at'] for m in [*materials.values(), *external_materials, q3_material]], live_source_calls=0, model_calls=0,
        historic_pit_eligible=False, current_pricing_accepted=False)
    write(Path(args.output), receipt)
    write(Path(args.output).with_name('real-lulu-command.json'), command.model_dump())
    write(Path(args.output).with_name('real-lulu-operating-model.json'), research.operating_model(result['operating_model_id']))
    print(json.dumps(dict(result=result, baseline_status=view['review']['status'], current_status=current['status'], model_calls=0), ensure_ascii=False))


if __name__ == '__main__':
    main()
