"""Actual frozen JCC scope gaps plus explicitly symbolic numeric guard test.

This is not a financial forecast or a JCC value calculation. Original03store
is read only; imports and new economic records go into a new isolated store.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from roll.accounts.ledger import Ledger
from roll.market.directory import MarketDirectory
from roll.market.evidence import EvidenceStore
from roll.research.company import CompanyResearch, CompanyCommand, MaterialCommand, FactCommand, AnalysisCommand, OperatingValuationCommand

HERE = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser(); p.add_argument('--data-directory', required=True); p.add_argument('--source-data-directory', required=True); p.add_argument('--output', required=True)
    args = p.parse_args()
    directory = Path(args.data_directory)
    if directory.exists():
        raise RuntimeError('Choose a new empty isolated store')
    old = json.loads((HERE.parent / '03/real-input.json').read_text(encoding='utf-8'))
    source = old['payload']['materials'][0]
    raw = (Path(args.source_data_directory) / source['archive']['path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == '4493c7646001766896e6d4e3b97c702e9ee69423a86f8932df79e29bb75d5303'
    ledger = Ledger(directory); research = CompanyResearch(EvidenceStore(ledger, MarketDirectory(ledger)))
    company = research.register(CompanyCommand(legal_name=old['payload']['company']['legal_name'], jurisdiction='CN', industry='NON_FINANCIAL', accounting_standard='CAS', year_end='12-31',
        identity_basis='Frozen2025 issuer original identity, exact hash verified; this gate test does not turn symbolic numbers into facts',
        listings=[dict(exchange=l['exchange'], code=l['code'], share_class=l['share_class'], currency=l['currency']) for l in old['payload']['company']['listings']]))
    material = research.import_material(MaterialCommand(company_id=company['company_id'], source_id=source['source_id'], origin_root_id=source['origin_root_id'], source_url=source['source_url'],
        subject_name=company['legal_name'], media_type='application/pdf', scope=None, currency=None, unit=None, period_start='2025-01-01', period_end='2025-12-31', disclosed_at=None,
        limitations=['New import now, no original03store writes, no historical PIT']), raw)
    facts = []
    for oldfact in old['payload']['facts']:
        facts.append(research.add_fact(FactCommand(company_id=company['company_id'], material_id=material['material_id'],
            metric=oldfact['metric'], business=oldfact['business'], value=oldfact['value'], value_type='TEXT', unit=None, currency=None, scope=oldfact['scope'],
            period_start=oldfact['period_start'], period_end=oldfact['period_end'], page=oldfact['page'], change_reason='Retain exact previously frozen issuer excerpt and gap, no numeric interpretation')))
    ids = [f['version_id'] for f in facts]
    packet = research.freeze_analysis(AnalysisCommand(company_id=company['company_id'], as_of=datetime.now(timezone.utc).isoformat(), fact_version_ids=ids))
    claim = dict(text='The issuer discloses copper mining, processing and trading operations; group and partial-output scopes require separate reconciliation.', fact_version_ids=[ids[0]], gap_reason=None)
    snapshot = research.apply_analysis_candidate(packet['input_id'], dict(company_id=company['company_id'], input_sha256=packet['packet_sha256'], business_structure=[claim], attention_reasons=[], counterevidence=[], hypotheses=[],
        insufficient_hypotheses_reason='Reuse03 source excerpts to test economic gate; no new model invocation', limitations=['No full-cycle/segment operating profit and capital reconciliation'], valuation_unavailable_reason='Real source gaps not resolved'))
    template = json.loads((HERE / 'real-lulu-command.json').read_text(encoding='utf-8'))
    cfg = template['config']; cfg['metadata'].update(company=company['legal_name'], as_of=snapshot['as_of'], sources=ids, assumptions=['symbolic-gate-test'])
    cfg.update(shares=1, wacc=.1, terminal_g=0)
    for row in cfg['equity_bridge']: row.update(amount=0, source=ids[0], treatment='excluded')
    period = '2025-01-01/2025-12-31'

    def prov(unit='unit', period=period):
        return dict(kind='ASSUMED', references=['symbolic-gate-test'], unit=unit, currency='CNY' if unit == 'unit' else None, scope='CONSOLIDATED', period=period)

    provenance = {k: prov('share' if k == 'shares' else 'ratio' if k in {'wacc', 'terminal_g'} else 'unit') for k in template['provenance']}
    row = dict(period='2026-01-01/2026-12-31', revenue_growth=0, operating_margin=.2, tax_rate=.25, depreciation=.01, maintenance_capex=.01, growth_capex=0, delta_working_capital=0, invested_capital=.5)
    dp = {'scenarios/0/base_revenue': prov()}
    for key in row.keys() - {'period'}:
        dp['scenarios/0/years/0/' + key] = prov('ratio' if key in {'revenue_growth', 'operating_margin', 'tax_rate'} else 'unit', row['period'])
    basis = template['economic_basis']
    basis.pop('assumption_basis', None)  # No unrelated positive-company audit is reused.
    basis['applicability'] = dict(category='NON_FINANCIAL', reason='Deliberately ordinary-category claim to test frozen-source guard cannot be bypassed', references=[ids[0]])
    basis['wacc'].update(risk_free=.04, beta=1, equity_risk_premium=.06, cost_of_debt=.05, equity_weight=1, debt_weight=0, tax_rate=.25, as_of=snapshot['as_of'][:10], references=[ids[0]])
    basis['terminal'].update(roic=.3, references=[ids[0]])
    for key in ['risk_free', 'beta', 'equity_risk_premium', 'cost_of_debt', 'equity_weight', 'debt_weight', 'tax_rate']:
        dp['basis/wacc/' + key] = prov('ratio')
    dp['basis/terminal/roic'] = prov('ratio')
    basis['bridge']['references'] = [ids[0]]
    for item in basis['bridge']['components']: item.update(amount=0, references=[ids[0]])
    for item in basis['bridge']['exclusions']: item['references'] = [ids[0]]
    basis['valuation_basis'].update(latest_known_financial_period_end='2025-12-31', current_pricing_gaps=['Full copper cycle, industrial/trading/financial segments, equity production, associates and restricted cash remain unreconciled'])
    basis['limitations'] = ['ALL NUMBERS ARE SYMBOLIC METHOD INPUTS FOR THE GATE TEST, NOT JCC FINANCIAL FACTS OR FORECASTS', 'Two years are not a complete copper cycle; no segment profit/capital or associate reconciliation; no usable range']
    command = OperatingValuationCommand(snapshot_id=snapshot['snapshot_id'], config=cfg, provenance=provenance,
        assumptions=[dict(assumption_id='symbolic-gate-test', statement=basis['limitations'][0], anchor_fact_version_ids=ids, hypothesis_version_ids=[])],
        drivers=dict(scenarios=[dict(name='symbolic-guard-only', base_revenue=1, years=[row])], normalizations=[], provenance=dp), economic_basis=basis,
        change_reason='Demonstrate actual JCC source gaps remain blocked despite successful arithmetic and caller ordinary-category claim', idempotency_key='jcc-negative-v1')
    result = research.calculate_operating_valuation(command)
    view = research.valuation_presentation(result['review_id'], 'BASELINE_RESEARCH')
    checks = {c['check_id']: c for c in view['review']['checks']}
    assert view['review']['status'] == 'blocked' and view['scenarios'] == []
    assert checks['cycle_normalization']['status'] == checks['segment_basis']['status'] == 'BLOCKED'
    receipt = dict(kind='REAL_JCC_EVIDENCE_GAPS_WITH_SYMBOLIC_METHOD_NUMBERS', source_sha256=material['raw_sha256'], original03store_modified=False,
        result=result, view=view, real_source_count=1, numeric_financial_forecast=False, model_calls=0, network_calls=0)
    Path(args.output).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=view['review']['status'], cycle=checks['cycle_normalization']['status'], segment=checks['segment_basis']['status'], usable_range=False)))


if __name__ == '__main__':
    main()
