"""The Jiangxi Copper E0/E1 preset and its bounded development inputs."""

from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from urllib.parse import urlsplit, urlunsplit

from roll.v3.experiment import company_action_changes, economic_action_gap
from roll.v3.market import (
    RECONSTRUCTED_RESEARCH, STRICT_HISTORICAL_AS_OF, get_snapshot, read_snapshot,
    snapshot_window_selections, utc_timestamp,
)
from roll.v3.storage import database, json_text, session_time, sessions
from roll.v3.strategy import default_trend_definition, trend_conditions, trend_economic_close


PRESET_ID = "jxcc-e0-e1-v1"
PATHS = ("e0", "e1", "buy_and_hold", "no_active_trading")
_OPEN = ("open", "prior_close", "pre_close", "pre_close_basis", "trading_status", "risk_warning", "price_limit_rate")
_FIELDS = {
    "daily_bar": (*_OPEN, "close", "high", "low", "volume", "amount"),
    "daily_open": _OPEN,
    "adjustment_factor": ("dividend_per_share", "bonus_per_share", "rights_per_share"),
    "corporate_action": ("record_date", "ex_date", "payment_date", "listing_date", "cash_per_share",
                         "shares_per_share", "reference_deduction"),
}
_PROVENANCE = (
    "seq", "series", "symbol", "trade_date", "item_id", "source", "revision", "received_at",
    "selected_available_at", "availability_assumption", "reconstruction_only",
)


def development_preset(preset_id=PRESET_ID):
    """Return the fixed experiment rules available before seeing any result."""
    if preset_id != PRESET_ID:
        raise ValueError(f"未知开发实验预设 {preset_id}")
    strategy, source = default_trend_definition()
    protocol = {key: source[key] for key in (
        "family", "version", "strategy_version", "initial_cash_cny", "baselines", "costs", "decision_order",
    )}
    protocol["windows"] = {"development": source["windows"]["development"]}
    return {
        "id": PRESET_ID, "symbol": "600362.SH", "strategy": strategy, "protocol": protocol,
        "e0": {"feature": "total_return_index", "parameters": strategy["parameters"], "entry_operator": ">"},
        "e1": {"symbol": "000300.SH", "feature": "raw_close", "lookback_sessions": 20,
               "includes_signal_day": True, "entry_operator": ">", "applies_to": "buy_only"},
        "signal_time": "15:05 Asia/Shanghai", "execution_time": "next_session_open 09:30 Asia/Shanghai",
    }


@dataclass(frozen=True)
class FrozenDevelopmentInputs:
    preset: dict
    snapshot: dict
    sample: dict
    market: dict
    input_ref: str


def _source_url(value):
    if not value:
        return None
    try:
        url = urlsplit(value)
    except ValueError:
        return None
    if url.scheme not in ("https", "http") or not url.hostname or url.username or url.password:
        return None
    return urlunsplit((url.scheme, url.netloc, url.path, "", ""))


def _project(row):
    return {
        **{key: row[key] for key in _PROVENANCE},
        "source_ref": _source_url(row["source_ref"]),
        "payload": {key: row["payload"][key] for key in _FIELDS[row["series"]]
                    if key in row["payload"] and type(row["payload"][key]) in (str, int, float, bool, type(None))},
    }


def _selections(data_dir, snapshot_id, symbol, series, cutoffs, witnessed):
    selected = snapshot_window_selections(
        data_dir, snapshot_id, series=series, symbol=symbol, cutoffs=cutoffs, strict_receipt=True,
    )
    for items in selected.values():
        for key, (row, state) in items.items():
            if row:
                projected = _project(row)
                items[key] = (projected, state)
                witnessed[row["seq"]] = projected
    return selected


def _daily_quotes(data_dir, snapshot_id, symbol, series, cutoffs, witnessed):
    selected = _selections(data_dir, snapshot_id, symbol, series, cutoffs, witnessed)
    return {day: items.get("", (None, "missing")) for day, items in selected.items()}


def _read_actions(data_dir, snapshot_id, symbol, days, closes, factors, openings, evenings, witnessed):
    prior_actions, details, failures = {}, {}, {}
    previous_cutoff = session_time(days[0], 0)
    with database(data_dir) as db:
        for day in days:
            scope = {"series": "corporate_action", "symbol": symbol, "start": days[0], "end": day,
                     "db": db, "strict_receipt": True}
            at_open = read_snapshot(data_dir, snapshot_id, cutoff=openings[day], **scope)
            at_close = read_snapshot(data_dir, snapshot_id, cutoff=evenings[day], **scope)
            projected = []
            for record in (at_open, at_close):
                rows = []
                for source in record["observations"]:
                    row = _project(source)
                    ex_date = row["payload"].get("ex_date", row["trade_date"])
                    try:
                        if date.fromisoformat(ex_date).isoformat() > day:
                            continue
                    except (TypeError, ValueError):
                        pass  # The entitlement reader records malformed terms as a coverage issue.
                    rows.append(row)
                projected.append(rows)
                witnessed.update({row["seq"]: row for row in rows})
            open_actions, opening, open_issues = company_action_changes(
                projected[0], openings[day], previous_cutoff, prior_actions,
            )
            prior_actions, closing, close_issues = company_action_changes(
                projected[1], evenings[day], openings[day], open_actions,
            )
            previous_cutoff = evenings[day]
            mark = closes[day][0]
            selected_factors = [row for row, _ in factors[day].values() if row]
            actions_today = [action for action in prior_actions.values() if action.ex_date == day]
            issue = economic_action_gap(mark["payload"] if mark else {}, selected_factors, actions_today)
            issues = [*open_issues, *close_issues]
            if issue:
                issues.append((day, issue, tuple(action.record_date for action in actions_today)))
            states = {state for scope_coverage in at_close["coverage"]
                      for state in scope_coverage["quality_by_date"].get(day, ()) if state != "usable"}
            for state in sorted(states):
                issues.append((day, f"CORPORATE_ACTION_{state.upper()}", ()))
            for state in sorted({state for _, state in factors[day].values() if state != "usable"}):
                issues.append((day, f"ADJUSTMENT_FACTOR_{state.upper()}", ()))
            if any(reason == "INVALID_CORPORATE_ACTION" and date == day for date, reason, _ in close_issues):
                states.add("unusable")
            details[day] = {"opening": opening, "closing": closing, "issues": issues,
                            "factors": [factor["seq"] for factor in selected_factors]}
            failures[day] = sorted(states)
    return details, failures


def _close(row, status, *, require_trading=False):
    if row is None:
        return None, status
    payload = row["payload"]
    trading = payload.get("trading_status")
    if trading != "trading" and (require_trading or trading is not None):
        return None, trading if trading in ("suspended", "unknown") else "trading_status"
    try:
        close = Decimal(str(payload.get("close")))
    except InvalidOperation:
        return None, "close"
    return (close, None) if close.is_finite() and close > 0 else (None, "close")


def _stock_signal(day, at, preset, history, reasons):
    parameters = preset["e0"]["parameters"]
    required = parameters["slow"]
    result = {"trade_date": day, "as_of": utc_timestamp(at), "strategy_version": preset["strategy"]["version"],
              "symbol": preset["symbol"], "status": "missing" if reasons else "warmup", "signal": None,
              "target_fraction": None, "conditions": None, "required_sessions": required,
              "available_sessions": len(history),
              "missing": [{"trade_date": day, "reason": reason} for reason in reasons]}
    if len(history) == required:
        index = [Decimal(100)]
        for (_, previous, _), (_, _, economic) in zip(history, list(history)[1:]):
            level = index[-1]
            index.append(level if economic == previous else level * economic / previous)
        conditions = trend_conditions(index, parameters, history[0][0])
        rising = conditions["above_slow_average"]
        result.update(status="ready", conditions=conditions, signal="long" if rising else "flat",
                      target_fraction="1" if rising else "0")
    return result


def _common_sample(preset, days, evenings, stock, benchmark, factors, action_failures):
    nominal = preset["protocol"]["windows"]["development"]
    stock_history = deque(maxlen=preset["e0"]["parameters"]["slow"])
    market_history = deque(maxlen=preset["e1"]["lookback_sessions"])
    by_date, losses, common = {}, {}, []
    for day in days:
        stock_row, stock_status = stock[day]
        stock_close, stock_issue = _close(stock_row, stock_status, require_trading=True)
        stock_reasons = [{"feature": "e0", "reason": stock_issue}] if stock_issue else []
        factor_rows = [row["payload"] for row, _ in factors[day].values() if row]
        factor_failures = sorted({state for _, state in factors[day].values() if state != "usable"})
        stock_reasons.extend({"feature": "adjustment_factor", "reason": state} for state in factor_failures)
        stock_reasons.extend({"feature": "corporate_action", "reason": state} for state in action_failures[day])
        economic = stock_close
        if stock_close is not None and (stock_history or factor_rows) and not factor_failures:
            economic, issue = trend_economic_close(stock_row["payload"], factor_rows)
            if issue:
                stock_reasons.append({"feature": "adjustment_factor", "reason": issue})
        if stock_reasons:
            stock_history.clear()
        else:
            stock_history.append((day, stock_close, economic))
        e0 = _stock_signal(day, evenings[day], preset, stock_history, [item["reason"] for item in stock_reasons])

        market_close, market_issue = _close(*benchmark[day])
        if market_issue:
            market_history.clear()
        else:
            market_history.append(market_close)
        average = sum(market_history) / len(market_history) if len(market_history) == market_history.maxlen else None
        market = {"status": "ready" if average is not None else "missing" if market_issue else "warmup",
                  "close": format(market_close, "f") if market_close is not None else None,
                  "average": format(average, "f") if average is not None else None,
                  "above_average": market_close > average if average is not None else None,
                  "available_sessions": len(market_history), "required_sessions": market_history.maxlen}
        reasons = stock_reasons or ([{"feature": "e0", "reason": "warmup"}] if e0["status"] == "warmup" else [])
        if market["status"] != "ready":
            reasons.append({"feature": "market", "reason": market_issue or "warmup"})
        if reasons:
            losses[day] = reasons
        else:
            common.append(day)
        by_date[day] = {"e0": e0, "market": market, "common_evaluable": not reasons, "reasons": reasons}
    return {
        "nominal_window": nominal, "effective_window": {"start": common[0], "end": nominal["end"]} if common else None,
        "candidate_day_count": len(days), "common_evaluable_day_count": len(common), "common_evaluable_dates": common,
        "loss_day_count": len(losses), "losses": losses, "by_date": by_date,
        "loss_reason_counts": dict(Counter(f'{item["feature"]}:{item["reason"]}'
                                             for reasons in losses.values() for item in reasons)),
    }


def _snapshot_audit(snapshot, witnessed):
    grouped = defaultdict(list)
    for row in witnessed.values():
        grouped[row["series"], row["symbol"], row["source"]].append(row)
    sources = []
    for (series, symbol, source), rows in sorted(grouped.items()):
        received_times = sorted({row["received_at"] for row in rows})
        sources.append({
            "series": series, "symbol": symbol, "source": source,
            "revisions": sorted({str(row["revision"]) for row in rows if row["revision"] is not None}),
            "first_observation_seq": min(row["seq"] for row in rows),
            "last_observation_seq": max(row["seq"] for row in rows),
            "first_received_at": received_times[0], "last_received_at": received_times[-1],
            "availability_assumptions": sorted({row["availability_assumption"] for row in rows
                                               if row["availability_assumption"]}),
        })
    reconstructed = snapshot["use_mode"] == RECONSTRUCTED_RESEARCH
    return {
        "snapshot_id": snapshot["snapshot_id"], "as_of": snapshot["as_of"], "use_mode": snapshot["use_mode"],
        "selection_rules_version": snapshot["selection_rules_version"], "sources": sources,
        "availability_basis": ("逐日以冻结记录的历史证据或显式重建假设判断；实际取得时间以来源记录为准。"
                               if reconstructed else "逐日使用同时具备披露证据与实际取得时间的记录。"),
        "risks": ["同一数据序列可能只选到一个来源，来源的独立核验与版本修订可能影响重建结果。"],
        "external_data_requests": 0, "paid_data_cost_cny": "0",
    }


def freeze_development_inputs(data_dir, snapshot_id, *, preset_id):
    """Read the immutable DataSnapshot using only the preset window and daily phase cutoffs."""
    preset = development_preset(preset_id)
    snapshot = get_snapshot(data_dir, snapshot_id)
    if snapshot["use_mode"] not in (RECONSTRUCTED_RESEARCH, STRICT_HISTORICAL_AS_OF):
        raise ValueError("开发实验需要重建研究或严格历史时点数据快照")
    window = preset["protocol"]["windows"]["development"]
    start, end = window["start"], window["end"]
    days = list(sessions(start, end))
    evenings = {day: session_time(day, 15, 5) for day in days}
    openings = {day: session_time(day, 9, 30) for day in days}
    symbol = preset["symbol"]
    witnessed = {}
    stock = _daily_quotes(data_dir, snapshot_id, symbol, "daily_bar", evenings, witnessed)
    index = _daily_quotes(data_dir, snapshot_id, preset["e1"]["symbol"], "daily_bar", evenings, witnessed)
    opened = _daily_quotes(data_dir, snapshot_id, symbol, "daily_open", openings, witnessed)
    factors = _selections(data_dir, snapshot_id, symbol, "adjustment_factor", evenings, witnessed)
    actions, failures = _read_actions(data_dir, snapshot_id, symbol, days, stock, factors, openings, evenings, witnessed)
    sample = _common_sample(preset, days, evenings, stock, index, factors, failures)
    covered = {item["series"] for item in snapshot["scope"]
               if item["symbol"] == symbol and item["start"] <= start and item["end"] >= end}
    market = {
        "days": days, "gaps": [(start, f"SNAPSHOT_SCOPE_MISSING:{series}", PATHS)
                               for series in _FIELDS if series not in covered],
        "opens": {day: row for day, (row, _) in opened.items()},
        "closes": {day: row for day, (row, _) in stock.items()},
        "actions": actions, "signals": {day: detail["e0"] for day, detail in sample["by_date"].items()},
    }
    snapshot_metadata = _snapshot_audit(snapshot, witnessed)
    # Track the snapshot reference separately so unrelated imports cannot change the bounded input identity.
    binding = {"preset": preset, "sample": sample, "gaps": market["gaps"],
               "snapshot": {key: snapshot_metadata[key] for key in ("use_mode", "selection_rules_version")},
               "observations": list(witnessed.values()),
               "actions": {day: {**detail, "opening": [asdict(action) for action in detail["opening"]],
                                 "closing": [asdict(action) for action in detail["closing"]]}
                           for day, detail in actions.items()}}
    input_ref = "development-input-" + sha256(json_text(binding).encode()).hexdigest()
    return FrozenDevelopmentInputs(preset, snapshot_metadata, sample, market, input_ref)


def public_manifest(inputs):
    """Describe the bounded experiment basis without loading general research or account inputs."""
    end = inputs.sample["nominal_window"]["end"]
    return {"kind": "development_experiment", "symbol": inputs.preset["symbol"],
            "question": "沪深 300 入场条件改变了江西铜业趋势策略的哪些开发期结果？",
            "as_of": utc_timestamp(session_time(end, 15, 5)), "snapshot_id": inputs.snapshot["snapshot_id"],
            "preset": inputs.preset, "snapshot": inputs.snapshot, "sample": inputs.sample, "input_ref": inputs.input_ref}
