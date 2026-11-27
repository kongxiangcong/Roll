from argparse import ArgumentParser
from decimal import Decimal
import io
import json
import sys

import pytest

from roll.v3.account_cli import register_account_commands
from roll.v3.market_cli import register as register_market
from roll.v3.plan_cli import register_plan_commands
from roll.v3.research import register_research_commands
from roll.v3.review_cli import register_review_commands
from roll.v3.strategy_cli import register as register_strategy


SYMBOL = "600362.SH"
DECISION = "2026-11-27T16:00:00+08:00"
NEXT_OPEN = "2026-11-30T09:30:00+08:00"
NEXT_CLOSE = "2026-11-30T16:00:00+08:00"


def cli(data_dir, *argv, payload=None):
    root = ArgumentParser()
    commands = root.add_subparsers(required=True)
    for register in (register_account_commands, register_market, register_plan_commands,
                     register_review_commands, register_research_commands, register_strategy):
        register(commands)
    args = root.parse_args(argv)
    if payload is None:
        return args.handler(args, data_dir)
    original = sys.stdin
    try:
        sys.stdin = io.StringIO(json.dumps(payload))
        return args.handler(args, data_dir)
    finally:
        sys.stdin = original


def seed_trend(tmp_path, *, opening=None):
    cli(tmp_path, "account", "init", payload={
        "cash": "2200", "available_cash": "2200", "effective_at": DECISION, "known_at": DECISION,
    })
    cli(tmp_path, "account", "budget", payload={
        "budget_id": "fixture-budget", "effective_at": DECISION, "known_at": DECISION,
        "cash_reserve": "0", "max_total_exposure": "1", "max_symbol_exposure": "1", "max_industry_exposure": "1",
    })
    strategy = cli(tmp_path, "strategy", "freeze", "--fast", "1", "--slow", "2", "--at",
                   "2026-11-26T15:05:00+08:00")["strategy"]["version"]
    rows = [
        {"series": "daily_bar", "symbol": SYMBOL, "trade_date": day, "source": "fixture",
         "available_at": f"{day}T15:05:00+08:00", "received_at": f"{day}T15:05:00+08:00",
         "payload": {"close": close, "prior_close": "10", "pre_close": "10", "trading_status": "trading"}}
        for day, close in (("2026-11-26", "10"), ("2026-11-27", "11"))
    ]
    if opening is not None:
        rows.append({
            "series": "daily_open", "symbol": SYMBOL, "trade_date": "2026-11-30", "source": "fixture",
            "available_at": NEXT_OPEN, "received_at": NEXT_OPEN, "payload": {
                "open": opening, "prior_close": "11", "pre_close": "11", "trading_status": "trading",
            },
        })
    path = tmp_path / "quotes.json"
    path.write_text(json.dumps(rows))
    cli(tmp_path, "market", "import", str(path))
    return strategy


def test_rehearsal_keeps_rejection_and_settles_the_frozen_shadow_once(tmp_path):
    strategy = seed_trend(tmp_path, opening="10.90")

    registration = cli(tmp_path, "review", "register", "--mode", "rehearsal", "--now", DECISION,
                       "--strategy-version", strategy, "--price-only")
    registration_id = registration["registration_id"]
    planned, = registration["plans"]
    assert planned["real_plan"]["action"] == "WATCH"
    assert planned["shadow_plan"]["action"] == "BUY"
    assert planned["shadow"] is None

    cli(tmp_path, "review", "outcome", registration_id, SYMBOL, "rejected",
        "--now", DECISION, "--reason", "暂缓交易")
    settled = cli(tmp_path, "review", "settle", registration_id, "--now", NEXT_OPEN)
    reviewed, = settled["plans"]
    assert reviewed["real_plan"] == planned["real_plan"]
    assert reviewed["actual"]["status"] == "REJECTED"
    assert reviewed["actual"]["events"][0]["reason"] == "暂缓交易"
    assert reviewed["shadow"]["status"] == "FILLED"
    assert reviewed["shadow"]["fill"]["quantity"] == 100
    assert reviewed["shadow"]["fill"]["price"] == "10.91"
    assert Decimal(reviewed["shadow"]["account"]["cash"]) == Decimal("1103.99")
    assert cli(tmp_path, "review", "settle", registration_id, "--now", NEXT_OPEN) == settled
    assert cli(tmp_path, "review", "show", registration_id, "--as-of", NEXT_OPEN) == settled
    assert [event["kind"] for event in cli(tmp_path, "account", "log", "--as-of", NEXT_CLOSE)] == ["BASELINE"]


def test_late_broker_report_and_correction_preserve_the_original_rehearsal_plan(tmp_path):
    strategy = seed_trend(tmp_path, opening="10.90")
    registration = cli(tmp_path, "review", "register", "--mode", "rehearsal", "--now", DECISION,
                       "--strategy-version", strategy, "--price-only")
    key = registration["registration_id"]
    original, = registration["plans"]
    report = "2026-12-01T17:00:00+08:00"
    received = "2026-12-02T20:00:00+08:00"
    payload = {
        "event_id": "broker-1", "effective_at": "2026-11-30T10:00:00+08:00",
        "side": "BUY", "quantity": 100, "price": "10.85", "fee": "5.02", "reported_at": report,
    }
    result = cli(tmp_path, "review", "outcome", key, SYMBOL, "filled", "--now", received, payload=payload)
    plan, = result["plans"]

    assert plan["real_plan"] == original["real_plan"]
    assert plan["actual"]["status"] == "DEVIATION"
    event, = plan["actual"]["events"]
    assert event["reported_at"] == "2026-12-01T09:00:00.000000+00:00"
    assert event["recorded_at"] == "2026-12-02T12:00:00.000000+00:00"
    fill, = plan["actual"]["fills"]
    assert fill["plan_id"] == original["real_plan"]["plan_id"]
    assert fill["known_at"] == event["recorded_at"]
    assert cli(tmp_path, "review", "outcome", key, SYMBOL, "filled", "--now", received, payload=payload) == result
    before, = cli(tmp_path, "review", "show", key, "--as-of", report)["plans"]
    assert before["actual"]["fills"] == []

    corrected_at = "2026-12-03T20:00:00+08:00"
    cli(tmp_path, "account", "correct", "--book-id", result["actual_book_id"], payload={
        "event_id": "broker-correction", "target_event_id": "broker-1",
        "replacement": None, "known_at": corrected_at,
    })
    corrected, = cli(tmp_path, "review", "show", key, "--as-of", corrected_at)["plans"]
    assert corrected["real_plan"] == original["real_plan"]
    assert corrected["actual"]["status"] == "OBSERVED"
    assert corrected["actual"]["fills"] == []
    assert [fact["event_id"] for fact in corrected["actual"]["account_events"]] == [
        "broker-1", "broker-correction",
    ]


def test_next_rehearsal_uses_its_existing_holdings_and_records_missing_opening(tmp_path):
    strategy = seed_trend(tmp_path, opening="10.90")
    first = cli(tmp_path, "review", "register", "--mode", "rehearsal", "--now", DECISION,
                "--strategy-version", strategy, "--price-only")
    close_path = tmp_path / "monday-close.json"
    close_path.write_text(json.dumps([{
        "series": "daily_bar", "symbol": SYMBOL, "trade_date": "2026-11-30", "source": "fixture",
        "available_at": "2026-11-30T15:05:00+08:00", "received_at": "2026-11-30T15:05:00+08:00",
        "payload": {"close": "9.00", "prior_close": "11.00", "pre_close": "11.00", "trading_status": "trading"},
    }]))
    cli(tmp_path, "market", "import", str(close_path))

    second = cli(tmp_path, "review", "register", "--mode", "rehearsal", "--now", NEXT_CLOSE)
    assert second["shadow_book_id"] == first["shadow_book_id"]
    assert second["strategy_versions"] == [strategy]
    planned, = second["plans"]
    assert planned["shadow_plan"]["action"] == "SELL"
    assert planned["shadow_plan"]["current_quantity"] == 100
    assert planned["real_plan"]["current_quantity"] == 0
    previous = cli(tmp_path, "review", "show", first["registration_id"], "--as-of", NEXT_CLOSE)
    assert Decimal(previous["shadow_closing"]["valuation"]["nav"]) == Decimal("2003.99")
    settled, = cli(tmp_path, "review", "settle", second["registration_id"],
                   "--now", "2026-12-01T09:30:00+08:00")["plans"]
    assert settled["shadow"]["status"] == "UNFILLED"
    assert settled["shadow"]["reason"] == "MISSING_OPENING"
    assert settled["shadow"]["account"]["lots"][0]["quantity"] == 100


def test_review_keeps_a_missed_live_day_after_historical_reconstruction(tmp_path, monkeypatch):
    from roll.v3 import review
    from roll.v3.storage import instant

    clock = "2026-12-01T16:00:00+08:00"
    monkeypatch.setattr(review, "instant", lambda value=None: instant(value or clock))
    strategy = seed_trend(tmp_path, opening="10.90")

    with pytest.raises(ValueError, match="历史|重建"):
        cli(tmp_path, "review", "register", "--as-of", DECISION)
    reconstructed = cli(tmp_path, "review", "register", "--mode", "reconstructed", "--as-of", DECISION,
                        "--strategy-version", strategy, "--price-only")
    reviewed = cli(tmp_path, "review", "settle", reconstructed["registration_id"])
    assert reviewed["plans"][0]["shadow"]["status"] == "FILLED"
    assert cli(tmp_path, "plan", "--session", "2026-11-30") == []

    live = cli(tmp_path, "review", "register")
    assert live["shadow_book_id"] != reconstructed["shadow_book_id"]
    dates = cli(tmp_path, "review", "list", "--start", "2026-11-27", "--end", "2026-12-01", "--as-of", clock)
    assert dates["missing_live_dates"] == ["2026-11-27", "2026-11-30"]
    assert [record["mode"] for record in dates["registrations"]] == ["reconstructed", "live"]


def test_triggering_frozen_hypothesis_adds_a_linked_research_followup(tmp_path, monkeypatch):
    from roll.v3 import research
    from roll.v3.storage import instant

    publication_time = "2026-11-26T16:00:00+08:00"
    monkeypatch.setattr(research, "instant", lambda value=None: instant(value or publication_time))
    version = seed_trend(tmp_path)
    path = tmp_path / "copper.md"
    path.write_text(
        """---
version: copper
valid_until: "2026-12-15T00:00:00+08:00"
fundamental_gate: pass
evidence:
  - id: quarterly-report
    title: 演练用季报
    source: 测试材料
    document_id: quarterly-report
    locator: 合并现金流量表
constraint_basis:
  fundamental_gate:
    evidence_refs: [quarterly-report]
  thesis_status:
    rationale: 演练假设由研究者定期复核
thesis_status: intact
hypothesis: 价格维持十元以下
invalidation_triggers:
  - id: close-above-ten
    feature: close
    operator: ">"
    threshold: 10
    effect: block_new_risk
---
# 价格假设
""", encoding="utf-8",
    )
    cli(tmp_path, "research", "draft", SYMBOL, str(path))
    dossier = cli(tmp_path, "research", "publish", SYMBOL, "copper", "--reviewer", "研究者")
    review = cli(tmp_path, "review", "register", "--mode", "rehearsal", "--now", DECISION,
                 "--strategy-version", version)
    plan, = review["plans"]
    followup, = cli(tmp_path, "research", "followups", SYMBOL, "--mode", "rehearsal", "--as-of", DECISION)
    assert followup["plan_id"] == plan["real_plan"]["plan_id"]
    assert followup["hypothesis"] == "价格维持十元以下"
    assert followup["dossier_version"] == "copper"
    assert followup["evidence_refs"] == ["market:" + plan["real_plan"]["snapshot_id"]]
    assert followup["trigger_id"] == "close-above-ten"
    assert cli(tmp_path, "research", "show", SYMBOL, "--as-of", DECISION) == dossier


@pytest.mark.parametrize(("opening_evidence", "reconstruction_only", "status", "evidence_status"), [
    ("opening receipt captured at 09:30", False, "FILLED", "AVAILABLE"),
    (None, False, "UNFILLED", "TIMING_UNVERIFIED"),
    ("part of the closing bar", True, "UNFILLED", "MISSING_OR_NOT_VISIBLE"),
])
def test_live_shadow_requires_opening_evidence(
    tmp_path, monkeypatch, opening_evidence, reconstruction_only, status, evidence_status,
):
    from roll.v3 import review
    from roll.v3.storage import instant

    now = DECISION
    monkeypatch.setattr(review, "instant", lambda value=None: instant(value or now))
    strategy = seed_trend(tmp_path)
    first = cli(tmp_path, "review", "register", "--strategy-version", strategy, "--price-only")
    path = tmp_path / "opening.json"
    path.write_text(json.dumps([{
        "series": "daily_open", "symbol": SYMBOL, "trade_date": "2026-11-30", "source": "fixture",
        "available_at": NEXT_OPEN, "received_at": NEXT_OPEN, "available_evidence": opening_evidence,
        "reconstruction_only": reconstruction_only,
        "payload": {"open": "10.90", "prior_close": "11", "pre_close": "11", "trading_status": "trading"},
    }]))
    cli(tmp_path, "market", "import", str(path))
    now = NEXT_OPEN

    settled, = cli(tmp_path, "review", "settle", first["registration_id"])["plans"]
    assert settled["shadow"]["status"] == status
    assert settled["shadow"]["opening_evidence_status"] == evidence_status
    assert (settled["shadow"]["fill"] is not None) == (status == "FILLED")


def test_shadow_carries_starting_receivables_and_posts_cash_at_due_close(tmp_path, monkeypatch):
    from roll.v3 import review
    from roll.v3.storage import instant

    now = DECISION
    monkeypatch.setattr(review, "instant", lambda value=None: instant(value or now))
    initial = "2026-11-25T14:00:00+08:00"
    cli(tmp_path, "account", "init", payload={
        "cash": "1000", "available_cash": "1000", "effective_at": initial, "known_at": initial,
        "lots": [{"lot_id": "existing", "symbol": SYMBOL, "quantity": 100, "known_sellable": 100}],
    })
    path = tmp_path / "dividend.json"
    path.write_text(json.dumps([{
        "series": "corporate_action", "symbol": SYMBOL, "trade_date": "2026-11-26", "source": "fixture",
        "item_id": "distribution", "available_at": initial, "received_at": initial,
        "payload": {
            "record_date": "2026-11-25", "ex_date": "2026-11-26",
            "payment_date": "2026-11-30", "cash_per_share": "0.5",
        },
    }]))
    cli(tmp_path, "market", "import", str(path))
    first = cli(tmp_path, "review", "register")
    original, = first["plans"]
    shadow_start = cli(tmp_path, "account", "show", "--snapshot-id", original["shadow_plan"]["account_snapshot_id"])
    assert shadow_start["receivables"][0]["amount"] == "50"

    now = NEXT_CLOSE
    settled = cli(tmp_path, "review", "settle", first["registration_id"])
    plan, = settled["plans"]
    assert plan["shadow"]["account"]["cash"] == "1000"
    assert settled["shadow_closing"]["account"]["cash"] == "1050"
    assert settled["shadow_closing"]["account"]["receivables"] == []
    real = cli(tmp_path, "account", "show", "--as-of", NEXT_CLOSE)
    assert real["cash"] == "1000"
    assert real["receivables"][0]["amount"] == "50"


def test_live_review_completes_a_close_received_after_the_target_cutoff(tmp_path, monkeypatch):
    from roll.v3 import review
    from roll.v3.storage import instant

    now = DECISION
    monkeypatch.setattr(review, "instant", lambda value=None: instant(value or now))
    cli(tmp_path, "account", "init", payload={
        "cash": "1000", "available_cash": "1000", "effective_at": DECISION, "known_at": DECISION,
        "lots": [{"lot_id": "holding", "symbol": SYMBOL, "quantity": 100, "known_sellable": 100}],
    })
    first = cli(tmp_path, "review", "register")
    key = first["registration_id"]

    now = NEXT_CLOSE
    pending = cli(tmp_path, "review", "settle", key)
    assert pending["shadow_closing"]["missing_marks"] == [SYMBOL]

    now = "2026-11-30T16:15:00+08:00"
    path = tmp_path / "actual-close.json"
    path.write_text(json.dumps([{
        "series": "daily_bar", "symbol": SYMBOL, "trade_date": "2026-11-30",
        "source": "verified-sample", "received_at": now, "payload": {"close": "11.25"},
    }]))
    cli(tmp_path, "market", "import", str(path))

    complete = cli(tmp_path, "review", "settle", key)
    assert complete["shadow_closing"]["missing_marks"] == []
    assert Decimal(complete["shadow_closing"]["valuation"]["nav"]) == Decimal("2125.00")
    assert cli(tmp_path, "review", "show", key, "--as-of", NEXT_CLOSE) == pending
    assert cli(tmp_path, "review", "settle", key) == complete


def test_review_replays_original_watch_and_counts_fills_on_the_published_sell_revision(tmp_path, monkeypatch):
    from roll.v3 import plan, research, review
    from roll.v3.storage import instant

    now = DECISION
    monkeypatch.setattr(review, "instant", lambda value=None: instant(value or now))
    monkeypatch.setattr(research, "instant", lambda value=None: instant(value or now))
    utc_timestamp = plan.utc_timestamp
    monkeypatch.setattr(plan, "utc_timestamp", lambda value=None: utc_timestamp(value or now))
    seed_trend(tmp_path)
    cli(tmp_path, "account", "shares", payload={
        "event_id": "original-shares", "effective_at": DECISION, "known_at": DECISION,
        "lot": {"lot_id": "original", "symbol": SYMBOL, "quantity": 100, "known_sellable": 100},
    })
    registered = cli(tmp_path, "review", "register")
    key = registered["registration_id"]
    original, = registered["plans"]
    assert original["real_plan"]["action"] == "WATCH"

    now = "2026-11-27T17:00:00+08:00"
    dossier = tmp_path / "broken.md"
    dossier.write_text('---\nvalid_until: "2026-12-10T00:00:00+08:00"\n'
                       'fundamental_gate: fail\nthesis_status: broken\n---\n# 假设已失效\n', encoding="utf-8")
    cli(tmp_path, "research", "draft", SYMBOL, str(dossier))
    cli(tmp_path, "research", "publish", SYMBOL, "broken", "--reviewer", "研究者")
    revised, = cli(tmp_path, "plan", "--as-of", now)["plans"]
    assert revised["action"] == "SELL"
    assert revised["replaces_plan_id"] == original["real_plan"]["plan_id"]

    now = NEXT_CLOSE
    fill = {"symbol": SYMBOL, "effective_at": NEXT_OPEN, "side": "SELL", "quantity": 50, "price": "10.90"}
    cli(tmp_path, "account", "fill", payload={
        **fill, "event_id": "broker-sale-a", "plan_id": revised["plan_id"], "known_at": now,
    })
    first, = cli(tmp_path, "review", "show", key)["plans"]
    assert first["actual"]["status"] == "PARTIAL"
    result = cli(tmp_path, "review", "outcome", key, SYMBOL, "filled", payload={
        **fill, "event_id": "broker-sale-b",
    })
    current, = result["plans"]
    assert current["real_plan"] == original["real_plan"]
    assert current["active_real_plan"] == revised
    assert current["actual"]["status"] == "FILLED"
    assert [fill["plan_id"] for fill in current["actual"]["fills"]] == [revised["plan_id"]] * 2
    assert current["actual"]["events"][0]["plan_id"] == revised["plan_id"]
    assert cli(tmp_path, "review", "show", key, "--as-of", DECISION) == registered
    assert cli(tmp_path, "plan", "--plan-id", original["real_plan"]["plan_id"]) == original["real_plan"]


@pytest.mark.parametrize("effect", ["pause", "pause_strategy"])
def test_a_structured_research_pause_blocks_a_strategy_sale_but_keeps_the_risk_exit(tmp_path, monkeypatch, effect):
    from roll.v3 import research
    from roll.v3.storage import instant

    now = "2026-11-27T15:30:00+08:00"
    monkeypatch.setattr(research, "instant", lambda value=None: instant(value or now))
    symbol = SYMBOL
    book = "independent-simulation"
    cli(tmp_path, "account", "init", "--book-id", book, payload={
        "cash": "0", "available_cash": "0", "effective_at": DECISION, "known_at": DECISION, "simulated": True,
        "lots": [{"lot_id": "held", "symbol": symbol, "quantity": 100, "known_sellable": 100}],
    })
    version = seed_trend(tmp_path)
    correction = tmp_path / "pause-inputs.json"
    correction.write_text(json.dumps([
        {"series": "daily_bar", "symbol": symbol, "trade_date": "2026-11-27", "source": "fixture",
         "available_at": "2026-11-27T15:10:00+08:00", "received_at": "2026-11-27T15:10:00+08:00",
         "payload": {"close": "9", "prior_close": "10", "pre_close": "10", "trading_status": "trading"}},
        {"series": "research_feature", "symbol": symbol, "trade_date": "2026-09-30",
         "source": "filing", "source_ref": "fixture-filing#cash-flow",
         "available_at": "2026-11-27T15:55:00+08:00", "received_at": "2026-11-27T17:00:00+08:00",
         "payload": {"feature": "operating_cash_flow_ytd_cny", "value": "-100"}},
    ]))
    cli(tmp_path, "market", "import", str(correction))

    def publish(name, thesis):
        path = tmp_path / f"{name}.md"
        path.write_text(f"""---
valid_until: "2026-12-15T00:00:00+08:00"
fundamental_gate: pass
evidence:
  - id: quarterly-report
    title: 演练用季报
    source: 测试材料
    document_id: quarterly-report
    locator: 合并现金流量表
constraint_basis:
  fundamental_gate:
    evidence_refs: [quarterly-report]
  thesis_status:
    rationale: 演练假设由研究者定期复核
thesis_status: {thesis}
invalidation_triggers:
  - id: cash-pause
    feature: operating_cash_flow_ytd_cny
    operator: "<="
    threshold: 0
    effect: {effect}
---
# 经营现金流暂停条件
""", encoding="utf-8")
        cli(tmp_path, "research", "draft", symbol, str(path))
        cli(tmp_path, "research", "publish", symbol, name, "--reviewer", "研究者")

    def next_plan(cutoff):
        result = cli(tmp_path, "plan", "--book-id", book, "--as-of", cutoff, "--simulate", "--preview",
                     "--price-only", "--strategy-version", version)
        return result["plans"][0]

    publish("paused", "intact")
    before = next_plan(DECISION)
    assert before["action"] == "SELL"
    assert "TRIGGER_UNKNOWN:cash-pause" in before["reasons"]["P2"]
    after = next_plan("2026-11-27T17:15:00+08:00")
    assert after["action"] == "WATCH"
    assert "TRIGGER_FIRED:cash-pause" in after["reasons"]["P2"]
    assert "STRATEGY_PAUSED_BY_RESEARCH" in after["candidates"][0]["selection_reasons"]
    assert after["research"]["triggers"][0]["observation"]["source_ref"] == "fixture-filing#cash-flow"

    now = "2026-11-27T17:30:00+08:00"
    publish("risk", "broken")
    risk_exit = next_plan(now)
    assert risk_exit["action"] == "SELL"
    assert risk_exit["strategy_version"] is None
    assert risk_exit["reasons"]["P4"] == ["RISK_EXIT"]
