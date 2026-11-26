"""Metrics for continuous paths, using the prior close for every window."""
from collections import Counter
from decimal import Decimal
from math import sqrt
from statistics import pstdev


ZERO = Decimal(0)
SESSIONS_PER_YEAR = 252


def _nav(day, path):
    valuation = day["paths"][path]["valuation"]
    return Decimal(valuation["nav"]) if valuation else None


def _shares(account):
    return sum(item["quantity"] for item in (*account["lots"], *account["receivables"]))


def _cash_assets(account):
    return Decimal(account["cash"]) + sum(Decimal(item["amount"]) for item in account["receivables"])


def _round_trips(trace, path):
    trips = []
    entry = None
    for item in trace:
        day = item["date"]
        detail = item["paths"][path]
        opening, closing = detail["open_account"], detail["account"]
        fill = detail["execution"]["fill"]
        if entry is None and fill and fill["side"] == "BUY" and not _shares(opening):
            entry = day, _cash_assets(opening)
        if entry is not None and not _shares(closing):
            opened, cash = entry
            trips.append((opened, day, _cash_assets(closing) - cash))
            entry = None
    return trips


def _decimal_text(value):
    return format(value.normalize(), "f") if value is not None else None


def _metrics(trace, path, base, complete, trips):
    nav = [_nav(item, path) for item in trace]
    observed = [point for point in nav if point is not None]
    valid = bool(complete and base is not None and base > 0 and len(observed) == len(nav) and nav)
    returns, max_drawdown = [], None
    if valid:
        peak = base
        max_drawdown = ZERO
        previous = base
        for value in nav:
            peak = max(peak, value)
            max_drawdown = max(max_drawdown, (peak - value) / peak)
            if previous > 0:
                returns.append(float(value / previous - 1))
            previous = value
    executables = [item["paths"][path]["execution"] for item in trace]
    filled = [item for item in executables if item["fill"]]
    gross = sum((item["fill"]["gross"] for item in filled), ZERO)
    costs = sum((item["fill"]["fee"] for item in filled), ZERO)
    slippage = sum((abs(item["fill"]["price"] - item["opening"]["raw_open"]) *
                    item["fill"]["quantity"] for item in filled), ZERO)
    wins = [pnl for _, _, pnl in trips if pnl > 0]
    losses = [pnl for _, _, pnl in trips if pnl < 0]
    return {
        "path_complete": complete, "valued_sessions": len(observed),
        "start_nav": _decimal_text(base), "end_nav": _decimal_text(nav[-1]) if nav else None,
        "total_return": _decimal_text(nav[-1] / base - 1) if valid else None,
        "max_drawdown": _decimal_text(max_drawdown),
        "volatility": pstdev(returns) * sqrt(SESSIONS_PER_YEAR) if len(returns) >= 2 else None,
        "downside_risk": sqrt(SESSIONS_PER_YEAR * sum(min(0, value) ** 2 for value in returns) / len(returns))
        if returns else None,
        "turnover": _decimal_text(gross * len(nav) / sum(nav)) if valid and sum(nav) > 0 else None,
        "gross_traded": _decimal_text(gross), "costs": _decimal_text(costs),
        "slippage_cost": _decimal_text(slippage), "fills": len(filled),
        "partial_fills": sum(item["status"] == "PARTIAL" for item in executables),
        "failed_fills": sum(item["status"] == "UNFILLED" for item in executables),
        "nonexecution_reasons": dict(Counter(item["reason"] for item in executables if item["reason"])),
        "completed_round_trips": len(trips), "wins": len(wins), "losses": len(losses),
        "win_rate": _decimal_text(Decimal(len(wins)) / len(trips)) if trips else None,
        "profit_loss_ratio": _decimal_text(sum(wins) * len(losses) / (-sum(losses) * len(wins)))
        if wins and losses else None,
    }


def _window(trace, paths, window, earliest_gap, round_trips, initial_mark, prior_date):
    start, end = window["start"], window["end"]
    included = [item for item in trace if start <= item["date"] <= end]
    previous = next((item for item in reversed(trace) if item["date"] < start), None)
    result = {}
    evaluable = sum(
        all(_nav(item, path) is not None and item["date"] < earliest_gap.get(path, "9999") for path in paths)
        and item["paths"]["trend"]["signal"]["status"] == "ready"
        for item in included
    )
    for path in paths:
        baseline = initial_mark.get(path)
        base = _nav(previous, path) if previous else Decimal(baseline["nav"]) if baseline else None
        trips = [trip for trip in round_trips[path] if start <= trip[0] <= trip[1] <= end]
        complete = end < earliest_gap.get(path, "9999")
        result[path] = _metrics(included, path, base, complete, trips)
    trend_return = result["trend"]["total_return"]
    for name in ("buy_and_hold", "no_active_trading"):
        control_return = result[name]["total_return"]
        result["trend"][f"excess_return_vs_{name}"] = _decimal_text(
            Decimal(trend_return) - Decimal(control_return)
        ) if trend_return is not None and control_return is not None else None
    return {
        **window, "base_date": previous["date"] if previous else prior_date,
        "sessions": len(included), "evaluable_sessions": evaluable, "paths": result,
    }


def _verdict(acceptance, evaluation, coverage):
    trend = acceptance["paths"]["trend"]
    buy_and_hold = acceptance["paths"]["buy_and_hold"]
    no_active = acceptance["paths"]["no_active_trading"]
    metrics = (
        trend["total_return"], trend["max_drawdown"], buy_and_hold["total_return"],
        buy_and_hold["max_drawdown"], no_active["total_return"],
    )
    insufficient = []
    if coverage["path_gaps"]:
        insufficient.append("UNRESOLVED_PATH_GAPS")
    if acceptance["evaluable_sessions"] < evaluation["min_acceptance_evaluable_sessions"]:
        insufficient.append("TOO_FEW_EVALUABLE_ACCEPTANCE_SESSIONS")
    if trend["completed_round_trips"] < evaluation["min_acceptance_completed_round_trips"]:
        insufficient.append("TOO_FEW_COMPLETE_ACCEPTANCE_ROUND_TRIPS")
    if any(value is None for value in metrics):
        insufficient.append("ACCEPTANCE_METRICS_UNAVAILABLE")
    if insufficient:
        return "insufficient", insufficient
    trend_return, trend_drawdown, hold_return, hold_drawdown, no_active_return = map(Decimal, metrics)
    failed = []
    if trend_return <= no_active_return:
        failed.append("RETURN_DID_NOT_EXCEED_NO_ACTIVE_TRADING")
    if trend_drawdown >= hold_drawdown:
        failed.append("DRAWDOWN_DID_NOT_IMPROVE_ON_BUY_AND_HOLD")
    if hold_return - trend_return > Decimal(evaluation["max_return_lag_to_buy_and_hold"]):
        failed.append("RETURN_LAG_EXCEEDED_CAP")
    return ("fail", failed) if failed else ("pass", [])


def _overlap(trace, complete):
    if not trace or not complete:
        return None, "基准路径证据不足"
    for item in trace:
        buy_and_hold = item["paths"]["buy_and_hold"]
        no_active = item["paths"]["no_active_trading"]
        if buy_and_hold["execution"]["fill"] or buy_and_hold["valuation"] != no_active["valuation"]:
            return False, "买入持有发生独立配置或净值路径不同"
    return True, "买入持有未产生独立成交，两个基准共享初始现金、批次和权益"


def summarize(trace, coverage, initial_mark, boundary, configuration):
    protocol = configuration["protocol"]
    paths = ("trend", "buy_and_hold", "no_active_trading")
    earliest_gap = {}
    for gap in coverage["path_gaps"]:
        for path in gap["paths"]:
            earliest_gap[path] = min(earliest_gap.get(path, gap["date"]), gap["date"])
    round_trips = {path: _round_trips(trace, path) for path in paths}
    prior_date = boundary["pre_window"]["date"] if boundary["pre_window"] else None
    windows = {
        name: _window(trace, paths, window, earliest_gap, round_trips, initial_mark, prior_date)
        for name, window in protocol["windows"].items()
    }
    verdict, reasons = _verdict(windows["acceptance"], protocol["evaluation"], coverage)
    overlap, overlap_reason = _overlap(trace, not {"buy_and_hold", "no_active_trading"}.intersection(earliest_gap))
    return {
        "windows": windows, "verdict": verdict, "verdict_reasons": reasons,
        "baseline_paths_overlap": overlap, "baseline_overlap_reason": overlap_reason,
        "independent_baselines": (1 if overlap else 2) if overlap is not None else None,
        "metric_basis": {
            "base": "窗口首日之前最近交易日的各账本收盘净值，开发期起点使用共同初始资产。",
            "drawdown": "包含起点净值，报告从历史峰值到后续低点的最大跌幅。",
            "turnover": "窗口买卖总成交金额除以窗口日末平均净值。",
            "daily_risk": "日收益标准差和零目标下行偏差，按每年 252 个交易日年化。",
            "round_trips": "从零股票风险敞口买入再回到零，买入与平仓均须在窗口内，收益含已确认股息和费用。",
        },
        "limitations": [
            "单标的冻结试验，试验次数和候选假设见协议。不同历史阶段的结果分别列出。",
            "本协议固定参数和成本，仅登记一个独立验收运行；未登记参数或成本敏感性试验。",
            "历史重建及历史验收只形成研究证据。策略生产准入由注册表另行登记。",
        ],
    }
