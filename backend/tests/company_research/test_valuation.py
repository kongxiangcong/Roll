import copy
import pytest


def issuer():
    return {"company_id": "issuer", "industry": "NON_FINANCIAL", "listings": [
        {"listing_id": "SSE:600001", "share_class": "A", "currency": "CNY"}]}


def config():
    return dict(metadata=dict(company="Issuer", as_of="2026-10-26", currency="CNY",
        amount_unit="million", shares_unit="million_shares", sources=["disclosed-anchor"],
        assumptions=["explicit-research-assumption"]), cash_flow_basis="FCFF", shares=100,
        equity_bridge=[dict(name="debt", amount=300, source="disclosed-anchor", treatment="deduct"),
                       dict(name="cash", amount=-100, source="disclosed-anchor", treatment="add")],
        wacc=.1, terminal_g=0, scenarios=[dict(name="base", fcf=[100, 100])])


def test_calculator_unweighted_full_paths_and_parent_equity_bridge():
    from roll.research.company.calculator import calculate
    result = calculate(config(), issuer())
    # Literal worked example: 100/1.1 + 100/1.21 + 1000/1.21 = 1000.
    # EV 1000 - debt 300 + cash 100 = parent equity 800 / 100 shares = 8.
    row = result["scenarios"][0]
    assert row["enterprise_value"] == pytest.approx(1000)
    assert row["equity_value"] == pytest.approx(800)
    assert row["per_share"] == pytest.approx(8)
    assert row["fcff"] == [100, 100]
    assert "weighted_per_share" not in result and "probability" not in row
    assert result["review"]["status"] == "unreviewed" and result["usable_range"] is False


def market_basis():
    return [dict(listing_id="SSE:600001", shares=60, shares_unit="million_shares",
                 shares_as_of="2026-10-26", price=10, currency="CNY",
                 priced_at="2026-10-26T07:00:00+00:00", share_refs=["shares-a"], price_refs=["price-a"]),
            dict(listing_id="HKEX:00001", shares=40, shares_unit="million_shares",
                 shares_as_of="2026-10-26", price=20, currency="HKD",
                 priced_at="2026-10-26T08:00:00+00:00", share_refs=["shares-h"], price_refs=["price-h"],
                 fx=dict(rate=.9, from_currency="HKD", to_currency="CNY",
                         as_of="2026-10-26", source_refs=["same-day-fx"]))]


def test_reverse_uses_frozen_ah_identity_and_complete_same_day_class_basis():
    from roll.research.company.calculator import calculate
    identity = issuer()
    identity["listings"].append(dict(listing_id="HKEX:00001", share_class="H", currency="HKD"))
    cfg = config()
    cfg["metadata"]["listing_structure"] = "A"  # Caller cannot conceal H listing.
    cfg["reverse"] = dict(scenario="base", price=10)
    refused = calculate(cfg, identity)
    assert refused["reverse"]["error"]["code"] == "AH_BASIS_INCOMPLETE"
    assert refused["scenarios"][0]["per_share"] == pytest.approx(8)
    cfg["reverse"] = dict(scenario="base", market_basis=market_basis(),
                          steady_margins=[.1], base_revenue=1000,
                          comparable_margin_basis="Same consolidated FCFF/revenue at steady state")
    result = calculate(cfg, identity)["reverse"]
    # Equity = 60*10 + 40*20*.9 = 1320; EV = 1520.
    # (1520 - 100/1.1 - 100/1.21) * 1.21 * .1 = 162.92.
    assert result["market_equity_value"] == pytest.approx(1320)
    assert result["terminal_fcf_required"] == pytest.approx(162.92)
    assert result["terminal_year"] == 3
    assert result["rows"][0]["terminal_revenue_required"] == pytest.approx(1629.2)
    assert result["rows"][0]["revenue_cagr_to_terminal_year"] == pytest.approx(.176679355108605)
    for change in [lambda r: r["market_basis"].pop(),
                   lambda r: r["market_basis"][1].pop("fx"),
                   lambda r: r["market_basis"][1].update(priced_at="2026-10-25T08:00:00+00:00"),
                   lambda r: r.update(market_equity_value=1320),
                   lambda r: r["market_basis"][1].update(shares_unit="share")]:
        bad = copy.deepcopy(cfg); change(bad["reverse"])
        assert calculate(bad, identity)["reverse"]["error"]["code"] == "AH_BASIS_INCOMPLETE"


def test_calculator_diagnostics_limits_bridge_and_normalized_epv():
    from roll.research.company.calculator import calculate, perpetuity
    assert perpetuity(100, .1) == 1000
    assert perpetuity(100, .08) == 1250
    cfg = config()
    cfg["scenarios"][0]["fcf"] = [-100, 120]
    cfg["sensitivity"] = dict(scenario="base", wacc=[.1, .12], terminal_g=[0, .02])
    cfg["epv"] = dict(normalized_fcff=100)
    r = calculate(cfg, issuer())
    assert r["scenarios"][0]["enterprise_value"] == pytest.approx(1000)
    assert r["epv"]["status"] == "NOT_APPLICABLE"
    cfg["epv"].update(applicability="APPLICABLE", normalization_basis="After maintenance capex; disclosed normalization schedule")
    r = calculate(cfg, issuer())
    assert r["epv"]["per_share"] == pytest.approx(8)
    assert r["epv"]["independent_validation"] is False
    assert len(r["sensitivity"]) == 4
    for edit in [lambda c: c.update(wacc=0), lambda c: c.update(wacc=0.0, terminal_g=0.0),
                 lambda c: c.update(shares=float("nan")), lambda c: c.update(net_debt=0),
                 lambda c: c["metadata"].update(shares_unit="share"),
                 lambda c: c["scenarios"][0].update(fcf=[100, -1]),
                 lambda c: c["equity_bridge"].append(dict(name=" DEBT ", amount=300, source="same debt", treatment="deduct")),
                 lambda c: c["equity_bridge"][0].update(treatment="add"),
                 lambda c: c.update(review=dict(status="reviewed", limitations=[]))]:
        bad = copy.deepcopy(cfg); edit(bad)
        with pytest.raises(ValueError):
            calculate(bad, issuer())
    cfg["scenarios"][0]["fcf"] = [1000, 1000]
    cfg["reverse"] = dict(scenario="base", market_basis=[dict(market_basis()[0], shares=100, price=.01)])
    no_terminal = calculate(cfg, issuer())["reverse"]
    assert no_terminal["status"] == "no_positive_terminal_requirement"
    assert no_terminal["rows"] == []
    cfg["scenarios"].append(dict(name="bull", fcf=[150, 150]))
    cfg["scenarios"][0]["probability"] = .5
    with pytest.raises(ValueError): calculate(cfg, issuer())
    cfg["scenarios"][1]["probability"] = .5
    assert "weighted_per_share" in calculate(cfg, issuer())
    financial = dict(issuer(), industry="BANK")
    assert calculate(cfg, financial)["applicability"] == "NOT_APPLICABLE"


def valuation_request(research):
    from test_shared_evidence import company
    from test_analysis_snapshots import evidence, freeze, candidate
    from roll.research.company import ValuationCommand
    identity = research.register(company())
    _, fact = evidence(research, identity)
    packet = freeze(research, identity, fact)
    snapshot = research.apply_analysis_candidate(packet["input_id"], candidate(packet, fact))
    cfg = config()
    cfg["metadata"].update(company=identity["legal_name"], sources=[fact["version_id"]], assumptions=["research-path"])
    assumption = dict(assumption_id="research-path", statement="Illustrative explicit forecast; no economic suitability claimed",
        anchor_fact_version_ids=[fact["version_id"]], hypothesis_version_ids=snapshot["hypothesis_version_ids"])
    provenance = {}
    for path in ["shares", "equity_bridge/0/amount", "equity_bridge/1/amount", "wacc", "terminal_g", "scenarios/0/fcf/0", "scenarios/0/fcf/1"]:
        unit = "million_shares" if path == "shares" else "ratio" if path in ["wacc", "terminal_g"] else "million"
        provenance[path] = dict(kind="ASSUMED", references=["research-path"], unit=unit,
                               currency="CNY" if unit == "million" else None, scope="CONSOLIDATED", period="2026-2028")
    return ValuationCommand(snapshot_id=snapshot["snapshot_id"], config=cfg, assumptions=[assumption],
                            provenance=provenance, change_reason="Initial diagnostic", idempotency_key="v1"), snapshot


def test_research_valuation_is_snapshot_bound_immutable_and_replayed_offline(tmp_path):
    from test_shared_evidence import service
    research = service(tmp_path)
    command, snapshot = valuation_request(research)
    result = research.calculate_valuation(command)
    assert result["result"]["scenarios"][0]["per_share"] == pytest.approx(8)
    assert result["result"]["usable_range"] is False
    assert result["snapshot_id"] == snapshot["snapshot_id"]
    assert research.analysis_snapshot(snapshot["snapshot_id"]) == snapshot
    frozen = research.valuation_input(result["input_version_id"])
    assert frozen["config"] == command.config
    assert frozen["snapshot_sha256"] == snapshot["content_sha256"]
    assert len(frozen["algorithm"]["files"]) >= 5
    reopened = service(tmp_path)
    assert reopened.valuation(result["valuation_id"]) == result
    replay = reopened.replay_valuation(result["valuation_id"])
    assert replay["matches_saved_result"] is True and replay["network_calls"] == 0
    assert reopened.calculate_valuation(command) == result
    changed = command.model_copy(deep=True); changed.config["wacc"] = .12
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc: reopened.calculate_valuation(changed)
    assert exc.value.detail["code"] == "IDEMPOTENCY_CONFLICT"
    changed.idempotency_key = "v2"
    changed.parent_version_id = frozen["version_id"]
    changed.change_reason = "Explicitly test alternate discount assumption"
    new = reopened.calculate_valuation(changed)
    assert new["input_version_id"] != result["input_version_id"]
    assert reopened.valuation(result["valuation_id"]) == result
    assert reopened.evidence.ledger.account()["version"] == 0


def test_market_basis_uses_shanghai_trading_day_exact_cutoff_and_identity_fx():
    from roll.research.company.calculator import calculate
    cfg = config(); identity = issuer()
    identity["listings"].append(dict(listing_id="HKEX:00001", share_class="H", currency="HKD"))
    cfg["reverse"] = dict(scenario="base", market_basis=market_basis())
    cfg["metadata"]["as_of"] = "2026-10-26T08:00:00+00:00"
    # Same local trading date, but the price is still in the future at cutoff.
    cfg["reverse"]["market_basis"][1]["priced_at"] = "2026-10-26T08:01:00+00:00"
    assert calculate(cfg, identity)["reverse"]["error"]["code"] == "AH_BASIS_INCOMPLETE"
    cfg["reverse"]["market_basis"] = market_basis()
    cfg["reverse"]["market_basis"][0]["fx"] = dict(rate=.9, from_currency="CNY", to_currency="CNY", as_of="2026-10-26", source_refs=["bad-fx"])
    assert calculate(cfg, identity)["reverse"]["error"]["code"] == "AH_BASIS_INCOMPLETE"
    cfg["metadata"]["as_of"] = "2026-10-26"  # Defined as end of Shanghai calendar day.
    cfg["reverse"]["market_basis"] = market_basis()
    cfg["reverse"]["market_basis"][0]["priced_at"] = "2026-10-25T23:30:00+00:00"
    cfg["reverse"]["market_basis"][1]["priced_at"] = "2026-10-26T00:30:00+00:00"
    assert calculate(cfg, identity)["reverse"]["market_equity_value"] == pytest.approx(1320)


def test_valuation_api_backup_restore_and_rehashed_missing_binding_rejected(tmp_path):
    import json, sqlite3
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient
    from roll.research.company.api import router
    from roll.runtime.backups import Backups, restore_at_start
    from roll.research.company.service import record
    from test_shared_evidence import service
    research = service(tmp_path / "source")
    command, snapshot = valuation_request(research)
    app = FastAPI(); app.include_router(router(research))
    with TestClient(app) as client:
        response = client.post("/api/company-research/valuations", json=command.model_dump())
        assert response.status_code == 201, response.text
        value = response.json()
        assert client.get("/api/company-research/valuations/" + value["valuation_id"]).json() == value
        assert client.post("/api/company-research/valuations/" + value["valuation_id"] + "/replay").json()["matches_saved_result"]
        bundle = client.get("/api/company-research/valuations/" + value["valuation_id"] + "/bundle").json()
    from roll.research.company.valuation import replay_bundle
    assert replay_bundle(json.loads(json.dumps(bundle)))["matches_saved_result"]
    backups = Backups(research.ledger.path.parent)
    backup = backups.create()
    exported = backups.export(backup["backup_id"])
    target = tmp_path / "restored"
    recovery = Backups(target); recovery.stage_restore(exported); restore_at_start(recovery)
    restored = service(target)
    assert restored.valuation(value["valuation_id"]) == value
    assert restored.replay_valuation(value["valuation_id"])["matches_saved_result"]
    # Deliberately rehash a missing relationship: public backup must reject structurally, not merely by record hash.
    with sqlite3.connect(research.ledger.path) as db:
        changed = dict(value, input_version_id="nonexistent")
        changed.pop("content_sha256")
        changed = record(changed)
        db.execute("UPDATE company_research_valuations SET value=? WHERE valuation_id=?", (json.dumps(changed), value["valuation_id"]))
    with pytest.raises(HTTPException) as exc: backups.create()
    assert exc.value.detail["code"] == "RESEARCH_REFERENCE_INVALID"


def test_numeric_origin_cannot_relabel_assumptions_as_disclosures_or_derivations(tmp_path):
    from test_shared_evidence import service
    from fastapi import HTTPException
    research = service(tmp_path)
    command, _ = valuation_request(research)
    for kind in ["DISCLOSED", "DERIVED"]:
        bad = command.model_copy(deep=True)
        bad.provenance["scenarios/0/fcf/0"]["kind"] = kind
        with pytest.raises(HTTPException) as exc: research.calculate_valuation(bad)
        assert exc.value.detail["code"] == "FACT_VALUE_MISMATCH"
    bad = command.model_copy(deep=True)
    bad.provenance["scenarios/0/fcf/0"].update(kind="DISCLOSED", references=bad.config["metadata"]["sources"])
    with pytest.raises(HTTPException) as exc: research.calculate_valuation(bad)
    assert exc.value.detail["code"] == "FACT_VALUE_MISMATCH"
    for path, field, replacement, code in [("scenarios/0/fcf/0", "unit", "unit", "UNIT_MISMATCH"),
                                           ("equity_bridge/0/amount", "currency", "HKD", "CURRENCY_MISMATCH"),
                                           ("wacc", "references", ["unfrozen"], "UNKNOWN_CITATION")]:
        bad = command.model_copy(deep=True); bad.provenance[path][field] = replacement
        with pytest.raises(HTTPException) as exc: research.calculate_valuation(bad)
        assert exc.value.detail["code"] == code
    bad = command.model_copy(deep=True); bad.provenance.pop("scenarios/0/fcf/0")
    with pytest.raises(HTTPException) as exc: research.calculate_valuation(bad)
    assert exc.value.detail["code"] == "PROVENANCE_REQUIRED"


def test_canonical_archive_descriptor_and_frozen_company_label(tmp_path):
    from test_shared_evidence import service
    from roll.research.company.valuation import source_files
    from roll.runtime.backups import Backups
    from fastapi import HTTPException
    research = service(tmp_path)
    command, snapshot = valuation_request(research)
    raw = dict(source_files())["calculator.py"]
    registered = research.evidence.archive(raw, "EARLIER_REGISTERED_KIND")
    saved = research.calculate_valuation(command)
    frozen = research.valuation_input(saved["input_version_id"])
    assert next(f["archive"] for f in frozen["algorithm"]["files"] if f["path"] == "calculator.py") == registered
    assert Backups(tmp_path).create()["status"] == "COMPLETE"
    bad = command.model_copy(deep=True); bad.config["metadata"]["company"] = "Another issuer"
    with pytest.raises(HTTPException) as exc: research.calculate_valuation(bad)
    assert exc.value.detail["code"] == "SOURCE_IDENTITY_MISMATCH"


def test_bridge_restricted_cash_nci_nonoperating_assets_conserve_parent_equity():
    from roll.research.company.calculator import calculate
    cfg = config()
    cfg["scenarios"][0]["fcf"] = [100] * 5
    cfg["equity_bridge"] += [dict(name="restricted cash retained in operations", amount=0, source="restricted cash note", treatment="excluded"),
                             dict(name="noncontrolling interests", amount=50, source="NCI note", treatment="deduct"),
                             dict(name="nonoperating asset", amount=-20, source="asset note", treatment="add")]
    result = calculate(cfg, issuer())
    assert result["scenarios"][0]["pv_explicit"] == pytest.approx(379.0786769408448)
    assert result["scenarios"][0]["pv_terminal"] == pytest.approx(620.9213230591552)
    assert result["equity_adjustment"] == 230
    assert result["scenarios"][0]["equity_value"] == pytest.approx(770)
    assert result["scenarios"][0]["per_share"] == pytest.approx(7.7)
    assert result["equity_bridge"][2]["amount"] == 0


def test_optional_sensitivity_keeps_valid_cells_and_the_base_diagnostic():
    from roll.research.company.calculator import calculate
    cfg = config()
    cfg["sensitivity"] = dict(scenario="base", wacc=[.1, .02], terminal_g=[0, .02])
    result = calculate(cfg, issuer())
    assert result["scenarios"][0]["enterprise_value"] == pytest.approx(1000)
    assert len(result["sensitivity"]) == 4
    assert sum(r.get("status") == "NOT_APPLICABLE" for r in result["sensitivity"]) == 1
    assert result["sensitivity"][-1]["error"]["code"] == "WACC_NOT_ABOVE_G"


def test_service_ah_market_basis_uses_matching_frozen_numeric_facts(tmp_path):
    from test_shared_evidence import service, material_input
    from test_analysis_snapshots import candidate
    from roll.research.company import FactCommand, AnalysisCommand, MaterialCommand
    from datetime import datetime, timezone
    research = service(tmp_path)
    command, old = valuation_request(research)
    anchor = research.fact(old["fact_version_ids"][0])
    basis = market_basis()
    basis[0]["listing_id"] = "SSE:600362"; basis[1]["listing_id"] = "HKEX:00358"
    fact_ids = [anchor["version_id"]]
    for index, row in enumerate(basis):
        values = [("shares", row["shares"], "million_shares", None, row["listing_id"]),
                  ("price", row["price"], "price_per_share", row["currency"], row["listing_id"])]
        if row.get("fx"): values.append(("fx/rate", .9, "ratio", None, "HKD->CNY"))
        for field, value, unit, currency, scope in values:
            metadata = material_input(old["company_id"])
            metadata.update(unit=unit, currency=currency, scope=scope, source_id=f"method-market-{index}-{field}",
                            origin_root_id=f"method-market-{index}-{field}", period_start="2026-10-26", period_end="2026-10-26")
            material = research.import_material(MaterialCommand(**metadata), f"METHOD {scope} {field} {value}".encode())
            fact = research.add_fact(FactCommand(company_id=old["company_id"], material_id=material["material_id"],
                metric=row["listing_id"] + ":" + field, business="LISTED_CAPITAL", value=str(value),
                unit=unit, currency=currency, scope=scope, period_start="2026-10-26", period_end="2026-10-26",
                change_reason="METHOD market basis reference"))
            fact_ids.append(fact["version_id"])
            ref = [fact["version_id"]]
            if field == "fx/rate": row["fx"]["source_refs"] = ref
            else: row["share_refs" if field == "shares" else "price_refs"] = ref
            command.provenance[f"reverse/market_basis/{index}/{field}"] = dict(kind="DISCLOSED", references=ref,
                unit=unit, currency=currency, scope=scope, period="2026-10-26/2026-10-26")
    packet = research.freeze_analysis(AnalysisCommand(company_id=old["company_id"], as_of=datetime.now(timezone.utc).isoformat(),
        fact_version_ids=fact_ids, parent_snapshot_id=old["snapshot_id"]))
    snapshot = research.apply_analysis_candidate(packet["input_id"], candidate(packet, anchor, hypotheses=[], insufficient_hypotheses_reason="Reuse facts for calculator-only diagnostic"))
    command.snapshot_id = snapshot["snapshot_id"]
    command.assumptions[0]["hypothesis_version_ids"] = []
    command.config["reverse"] = dict(scenario="base", market_basis=basis)
    saved = research.calculate_valuation(command)
    assert saved["result"]["reverse"]["market_equity_value"] == pytest.approx(1320)
    assert saved["result"]["reverse"]["terminal_fcf_required"] == pytest.approx(162.92)
    assert research.replay_valuation(saved["valuation_id"])["matches_saved_result"]
    missing = command.model_copy(deep=True); missing.idempotency_key = "missing-fx"
    missing.config["reverse"]["market_basis"][1].pop("fx")
    missing.provenance.pop("reverse/market_basis/1/fx/rate")
    partial = research.calculate_valuation(missing)
    assert partial["result"]["scenarios"][0]["per_share"] == pytest.approx(8)
    assert partial["result"]["reverse"]["error"]["code"] == "AH_BASIS_INCOMPLETE"
