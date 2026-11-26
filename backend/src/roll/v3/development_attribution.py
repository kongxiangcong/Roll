"""Trace development comparisons back to simulated signals and ledger activity."""

from decimal import Decimal

from roll.v3.experiment_metrics import _decimal_text


_PATHS = ("e0", "e1")
_ZERO = Decimal(0)


def _signal_ref(date):
    return f"signal:{date}"


def _market_block(session):
    return session["paths"]["e1"]["gate"]["reason"] == "MARKET_AT_OR_BELOW_AVERAGE"


def _fill(result):
    fill = result["fill"]
    return {key: fill[key] for key in ("side", "quantity", "price", "fee", "gross")} if fill else None


def _trade(path, session, previous):
    date = session["date"]
    result = session["paths"][path]["execution"]
    fill = _fill(result)
    raw_open = (result["opening"] or {}).get("raw_open")
    slippage = abs(Decimal(fill["price"]) - Decimal(raw_open)) * fill["quantity"] if fill else None
    intent = result["intent"]
    return {
        "ref": f"trade:{path}:{date}", "path": path, "date": date, "signal_ref": _signal_ref(previous),
        "status": result["status"], "reason": result["reason"], "side": intent["side"],
        "intended_quantity": intent["quantity"], "quantity": fill["quantity"] if fill else 0,
        "price": fill["price"] if fill else None, "raw_open": raw_open, "fee": fill["fee"] if fill else None,
        "gross": fill["gross"] if fill else None, "slippage_cost": _decimal_text(slippage),
    }


def _trades(trace):
    return {
        (path, current["date"]): _trade(path, current, previous["date"])
        for previous, current in zip(trace, trace[1:]) for path in _PATHS
        if current["paths"][path]["execution"]["status"] != "NO_INTENT"
    }


def _coverage_ref(date, gap):
    return f"coverage:{date}:{gap['feature']}:{gap['reason']}"


def _path_gap_ref(gap):
    return f"gap:{gap['date']}:{gap['phase']}:{gap['reason']}"


def _signal_path(path, details, trades):
    outcome = details["next_open"]
    trade = trades.get((path, outcome["date"]))
    return {
        "candidate": details["decision_before_gate"], "action": details["decision"]["action"],
        "quantity": details["decision"]["quantity"], "gate_reason": details["gate"]["reason"],
        "decision_reasons": details["decision"]["reasons"],
        "next_open": {
            **outcome, "trade_ref": trade["ref"] if trade else None, "fill": _fill(outcome),
        },
    }


def _signals(trace, trades):
    signals = []
    first_diverging_filter = None
    for session in trace:
        date = session["date"]
        ref = _signal_ref(date)
        e0, e1 = (_signal_path(path, session["paths"][path], trades) for path in _PATHS)
        candidate_difference = e0["candidate"] != e1["candidate"]
        direct = _market_block(session)
        signals.append({
            "ref": ref, "date": date, "stock": session["paths"]["e0"]["signal"], "market": session["market"],
            "common_evaluable": session["common_evaluable"],
            "gap_refs": [_coverage_ref(date, gap) for gap in session["sample_gaps"]],
            "paths": {"e0": e0, "e1": e1}, "direct_market_block": direct,
            "candidate_difference": candidate_difference,
            "prior_filter_signal_ref": first_diverging_filter if candidate_difference else None,
        })
        if direct and first_diverging_filter is None and e0["next_open"]["fill"] != e1["next_open"]["fill"]:
            first_diverging_filter = ref
    return signals


def _position(account):
    shares = sum(lot["quantity"] for lot in account["lots"])
    receivable_shares = sum(item["quantity"] for item in account["receivables"] if item["kind"] == "shares")
    return {"shares": shares, "receivable_shares": receivable_shares, "total_shares": shares + receivable_shares}


def _positions(trace, path, trades):
    positions = []
    for session in trace:
        date = session["date"]
        detail = session["paths"][path]
        opening = detail["open_account"]
        trade = trades.get((path, date))
        positions.append({
            "date": date, "opening": _position(opening),
            "after_execution": _position(detail["execution"].get("account", opening)),
            "closing": _position(detail["account"]), "close": session["close"], "mark_basis": session["mark_basis"],
            "nav": detail["valuation"]["nav"] if detail["valuation"] else None,
            "trade_ref": trade["ref"] if trade and trade["quantity"] else None,
        })
    return positions


def _difference(new, old):
    return Decimal(new) - Decimal(old) if new is not None and old is not None else None


def _sum_amount(rows, name):
    return sum((Decimal(row[name]) for row in rows if row[name] is not None), _ZERO)


def _period_economics(positions, start, end, base, trades, path, gaps):
    previous = positions[max(0, start - 1)]
    first, last = positions[start], positions[end]
    before = previous["nav"] if start else base
    filled = [trades[path, row["date"]] for row in positions[start:end + 1] if row["trade_ref"]]
    affected = {ref: gap for ref, gap in gaps.items() if gap["date"] <= last["date"]
                and (gap["phase"] != "valuation" or gap["date"] >= previous["date"])}
    observed = _decimal_text(_difference(last["nav"], before))
    return {
        "start": first["date"], "end": last["date"], "prior_close_date": previous["date"], "prior_nav": before,
        "end_nav": last["nav"], "nav_change": observed if not affected else None,
        "observed_nav_change": observed, "gap_refs": list(affected),
        "trade_scope": "observed_only" if any(gap["phase"] != "valuation" for gap in affected.values()) else "complete_period",
        "costs": _decimal_text(_sum_amount(filled, "fee")),
        "slippage_cost": _decimal_text(_sum_amount(filled, "slippage_cost")),
        "trade_refs": [trade["ref"] for trade in filled],
    }


def _holding_periods(path, positions, base, trades, gaps):
    periods = []
    start = None
    for index, point in enumerate(positions):
        if start is None and any(point[phase]["total_shares"] for phase in ("opening", "after_execution", "closing")):
            start = index
        open_at_close = bool(point["closing"]["total_shares"])
        if start is not None and (not open_at_close or index == len(positions) - 1):
            period = _period_economics(positions, start, index, base, trades, path, gaps)
            periods.append({
                **period, "ref": f"holding:{path}:{period['start']}", "open_at_end": open_at_close,
                "positions": positions[start:index + 1],
            })
            start = None
    return periods


def _unions(periods):
    start, end, refs = None, None, []
    for period in sorted(periods, key=lambda item: (item["start"], item["end"], item["ref"])):
        if end is None or period["start"] > end:
            if refs:
                yield start, end, refs
            start, end, refs = period["start"], period["end"], []
        end = max(end, period["end"])
        refs.append(period["ref"])
    if refs:
        yield start, end, refs


def _segments(holding_periods, positions, base, trades, gaps):
    by_date = {point["date"]: index for index, point in enumerate(positions["e0"])}
    periods = (period for group in holding_periods.values() for period in group)
    segments = []
    for start, end, refs in _unions(periods):
        paths = {path: _period_economics(positions[path], by_date[start], by_date[end], base, trades, path, gaps[path])
                 for path in _PATHS}
        e0, e1 = (paths[path] for path in _PATHS)
        net_difference = _difference(e1["nav_change"], e0["nav_change"])
        segments.append({
            "ref": f"segment:{start}:{end}", "start": start, "end": end, "holding_refs": refs, "paths": paths,
            "net_difference": _decimal_text(net_difference),
            "return_contribution": _decimal_text(net_difference / Decimal(base) if net_difference is not None else None),
            "cost_difference": _decimal_text(_difference(e1["costs"], e0["costs"])),
            "slippage_difference": _decimal_text(_difference(e1["slippage_cost"], e0["slippage_cost"])),
        })
    return segments


def _drawdown(path, positions, metrics, holding_periods, gaps):
    magnitude = metrics["max_drawdown"]
    result = {
        "ref": f"drawdown:{path}", "path": path, "magnitude": magnitude,
        "peak_date": None, "trough_date": None, "peak_nav": None, "trough_nav": None,
        "positions": [], "trade_refs": [], "holding_refs": [], "gap_refs": gaps,
    }
    if magnitude is None:
        return {**result, "status": "unavailable"}
    if Decimal(magnitude) == _ZERO:
        return {**result, "status": "none"}

    running_peak, worst_peak, trough = 0, 0, 0
    maximum = _ZERO
    for index, point in enumerate(positions):
        nav, peak_nav = Decimal(point["nav"]), Decimal(positions[running_peak]["nav"])
        if nav > peak_nav:
            running_peak = index
        elif (drop := (peak_nav - nav) / peak_nav) > maximum:
            worst_peak, trough, maximum = running_peak, index, drop

    affected = positions[worst_peak:trough + 1]
    first, last = affected[0], affected[-1]
    return {
        **result, "status": "computed", "peak_date": first["date"], "trough_date": last["date"],
        "peak_nav": first["nav"], "trough_nav": last["nav"], "positions": affected,
        "trade_refs": [point["trade_ref"] for point in affected if point["trade_ref"]],
        "holding_refs": [period["ref"] for period in holding_periods
                         if period["start"] <= last["date"] and period["end"] >= first["date"]],
    }


def _costs_only(positions, trades):
    cumulative_difference = _ZERO
    had_cost_difference = False
    for left, right in zip(positions["e0"], positions["e1"]):
        e0, e1 = (_trade_cost(trades.get((path, left["date"]))) for path in _PATHS)
        cumulative_difference += e1 - e0
        if _difference(right["nav"], left["nav"]) + cumulative_difference != _ZERO:
            return False
        had_cost_difference = had_cost_difference or bool(cumulative_difference)
    return had_cost_difference


def _trade_cost(trade):
    return Decimal(trade["fee"]) + Decimal(trade["slippage_cost"]) if trade and trade["quantity"] else _ZERO


def _compare(receipt, segments, path_gaps, positions, trades):
    e0, e1 = (receipt["metrics"][path] for path in _PATHS)
    complete = e0["path_complete"] and e1["path_complete"]
    total = _difference(e1["end_nav"], e0["end_nav"]) if complete else None
    attributed = _sum_amount(segments, "net_difference") if complete else None
    residual = _difference(total, attributed)
    changed = [segment for segment in segments if segment["net_difference"] not in (None, "0")]
    dominant = max(changed, key=lambda segment: abs(Decimal(segment["net_difference"])), default=None)
    absolute_total = sum(abs(Decimal(segment["net_difference"])) for segment in changed)
    divergence = receipt["opportunities"]["path_divergence"]
    action_dates = divergence["final_action_difference_dates"]
    fill_dates = divergence["next_open_fill_difference_signal_dates"]

    if total is None or not (e0["fills"] or e1["fills"]):
        classification = "evidence_insufficient"
    elif not action_dates and not fill_dates and not total:
        classification = "actions_identical"
    elif residual:
        classification = "unattributed_difference"
    elif _costs_only(positions, trades):
        classification = "costs_only"
    elif not changed:
        classification = "no_net_difference"
    elif len(changed) == 1:
        classification = "single_segment"
    else:
        classification = "multiple_segments"

    return {
        "classification": classification, "gap_refs": list(path_gaps),
        "action_difference_signal_refs": [_signal_ref(date) for date in action_dates],
        "fill_difference_signal_refs": [_signal_ref(date) for date in fill_dates],
        "total_net_difference": _decimal_text(total), "attributed_net_difference": _decimal_text(attributed),
        "residual_net_difference": _decimal_text(residual),
        "total_cost_difference": _decimal_text(_difference(e1["costs"], e0["costs"])),
        "total_slippage_difference": _decimal_text(_difference(e1["slippage_cost"], e0["slippage_cost"])),
        "trade_scope": "complete_path" if all(path["metric_scope"]["trade_totals"] == "complete_path"
                                               for path in (e0, e1)) else "observed_only",
        "segment_refs": [segment["ref"] for segment in changed],
        "dominant_segment_ref": dominant["ref"] if dominant else None,
        "dominant_absolute_share": _decimal_text(abs(Decimal(dominant["net_difference"])) / absolute_total if dominant else None),
    }


def _no_fills_gap(signals, trades):
    blocked = [signal for signal in signals if any(path["gate_reason"] == "COMMON_ENTRY_INPUT_UNAVAILABLE"
                                                  for path in signal["paths"].values())]
    return {
        "date": signals[-1]["date"], "phase": "comparison", "paths": list(_PATHS), "reason": "NO_SIMULATED_FILLS",
        "required_evidence": "开发窗口内至少一笔可核对的模拟成交。",
        "related_gap_refs": [ref for signal in blocked for ref in signal["gap_refs"]],
        "related_signal_refs": [signal["ref"] for signal in blocked],
        "trade_refs": [trade["ref"] for trade in trades.values()],
    }


def attribute_development(receipt):
    """Build receipt-local references for the two strategy paths and shared metrics."""
    trace = receipt["sessions"]
    trades = _trades(trace)
    signals = _signals(trace, trades)
    base = receipt["metrics"]["e0"]["start_nav"]
    positions = {path: _positions(trace, path, trades) for path in _PATHS}
    gaps = {
        _coverage_ref(date, gap): {"date": date, "phase": "signal_coverage", **gap}
        for date, losses in receipt["sample"]["losses"].items() for gap in losses
    }
    path_gaps = {_path_gap_ref(gap): gap for gap in receipt["coverage"]["path_gaps"]}
    comparison_gaps = {ref: gap for ref, gap in path_gaps.items() if any(path in gap["paths"] for path in _PATHS)}
    gaps_by_path = {path: {ref: gap for ref, gap in comparison_gaps.items() if path in gap["paths"]} for path in _PATHS}
    gaps.update(path_gaps)
    if not any(trade["quantity"] for trade in trades.values()):
        gaps["gap:comparison:no_fills"] = comparison_gaps["gap:comparison:no_fills"] = _no_fills_gap(signals, trades)
    holding_periods = {path: _holding_periods(path, positions[path], base, trades, gaps_by_path[path]) for path in _PATHS}
    segments = _segments(holding_periods, positions, base, trades, gaps_by_path)
    return {
        "version": "development-attribution-v1",
        "basis": {
            "signals": "候选动作分化时可回溯到首次造成次日实际成交差异的指数拦截信号。",
            "positions": "按交易日列出开盘撮合前、撮合后及收盘股份，含在途股份。同日清仓后恢复持仓的过程保留在持仓明细。现金应收继续计价。",
            "segments": "仅合并日期重叠的持仓段。每段以段首前一收盘至段末收盘的净值变化归因，除以共同期初净值得收益贡献。",
            "comparison": "差异方向为 E1 减 E0，金额单位为人民币。集中度按各段净值差异绝对值之和计算，段外差异单列。",
            "costs_only": "逐日将累计交易费用及滑点加回净值，两条曲线在该口径下逐日相同。",
            "drawdowns": "峰谷按各路径每日收盘净值计算。等值峰或回撤幅度重复时取先出现的日期。",
        },
        "metrics": {f"metric:{path}:{metric}": {"path": path, "metric": metric, "value": value}
                    for path, values in receipt["metrics"].items() for metric, value in values.items()},
        "signals": signals, "trades": list(trades.values()), "gaps": gaps,
        "holding_periods": holding_periods, "segments": segments,
        "comparison": _compare(receipt, segments, comparison_gaps, positions, trades),
        "drawdowns": {path: _drawdown(path, positions[path], receipt["metrics"][path], holding_periods[path],
                                     list(gaps_by_path[path]))
                      for path in _PATHS},
    }
