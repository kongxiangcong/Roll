"""Fixed 510300.SH strategy and buy-and-hold replay on raw ETF opens and closes."""
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP

from roll.barometer import scores_in_transaction
from roll.costs import execution_price, transaction_cost
from roll.db import connect
from roll.market.calendar import is_session
from roll.market.daily import initialize_market
from roll.market.inputs import initialize_inputs, input_rows
from roll.market.rules import round_lot
from roll.statistics import continuous_summary


ETF = "510300.SH"
INITIAL_CASH = Decimal("100000")
COMMISSION = Decimal("0.0003")
MINIMUM = Decimal("5")
TRANSFER = Decimal("0.00001")
SELL_TAX = Decimal("0.0005")
SLIPPAGE = Decimal("0.0005")
TICK = Decimal("0.001")
ZERO = Decimal(0)


def _price(bar, key):
    raw = bar.get(key)
    if raw is None:
        return None
    value = Decimal(str(raw))
    return value if value.is_finite() and value > 0 else None


@dataclass
class Portfolio:
    cash: Decimal
    shares: int = 0
    trades: list = field(default_factory=list)
    curve: list = field(default_factory=list)
    skips: list = field(default_factory=list)
    known: bool = True

    def rebalance(self, day, signal_day, cap, bar, previous_close):
        if not self.known:
            return
        opened = _price(bar, "open")
        if opened is None:
            self.known = False
            self.skips.append({"trade_date": day, "signal_date": signal_day, "reason": "缺少原始开盘价"})
            return
        equity = self.cash + self.shares * opened
        target = round_lot(equity * cap / opened)
        delta = target - self.shares
        if not delta:
            return
        side = "BUY" if delta > 0 else "SELL"
        if _price(bar, "high") == _price(bar, "low") == opened:
            if previous_close is None:
                self.known = False
                self.skips.append({"trade_date": day, "signal_date": signal_day, "reason": "单一价缺少上一交易日收盘"})
                return
            band = Decimal("1.10") if delta > 0 else Decimal("0.90")
            limit = (previous_close * band).quantize(TICK, rounding=ROUND_HALF_UP)
            if (delta > 0 and opened >= limit) or (delta < 0 and opened <= limit):
                self.skips.append({"trade_date": day, "signal_date": signal_day, "reason": "单一价触及模拟涨跌停"})
                return
        price = execution_price(opened, side, SLIPPAGE, TICK)
        quantity = abs(delta)
        tax = SELL_TAX if delta < 0 else ZERO
        if delta > 0:
            quantity = min(quantity, round_lot(self.cash / (price * (1 + COMMISSION + TRANSFER))))
        gross = price * quantity
        fee = transaction_cost(gross, COMMISSION, MINIMUM, TRANSFER, tax)
        if delta > 0 and gross + fee > self.cash:
            quantity = max(0, quantity - 100)
            gross = price * quantity
            fee = transaction_cost(gross, COMMISSION, MINIMUM, TRANSFER)
        if not quantity:
            return
        self.shares += quantity if delta > 0 else -quantity
        self.cash += (-gross if delta > 0 else gross) - fee
        self.trades.append({"trade_date": day, "signal_date": signal_day, "side": side,
                            "shares": quantity, "raw_open": str(opened), "price": str(price),
                            "gross_yuan": str(gross), "fee_yuan": str(fee), "target": float(cap)})

    def mark(self, day, close, initial):
        value = self.shares * close if close else (None if self.shares else ZERO)
        nav = self.cash + value if self.known and value is not None else None
        self.curve.append({"trade_date": day, "cash_yuan": str(self.cash) if self.known else None,
                           "shares": self.shares if self.known else None,
                           "nav_yuan": str(nav) if nav is not None else None,
                           "net_value": float(nav / initial) if nav is not None else None,
                           "exposure": float(value / nav) if nav else None})

    def result(self, initial, has_signal=True):
        summary = continuous_summary([{"nav_yuan": initial}, *self.curve])
        complete = summary["net_return"] is not None and self.known and bool(self.curve)
        metrics = dict.fromkeys(("net_value", "annual_return", "maximum_drawdown", "calmar", "turnover"))
        if complete:
            last = self.curve[-1]["net_value"]
            drawdown = summary["maximum_drawdown"]
            annual = last ** (252 / len(self.curve)) - 1
            mean_nav = sum(Decimal(r["nav_yuan"]) for r in self.curve) / len(self.curve)
            traded = sum((Decimal(t["gross_yuan"]) for t in self.trades), ZERO)
            metrics.update(net_value=last, annual_return=annual, maximum_drawdown=drawdown,
                           calmar=annual / drawdown if drawdown > 0 else None, turnover=float(traded / mean_nav))
        status = "行情缺口" if not complete else ("有效" if has_signal else "无有效档位，保持现金")
        return {"status": status, "metrics": metrics, "trades": self.trades, "curve": self.curve,
                "skipped": self.skips}


def compare_sessions(signals, bars, initial=INITIAL_CASH):
    """Each signal row identifies one expected exchange session, including unavailable regimes."""
    initial = Decimal(str(initial))
    if not initial.is_finite() or initial <= 0:
        raise ValueError("模拟初始资金必须是正数")
    by_day = {r["trade_date"]: r for r in bars}
    strategy, buy_hold = Portfolio(initial), Portfolio(initial)
    pending = None
    last_regime = None
    previous_close = None
    if signals:
        prior = date.fromisoformat(signals[0]["trade_date"]) - timedelta(days=1)
        while not is_session(prior):
            prior -= timedelta(days=1)
        previous_close = _price(by_day.get(prior.isoformat(), {}), "close")
    missing_prices = []
    valid_signals = 0
    for i, signal in enumerate(signals):
        day = signal["trade_date"]
        bar = by_day.get(day, {})
        close = _price(bar, "close")
        absent = [name for name in ("open", "close") if _price(bar, name) is None]
        if absent:
            missing_prices.append({"trade_date": day, "fields": absent})
        if i == 0:
            buy_hold.rebalance(day, None, Decimal(1), bar, previous_close)
        if pending:
            strategy.rebalance(day, *pending, bar, previous_close)
        buy_hold.mark(day, close, initial)
        strategy.mark(day, close, initial)
        strategy.curve[-1].update(regime=signal["regime"], position_cap=signal["position_cap"],
                                  coverage=signal.get("coverage"))
        pending = None
        regime = signal["regime"]
        if regime is not None:
            valid_signals += 1
            if regime != last_regime:
                pending = (day, Decimal(str(signal["position_cap"])))
            last_regime = regime
        previous_close = close
    return {"sessions": len(signals), "valid_signals": valid_signals,
            "missing_input_days": dict(Counter(reason for s in signals for reason in s.get("missing", ()))),
            "regime_days": dict(Counter(s["regime"] for s in signals if s["regime"] is not None)),
            "missing_signals": len(signals) - valid_signals, "missing_prices": missing_prices,
            "strategy": strategy.result(initial, bool(valid_signals)), "buy_hold": buy_hold.result(initial)}


def run_backtest(data_dir: Path, start="2020-01-01", end=None, initial=INITIAL_CASH):
    """Replay independent fitting and out-of-sample windows against one SQLite snapshot."""
    start = date.fromisoformat(start).isoformat()
    if start < "2020-01-01":
        raise ValueError("起始日期须在 2020 年或以后")
    now = datetime.now(timezone(timedelta(hours=8)))
    last_complete = now.date() if now.hour >= 15 else now.date() - timedelta(days=1)
    ceiling = min(last_complete.isoformat(), "2026-12-31")
    if end is not None:
        end = date.fromisoformat(end).isoformat()
        if end < start or end > ceiling:
            raise ValueError("无效回测区间：截止日不得晚于最近完整交易时段或 2026 年末")
    initial = Decimal(str(initial))
    if not initial.is_finite() or initial <= 0:
        raise ValueError("模拟初始资金必须是正数")
    report = {"symbol": ETF, "initial_cash_yuan": str(initial), "requested_start": start,
              "requested_end": end, "effective_end": None, "periods": [],
              "fees": {"commission_rate": str(COMMISSION), "minimum_commission_yuan": str(MINIMUM),
                       "transfer_rate": str(TRANSFER), "sell_tax_rate": str(SELL_TAX),
                       "slippage_rate": str(SLIPPAGE), "price_tick": str(TICK), "lot": 100,
                       "basis": "两组合用固定模拟费率，费用各分项四舍五入到分。"},
              "basis": "每段从现金独立起算。对照首日开盘尽量整手买入；策略首次有效或换档后下一交易日开盘调仓。"
                       "使用原始收盘计价，仅模拟价格变化与交易成本。前收盘上下10%且全天单一价时，模拟同向无法成交。"
                       "收益按252交易日年化，回撤含期初现金，卡玛为年化收益除最大回撤，换手为双边成交总额除日均净资产。"}
    with connect(data_dir / "roll.sqlite3") as db:
        initialize_market(db)
        initialize_inputs(db)
        db.execute("BEGIN")
        # Include one exchange session before the requested start to check a one-price opening.
        prior = date.fromisoformat(start) - timedelta(days=1)
        while not is_session(prior):
            prior -= timedelta(days=1)
        bars = input_rows(db, "etf_bars", ETF, prior.isoformat(), end or ceiling)
        if end is None and (not bars or bars[-1]["trade_date"] < start):
            report["status"] = "缺少 510300.SH 原始行情，无法确定截止日"
            return report
        finish = end or bars[-1]["trade_date"]
        signals = scores_in_transaction(db, start, finish)
    report["effective_end"] = finish
    for name, first, last in [("定权期", "2020-01-01", "2023-12-31"), ("样本外", "2024-01-01", ceiling)]:
        window = [s for s in signals if first <= s["trade_date"] <= last]
        if window:
            report["periods"].append({"period": name, "start": window[0]["trade_date"], "end": window[-1]["trade_date"],
                                      **compare_sessions(window, bars, initial)})
    report["status"] = "已完成" if report["periods"] else "区间内没有交易日"
    return report
