import copy
import pytest


def test_perpetual_conditions_separate_rate_change_from_operating_evidence():
    from roll.research.company.change_calculator import compare_perpetuity
    result = compare_perpetuity(100, .1, 100, .08, 1000, 1250)
    assert result['old_value'] == 1000
    assert result['new_value'] == 1250
    assert result['value_change_fraction'] == .25
    assert result['operating_change'] is False
    assert result['new_price_conditions'] == {'fixed_old_rate_required_cashflow': 125, 'fixed_old_cashflow_required_rate': .08}
    assert result['market_cause_identified'] is False


def research_pair(research):
    from test_shared_evidence import company
    from test_analysis_snapshots import evidence, freeze, candidate
    issuer = research.register(company())
    _, fact = evidence(research, issuer)
    packet = freeze(research, issuer, fact)
    old = research.apply_analysis_candidate(packet['input_id'], candidate(packet, fact))
    _, new_fact = evidence(research, issuer, 'Feedstock interruption challenges refining contribution')
    packet = freeze(research, issuer, new_fact, parent_snapshot_id=old['snapshot_id'])
    draft = candidate(packet, new_fact)
    draft['hypotheses'][0].update(previous_version_id=old['hypothesis_version_ids'][0],
        support_fact_version_ids=[], counter_fact_version_ids=[new_fact['version_id']], change_reason='New interruption counterevidence')
    new = research.apply_analysis_candidate(packet['input_id'], draft)
    return old, new, new_fact


def test_change_set_freezes_explicit_snapshots_new_fact_and_hypothesis_counterevidence(tmp_path):
    from test_shared_evidence import service
    from roll.research.company import ChangeSetCommand
    research = service(tmp_path)
    old, new, fact = research_pair(research)
    saved = research.compare_snapshots(ChangeSetCommand(old_snapshot_id=old['snapshot_id'], new_snapshot_id=new['snapshot_id'], idempotency_key='compare'))
    assert set(saved['changes']) == {'OPERATING_EVIDENCE', 'PRICE', 'VALUATION_ASSUMPTION_OR_METHOD'}
    op = saved['changes']['OPERATING_EVIDENCE']
    assert op['new_fact_version_ids'] == [fact['version_id']]
    assert op['hypothesis_revisions'][0]['after']['counter_fact_version_ids'] == [fact['version_id']]
    assert op['facts'][0]['consumable_at'] == fact['consumable_at']
    assert research.change_set(saved['change_set_id']) == saved
    assert research.compare_snapshots(ChangeSetCommand(old_snapshot_id=old['snapshot_id'], new_snapshot_id=new['snapshot_id'], idempotency_key='compare')) == saved
    assert research.analysis_snapshot(old['snapshot_id']) == old
    assert saved['changes']['PRICE']['status'] == 'NOT_COMPARABLE'
    assert saved['quick_summary']['valuation_scenarios'] == []


def test_source_checks_are_frozen_independent_of_retained_operating_view_and_aging(tmp_path):
    from test_shared_evidence import service
    from roll.research.company import ChangeSetCommand, ResearchContextCommand, CheckCommand
    research = service(tmp_path)
    old, new, _ = research_pair(research)
    def failed(scope):
        raise TimeoutError('METHOD failure')
    success = research.check_source(CheckCommand(company_id=old['company_id'], source_id='METHOD', requested_scopes=['annual'], idempotency_key='success'), lambda scope: [])
    failure = research.check_source(CheckCommand(company_id=old['company_id'], source_id='METHOD', requested_scopes=['annual'], idempotency_key='failure'), failed)
    partial = research.check_source(CheckCommand(company_id=old['company_id'], source_id='METHOD', requested_scopes=['annual', 'quarter'], idempotency_key='partial'), lambda scope: [] if scope == 'annual' else failed(scope))
    bound = research.freeze_research_context(ResearchContextCommand(snapshot_id=new['snapshot_id'], check_ids=[success['check_id'], failure['check_id'], partial['check_id']], change_reason='Record actual completed attempts'))
    result = research.compare_snapshots(ChangeSetCommand(old_snapshot_id=new['snapshot_id'], new_snapshot_id=bound['snapshot_id'], source_max_age_seconds=0, idempotency_key='checks'))
    states = result['information_state']['new']['checks']
    assert [c['outcome'] for c in states] == ['SUCCESS_NO_NEW', 'FAILED', 'PARTIAL']
    assert all(c['aging_status'] == 'STALE' for c in states)
    assert states[1]['last_success_at'] == success['finished_at']
    assert states[1]['last_checked_at'] == failure['finished_at']
    assert states[2]['failed_scopes'] == ['quarter']
    assert result['changes']['OPERATING_EVIDENCE']['evidence_changed'] is False
    assert bound['as_of'] >= partial['finished_at']
    assert bound['research_basis_as_of'] == new['as_of']
    assert research.analysis_snapshot(new['snapshot_id']) == new


def quote_basis(research, snapshot, price=10, basis='RAW_NOMINAL'):
    from roll.research.company import MaterialCommand, FactCommand
    from test_shared_evidence import material_input
    from datetime import datetime, timezone, timedelta
    stamp = datetime.now(timezone.utc) - timedelta(seconds=1)
    day = stamp.astimezone(timezone(timedelta(hours=8))).date().isoformat()
    rows = []
    for lid, count, currency, value in [('SSE:600362', 60, 'CNY', price), ('HKEX:00358', 40, 'HKD', price)]:
        def fact(metric, number, unit, cur, scope):
            mat = material_input(snapshot['company_id']); mat.update(source_id='METHOD-' + metric, unit=unit, currency=cur, scope=scope, period_start=day, period_end=day)
            material = research.import_material(MaterialCommand(**mat), ('METHOD synthetic ' + metric + ' ' + str(number) + ' ' + basis).encode())
            return research.add_fact(FactCommand(company_id=snapshot['company_id'], material_id=material['material_id'], metric=metric, business='METHOD_QUOTE', value=str(number), unit=unit, currency=cur, scope=scope, period_start=day, period_end=day, change_reason='METHOD independent quote example'))['version_id']
        shares = fact('class_shares', count, 'million_shares', None, lid)
        quoted = fact('raw_nominal_price' if basis == 'RAW_NOMINAL' else 'unknown_adjusted_price', value, 'price_per_share', currency, lid)
        row = dict(listing_id=lid, shares=count, shares_unit='million_shares', shares_as_of=day, price=value, currency=currency,
            priced_at=stamp.isoformat(), share_refs=[shares], price_refs=[quoted], price_basis=basis)
        if currency == 'HKD':
            fx = fact('direct_fx', 1, 'ratio', None, 'HKD->CNY')
            row['fx'] = dict(rate=1, from_currency='HKD', to_currency='CNY', as_of=day, source_refs=[fx])
        rows.append(row)
    return rows


def test_price_only_fixes_old_paths_and_parameters_and_uses_all_listing_sources(tmp_path):
    from test_shared_evidence import service
    from test_economic_review import operating_request
    from roll.research.company import ChangeSetCommand, ResearchContextCommand
    research = service(tmp_path)
    command, _ = operating_request(research)
    value = research.calculate_operating_valuation(command)
    original = research.analysis_snapshot(value['snapshot_id'])
    old = research.freeze_research_context(ResearchContextCommand(snapshot_id=original['snapshot_id'], quotes=quote_basis(research, original, 10), change_reason='METHOD old quote'))
    new = research.freeze_research_context(ResearchContextCommand(snapshot_id=old['snapshot_id'], quotes=quote_basis(research, old, 12.5), change_reason='METHOD new quote'))
    change = research.compare_snapshots(ChangeSetCommand(old_snapshot_id=old['snapshot_id'], new_snapshot_id=new['snapshot_id'], idempotency_key='price'))
    price = change['changes']['PRICE']
    assert price['status'] == 'COMPARABLE' and price['changed'] is True
    assert price['fixed_old_config']['wacc'] == .1
    assert price['fixed_old_config']['scenarios'][0]['fcf'] == [150, 150]
    # Fixed years1/2 at150. Combined equity1000/1250; +200 bridge. N+1 requirement113.7/143.95.
    assert price['old_conditions'][0]['terminal_fcf_required'] == pytest.approx(113.7)
    assert price['new_conditions'][0]['terminal_fcf_required'] == pytest.approx(143.95)
    assert price['new_conditions'][0]['terminal_year'] == 3
    assert change['changes']['OPERATING_EVIDENCE']['evidence_changed'] is False
    assert change['quick_summary']['valuation_scenarios'] == []  # old bridge blocks current use
    assert change['counterfactual']['market_cause_identified'] is False
    assert research.operating_model(value['operating_model_id'])['request'] == command.model_dump()


@pytest.mark.parametrize('margin,rate,price,expected_steps,interaction', [
    (.22, .1, 10, [300, 450, 450, 450], 0),
    (.2, .08, 10, [300, 300, 300, 675], 0),
    (.22, .08, 12.5, [300, 450, 200, 612.5], 37.5)])
def test_pure_operating_method_and_mixed_changes_keep_order_and_interactions(tmp_path, margin, rate, price, expected_steps, interaction):
    from test_shared_evidence import service
    from test_economic_review import operating_request
    from roll.research.company import ResearchContextCommand, ChangeSetCommand
    research = service(tmp_path)
    command, _ = operating_request(research)
    initial = research.calculate_operating_valuation(command)
    snap = research.analysis_snapshot(initial['snapshot_id'])
    old = research.freeze_research_context(ResearchContextCommand(snapshot_id=snap['snapshot_id'], quotes=quote_basis(research, snap, 10), change_reason='METHOD baseline quote'))
    changed = command.model_copy(deep=True)
    changed.snapshot_id = old['snapshot_id']; changed.idempotency_key = 'new-method'
    changed.config['wacc'] = rate
    changed.economic_basis['wacc']['equity_risk_premium'] = rate - .04
    for row in changed.drivers['scenarios'][0]['years']: row['operating_margin'] = margin
    changed.economic_basis['terminal']['roic'] = margin * 1.5
    changed.change_reason = 'METHOD explicit operating/rate assumption revision, no new operating evidence'
    newer = research.calculate_operating_valuation(changed)
    current = research.analysis_snapshot(newer['snapshot_id'])
    new = research.freeze_research_context(ResearchContextCommand(snapshot_id=current['snapshot_id'], quotes=quote_basis(research, current, price), change_reason='METHOD comparison quote'))
    result = research.compare_snapshots(ChangeSetCommand(old_snapshot_id=old['snapshot_id'], new_snapshot_id=new['snapshot_id'], idempotency_key='mixed', presentation_purpose='BASELINE_RESEARCH'))
    assert result['changes']['OPERATING_EVIDENCE']['evidence_changed'] is False
    assert result['changes']['PRICE']['changed'] is (price != 10)
    counter = result['counterfactual']
    assert counter['status'] == 'COMPARABLE'
    assert [s['model_equity_minus_market']['base'] for s in counter['steps']] == pytest.approx(expected_steps)
    assert counter['interaction']['base'] == pytest.approx(interaction)
    assert counter['market_cause_identified'] is False and counter['diagnostic_only'] is True
    assert result['quick_summary']['valuation_scenarios'][0]['per_share'] == pytest.approx((expected_steps[-1] + price*100)/100)
    assert result['pinned_presentations'][1]['review']['review_id'] == newer['review_id']
    method = result['changes']['VALUATION_ASSUMPTION_OR_METHOD']
    assert method['before']['output']['scenarios'][0]['enterprise_value'] == pytest.approx(1500)
    assert method['after']['output']['scenarios'][0]['equity_value'] == pytest.approx(expected_steps[-1] + price*100)
    assert method['diagnostic_only'] is True and method['economic_review_upgraded'] is False


def test_context_and_change_set_api_restore_archives_and_replay_without_model(tmp_path):
    from test_shared_evidence import service
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from roll.research.company.api import router
    from roll.runtime.backups import Backups, restore_at_start
    research = service(tmp_path / 'source')
    old, new, _ = research_pair(research)
    app = FastAPI(); app.include_router(router(research))
    with TestClient(app) as client:
        context = client.post('/api/company-research/contexts', json=dict(snapshot_id=new['snapshot_id'], change_reason='METHOD immutable checkpoint'))
        assert context.status_code == 201, context.text
        latest = context.json()
        response = client.post('/api/company-research/change-sets', json=dict(old_snapshot_id=old['snapshot_id'], new_snapshot_id=latest['snapshot_id'], idempotency_key='api'))
        assert response.status_code == 201, response.text
        saved = response.json()
        assert client.get('/api/company-research/change-sets/' + saved['change_set_id']).json() == saved
    backups = Backups(research.ledger.path.parent)
    backup = backups.create()
    recovery = Backups(tmp_path / 'restored')
    recovery.stage_restore(backups.export(backup['backup_id'])); restore_at_start(recovery)
    restored = service(tmp_path / 'restored')
    assert restored.change_set(saved['change_set_id']) == saved
    assert restored.analysis_snapshot(latest['snapshot_id'], 'REPORT') == latest
    replay = restored.replay_change_set(saved['change_set_id'])
    assert replay['matches_saved_comparison'] is True
    assert replay['network_calls'] == replay['model_calls'] == 0
    assert restored.ledger.account()['version'] == 0


def test_reinterpreting_same_facts_is_not_new_operating_evidence_or_refreshed_material(tmp_path):
    from test_shared_evidence import service, company
    from test_analysis_snapshots import evidence, freeze, candidate
    from roll.research.company import ChangeSetCommand
    research = service(tmp_path)
    issuer = research.register(company()); _, fact = evidence(research, issuer)
    packet = freeze(research, issuer, fact)
    old = research.apply_analysis_candidate(packet['input_id'], candidate(packet, fact))
    packet = freeze(research, issuer, fact, parent_snapshot_id=old['snapshot_id'])
    draft = candidate(packet, fact); draft['hypotheses'][0].update(previous_version_id=old['hypothesis_version_ids'][0], change_reason='Same facts, reconsidered research judgment')
    new = research.apply_analysis_candidate(packet['input_id'], draft)
    result = research.compare_snapshots(ChangeSetCommand(old_snapshot_id=old['snapshot_id'], new_snapshot_id=new['snapshot_id'], idempotency_key='reinterpret'))
    assert result['changes']['OPERATING_EVIDENCE']['evidence_changed'] is False
    assert result['changes']['OPERATING_EVIDENCE']['hypothesis_revision_changed'] is True
    material = result['information_state']['new']['material_dates'][0]
    assert material['age_basis'] == 'REPORT_PERIOD_END'
    assert material['material_age_days'] > 180
    assert material['disclosed_at'] is None and material['disclosure_age_days'] is None
    assert result['information_state']['new']['research_verification_refreshed'] is False


def test_missing_or_adjusted_ah_quotes_remain_explicitly_incomparable_and_cannot_claim_raw_basis(tmp_path):
    from test_shared_evidence import service
    from test_economic_review import operating_request
    from roll.research.company import ResearchContextCommand, ChangeSetCommand
    from fastapi import HTTPException
    research = service(tmp_path)
    command, _ = operating_request(research)
    value = research.calculate_operating_valuation(command)
    snap = research.analysis_snapshot(value['snapshot_id'])
    old = research.freeze_research_context(ResearchContextCommand(snapshot_id=snap['snapshot_id'], quotes=quote_basis(research, snap), change_reason='METHOD complete old quote'))
    current = old
    for name, quotes in [('missing-H', quote_basis(research, old)[:1]), ('unknown-basis', quote_basis(research, old, basis='UNKNOWN')), ('adjusted', quote_basis(research, old, basis='ADJUSTED'))]:
        current = research.freeze_research_context(ResearchContextCommand(snapshot_id=current['snapshot_id'], quotes=quotes, change_reason='METHOD ' + name))
        result = research.compare_snapshots(ChangeSetCommand(old_snapshot_id=old['snapshot_id'], new_snapshot_id=current['snapshot_id'], idempotency_key=name))
        assert result['changes']['PRICE']['status'] == 'NOT_COMPARABLE'
        assert 'new_conditions' not in result['changes']['PRICE']
        assert result['counterfactual']['status'] == 'NOT_COMPARABLE'
        assert result['quick_summary']['valuation_scenarios'] == []
    spoofed = quote_basis(research, old, basis='UNKNOWN')
    for row in spoofed: row['price_basis'] = 'RAW_NOMINAL'
    with pytest.raises(HTTPException) as exc:
        research.freeze_research_context(ResearchContextCommand(snapshot_id=current['snapshot_id'], quotes=spoofed, change_reason='Cannot relabel unknown quote nominal'))
    assert exc.value.detail['code'] == 'QUOTE_BASIS_INVALID'
    assert old['as_of'] >= max(q['available_at'] for q in old['context']['quotes'])


@pytest.mark.parametrize('incompatible', ['units', 'currency', 'scope', 'horizon', 'method'])
def test_incompatible_valuation_bases_keep_both_references_without_subtraction(tmp_path, incompatible):
    from test_shared_evidence import service
    from test_economic_review import operating_request
    from roll.research.company import ChangeSetCommand
    research = service(tmp_path)
    command, _ = operating_request(research)
    previous = research.calculate_operating_valuation(command)
    old = research.analysis_snapshot(previous['snapshot_id'])
    changed = command.model_copy(deep=True); changed.snapshot_id=old['snapshot_id']; changed.idempotency_key='incompatible'
    if incompatible == 'method':
        changed.economic_basis['applicability']['category'] = 'FINANCIAL'
    elif incompatible == 'horizon':
        year = copy.deepcopy(changed.drivers['scenarios'][0]['years'][-1]); year['period']='2028-01-01/2028-12-31'
        changed.drivers['scenarios'][0]['years'].append(year)
        for key, p in list(changed.drivers['provenance'].items()):
            if key.startswith('scenarios/0/years/1/'):
                changed.drivers['provenance'][key.replace('/1/', '/2/')] = dict(p, period=year['period'])
    else:
        if incompatible == 'units': changed.config['metadata'].update(amount_unit='unit', shares_unit='share')
        if incompatible == 'currency': changed.config['metadata']['currency']='HKD'
        for p in [*changed.provenance.values(), *changed.drivers['provenance'].values()]:
            if incompatible == 'units': p['unit']={'million':'unit','million_shares':'share'}.get(p['unit'],p['unit'])
            if incompatible == 'currency' and p['currency']=='CNY': p['currency']='HKD'
            if incompatible == 'scope': p['scope']='SEGMENT_ONLY'
    newer = research.calculate_operating_valuation(changed)
    result = research.compare_snapshots(ChangeSetCommand(old_snapshot_id=old['snapshot_id'], new_snapshot_id=newer['snapshot_id'], idempotency_key='incompatible'))
    method = result['changes']['VALUATION_ASSUMPTION_OR_METHOD']
    assert method['status'] == 'NOT_COMPARABLE'
    assert method['old_snapshot_id'] == old['snapshot_id'] and method['new_snapshot_id'] == newer['snapshot_id']
    assert method['reason']
    assert result['counterfactual']['status'] == 'NOT_COMPARABLE' and 'steps' not in result['counterfactual']
    assert result['quick_summary']['valuation_scenarios'] == []


def test_backup_refuses_rehashed_context_quote_that_differs_from_its_source_fact(tmp_path):
    import json
    from test_shared_evidence import service
    from roll.research.company import ResearchContextCommand
    from roll.research.company.service import record
    from roll.accounts.ledger import encode
    from roll.runtime.backups import Backups
    from fastapi import HTTPException
    research = service(tmp_path)
    _, snapshot, _ = research_pair(research)
    bound = research.freeze_research_context(ResearchContextCommand(snapshot_id=snapshot['snapshot_id'], quotes=quote_basis(research, snapshot), change_reason='METHOD source binding check'))
    damaged = {k: copy.deepcopy(v) for k,v in bound.items() if k != 'content_sha256'}
    damaged['context']['quotes'][0]['row']['price'] = 999
    # Simulate external corruption with recomputed JSON/archive hashes. Observable seam is backup validation.
    with research.transaction() as db:
        archive = research.evidence.archive(encode(damaged['context']).encode(), 'COMPANY_RESEARCH_CONTEXT', db=db)
        damaged['context_archive'] = json.loads(db.execute('SELECT value FROM evidence_archives WHERE sha256=?', (archive['sha256'],)).fetchone()[0])
        db.execute('UPDATE company_research_snapshots SET value=? WHERE snapshot_id=?', (encode(record(damaged)), bound['snapshot_id']))
    with pytest.raises(HTTPException) as exc:
        Backups(tmp_path).create()
    assert exc.value.detail['code'] == 'RESEARCH_REFERENCE_INVALID'


def test_group_revenue_cannot_use_segment_margin_source_as_reviewed_group_cashflow(tmp_path):
    from test_shared_evidence import service, material_input
    from test_economic_review import operating_request
    from test_analysis_snapshots import candidate
    from roll.research.company import MaterialCommand, FactCommand, AnalysisCommand
    from datetime import datetime, timezone
    research = service(tmp_path)
    command, snapshot = operating_request(research)
    mat = material_input(snapshot['company_id']); mat.update(unit='ratio', currency=None, scope='PARTIAL_SEGMENT')
    material = research.import_material(MaterialCommand(**mat), b'METHOD partial segment margin0.2 cannot multiply consolidated revenue')
    fact = research.add_fact(FactCommand(company_id=snapshot['company_id'], material_id=material['material_id'], metric='operating_margin', business='PARTIAL_SEGMENT', value='.2', unit='ratio', currency=None, scope='PARTIAL_SEGMENT', period_start='2025-01-01', period_end='2025-12-31', change_reason='METHOD partial margin source'))
    packet = research.freeze_analysis(AnalysisCommand(company_id=snapshot['company_id'], as_of=datetime.now(timezone.utc).isoformat(), fact_version_ids=snapshot['fact_version_ids']+[fact['version_id']], parent_snapshot_id=snapshot['snapshot_id']))
    draft = candidate(packet, research.fact(snapshot['fact_version_ids'][0])); draft['hypotheses'][0]['previous_version_id']=snapshot['hypothesis_version_ids'][0]
    current = research.apply_analysis_candidate(packet['input_id'], draft)
    command.snapshot_id=current['snapshot_id']; command.assumptions[0]['hypothesis_version_ids']=current['hypothesis_version_ids']
    for year in range(2):
        # Labeling the forecast CONSOLIDATED does not reconcile a partial source.
        command.economic_basis['assumption_basis'][f'drivers/scenarios/0/years/{year}/operating_margin']['support_fact_version_ids']=[fact['version_id']]
    result = research.calculate_operating_valuation(command)
    assert research.economic_review(result['review_id'])['status'] == 'blocked'
    assert research.valuation_presentation(result['review_id'], 'BASELINE_RESEARCH')['scenarios'] == []
    assert research.valuation_presentation(result['review_id'])['scenarios'] == []
    assert any(c['check_id'] == 'operating_scope' and c['status'] == 'BLOCKED' for c in research.economic_review(result['review_id'])['checks'])
