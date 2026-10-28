import copy
import pytest


def operating_request(research):
    from test_valuation import valuation_request
    from roll.research.company import OperatingValuationCommand, MaterialCommand, FactCommand, AnalysisCommand
    from test_shared_evidence import material_input
    from test_analysis_snapshots import candidate
    from datetime import datetime, timezone
    base, snapshot = valuation_request(research)
    issuer = research.company(snapshot['company_id'])
    mat = material_input(issuer['company_id']); mat.update(source_id='METHOD-rates', unit='ratio', currency=None)
    material = research.import_material(MaterialCommand(**mat), b'METHOD observed riskfree annual ratio0.04; source is synthetic, not market data')
    rf = research.add_fact(FactCommand(company_id=issuer['company_id'], material_id=material['material_id'],
        metric='risk_free', business='MACRO', value='.04', value_type='NUMBER', unit='ratio', currency=None,
        scope='CONSOLIDATED', period_start='2025-01-01', period_end='2025-12-31', page='METHOD', change_reason='METHOD source anchor'))
    packet = research.freeze_analysis(AnalysisCommand(company_id=issuer['company_id'], as_of=datetime.now(timezone.utc).isoformat(),
        fact_version_ids=snapshot['fact_version_ids'] + [rf['version_id']], parent_snapshot_id=snapshot['snapshot_id']))
    cand = candidate(packet, research.fact(snapshot['fact_version_ids'][0]))
    cand['hypotheses'][0]['previous_version_id'] = snapshot['hypothesis_version_ids'][0]
    snapshot = research.apply_analysis_candidate(packet['input_id'], cand)
    base.snapshot_id = snapshot['snapshot_id']
    base.assumptions[0]['hypothesis_version_ids'] = snapshot['hypothesis_version_ids']
    base.config.pop('scenarios')
    base.provenance = {k: v for k, v in base.provenance.items() if not k.startswith('scenarios/')}
    for path, p in base.provenance.items():
        if path == 'shares' or path.startswith('equity_bridge/'):
            p['period'] = '2025-01-01/2025-12-31'
    year = dict(period='2026-01-01/2026-12-31', revenue_growth=0,
                operating_margin=.2, tax_rate=.25, depreciation=20,
                maintenance_capex=20, growth_capex=0, delta_working_capital=0,
                invested_capital=500)
    drivers = dict(scenarios=[dict(name='base', base_revenue=1000,
        years=[year, dict(year, period='2027-01-01/2027-12-31')])], normalizations=[], provenance={})
    ratios = {'revenue_growth', 'operating_margin', 'tax_rate'}
    for si, scenario in enumerate(drivers['scenarios']):
        for path, value in [('base_revenue', scenario['base_revenue'])]:
            drivers['provenance'][f'scenarios/{si}/{path}'] = dict(base.provenance['equity_bridge/0/amount'])
        for yi, row in enumerate(scenario['years']):
            for key in row.keys() - {'period'}:
                p = dict(base.provenance['equity_bridge/0/amount'], period=row['period'])
                if key in ratios: p.update(unit='ratio', currency=None)
                drivers['provenance'][f'scenarios/{si}/years/{yi}/{key}'] = p
    ref = snapshot['fact_version_ids'][0]
    basis = dict(applicability=dict(category='NON_FINANCIAL', reason='METHOD ordinary industrial issuer', references=[ref]),
        wacc=dict(risk_free=.04, beta=1, equity_risk_premium=.06, cost_of_debt=.05,
                  equity_weight=1, debt_weight=0, tax_rate=.25, currency='CNY', as_of='2026-10-26',
                  tax_shield_reason='Debt weight zero; no tax shield benefit', references=[rf['version_id']]),
        terminal=dict(roic=.3, maintenance_reason='Maintenance capex equals depreciation in steady state', references=[ref]),
        bridge=dict(shares_reason='METHOD total diluted shares', references=[ref],
                    components=[dict(component_id='debt', economic_id='debt', included_in_fcff=False, category='DEBT', amount=300, reason='Deduct debt', references=[ref]),
                                dict(component_id='cash', economic_id='cash', included_in_fcff=False, category='CASH', amount=-100, reason='Unrestricted nonoperating cash only', references=[ref])],
                    exclusions=[dict(category=c, reason='METHOD absent', references=[ref]) for c in
                                ['RESTRICTED_CASH', 'NCI', 'NONOPERATING_ASSETS', 'ASSOCIATES']],
                    overlap_reason='Each component excluded from operating earnings and other bridge rows'),
        limitations=['METHOD forecast assumptions; no investment recommendation'])
    for key in ['risk_free', 'beta', 'equity_risk_premium', 'cost_of_debt', 'equity_weight', 'debt_weight', 'tax_rate']:
        drivers['provenance']['basis/wacc/' + key] = dict(base.provenance['wacc'])
    drivers['provenance']['basis/terminal/roic'] = dict(base.provenance['wacc'])
    # Fully sourced METHOD anchors: each role has a separate numeric source fact.
    anchor_values = {'revenue': (1000, 'million', 'CNY'), 'cash': (100, 'million', 'CNY'), 'debt': (300, 'million', 'CNY'),
        'share_count': (100, 'million_shares', None), 'depreciation': (20, 'million', 'CNY'), 'maintenance_capex': (20, 'million', 'CNY'),
        'growth_capex': (0, 'million', 'CNY'), 'delta_working_capital': (0, 'million', 'CNY'), 'invested_capital': (500, 'million', 'CNY'),
        'operating_margin': (.2, 'ratio', None), 'tax_rate': (.25, 'ratio', None), 'revenue_growth': (0, 'ratio', None),
        'beta': (1, 'ratio', None), 'equity_risk_premium': (.06, 'ratio', None), 'debt_rate': (.05, 'ratio', None), 'roic': (.3, 'ratio', None)}
    role_facts = {'risk_free': rf}
    mats = {}
    for metric, (value, unit, currency) in anchor_values.items():
        if unit not in mats:
            m = material_input(issuer['company_id']); m.update(source_id='METHOD-input-' + unit, unit=unit, currency=currency)
            mats[unit] = research.import_material(MaterialCommand(**m), ('METHOD input anchors for ' + unit).encode())
        role_facts[metric] = research.add_fact(FactCommand(company_id=issuer['company_id'], material_id=mats[unit]['material_id'], metric=metric,
            business='METHOD_ECONOMIC_ANCHOR', value=str(value), unit=unit, currency=currency, scope='CONSOLIDATED', period_start='2025-01-01', period_end='2025-12-31', change_reason='Synthetic worked-example anchor, no real financial claim'))
    packet = research.freeze_analysis(AnalysisCommand(company_id=issuer['company_id'], as_of=datetime.now(timezone.utc).isoformat(),
        fact_version_ids=snapshot['fact_version_ids'] + [f['version_id'] for f in role_facts.values() if f['version_id'] not in snapshot['fact_version_ids']], parent_snapshot_id=snapshot['snapshot_id']))
    cand = candidate(packet, research.fact(snapshot['fact_version_ids'][0])); cand['hypotheses'][0]['previous_version_id'] = snapshot['hypothesis_version_ids'][0]
    snapshot = research.apply_analysis_candidate(packet['input_id'], cand)
    base.snapshot_id = snapshot['snapshot_id']; base.assumptions[0]['hypothesis_version_ids'] = snapshot['hypothesis_version_ids']
    base.assumptions[0]['anchor_fact_version_ids'] = snapshot['fact_version_ids']
    basis['valuation_basis'] = dict(valuation_basis_date='2025-12-31', financial_period_end='2025-12-31', bridge_as_of='2025-12-31', latest_known_financial_period_end='2025-12-31', current_pricing_gaps=[])
    basis['assumption_basis'] = {}
    for path, p in [('config/' + k, p) for k, p in base.provenance.items()] + [('drivers/' + k, p) for k, p in drivers['provenance'].items()]:
        field = path.rsplit('/', 1)[-1]
        metric = {'shares': 'share_count', 'wacc': 'risk_free', 'terminal_g': 'revenue_growth', 'base_revenue': 'revenue',
            'cost_of_debt': 'debt_rate', 'equity_weight': 'debt', 'debt_weight': 'debt'}.get(field, field)
        if path.startswith('config/equity_bridge/'): metric = 'debt' if '/0/' in path else 'cash'
        basis['assumption_basis'][path] = dict(reason='METHOD explicit steady-state or capital-policy assumption anchored to the named quantitative input; supported only for the worked example',
            support_fact_version_ids=[role_facts[metric]['version_id']], counter_fact_version_ids=[], limitations=[])
    return OperatingValuationCommand(**base.model_dump(), drivers=drivers, economic_basis=basis), snapshot


def test_operating_drivers_build_fcff_and_conditional_view_without_mutating_diagnostic(tmp_path):
    from test_shared_evidence import service
    research = service(tmp_path)
    command, original = operating_request(research)
    result = research.calculate_operating_valuation(command)
    model = research.operating_model(result['operating_model_id'])
    # Worked example: revenue1000 * margin20%=EBIT200, tax50, NOPAT150;
    # + depreciation20 - maintenance20 - growth0 - NWC0 = FCFF150.
    row = model['cashflows'][0]['years'][0]
    assert (row['revenue'], row['operating_profit'], row['tax'], row['nopat'], row['fcff']) == (1000, 200, 50, 150, 150)
    assert row['derivation']['formula'] == 'NOPAT + depreciation - maintenance_capex - growth_capex - delta_working_capital'
    view = research.valuation_presentation(result['review_id'], 'BASELINE_RESEARCH')
    assert view['review']['status'] == 'conditional' and view['usable_range'] is True
    assert view['scenarios'][0]['per_share'] == pytest.approx(13)
    raw = research.valuation(result['valuation_id'])
    assert raw['result']['review']['status'] == 'unreviewed' and raw['result']['usable_range'] is False
    assert research.analysis_snapshot(original['snapshot_id']) == original
    enriched = research.analysis_snapshot(result['snapshot_id'], 'REPORT')
    assert enriched == research.analysis_snapshot(result['snapshot_id'], 'DAILY')
    assert enriched['parent_snapshot_id'] == original['snapshot_id']
    assert enriched['valuation_ids'] == [raw['valuation_id']]
    assert enriched['economic_review_ids'] == [result['review_id']]
    assert research.calculate_operating_valuation(command) == result


def test_growth_without_reinvestment_and_unsupported_wacc_cannot_publish_prices(tmp_path):
    from test_shared_evidence import service
    research = service(tmp_path)
    command, _ = operating_request(research)
    command.drivers['scenarios'][0]['years'][0]['revenue_growth'] = .1
    command.economic_basis['wacc']['references'] = []
    result = research.calculate_operating_valuation(command)
    view = research.valuation_presentation(result['review_id'], 'BASELINE_RESEARCH')
    assert view['review']['status'] == 'blocked' and view['scenarios'] == []
    checks = {r['check_id']: r for r in view['review']['checks']}
    assert checks['base/0/growth_reinvestment']['status'] == 'BLOCKED'
    assert checks['wacc_evidence']['status'] == 'BLOCKED'
    assert research.valuation(result['valuation_id'])['result']['scenarios']
    assert all(r['missing_path'] for r in checks.values() if r['status'] == 'BLOCKED')


def test_normalization_is_applied_once_with_before_after_formula_and_original_evidence(tmp_path):
    from test_shared_evidence import service
    research = service(tmp_path)
    command, _ = operating_request(research)
    ref = command.config['metadata']['sources'][0]
    command.drivers['normalizations'] = [dict(adjustment_id='tax-basis', target='scenarios/0/years/0/tax_rate',
        before=.25, delta=.025, after=.275, formula='before + delta', reason='METHOD one-year effective operating tax normalization', references=[ref],
        provenance={k: dict(command.drivers['provenance']['scenarios/0/years/0/tax_rate']) for k in ['before', 'delta', 'after']})]
    result = research.calculate_operating_valuation(command)
    model = research.operating_model(result['operating_model_id'])
    assert model['cashflows'][0]['years'][0]['fcff'] == 145
    assert research.economic_review(result['review_id'])['status'] == 'conditional'
    assert model['request']['drivers']['normalizations'][0]['before'] == .25
    other = service(tmp_path / 'duplicate')
    duplicate, _ = operating_request(other)
    ref = duplicate.config['metadata']['sources'][0]
    normalization = copy.deepcopy(command.drivers['normalizations'][0]); normalization['references'] = [ref]
    duplicate.drivers['normalizations'] = [normalization, dict(normalization, adjustment_id='same-adjustment-new-name')]
    result = other.calculate_operating_valuation(duplicate)
    assert other.economic_review(result['review_id'])['status'] == 'blocked'
    assert other.valuation_presentation(result['review_id'], 'BASELINE_RESEARCH')['scenarios'] == []


def test_bridge_disguised_duplicate_and_terminal_roic_mismatch_block_economic_review(tmp_path):
    from test_shared_evidence import service
    research = service(tmp_path)
    command, _ = operating_request(research)
    command.economic_basis['bridge']['components'][1]['economic_id'] = 'debt'
    command.economic_basis['terminal']['roic'] = .5
    result = research.calculate_operating_valuation(command)
    view = research.valuation_presentation(result['review_id'], 'BASELINE_RESEARCH')
    assert view['review']['status'] == 'blocked' and view['scenarios'] == []
    checks = {c['check_id']: c for c in view['review']['checks']}
    assert checks['equity_bridge']['status'] == 'BLOCKED'
    assert checks['base/terminal_reinvestment']['status'] == 'BLOCKED'


def test_frozen_cyclical_group_evidence_cannot_be_bypassed_by_plain_category_or_strings(tmp_path):
    from datetime import datetime, timezone
    from test_shared_evidence import service
    from test_analysis_snapshots import evidence, candidate
    from roll.research.company import AnalysisCommand, MaterialCommand, FactCommand
    from test_shared_evidence import material_input
    research = service(tmp_path)
    command, original = operating_request(research)
    issuer = research.company(original['company_id'])
    text = 'Copper LME commodity price cycle; trading business and financial segment plus associate scope remain unreconciled'
    material = research.import_material(MaterialCommand(**material_input(issuer['company_id'])), text.encode())
    fact = research.add_fact(FactCommand(company_id=issuer['company_id'], material_id=material['material_id'], metric='separate_operating_scope', business='BUSINESS_SCOPE', value=text, value_type='TEXT', unit='CNY_MILLION', currency='CNY', scope='CONSOLIDATED', period_start='2025-01-01', period_end='2025-12-31', change_reason='METHOD separate scope series'))
    packet = research.freeze_analysis(AnalysisCommand(company_id=issuer['company_id'], as_of=datetime.now(timezone.utc).isoformat(),
        fact_version_ids=original['fact_version_ids'] + [fact['version_id']], parent_snapshot_id=original['snapshot_id']))
    cand = candidate(packet, fact)
    cand['hypotheses'][0]['previous_version_id'] = original['hypothesis_version_ids'][0]
    snapshot = research.apply_analysis_candidate(packet['input_id'], cand)
    command.snapshot_id = snapshot['snapshot_id']
    command.assumptions[0]['hypothesis_version_ids'] = []
    command.economic_basis['applicability'].update(category='NON_FINANCIAL', cycle_normalization='two-year mean', segment_basis='done')
    result = research.calculate_operating_valuation(command)
    view = research.valuation_presentation(result['review_id'], 'BASELINE_RESEARCH')
    assert view['review']['status'] == 'blocked' and view['scenarios'] == []
    checks = {c['check_id']: c for c in view['review']['checks']}
    assert checks['cycle_normalization']['status'] == 'BLOCKED'
    assert checks['segment_basis']['status'] == 'BLOCKED'
    # Dropping the known scope fact in a later freeze cannot erase the guard.
    revision = research.freeze_analysis(AnalysisCommand(company_id=issuer['company_id'], as_of=datetime.now(timezone.utc).isoformat(),
        fact_version_ids=original['fact_version_ids'], parent_snapshot_id=result['snapshot_id']))
    cand = candidate(revision, research.fact(original['fact_version_ids'][0]))
    cand['hypotheses'][0]['previous_version_id'] = snapshot['hypothesis_version_ids'][0]
    next_snapshot = research.apply_analysis_candidate(revision['input_id'], cand)
    command.snapshot_id = next_snapshot['snapshot_id']; command.idempotency_key = 'drop-scope'
    next_result = research.calculate_operating_valuation(command)
    assert research.economic_review(next_result['review_id'])['status'] == 'blocked'


def test_operating_api_and_backup_restore_pin_review_valuation_and_enriched_snapshot(tmp_path):
    from test_shared_evidence import service
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from roll.research.company.api import router
    from roll.runtime.backups import Backups, restore_at_start
    research = service(tmp_path / 'source')
    command, _ = operating_request(research)
    app = FastAPI(); app.include_router(router(research))
    with TestClient(app) as client:
        response = client.post('/api/company-research/operating-valuations', json=command.model_dump())
        assert response.status_code == 201, response.text
        result = response.json()
        model = client.get('/api/company-research/operating-models/' + result['operating_model_id']).json()
        view = client.get('/api/company-research/economic-reviews/' + result['review_id'] + '/presentation').json()
        snapshot = client.get('/api/company-research/snapshots/' + result['snapshot_id']).json()
    backups = Backups(research.ledger.path.parent)
    backup = backups.create()
    target = tmp_path / 'restored'
    recovery = Backups(target); recovery.stage_restore(backups.export(backup['backup_id'])); restore_at_start(recovery)
    restored = service(target)
    assert restored.operating_model(result['operating_model_id']) == model
    restored_view = restored.valuation_presentation(result['review_id'])
    assert {k: v for k, v in restored_view.items() if k != 'evaluated_at'} == {k: v for k, v in view.items() if k != 'evaluated_at'}
    assert restored.analysis_snapshot(result['snapshot_id'], 'REPORT') == snapshot
    assert restored.replay_valuation(result['valuation_id'])['matches_saved_result']


def test_unreviewed_diagnostic_public_view_hides_prices_and_model_cannot_self_upgrade(tmp_path):
    from test_shared_evidence import service
    from test_valuation import valuation_request
    from fastapi import HTTPException
    research = service(tmp_path)
    raw_command, _ = valuation_request(research)
    raw = research.calculate_valuation(raw_command)
    view = research.valuation_presentation(raw['valuation_id'])
    assert view['review']['status'] == 'unreviewed' and view['scenarios'] == [] and view['usable_range'] is False
    other = service(tmp_path / 'other')
    command, _ = operating_request(other)
    command.economic_basis['status'] = 'reviewed'
    with pytest.raises(HTTPException) as exc:
        other.calculate_operating_valuation(command)
    assert exc.value.detail['code'] == 'OPERATING_MODEL_INVALID'


def test_volume_price_drivers_and_year_end_reinvestment_fund_next_year_growth(tmp_path):
    from test_shared_evidence import service
    research = service(tmp_path)
    command, _ = operating_request(research)
    command.config.update(wacc=.2, terminal_g=.1)
    command.economic_basis['wacc']['equity_risk_premium'] = .16
    years = command.drivers['scenarios'][0]['years']
    years[0]['growth_capex'] = 50
    years[1].update(growth_capex=55, invested_capital=550)
    for yi, row in enumerate(years):
        p = command.drivers['provenance'].pop(f'scenarios/0/years/{yi}/revenue_growth')
        row.pop('revenue_growth')
        row['revenue_driver'] = dict(volume_growth=0 if yi == 0 else .1, price_growth=0)
        for field in ['volume_growth', 'price_growth']:
            command.drivers['provenance'][f'scenarios/0/years/{yi}/revenue_driver/{field}'] = dict(p)
            old_audit = command.economic_basis['assumption_basis'][f'drivers/scenarios/0/years/{yi}/revenue_growth']
            command.economic_basis['assumption_basis'][f'drivers/scenarios/0/years/{yi}/revenue_driver/{field}'] = dict(old_audit)
    result = research.calculate_operating_valuation(command)
    rows = research.operating_model(result['operating_model_id'])['cashflows'][0]['years']
    # Year1 invests50 at year end; year2 begins with550 capital vs500,
    # stable2x turnover gives1100 revenue,165 NOPAT less55 reinvestment=110 FCFF.
    assert [r['fcff'] for r in rows] == [100, 110]
    assert rows[1]['revenue'] == 1100 and rows[1]['normalized_inputs']['invested_capital'] == 550
    # PV100/1.2 +110/1.44 +121/(20%-10%)/1.44 = EV1000.
    view = research.valuation_presentation(result['review_id'], 'BASELINE_RESEARCH')
    assert view['review']['status'] == 'conditional'
    assert view['scenarios'][0]['enterprise_value'] == pytest.approx(1000)


def test_missing_temporal_basis_cannot_be_presented_as_current_usable_prices(tmp_path):
    from test_shared_evidence import service
    research = service(tmp_path)
    command, _ = operating_request(research)
    command.economic_basis.pop('valuation_basis', None)
    result = research.calculate_operating_valuation(command)
    assert research.valuation_presentation(result['review_id'], 'BASELINE_RESEARCH')['usable_range'] is False
    current = research.valuation_presentation(result['review_id'])
    assert current['status'] == 'blocked' and current['usable_range'] is False and current['scenarios'] == []
    assert current['current_pricing_gaps']


def test_financial_applicability_preserves_research_without_executing_fcff(tmp_path):
    from test_shared_evidence import service
    research = service(tmp_path)
    command, original = operating_request(research)
    command.economic_basis['applicability']['category'] = 'FINANCIAL'
    result = research.calculate_operating_valuation(command)
    review = research.economic_review(result['review_id'])
    assert review['applicability'] == 'NOT_APPLICABLE' and review['status'] == 'blocked'
    assert result['valuation_id'] is None
    assert research.operating_model(result['operating_model_id'])['cashflows'] == []
    snapshot = research.analysis_snapshot(result['snapshot_id'])
    assert snapshot['valuation_ids'] == [] and snapshot['core']['business_structure'] == original['core']['business_structure']
    assert research.valuation_presentation(result['review_id'])['scenarios'] == []


def test_business_text_cannot_be_used_as_quantitative_discount_rate_source(tmp_path):
    from test_shared_evidence import service
    research = service(tmp_path)
    command, _ = operating_request(research)
    command.economic_basis['wacc']['references'] = command.config['metadata']['sources']
    result = research.calculate_operating_valuation(command)
    review = research.economic_review(result['review_id'])
    assert review['status'] == 'blocked'
    assert next(c for c in review['checks'] if c['check_id'] == 'wacc_source_values')['status'] == 'BLOCKED'


@pytest.mark.parametrize('field,value', [('revenue_growth', -1), ('tax_rate', -0.1), ('tax_rate', 1.1),
    ('depreciation', -1), ('maintenance_capex', -1), ('growth_capex', -1), ('invested_capital', 0)])
def test_operating_numeric_domains_are_rejected(field, value, tmp_path):
    from test_shared_evidence import service
    from fastapi import HTTPException
    research = service(tmp_path)
    command, _ = operating_request(research)
    command.drivers['scenarios'][0]['years'][0][field] = value
    with pytest.raises(HTTPException) as exc: research.calculate_operating_valuation(command)
    assert exc.value.detail['code'] == 'INVALID_NUMBER'


def test_early_operating_losses_do_not_automatically_create_cash_tax_refunds(tmp_path):
    from test_shared_evidence import service
    research = service(tmp_path)
    command, _ = operating_request(research)
    command.drivers['scenarios'][0]['years'][0]['operating_margin'] = -.2
    result = research.calculate_operating_valuation(command)
    row = research.operating_model(result['operating_model_id'])['cashflows'][0]['years'][0]
    assert row['tax'] == 0 and row['nopat'] == -200 and row['fcff'] == -200


def test_reviewed_requires_complete_sourced_assumption_checks_and_cannot_be_requested(tmp_path):
    from test_shared_evidence import service, material_input
    from test_analysis_snapshots import candidate
    from roll.research.company import MaterialCommand, FactCommand, AnalysisCommand
    from datetime import datetime, timezone
    research = service(tmp_path)
    command, previous = operating_request(research)
    command.economic_basis['limitations'] = []
    command.economic_basis['valuation_basis'] = dict(valuation_basis_date='2025-12-31', financial_period_end='2025-12-31', bridge_as_of='2025-12-31', latest_known_financial_period_end='2025-12-31', current_pricing_gaps=[])
    result = research.calculate_operating_valuation(command)
    review = research.economic_review(result['review_id'])
    assert review['status'] == 'reviewed' and all(c['status'] == 'PASS' for c in review['checks'])
    assert research.valuation(result['valuation_id'])['result']['review']['status'] == 'unreviewed'
    assert research.valuation_presentation(result['review_id'])['status'] == 'blocked'  # stale bridge still prevents current pricing


def test_missing_critical_assumption_rationale_is_blocked_instead_of_usable_conditional(tmp_path):
    from test_shared_evidence import service
    research = service(tmp_path)
    command, _ = operating_request(research)
    command.economic_basis.pop('assumption_basis', None)
    result = research.calculate_operating_valuation(command)
    view = research.valuation_presentation(result['review_id'], 'BASELINE_RESEARCH')
    assert view['review']['status'] == 'blocked' and view['usable_range'] is False
    assert next(c for c in view['review']['checks'] if c['check_id'] == 'assumption/config/wacc')['status'] == 'BLOCKED'


def test_current_view_uses_read_time_and_detects_new_disclosures_without_rewriting_snapshot(tmp_path):
    from test_shared_evidence import service, material_input
    from roll.research.company import MaterialCommand, FactCommand
    research = service(tmp_path)
    command, original = operating_request(research)
    command.config['metadata']['as_of'] = '2025-12-31'
    command.economic_basis['wacc']['as_of'] = '2025-12-31'
    command.economic_basis['valuation_basis'] = dict(valuation_basis_date='2025-12-31', financial_period_end='2025-12-31', bridge_as_of='2025-12-31', latest_known_financial_period_end='2025-12-31', current_pricing_gaps=[])
    result = research.calculate_operating_valuation(command)
    saved = research.analysis_snapshot(result['snapshot_id'])
    current = research.valuation_presentation(result['review_id'])
    assert current['usable_range'] is False and current['evaluated_at'] > '2026-01-01'
    m = material_input(original['company_id']); m.update(source_id='METHOD-new-quarter', period_start='2026-01-01', period_end='2026-09-30')
    material = research.import_material(MaterialCommand(**m), b'METHOD issuer later quarter disclosure acquired after freeze')
    fact = research.add_fact(FactCommand(company_id=original['company_id'], material_id=material['material_id'], metric='latest_financial_disclosure', business='DISCLOSURE_AVAILABILITY',
        value='METHOD new quarterly filing', value_type='TEXT', unit='CNY_MILLION', currency='CNY', scope='CONSOLIDATED', period_start='2026-01-01', period_end='2026-09-30', change_reason='Actual new acquisition after snapshot freeze'))
    after = research.valuation_presentation(result['review_id'])
    assert fact['version_id'] in after['later_disclosure_fact_version_ids'] and after['scenarios'] == []
    assert research.analysis_snapshot(result['snapshot_id']) == saved
    assert research.valuation_presentation(result['review_id'], 'BASELINE_RESEARCH')['usable_range']
