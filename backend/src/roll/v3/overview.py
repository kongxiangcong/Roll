"""Aggregated daily overview and non-blocking market sync for the Roll workbench."""
from datetime import date, time, timedelta
from decimal import Decimal, InvalidOperation
from itertools import groupby
import math
import threading

from roll.market.calendar import extended_sessions, is_session, latest_session
from roll.v3.account import AccountLedger
from roll.v3.market import DEFAULT_SOURCE_PRIORITY, LIVE_RUN, _SCHEMA as MARKET_SCHEMA, _choose, utc_timestamp
from roll.v3.market_sources import INDUSTRY_PROXY, sync_daily_market
from roll.v3.plan import PlanLedger
from roll.v3.research import ResearchDossiers
from roll.v3.review import DecisionLedger
from roll.v3.storage import database, ensure_schema, instant
from roll.v3.strategy import StrategyRegistry
from roll.v3.watchlist import display_name, list_watchlist


BENCHMARK_SYMBOL = "000300.SH"
INDUSTRY_SYMBOL = "801055.SI"


def _dec(value):
    if value is None:
        return None
    try:
        num = Decimal(str(value))
    except InvalidOperation:
        return None
    return num if num.is_finite() else None


def _latest_bars(db, symbol, *, end, cutoff, limit=70):
    rows = db.execute(
        """SELECT * FROM observation
           WHERE series = 'daily_bar' AND symbol = ? AND trade_date <= ? AND item_id = ''
           ORDER BY trade_date DESC, source, seq""",
        (symbol.upper(), end),
    )
    policy = {"use_mode": LIVE_RUN, "source_priority": DEFAULT_SOURCE_PRIORITY}
    bars = []
    for day, versions in groupby(rows, key=lambda row: row["trade_date"]):
        chosen, _ = _choose(list(versions), policy, cutoff)
        if not chosen:
            continue
        payload = chosen["payload"]
        close = _dec(payload.get("close"))
        if close is None or close <= 0:
            continue
        bars.append({
            "trade_date": day,
            "close": float(close),
            "prior_close": float(_dec(payload.get("pre_close") or payload.get("prior_close")) or 0) or None,
            "volume": float(_dec(payload.get("volume")) or 0) or None,
            "amount": float(_dec(payload.get("amount")) or 0) or None,
        })
        if len(bars) >= limit:
            break
    return bars[::-1]


def _series_metrics(bars):
    if not bars:
        return {
            "trade_date": None, "close": None, "change_pct": None,
            "return_5d": None, "return_20d": None, "return_60d": None,
            "volatility_20d": None, "max_drawdown_60d": None, "trend_state": "unknown",
        }
    closes = [row["close"] for row in bars]
    last = bars[-1]
    prev = last["prior_close"] or (closes[-2] if len(closes) >= 2 else None)
    change_pct = (last["close"] - prev) / prev if prev and prev > 0 else None

    def span_return(days):
        if len(closes) <= days:
            return None
        base = closes[-1 - days]
        return (closes[-1] - base) / base if base > 0 else None

    vol_20d = None
    if len(closes) >= 21:
        rets = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(len(closes) - 20, len(closes)) if closes[i - 1] > 0]
        if len(rets) >= 2:
            mean = sum(rets) / len(rets)
            var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
            vol_20d = math.sqrt(var) * math.sqrt(252)

    mdd_60d = None
    window = closes[-60:]
    if len(window) >= 2:
        peak = window[0]
        worst = 0.0
        for price in window:
            if price > peak:
                peak = price
            elif peak > 0:
                drop = (peak - price) / peak
                if drop > worst:
                    worst = drop
        mdd_60d = worst

    trend_state = "unknown"
    if len(closes) >= 20:
        ma20 = sum(closes[-20:]) / 20
        if len(closes) >= 60:
            ma60 = sum(closes[-60:]) / 60
            if closes[-1] > ma20 and ma20 > ma60:
                trend_state = "uptrend"
            elif closes[-1] < ma20 and ma20 < ma60:
                trend_state = "downtrend"
            else:
                trend_state = "range"
        else:
            trend_state = "uptrend" if closes[-1] > ma20 else "downtrend"

    return {
        "trade_date": last["trade_date"],
        "close": round(last["close"], 4),
        "change_pct": change_pct,
        "return_5d": span_return(5),
        "return_20d": span_return(20),
        "return_60d": span_return(60),
        "volatility_20d": vol_20d,
        "max_drawdown_60d": mdd_60d,
        "trend_state": trend_state,
    }


def _plain_plan_summary(plan):
    if not plan:
        return None
    action = plan.get("action")
    reasons = plan.get("reasons") or {}
    p0, p1, p2, p3 = reasons.get("P0", []), reasons.get("P1", []), reasons.get("P2", []), reasons.get("P3", [])
    if any("SUSPENDED" in code or "CLOSE_UNAVAILABLE" in code for code in p0):
        return "行情或交易状态受限"
    if any("RISK_BUDGET_MISSING" in code for code in p1):
        return "待配置风险预算"
    if any("LIMIT" in code or "CASH_RESERVE" in code for code in p1):
        return "触及资金或仓位上限"
    if any("THESIS_BROKEN" in code or "FUNDAMENTAL_FAIL" in code or "TRIGGER_FIRED" in code for code in p2):
        return "投资逻辑或门禁受阻"
    if any("DOSSIER_MISSING" in code or "DOSSIER_EXPIRED" in code for code in p2):
        return "待更新个股研究结论"
    if any("THESIS_WATCH" in code or "FUNDAMENTAL_UNKNOWN" in code for code in p2):
        return "当前维持观察状态"
    if any("STRATEGY_NOT_ADMITTED" in code or "NO_FEASIBLE_STRATEGY" in code for code in p3):
        return "策略尚在观察期"
    if action == "BUY":
        return f"计划买入 {plan.get('quantity', 0)} 股"
    if action == "SELL":
        return f"计划卖出 {plan.get('quantity', 0)} 股"
    if action == "HOLD":
        return "维持现有持仓"
    return "暂无主动交易动作"


def _read_account(data_dir, book_id, cutoff):
    try:
        return AccountLedger(data_dir).snapshot(book_id, as_of=cutoff)
    except ValueError:
        return None


def _pool_members(data_dir, account):
    saved = list_watchlist(data_dir)
    names = {item["symbol"]: item["name"] for item in saved}
    held = sorted({lot.symbol for lot in account.lots} | {r.symbol for r in account.receivables}) if account else []
    return names, list(dict.fromkeys([*names, *held]))


def _market_metrics(db, symbols, *, end, cutoff):
    return {symbol: _series_metrics(_latest_bars(db, symbol, end=end, cutoff=cutoff)) for symbol in symbols}


def market_trade_dates(data_dir, *, as_of=None):
    clock = instant(as_of)
    with database(data_dir) as db:
        ensure_schema(db, MARKET_SCHEMA)
        last_closed, _ = latest_session(db, clock.date() - timedelta(days=clock.time() < time(15)))
        latest = db.execute(
            """SELECT MAX(trade_date) FROM observation
               WHERE trade_date <= ? AND received_at <= ? AND (available_at IS NULL OR available_at <= ?)
                 AND quality = 'usable' AND withdrawn = 0 AND reconstruction_only = 0
                 AND series IN ('daily_bar', 'etf_shares', 'etf_nav')""",
            (last_closed.isoformat(), utc_timestamp(clock), utc_timestamp(clock)),
        ).fetchone()[0]
    return {"latest_trade_date": latest, "last_closed_trade_date": last_closed.isoformat()}


def _account_summary(account_snap, book_id, cutoff, watch_map, symbol_metrics):
    holdings_by_symbol = {}
    lots_view = []
    receivables_view = []
    holdings_value = 0.0
    receivables_value = 0.0
    total_cost = 0.0
    has_full_cost = True
    if account_snap is not None:
        for lot in account_snap.lots:
            holdings_by_symbol[lot.symbol] = holdings_by_symbol.get(lot.symbol, 0) + lot.quantity
            price = (symbol_metrics.get(lot.symbol) or {}).get("close")
            mv = price * lot.quantity if price is not None else None
            if mv is not None:
                holdings_value += mv
            cost_val = float(lot.cost) if lot.cost is not None else None
            if cost_val is not None:
                total_cost += cost_val
            else:
                has_full_cost = False
            lots_view.append({
                "symbol": lot.symbol,
                "name": display_name(lot.symbol, watch_map.get(lot.symbol)),
                "quantity": lot.quantity,
                "acquired_on": lot.acquired_on,
                "sellable_quantity": lot.sellable_quantity(cutoff.date()),
                "cost": cost_val,
                "market_value": round(mv, 2) if mv is not None else None,
            })
        for rec in account_snap.receivables:
            val = float(rec.amount)
            if rec.quantity:
                price = (symbol_metrics.get(rec.symbol) or {}).get("close")
                if price is not None:
                    val += price * rec.quantity
            receivables_value += val
            receivables_view.append({
                "symbol": rec.symbol,
                "name": display_name(rec.symbol, watch_map.get(rec.symbol)),
                "kind": rec.kind,
                "amount": float(rec.amount),
                "quantity": rec.quantity,
                "due_date": rec.due_date,
            })
        cash = float(account_snap.cash)
        available_cash = float(account_snap.available_cash) if account_snap.available_cash is not None else None
        total_nav = cash + holdings_value + receivables_value
        position_ratio = holdings_value / total_nav if total_nav > 0 else 0.0
        unrealized_pnl = (holdings_value - total_cost) if (holdings_by_symbol and has_full_cost and total_cost > 0) else None
        unrealized_pnl_pct = (unrealized_pnl / total_cost) if unrealized_pnl is not None and total_cost > 0 else None
        budget = account_snap.risk_budget
        account_summary = {
            "initialized": True,
            "book_id": book_id,
            "cash": round(cash, 2),
            "available_cash": round(available_cash, 2) if available_cash is not None else None,
            "holdings_value": round(holdings_value, 2),
            "receivables_value": round(receivables_value, 2),
            "total_nav": round(total_nav, 2),
            "position_ratio": position_ratio,
            "unrealized_pnl": round(unrealized_pnl, 2) if unrealized_pnl is not None else None,
            "unrealized_pnl_pct": unrealized_pnl_pct,
            "risk_budget": {
                "cash_reserve": float(budget.cash_reserve),
                "max_total_exposure": float(budget.max_total_exposure),
                "max_symbol_exposure": float(budget.max_symbol_exposure),
                "max_industry_exposure": float(budget.max_industry_exposure),
                "expires_at": budget.expires_at,
            } if budget else None,
            "lots": lots_view,
            "receivables": receivables_view,
        }
    else:
        account_summary = {
            "initialized": False, "book_id": book_id, "cash": None, "available_cash": None,
            "holdings_value": 0.0, "receivables_value": 0.0, "total_nav": None, "position_ratio": None,
            "unrealized_pnl": None, "unrealized_pnl_pct": None, "risk_budget": None, "lots": [], "receivables": [],
        }

    return account_summary, holdings_by_symbol


def _watchlist_rows(data_dir, *, book_id, cutoff_iso, watch_map, ordered_symbols, symbol_metrics,
                    position_data, benchmark_metrics, industry_metrics):
    dossiers = ResearchDossiers(data_dir)
    plans = PlanLedger(data_dir)
    registry = StrategyRegistry(data_dir)
    active_plans = plans.active(book_id)
    latest_plan_by_symbol = {}
    for item in active_plans:
        latest_plan_by_symbol[item["symbol"]] = item

    watchlist_rows = []
    for symbol in ordered_symbols:
        m = symbol_metrics[symbol]
        shares, pos_ratio = position_data[symbol]
        dossier = dossiers.active(symbol, cutoff_iso)
        effective = dossier or dossiers.effective_version(symbol, cutoff_iso)
        if dossier:
            dossier_view = {
                "status": "active",
                "version": dossier["version"],
                "fundamental_gate": dossier.get("fundamental_gate", "unknown"),
                "thesis_status": dossier.get("thesis_status", "unknown"),
                "hypothesis": dossier.get("hypothesis"),
                "valid_until": dossier.get("valid_until"),
            }
        elif effective:
            dossier_view = {
                "status": "expired",
                "version": effective["version"],
                "fundamental_gate": effective.get("fundamental_gate", "unknown"),
                "thesis_status": effective.get("thesis_status", "unknown"),
                "hypothesis": effective.get("hypothesis"),
                "valid_until": effective.get("valid_until"),
            }
        else:
            dossier_view = {
                "status": "missing", "version": None, "fundamental_gate": "unknown",
                "thesis_status": "unknown", "hypothesis": None, "valid_until": None,
            }

        plan = latest_plan_by_symbol.get(symbol)
        strategies = registry.for_symbol(symbol, cutoff_iso, include_ineligible=True)
        admitted = [s for s in strategies if s["production_eligible"]]
        accepted = [s for s in strategies if s["status"] == "accepted"]
        rel_bench = (
            (m["return_20d"] - benchmark_metrics["return_20d"])
            if (m["return_20d"] is not None and benchmark_metrics["return_20d"] is not None) else None
        )
        rel_ind = (
            (m["return_20d"] - industry_metrics["return_20d"])
            if (m["return_20d"] is not None and industry_metrics["return_20d"] is not None) else None
        )
        watchlist_rows.append({
            "symbol": symbol,
            "name": display_name(symbol, watch_map.get(symbol)),
            "in_watchlist": symbol in watch_map,
            "trade_date": m["trade_date"],
            "close": m["close"],
            "change_pct": m["change_pct"],
            "holding_shares": shares,
            "position_ratio": pos_ratio,
            "metrics": {**m, "rel_benchmark_20d": rel_bench, "rel_industry_20d": rel_ind},
            "dossier": dossier_view,
            "latest_plan": {
                "action": plan["action"],
                "quantity": plan["quantity"],
                "session": plan["session"],
                "summary": _plain_plan_summary(plan),
            } if plan else None,
            "strategy": {
                "total": len(strategies),
                "admitted": len(admitted),
                "accepted": len(accepted),
                "status": "admitted" if admitted else "accepted" if accepted else ("frozen" if strategies else "none"),
            },
            "probability": None,
        })

    return watchlist_rows


def _position_data(symbols, account_summary, holdings, metrics, *, unavailable=None):
    total_nav = account_summary["total_nav"] or 0
    result = {}
    for symbol in symbols:
        shares = holdings.get(symbol, 0)
        close = metrics[symbol]["close"]
        ratio = shares * close / total_nav if close is not None and total_nav else unavailable
        result[symbol] = (shares, ratio)
    return result


def build_market_watchlist(data_dir, *, book_id="real", trade_date=None, as_of=None):
    now = instant()
    cutoff = instant(as_of) if as_of else now
    cutoff_iso = utc_timestamp(cutoff)
    end = cutoff.date().isoformat()
    account = _read_account(data_dir, book_id, cutoff)
    watch_map, symbols = _pool_members(data_dir, account)
    with database(data_dir) as db:
        ensure_schema(db, MARKET_SCHEMA)
        if trade_date:
            day = date.fromisoformat(trade_date)
            last_closed, _ = latest_session(db, cutoff.date() - timedelta(days=cutoff.time() < time(15)))
            if day > last_closed or not is_session(day, extended_sessions(db)):
                raise ValueError("请选择已收盘的交易日")
        market_symbols = tuple(dict.fromkeys([BENCHMARK_SYMBOL, INDUSTRY_SYMBOL, *symbols]))
        current = _market_metrics(db, market_symbols, end=end, cutoff=cutoff_iso)
        metrics = (
            _market_metrics(db, market_symbols, end=trade_date, cutoff=cutoff_iso)
            if trade_date and trade_date != end else current
        )

    account_summary, holdings = _account_summary(account, book_id, cutoff, watch_map, current)
    positions = _position_data(symbols, account_summary, holdings, current)
    return {
        "trade_date": trade_date or max(
            (m["trade_date"] for m in metrics.values() if m["trade_date"]), default=None,
        ),
        "watchlist_as_of": utc_timestamp(now),
        "account_as_of": account.effective_at if account else None,
        "book_id": book_id,
        "rows": _watchlist_rows(
            data_dir, book_id=book_id, cutoff_iso=cutoff_iso, watch_map=watch_map, ordered_symbols=symbols,
            symbol_metrics=metrics, position_data=positions, benchmark_metrics=metrics[BENCHMARK_SYMBOL],
            industry_metrics=metrics[INDUSTRY_SYMBOL],
        ),
    }


def build_overview(data_dir, *, book_id="real", as_of=None, include_watchlist=True):
    cutoff = instant(as_of)
    cutoff_iso = utc_timestamp(cutoff)
    account = _read_account(data_dir, book_id, cutoff)
    watch_map, ordered_symbols = _pool_members(data_dir, account)
    with database(data_dir) as db:
        ensure_schema(db, MARKET_SCHEMA)
        metrics = _market_metrics(
            db, tuple(dict.fromkeys([BENCHMARK_SYMBOL, INDUSTRY_PROXY, INDUSTRY_SYMBOL, *ordered_symbols])),
            end=cutoff.date().isoformat(), cutoff=cutoff_iso,
        )
    latest_trade_date = max((m["trade_date"] for m in metrics.values() if m["trade_date"]), default=None)
    account_summary, holdings = _account_summary(account, book_id, cutoff, watch_map, metrics)
    watchlist_rows = []
    if include_watchlist:
        positions = _position_data(ordered_symbols, account_summary, holdings, metrics, unavailable=0.0)
        watchlist_rows = _watchlist_rows(
            data_dir, book_id=book_id, cutoff_iso=cutoff_iso, watch_map=watch_map, ordered_symbols=ordered_symbols,
            symbol_metrics=metrics, position_data=positions,
            benchmark_metrics=metrics[BENCHMARK_SYMBOL], industry_metrics=metrics[INDUSTRY_SYMBOL],
        )

    # Review todos (concise actionable reminders)
    decisions = DecisionLedger(data_dir)
    recent_reviews = decisions.registrations(book_id=book_id, as_of=cutoff_iso)
    todos = []
    latest_review = recent_reviews[-1] if recent_reviews else None
    if latest_review:
        for entry in latest_review["plans"]:
            actual_status = entry["actual"]["status"]
            if entry["shadow"] is None:
                todos.append({
                    "kind": "settle",
                    "symbol": entry["symbol"],
                    "name": display_name(entry["symbol"], watch_map.get(entry["symbol"])),
                    "decision_date": latest_review["decision_date"],
                    "registration_id": latest_review["registration_id"],
                    "label": "待结算影子",
                })
            elif actual_status in ("PENDING", "UNREPORTED"):
                todos.append({
                    "kind": "outcome",
                    "symbol": entry["symbol"],
                    "name": display_name(entry["symbol"], watch_map.get(entry["symbol"])),
                    "decision_date": latest_review["decision_date"],
                    "registration_id": latest_review["registration_id"],
                    "label": "待确认执行",
                })
    if not todos:
        todos.append({
            "kind": "register",
            "symbol": ordered_symbols[0] if ordered_symbols else "600362.SH",
            "name": display_name(ordered_symbols[0], watch_map.get(ordered_symbols[0])) if ordered_symbols else "江西铜业",
            "decision_date": latest_trade_date,
            "registration_id": None,
            "label": "登记今日盘后计划" if account_summary["initialized"] else "待初始化账户",
        })

    return {
        "trade_date": latest_trade_date,
        "as_of": cutoff_iso,
        "market_env": {
            "benchmark": {"symbol": BENCHMARK_SYMBOL, "name": "沪深 300", **metrics[BENCHMARK_SYMBOL]},
            "sector_etf": {"symbol": INDUSTRY_PROXY, "name": "有色金属 ETF", **metrics[INDUSTRY_PROXY]},
            "industry": {"symbol": INDUSTRY_SYMBOL, "name": "申万工业金属", **metrics[INDUSTRY_SYMBOL]},
            "sentiment": None,
            "broad_etf_flow": None,
        },
        "account_summary": account_summary,
        "watchlist": watchlist_rows,
        "review_todos": todos[:4],
    }


class MarketSyncRunner:
    """Non-blocking daily market sync runner that never invokes any research harness."""

    def __init__(self, data_dir, *, sync_fn=sync_daily_market):
        self.data_dir = data_dir
        self._sync_fn = sync_fn
        self._lock = threading.Lock()
        self._state = {
            "status": "idle", "last_synced_at": None, "appended": 0,
            "symbols": [], "error": None,
        }

    def status(self):
        with self._lock:
            return dict(self._state)

    def start(self, symbols=None, *, start="2020-01-02", refresh=False):
        with self._lock:
            if self._state["status"] == "running":
                return dict(self._state)
            chosen = list(dict.fromkeys([
                *(s.upper() for s in (symbols or [item["symbol"] for item in list_watchlist(self.data_dir)])),
                BENCHMARK_SYMBOL,
                INDUSTRY_PROXY,
            ]))
            self._state = {
                "status": "running", "last_synced_at": self._state["last_synced_at"],
                "appended": 0, "symbols": chosen, "error": None,
            }

        def _worker():
            try:
                result = self._sync_fn(self.data_dir, symbols=chosen, start=start, refresh=refresh)
                with self._lock:
                    self._state = {
                        "status": "done",
                        "last_synced_at": utc_timestamp(None),
                        "appended": result.get("appended", 0),
                        "symbols": chosen,
                        "error": None if not result.get("failures") else f"{len(result['failures'])} 项区间未拉取成功",
                    }
            except Exception as error:
                with self._lock:
                    self._state = {
                        "status": "error",
                        "last_synced_at": self._state["last_synced_at"],
                        "appended": 0,
                        "symbols": chosen,
                        "error": str(error),
                    }

        thread = threading.Thread(target=_worker, name="roll-market-sync", daemon=True)
        thread.start()
        return self.status()
