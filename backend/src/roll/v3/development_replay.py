"""Replay and verify a bounded development experiment without opening a production ledger."""

from collections import defaultdict
from dataclasses import asdict
from decimal import Decimal
from hashlib import sha256
import json
from tempfile import TemporaryDirectory

from roll.v3.account import AccountLedger
from roll.v3.decision import DECISION_RULES_VERSION
from roll.v3.development_experiment import (
    PATHS, development_preset, freeze_development_inputs, observation_reference, public_manifest,
)
from roll.v3.entitlements import SIMULATION_BASIS
from roll.v3.execution import EXECUTION_RULES_VERSION, ExecutionRules
from roll.v3.experiment import (
    EXECUTION_GAPS, _Book, _account_at, _decision, _execute_pending, _initial_configuration,
    _intent_payload, _mark, _opening, _session_after, _valuation,
)
from roll.v3.experiment_metrics import _decimal_text, _metrics, _round_trips
from roll.v3.market import utc_timestamp
from roll.v3.storage import database, ensure_schema, json_text, session_time


REPLAY_VERSION = "development-replay-v1"
_NAV_METRICS = (
    "end_nav", "total_return", "max_drawdown", "volatility", "downside_risk", "turnover",
    "excess_return_vs_buy_and_hold", "excess_return_vs_no_active_trading",
)
_TRADE_METRICS = ("fills", "gross_traded", "costs", "slippage_cost", "completed_round_trips")
_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_development_receipt (
    task_id TEXT PRIMARY KEY REFERENCES research_task(task_id),
    receipt_id TEXT NOT NULL,
    receipt TEXT NOT NULL
)
"""


def _digest(value):
    return sha256(json_text(value).encode()).hexdigest()


def _identified(receipt):
    return {**receipt, "receipt_id": "development-receipt-" + _digest(receipt)}


def _start_book(ledger, book, at, initial):
    ledger.initialize(book.book_id, cash=initial["cash"], available_cash=initial["available_cash"],
                      effective_at=at, known_at=at, source="frozen-development-baseline", simulated=True)
    ledger.set_risk_budget(book.book_id, budget_id=f"development-budget-{_digest(initial['risk_budget'])[:16]}",
                           effective_at=at, known_at=at, **initial["risk_budget"])
    return ledger.snapshot(book.book_id, as_of=at)


def _decide(book, account, configuration, rules, features, at, following, close, status, market_always_true):
    signal = features["e0"]
    plan, intent = _decision(book, account, configuration, rules, signal, at, following, close, status)
    candidate = None
    if book.name in ("e0", "e1"):
        candidate = {"action": plan["action"], "quantity": plan.get("quantity", 0)}
    reason = None
    buy = intent is not None and intent.side == "BUY"
    if candidate is not None and buy:
        if not features["common_evaluable"]:
            reason = "COMMON_ENTRY_INPUT_UNAVAILABLE"
        elif book.name == "e1" and not (features["market"]["above_average"] or market_always_true):
            reason = "MARKET_AT_OR_BELOW_AVERAGE"
    if reason:
        plan = {**plan, "action": "HOLD", "quantity": 0, "target_quantity": plan["current_quantity"],
                "cash_reserved": "0", "estimated_fees": "0",
                "reasons": {**plan["reasons"], "P4": [reason]}}
        intent = None
    gate = None if candidate is None else {
        "common_evaluable": features["common_evaluable"],
        "market_above_average": features["market"]["above_average"],
        "blocked": reason is not None, "reason": reason,
        "coverage_reasons": features["reasons"] if not features["common_evaluable"] else [],
    }
    return plan, intent, candidate, gate


def _replay(inputs, market_always_true):
    initial = _initial_configuration(inputs.preset["protocol"], inputs.preset["symbol"],
                                     {"risk_budget": inputs.preset["simulation_risk_budget"]})
    configuration = {**inputs.preset, "market_snapshot": inputs.snapshot, "initial": initial}
    costs = inputs.preset["protocol"]["costs"]
    rules = ExecutionRules(Decimal(costs["commission_rate"]), Decimal(costs["minimum_commission_yuan"]),
                           Decimal(costs["slippage_rate"]))
    market, sample, symbol = inputs.market, inputs.sample, inputs.preset["symbol"]
    effective = sample["effective_window"]
    start, end = effective["start"], effective["end"]
    books = [_Book(name, f"development:{inputs.preset['id']}:{name}") for name in PATHS]
    gaps = defaultdict(set)
    trace = []
    last_close = None
    previous_day = start
    initial_accounts, initial_marks = {}, {}
    with TemporaryDirectory(prefix="roll-development-") as sandbox, database(sandbox, write=True) as db:
        ledger = AccountLedger(sandbox, db=db)
        for day in market["days"]:
            if day < start:
                continue
            start_day = day == start
            following = _session_after(day)
            at_open, at_close = session_time(day, 9, 30), session_time(day, 15, 5)
            opening = None if start_day else market["opens"][day]
            close_row = market["closes"][day]
            action = market["actions"][day]
            features = sample["by_date"][day]
            open_quote = _opening(opening, symbol, day)
            close, status, mark_basis = _mark(close_row, last_close, action["factors"] or action["issues"])
            last_close = close
            action_issues = [*action["issues"], *((day, f"SNAPSHOT_SCOPE_MISSING:{series}", ())
                                                  for series in market["missing_entitlement_scope"][day])]
            paths = {}
            for book in books:
                name = book.name
                if start_day:
                    account = open_account = _start_book(ledger, book, at_close, initial)
                    initial_accounts[name] = account.as_dict()
                    initial_marks[name] = _valuation(account, symbol, None)
                    execution = _execute_pending(ledger, book, None, open_account, rules, at_open)
                else:
                    open_account = _account_at(ledger, sandbox, db, book, action["opening"], at_open)
                    execution = _execute_pending(ledger, book, open_quote, open_account, rules, at_open)
                    account = _account_at(ledger, sandbox, db, book, action["closing"], at_close)
                if execution["reason"] in EXECUTION_GAPS:
                    quality = market["opening_quality"][day]
                    if opening is None:
                        execution["observation_quality"] = quality
                    gaps[day, execution["reason"], "execution", quality].add(name)
                valuation = _valuation(account, symbol, close)
                if valuation is None:
                    gaps[day, "MISSING_VALUATION_MARK", "valuation", market["closing_quality"][day]].add(name)
                if (name == "buy_and_hold" and not book.configured and status != "suspended"
                        and (close is None or status != "trading")):
                    gaps[day, "BASELINE_DECISION_INPUT_UNAVAILABLE", "decision", market["closing_quality"][day]].add(name)
                if account.lots or any(item.kind == "shares" for item in account.receivables):
                    book.holding_days.add(day)
                for impacted, reason, record_dates in action_issues:
                    if (book.holding_days.intersection(record_dates or (previous_day,)) or open_account.lots
                            or open_account.receivables):
                        gaps[impacted, reason, "entitlement", None].add(name)
                decision, book.pending, candidate, gate = _decide(
                    book, account, configuration, rules, features, at_close, following, close, status, market_always_true,
                )
                if following is None and (name in ("e0", "e1") or name == "buy_and_hold" and not book.configured):
                    gaps[day, "NEXT_SESSION_CALENDAR_UNAVAILABLE", "decision", None].add(name)
                outside = book.pending is not None and following > end
                paths[name] = {
                    "signal": features["e0"] if candidate is not None else None,
                    "execution": execution, "open_account": open_account.as_dict(),
                    "account": account.as_dict(), "valuation": valuation, "decision_before_gate": candidate,
                    "decision": decision, "gate": gate, "pending_intent": _intent_payload(book.pending, following),
                    "next_open": {
                        "date": following, "status": "OUTSIDE_WINDOW" if outside else "PENDING" if book.pending else "NO_INTENT",
                        "reason": "AFTER_DEVELOPMENT_WINDOW" if outside else None,
                        "fill": None,
                    },
                }
            if trace:
                for name, prior in trace[-1]["paths"].items():
                    if prior["pending_intent"]:
                        outcome = paths[name]["execution"]
                        prior["next_open"] = {"date": day, **{key: outcome[key] for key in ("status", "reason", "fill")}}
                        if "observation_quality" in outcome:
                            prior["next_open"]["observation_quality"] = outcome["observation_quality"]
            trace.append({
                "date": day, "close": close, "mark_basis": mark_basis, "trading_status": status,
                "closing_observation": observation_reference(close_row),
                "opening_observation": observation_reference(opening),
                "market": features["market"], "common_evaluable": features["common_evaluable"],
                "sample_gaps": features["reasons"],
                "entitlements": {"opening": [] if start_day else [asdict(item) for item in action["opening"]],
                                 "closing": [] if start_day else [asdict(item) for item in action["closing"]],
                                 "factor_observation_ids": action["factors"]},
                "paths": paths,
            })
            previous_day = day

    path_gaps = [{
        "date": day, "reason": reason, "phase": phase, "observation_quality": quality,
        "paths": sorted(names),
        "affected_metrics": list(_NAV_METRICS if phase == "valuation" else (*_NAV_METRICS, *_TRADE_METRICS)),
    } for (day, reason, phase, quality), names in sorted(gaps.items())]
    pending = {name: detail["pending_intent"] for name, detail in trace[-1]["paths"].items()
               if detail["pending_intent"]}
    return trace, path_gaps, {
        "initial_date": start, "initial_mark": initial_marks, "initial_accounts": initial_accounts,
        "last_session": trace[-1]["date"], "pending_intents": pending,
        "pending_policy": "末日的超窗意图未读取下一开盘，也未计入成交或未成交。",
    }, {"decision": DECISION_RULES_VERSION, "execution": EXECUTION_RULES_VERSION,
        "execution_parameters": asdict(rules), "accounting_basis": SIMULATION_BASIS,
        "initial": initial}


def _summarize(trace, gaps, boundary):
    metrics = {}
    for name in PATHS:
        affected = [gap for gap in gaps if name in gap["paths"]]
        base = Decimal(boundary["initial_mark"][name]["nav"])
        values = _metrics(trace, name, base, not affected, _round_trips(trace, name))
        values["metric_scope"] = {
            "returns": "complete_path" if not affected else "unavailable",
            "end_nav": "complete_path" if not affected else "observed_only",
            "trade_totals": "observed_only" if any(gap["phase"] != "valuation" for gap in affected) else "complete_path",
        }
        metrics[name] = values
    for name in PATHS:
        for baseline in PATHS[2:]:
            own, control = metrics[name]["total_return"], metrics[baseline]["total_return"]
            metrics[name][f"excess_return_vs_{baseline}"] = (
                _decimal_text(Decimal(own) - Decimal(control)) if own is not None and control is not None else None
            )
    return metrics


def _fill_value(fill):
    return {key: value for key, value in fill.items() if key != "event_id"} if fill else None


def _opportunities(trace, sample):
    entry = dict.fromkeys(("e0", "e1"), 0)
    missing = dict.fromkeys(("e0", "e1"), 0)
    direct, candidate_differences, action_differences, execution_differences, fill_differences = [], [], [], [], []
    for session in trace:
        day = session["date"]
        e0, e1 = (session["paths"][name] for name in ("e0", "e1"))
        for name, path in (("e0", e0), ("e1", e1)):
            if path["decision_before_gate"]["action"] == "BUY":
                if session["common_evaluable"]:
                    entry[name] += 1
                else:
                    missing[name] += 1
        if e1["gate"]["reason"] == "MARKET_AT_OR_BELOW_AVERAGE":
            direct.append(day)
        if e0["decision_before_gate"] != e1["decision_before_gate"]:
            candidate_differences.append(day)
        if any(e0["decision"][key] != e1["decision"][key] for key in ("action", "quantity")):
            action_differences.append(day)
        comparisons = [{**item["next_open"], "fill": _fill_value(item["next_open"]["fill"])} for item in (e0, e1)]
        if comparisons[0] != comparisons[1] and any(item["status"] != "OUTSIDE_WINDOW" and
                                                   item["status"] != "NO_INTENT" for item in comparisons):
            execution_differences.append(day)
        if comparisons[0]["fill"] != comparisons[1]["fill"]:
            fill_differences.append(day)
    return {
        "nominal_signal_days": sample["candidate_day_count"], "common_evaluable_days": sample["common_evaluable_day_count"],
        "coverage_loss_days": sample["loss_day_count"], "coverage_losses_by_reason": sample["loss_reason_counts"],
        "warmup_days_by_feature": sample["warmup_day_counts"],
        "evaluable_buy_candidates": entry, "buy_candidates_blocked_by_coverage": missing,
        "market_filter": {"blocked_buy_count": len(direct), "blocked_buy_signal_dates": direct,
                          "eligible_e1_buy_candidates": entry["e1"],
                          "common_evaluable_signal_days": sample["common_evaluable_day_count"]},
        "path_divergence": {
            "pre_gate_candidate_difference_count": len(candidate_differences),
            "pre_gate_candidate_difference_dates": candidate_differences,
            "final_action_difference_dates": action_differences,
            "next_open_difference_signal_dates": execution_differences,
            "next_open_fill_difference_signal_dates": fill_differences,
        },
    }


def _economic_account(account):
    return {
        "cash": account["cash"], "available_cash": account["available_cash"], "known_sellable": account["known_sellable"],
        "lots": [{key: value for key, value in lot.items() if key not in ("lot_id", "source_event_id")}
                 for lot in account["lots"]],
        "receivables": [{key: value for key, value in item.items() if key != "source_lot_id"}
                        for item in account["receivables"]],
    }


def _check_always_true(inputs):
    trace, gaps, boundary, _ = _replay(inputs, True)
    differences = []
    for day in trace:
        e0, e1 = (day["paths"][name] for name in ("e0", "e1"))
        if (_fill_value(e0["execution"]["fill"]) != _fill_value(e1["execution"]["fill"])
                or any(e0["execution"][key] != e1["execution"][key] for key in ("status", "reason"))
                or _economic_account(e0["open_account"]) != _economic_account(e1["open_account"])
                or _economic_account(e0["account"]) != _economic_account(e1["account"])
                or e0["valuation"] != e1["valuation"]):
            differences.append(day["date"])
    metrics = _summarize(trace, gaps, boundary)
    return {
        "condition": "always_true_on_common_evaluable_days",
        "passed": not differences and metrics["e0"] == metrics["e1"],
        "compared_sessions": len(trace), "common_evaluable_days": inputs.sample["common_evaluable_day_count"],
        "difference_dates": differences,
        "e0": {key: metrics["e0"][key] for key in ("fills", "costs", "slippage_cost", "end_nav")},
        "e1": {key: metrics["e1"][key] for key in ("fills", "costs", "slippage_cost", "end_nav")},
    }


def calculate_development(inputs, *, market_always_true=False):
    """Calculate the four isolated paths and a deterministic receipt from the frozen input."""
    basis = {
        "replay_version": REPLAY_VERSION, "preset_id": inputs.preset["id"], "preset": inputs.preset,
        "snapshot_id": inputs.snapshot["snapshot_id"], "snapshot": inputs.snapshot, "input_ref": inputs.input_ref,
        "sample": inputs.sample,
    }
    if inputs.sample["effective_window"] is None:
        return _identified({**basis, "status": "blocked", "failure_stage": "common_sample", "gaps": [{
            "reason": "开发窗口没有两组特征同时就绪的交易日",
            "required_evidence": "连续且可用的江西铜业量价与权益观测及沪深 300 收盘观测",
            "blocking": True, "coverage_ref": inputs.input_ref + "#sample",
            "candidate_day_count": inputs.sample["candidate_day_count"],
            "loss_reason_counts": inputs.sample["loss_reason_counts"],
        }]})
    trace, gaps, boundary, rules = _replay(inputs, market_always_true)
    receipt = {
        **basis, "status": "computed", "rules": rules, "sessions": trace, "boundary": boundary,
        "metrics": _summarize(trace, gaps, boundary), "opportunities": _opportunities(trace, inputs.sample),
        "coverage": {"sessions": len(trace), "path_gaps": gaps,
                     "input_scope_gaps": [reason for _, reason, _ in inputs.market["gaps"]]},
        "metric_basis": {
            "returns": "同一首个共同信号日盘后净值，收盘按原始收盘价，含已确认的股息红利税前权益和交易成本。",
            "slippage_cost": "成交价相对于原始开盘价的绝对偏差乘实际成交股份，已计入成交价。",
            "coverage": "共同机会覆盖按信号日去重；估值、成交和权益证据缺口另按日期和路径登记。",
        },
        "market_condition": "always_true" if market_always_true else "strictly_above_average",
    }
    if not market_always_true:
        receipt["self_check"] = _check_always_true(inputs)
        if not receipt["self_check"]["passed"]:
            return _identified({**receipt, "status": "failed", "failure_stage": "self_check",
                                "error": "E1 恒真自检与 E0 的撮合或账本轨迹不一致"})
    return _identified(receipt)


def prepare_development(data_dir, snapshot_id, *, preset_id):
    """Return task inputs and a computed receipt or a structured preflight/calculation failure."""
    preset = development_preset(preset_id)
    end = preset["protocol"]["windows"]["development"]["end"]
    manifest = {
        "kind": "development_experiment", "symbol": preset["symbol"], "preset": preset, "snapshot_id": snapshot_id,
        "as_of": utc_timestamp(session_time(end, 15, 5)),
    }
    stage = "freeze_inputs"
    try:
        inputs = freeze_development_inputs(data_dir, snapshot_id, preset_id=preset_id)
        manifest = public_manifest(inputs)
        stage = "replay"
        return manifest, calculate_development(inputs)
    except Exception as error:
        return manifest, _identified({
            "status": "failed", "replay_version": REPLAY_VERSION, "preset_id": preset_id, "preset": preset,
            "snapshot_id": snapshot_id, "input_ref": manifest.get("input_ref"), "failure_stage": stage,
            "error": str(error), "error_type": type(error).__name__,
        })


def development_attempt_fields(receipt):
    return {
        **{key: receipt[key] for key in ("status", "preset_id", "snapshot_id", "input_ref", "gaps", "failure_stage", "error")
           if key in receipt},
        "development_receipt_id": receipt["receipt_id"],
    }


def store_development_receipt(db, task_id, receipt):
    ensure_schema(db, _SCHEMA)
    db.execute("INSERT INTO research_development_receipt VALUES (?, ?, ?)",
               (task_id, receipt["receipt_id"], json_text(receipt)))


def read_development_receipt(data_dir, task_id):
    with database(data_dir) as db:
        ensure_schema(db, _SCHEMA)
        row = db.execute("SELECT receipt FROM research_development_receipt WHERE task_id=?", (task_id,)).fetchone()
    if row is None:
        raise ValueError(f"研究任务没有冻结开发回执：{task_id}")
    return json.loads(row["receipt"])


def verify_development(data_dir, task_id):
    """Rebuild one task's frozen calculation offline, without writing a new task or receipt."""
    previous = read_development_receipt(data_dir, task_id)
    if previous["status"] == "failed":
        raise ValueError(f"研究任务的开发计算失败，无法核验实验结果：{task_id}")
    _, recomputed = prepare_development(data_dir, previous["snapshot_id"], preset_id=previous["preset_id"])
    checks = {name: name in recomputed and json_text(previous[name]) == json_text(recomputed[name])
              for name in ("input_ref", "sample", "metrics", "opportunities", "coverage", "sessions", "self_check")
              if name in previous}
    checks["receipt_id"] = previous["receipt_id"] == recomputed["receipt_id"]
    return {
        "task_id": task_id, "verified": all(checks.values()), "checks": checks,
        "receipt_id": previous["receipt_id"], "recomputed_receipt_id": recomputed["receipt_id"],
    }
