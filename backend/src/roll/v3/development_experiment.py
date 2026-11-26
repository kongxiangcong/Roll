"""The Jiangxi Copper E0/E1 preset and its bounded development inputs."""

from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from urllib.parse import urlsplit, urlunsplit

from roll.v3.experiment import company_action_changes, economic_action_gap, economic_terms_gap
from roll.v3.market import (
    RECONSTRUCTED_RESEARCH, STRICT_HISTORICAL_AS_OF, get_snapshot, read_snapshot,
    snapshot_rolling_selections, utc_timestamp,
)
from roll.v3.storage import database, json_text, session_time, sessions
from roll.v3.strategy import default_trend_definition, evaluate_trend_window, trend_economic_close


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
_SELECTION_STATES = {"usable", "missing", "not_visible", "unusable", "conflict", "withdrawn"}


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
        "simulation_risk_budget": {"cash_reserve": "0", "max_total_exposure": "1",
                                   "max_symbol_exposure": "1", "max_industry_exposure": "1"},
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


def _selection_state(state):
    return state if state in _SELECTION_STATES else "unusable"


def _selections(data_dir, snapshot_id, symbol, series, cutoffs, witnessed, *, lookback=1):
    selected = snapshot_rolling_selections(
        data_dir, snapshot_id, series=series, symbol=symbol, cutoffs=cutoffs, lookback=lookback,
    )
    daily, revisions = {}, {}
    for cutoff_day, items in selected.items():
        daily[cutoff_day] = {}
        for (observed_day, item_id), (row, state) in items.items():
            projected = _project(row) if row else None
            selection = (projected, _selection_state(state))
            if observed_day == cutoff_day:
                daily[cutoff_day][item_id] = selection
            else:
                revisions.setdefault(cutoff_day, {}).setdefault(observed_day, {})[item_id] = selection
            if projected and observed_day == cutoff_day:
                witnessed[row["seq"]] = projected
    return daily, revisions


def _daily_quotes(selections):
    return {day: items.get("", (None, "missing")) for day, items in selections.items()}


def _read_actions(data_dir, snapshot_id, symbol, days, closes, factors, openings, evenings, witnessed):
    prior_actions, details, evidence = {}, {}, {}
    previous_cutoff = session_time(days[0], 0)
    with database(data_dir) as db:
        for day in days:
            scope = {"series": "corporate_action", "symbol": symbol, "start": days[0], "end": day, "db": db}
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
            actions_by_ex_date = defaultdict(list)
            for action in prior_actions.values():
                actions_by_ex_date[action.ex_date].append(action)
            actions_today = actions_by_ex_date.get(day, ())
            issue = economic_action_gap(mark["payload"] if mark else {}, selected_factors, actions_today)
            issues = [*open_issues, *close_issues]
            if issue:
                issues.append((day, issue, tuple(action.record_date for action in actions_today)))
            states_by_date = defaultdict(set)
            for scope_coverage in at_close["coverage"]:
                for observed, states in scope_coverage["quality_by_date"].items():
                    states_by_date[observed].update(_selection_state(state) for state in states if state != "usable")
            for state in sorted(states_by_date.get(day, ())):
                issues.append((day, f"CORPORATE_ACTION_{state.upper()}", ()))
            for state in sorted({state for _, state in factors[day].values() if state != "usable"}):
                issues.append((day, f"ADJUSTMENT_FACTOR_{state.upper()}", ()))
            for observed, reason, _ in close_issues:
                if reason == "INVALID_CORPORATE_ACTION":
                    states_by_date[observed].add("unusable")
            details[day] = {"opening": opening, "closing": closing, "issues": issues,
                            "factors": [factor["seq"] for factor in selected_factors]}
            evidence[day] = (actions_by_ex_date, states_by_date)
    return details, evidence


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


def observation_reference(row):
    return {key: value for key, value in row.items() if key != "payload"} if row else None


def _stock_signal(day, at, preset, history, reasons):
    parameters = preset["e0"]["parameters"]
    required = parameters["slow"]
    result = {"trade_date": day, "as_of": utc_timestamp(at), "strategy_version": preset["strategy"]["version"],
              "symbol": preset["symbol"], "status": "missing" if reasons else "warmup", "signal": None,
              "target_fraction": None, "conditions": None, "required_sessions": required,
              "available_sessions": len(history),
              "missing": [{"trade_date": reason.get("observation_date", day), "reason": reason["reason"]}
                          for reason in reasons]}
    if not reasons and len(history) == required:
        result.update(evaluate_trend_window(list(history), parameters))
    return result


def _stock_input(stock_selection, factors, actions, action_failures, *, base):
    stock_row, stock_status = stock_selection
    close, stock_issue = _close(stock_row, stock_status, require_trading=True)
    reasons = [{"feature": "e0", "reason": stock_issue}] if stock_issue else []
    factor_rows = [row for row, _ in factors.values() if row]
    factor_failures = sorted({state for _, state in factors.values() if state != "usable"})
    reasons.extend({"feature": "adjustment_factor", "reason": state} for state in factor_failures)
    reasons.extend({"feature": "corporate_action", "reason": state} for state in sorted(action_failures))
    bar = stock_row["payload"] if stock_row else {}
    terms_issue = economic_terms_gap(bar, factor_rows, actions)
    if terms_issue:
        reasons.append({"feature": "adjustment_factor", "reason": terms_issue})
    economic = close
    if not reasons and (not base or factor_rows):
        economic, issue = trend_economic_close(bar, [row["payload"] for row in factor_rows])
        if issue:
            reasons.append({"feature": "adjustment_factor", "reason": issue})
    return close, economic, reasons


def _common_sample(preset, days, evenings, stock_series, index_series, factor_series, action_evidence, witnessed):
    nominal = preset["protocol"]["windows"]["development"]
    stock, stock_revisions = stock_series
    benchmark, market_revisions = index_series
    factors, factor_revisions = factor_series
    stock_versions, market_versions, factor_versions = stock.copy(), benchmark.copy(), factors.copy()
    stock_history = deque(maxlen=preset["e0"]["parameters"]["slow"])
    market_history = deque(maxlen=preset["e1"]["lookback_sessions"])
    by_date, losses, common = {}, {}, []
    restarted = {"e0": False, "market": False}
    warmup_day_counts = Counter()
    for day in days:
        stock_versions.update({past: items[""] for past, items in stock_revisions.get(day, {}).items() if "" in items})
        market_versions.update({past: items[""] for past, items in market_revisions.get(day, {}).items() if "" in items})
        for past, items in factor_revisions.get(day, {}).items():
            factor_versions[past] = {**factor_versions[past], **items}
        actions, action_failures = action_evidence[day]
        stock_close, economic, stock_reasons = _stock_input(
            stock[day], factors[day], actions.get(day, ()), action_failures.get(day, ()), base=not stock_history,
        )
        revised = {}

        def record_revision(row, original):
            if row and row != original:
                witnessed[row["seq"]] = row
                revised[row["seq"]] = observation_reference(row)

        window = []
        if stock_reasons:
            restarted["e0"] |= bool(stock_history)
            stock_history.clear()
        else:
            stock_history.append(day)
            for past in list(stock_history)[:-1]:
                close, past_economic, unavailable = _stock_input(
                    stock_versions[past], factor_versions[past], actions.get(past, ()), action_failures.get(past, ()),
                    base=past == stock_history[0],
                )
                record_revision(stock_versions[past][0], stock[past][0])
                for item_id, (row, _) in factor_versions[past].items():
                    record_revision(row, factors[past].get(item_id, (None, "missing"))[0])
                original_actions = {action.observation_seq for action in action_evidence[past][0].get(past, ())}
                for action in actions.get(past, ()):
                    if action.observation_seq not in original_actions:
                        record_revision(witnessed[action.observation_seq], None)
                stock_reasons.extend({**reason, "observation_date": past} for reason in unavailable)
                if not unavailable:
                    window.append((past, close, past_economic))
            window.append((day, stock_close, economic))
        e0 = _stock_signal(day, evenings[day], preset, window, stock_reasons)

        market_close, market_issue = _close(*benchmark[day])
        market_reasons = [{"feature": "market", "reason": market_issue}] if market_issue else []
        market_window = []
        if market_issue:
            restarted["market"] |= bool(market_history)
            market_history.clear()
        else:
            market_history.append(day)
            for past in market_history:
                close, unavailable = _close(*market_versions[past])
                record_revision(market_versions[past][0], benchmark[past][0])
                if unavailable:
                    market_reasons.append({"feature": "market", "reason": unavailable, "observation_date": past})
                else:
                    market_window.append(close)
        average = sum(market_window) / len(market_window) if len(market_window) == market_history.maxlen else None
        market = {"status": "ready" if average is not None else "missing" if market_reasons else "warmup",
                  "close": format(market_close, "f") if market_close is not None else None,
                  "average": format(average, "f") if average is not None else None,
                  "above_average": market_close > average if average is not None else None,
                  "available_sessions": len(market_window), "required_sessions": market_history.maxlen}
        reasons = stock_reasons or ([{"feature": "e0", "reason": "warmup"}] if e0["status"] == "warmup" else [])
        if market["status"] != "ready":
            reasons.extend(market_reasons or [{"feature": "market", "reason": "warmup"}])
        if reasons:
            losses[day] = reasons
        else:
            common.append(day)
        preparation = {feature: "restarted_warmup" if restarted[feature] else "initial_warmup"
                       for feature, status in (("e0", e0["status"]), ("market", market["status"])) if status == "warmup"}
        warmup_day_counts.update(f"{feature}:{kind}" for feature, kind in preparation.items())
        by_date[day] = {"e0": e0, "market": market, "common_evaluable": not reasons, "reasons": reasons,
                        "preparation": preparation,
                        "stock_observation": observation_reference(stock[day][0]),
                        "index_observation": observation_reference(benchmark[day][0])}
        if revised:
            by_date[day]["revised_feature_observations"] = list(revised.values())
    return {
        "nominal_window": nominal, "effective_window": {"start": common[0], "end": nominal["end"]} if common else None,
        "candidate_day_count": len(days), "common_evaluable_day_count": len(common), "common_evaluable_dates": common,
        "loss_day_count": len(losses), "losses": losses, "by_date": by_date,
        "warmup_day_counts": dict(warmup_day_counts),
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
                               if reconstructed else "逐日按有证据的历史可得时间选取记录，并保留实际取得时间。"),
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
    slow = preset["e0"]["parameters"]["slow"]
    stock_selections, stock_revisions = _selections(
        data_dir, snapshot_id, symbol, "daily_bar", evenings, witnessed, lookback=slow,
    )
    index_selections, index_revisions = _selections(
        data_dir, snapshot_id, preset["e1"]["symbol"], "daily_bar", evenings, witnessed,
        lookback=preset["e1"]["lookback_sessions"],
    )
    open_selections, _ = _selections(data_dir, snapshot_id, symbol, "daily_open", openings, witnessed)
    factors, factor_revisions = _selections(data_dir, snapshot_id, symbol, "adjustment_factor", evenings, witnessed,
                                           lookback=slow)
    stock, index, opened = map(_daily_quotes, (stock_selections, index_selections, open_selections))
    actions, action_evidence = _read_actions(data_dir, snapshot_id, symbol, days, stock, factors, openings, evenings,
                                             witnessed)
    sample = _common_sample(preset, days, evenings, (stock, stock_revisions), (index, index_revisions),
                            (factors, factor_revisions), action_evidence, witnessed)
    covered = {item["series"] for item in snapshot["scope"]
               if item["symbol"] == symbol and item["start"] <= start and item["end"] >= end}
    entitlement_scope = {
        series: [(item["start"], item["end"]) for item in snapshot["scope"]
                 if item["symbol"] == symbol and item["series"] == series]
        for series in ("corporate_action", "adjustment_factor")
    }
    market = {
        "days": days, "gaps": [(start, f"SNAPSHOT_SCOPE_MISSING:{series}", PATHS)
                               for series in _FIELDS if series not in covered],
        "opens": {day: row for day, (row, _) in opened.items()},
        "opening_quality": {day: state for day, (_, state) in opened.items()},
        "closing_quality": {day: state for day, (_, state) in stock.items()},
        "missing_entitlement_scope": {
            day: [series for series, intervals in entitlement_scope.items()
                  if not any(first <= day <= last for first, last in intervals)] for day in days
        },
        "closes": {day: row for day, (row, _) in stock.items()},
        "actions": actions, "signals": {day: detail["e0"] for day, detail in sample["by_date"].items()},
    }
    snapshot_metadata = _snapshot_audit(snapshot, witnessed)
    # Track the snapshot reference separately so unrelated imports cannot change the bounded input identity.
    binding = {"preset": preset, "sample": sample, "gaps": market["gaps"],
               "opening_quality": market["opening_quality"], "closing_quality": market["closing_quality"],
               "missing_entitlement_scope": market["missing_entitlement_scope"],
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
