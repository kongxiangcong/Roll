"""Read-only holdings valuation, position limits and per-security close-of-day risk."""
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from roll.accounts.ledger import Ledger
from roll.barometer import scores_in_transaction
from roll.config import active_watchlist_in_transaction
from roll.db import connect
from roll.market.calendar import extended_sessions, is_session
from roll.market.daily import SHANGHAI, history_in_transaction, initialize_market
from roll.market.financials import SCHEMA as FINANCIAL_SCHEMA, financial_light_in_transaction
from roll.market.inputs import initialize_inputs, input_rows
from roll.market.rules import round_lot


def _text(number):
    return format(number.normalize(), "f") if number is not None else None


def position_exposure(cash, market_values, cap):
    missing = []
    if cash is None:
        missing.append("账户现金未确认")
    if None in market_values:
        missing.append("持仓计价价格不全")
    securities = sum(market_values, Decimal(0)) if None not in market_values else None
    assets = securities + cash if cash is not None and securities is not None else None
    fraction = securities / assets if assets is not None and assets > 0 else None
    if assets is not None and assets <= 0:
        missing.append("资产净值非正")
    if cap is None:
        missing.append("晴雨表仓位上限不可用")
    excess = fraction is not None and cap is not None and fraction > cap
    return {"market_value": _text(securities), "assets": _text(assets),
            "position_fraction": _text(fraction), "position_cap": _text(cap),
            "overage_amount": _text(securities-assets*cap) if excess else None,
            "overage_percentage_points": _text(100*(fraction-cap)) if excess else None,
            "missing": missing}

def _ledger_symbol(instrument):
    exchange, code = instrument.split(":")
    return code + "." + {"SSE": "SH", "SZSE": "SZ", "BSE": "BJ"}[exchange]


def _sellable(account, position, day):
    instrument = position["instrument"]
    quantity = Decimal(position["quantity"])
    lots = [lot for lot in account.get("lots", []) if lot["instrument"] == instrument
            and Decimal(lot["remaining_quantity"]) > 0]
    buys = {f["record_id"] for f in account.get("fills", []) if f["direction"] == "BUY"
            and f["instrument"] == instrument}
    unsettled = sum(Decimal(lot["remaining_quantity"]) for lot in lots if lot["lot_id"] in buys
                    and _local_day(lot["effective_at"]) >= day)
    explicit = position.get("sellable_quantity")
    if explicit is not None:
        return min(Decimal(explicit), quantity-unsettled)
    if sum(Decimal(lot["remaining_quantity"]) for lot in lots) == quantity and all(
            lot["lot_id"] in buys for lot in lots):
        return quantity-unsettled
    return None


def _local_day(stamp):
    return datetime.fromisoformat(stamp).astimezone(SHANGHAI).date().isoformat()


def _entry(account, position):
    # Walk back through actual fills to the last time this holding was opened.
    balance = Decimal(position["quantity"])
    instrument = position["instrument"]
    uncertain_dates = [r["effective_at"] for r in account.get("share_records", []) if r["instrument"] == instrument]
    uncertain_dates.extend(lot["effective_at"] for lot in account.get("lots", [])
                           if lot["instrument"] == instrument and lot["lot_id"].startswith("reconcile:"))
    boundary = max((datetime.fromisoformat(t) for t in uncertain_dates), default=None)
    for fill in reversed(account.get("fills", [])):
        if fill["instrument"] == instrument:
            if boundary and datetime.fromisoformat(fill["effective_at"]) <= boundary:
                break
            quantity = Decimal(fill["quantity"])
            balance += quantity if fill["direction"] == "SELL" else -quantity
            if balance == 0 and fill["direction"] == "BUY":
                return _local_day(fill["effective_at"])
            if balance < 0:
                break
    return None


def _excess_return(db, sector, day, benchmark):
    if not sector or len(benchmark) < 21 or benchmark[-1]["trade_date"] != day:
        return None
    first = benchmark[-21]["trade_date"]
    prices = {r["trade_date"]: Decimal(r["close"]) for r in input_rows(db, "etf_bars", sector, first, day)}
    if first not in prices or day not in prices or prices[first] <= 0:
        return None
    # Both returns span the same 20 exchange sessions, including the same endpoints.
    cursor = date.fromisoformat(first)
    finish = date.fromisoformat(day)
    count = 0
    extension = extended_sessions(db)
    while cursor < finish:
        cursor += timedelta(days=1)
        count += is_session(cursor, extension)
    if count != 20:
        return None
    return prices[day]/prices[first] - Decimal(benchmark[-1]["close"])/Decimal(benchmark[-21]["close"])


def _sector_flow(db, sector, day):
    if not sector:
        return None
    # Five same-day NAVs and the prior session's closing share count.
    finish = date.fromisoformat(day)
    extension = extended_sessions(db)
    sessions = [str(finish-timedelta(days=i)) for i in range(40)
                if is_session(finish-timedelta(days=i), extension)][:6]
    if len(sessions) != 6 or sessions[0] != day:
        return None
    shares = {r["trade_date"]: Decimal(r["shares"]) for r in
              input_rows(db, "etf_shares", sector, sessions[-1], day)}
    nav = {r["trade_date"]: Decimal(r["nav"]) for r in
           input_rows(db, "etf_nav", sector, sessions[-2], day)}
    if not all(d in shares for d in sessions) or not all(nav.get(d, 0) > 0 for d in sessions[:-1]):
        return None
    return sum((shares[d]-shares[prior])*nav[d] for d, prior in zip(sessions, sessions[1:]))


def risk_in_transaction(db, day, account, barometer):
    positions = {_ledger_symbol(p["instrument"]): p for p in account["positions"] if Decimal(p["quantity"]) > 0}
    settings = {item["code"]: item for item in active_watchlist_in_transaction(db)}
    benchmark = history_in_transaction(db, "000300.SH", None, day, "raw", False)
    cutoff = datetime.combine(date.fromisoformat(day), time(15), SHANGHAI).isoformat()
    effective = account.get("effective_at")
    cards = []
    market_values = []
    for symbol in dict.fromkeys([*settings, *positions]):
        config = settings.get(symbol, {})
        position = positions.get(symbol)
        quantity = Decimal(position["quantity"]) if position else Decimal(0)
        bars = history_in_transaction(db, symbol, None, day, "forward", True)
        # A fund in the actual ledger is valued from the ETF's own raw close.
        if not bars:
            bars = input_rows(db, "etf_bars", symbol, None, day)
        latest = bars[-1] if bars else {}
        price = Decimal(latest["close"]) if latest else None
        price_day = latest.get("trade_date")
        holding_value = quantity*price if price is not None else None
        if position:
            market_values.append(holding_value)
        missing = []
        if price is None:
            missing.append("缺收盘价")
        rs = _excess_return(db, config.get("sector_etf"), day, benchmark)
        if rs is None:
            missing.append("缺行业 ETF 或基准同日的 20 日收益")
        flow = _sector_flow(db, config.get("sector_etf"), day)
        if flow is None:
            missing.append("行业 ETF 近 5 个连续交易日的份额或净值不足")
        atr = Decimal(latest["atr14"]) if latest.get("atr14") is not None else None
        if atr is None:
            missing.append("缺 ATR14")
        low = min(Decimal(r["close"]) for r in bars[-21:-1]) if len(bars) >= 21 else None
        if low is None:
            missing.append("前 20 日收盘价不足")
        entry = _entry(account, position) if position else None
        peak = None
        if entry and bars and any(r["trade_date"] == entry for r in bars):
            peak = max(Decimal(r["close"]) for r in bars if r["trade_date"] >= entry)
        if position and peak is None:
            missing.append("持仓入场日期或入场以来的行情不足")
        multiplier = config.get("atr_stop_multiplier")
        stop = peak - Decimal(str(multiplier))*atr if None not in (peak,multiplier,atr) else None
        sellable = _sellable(account, position, day) if position else None
        light = financial_light_in_transaction(db, symbol, day)
        cards.append({
            "symbol":symbol, "name":config.get("name"), "sector_etf":config.get("sector_etf"),
            "trade_date":price_day, "close":_text(price), "price_stale":price_day != day,
            "market_cutoff_at":cutoff, "account_confirmed_at":account["confirmed_at"],
            "account_effective_at":effective, "account_stale":not effective or _local_day(effective) < day,
            "quantity":_text(quantity), "market_value":_text(holding_value), "position_cap":config.get("max_position_pct"),
            "position_fraction":None, "single_overage":None, "reference_shares":None,
            "sellable_quantity":_text(sellable), "sector_excess_return20":_text(rs),
            "sector_net_flow5_yuan":_text(flow),
            "ma20":latest.get("ma20"), "atr14":_text(atr), "atr_stop_multiplier":multiplier,
            "highest_close_since_entry":_text(peak), "atr_stop_price":_text(stop),
            "atr_stop_breached":price < stop if stop is not None else None,
            "previous_low20":_text(low), "below_low20":price < low if low is not None else None,
            "financial_light":light, "missing":missing,
        })
    cap = barometer["position_cap"]
    portfolio = position_exposure(Decimal(account["cash_balance"]) if account["cash_balance"] is not None else None,
                                  market_values, Decimal(str(cap)) if cap is not None else None)
    portfolio["stale_prices"] = [c["symbol"] for c in cards if c["symbol"] in positions and c["price_stale"]]
    assets = Decimal(portfolio["assets"]) if portfolio["assets"] is not None else None
    for card in cards:
        if card["symbol"] not in positions:
            continue
        if assets is None or assets <= 0 or card["market_value"] is None:
            card["missing"].append("账户总资产或个股估值不足")
            continue
        value = Decimal(card["market_value"])
        card["position_fraction"] = _text(value / assets)
        if card["position_cap"] is None:
            card["missing"].append("缺单票配置上限")
            continue
        excess = value - assets * Decimal(str(card["position_cap"]))
        if excess > 0:
            card["single_overage"] = _text(excess)
            if card["sellable_quantity"] is None:
                card["missing"].append("账本可卖数量未知")
            else:
                shares = min(excess / Decimal(card["close"]), Decimal(card["sellable_quantity"]))
                card["reference_shares"] = round_lot(shares)
    return {"trade_date":day, "market_cutoff_at":cutoff, "account_confirmed_at":account["confirmed_at"],
            "portfolio":portfolio, "cards":cards}


def risk_at(data_dir, trade_date):
    day = date.fromisoformat(trade_date)
    ledger = Ledger(data_dir)
    with connect(ledger.path) as db:
        if not is_session(day, extended_sessions(db)):
            raise ValueError('请选择已核实的交易日')
        initialize_market(db)
        initialize_inputs(db)
        db.executescript(FINANCIAL_SCHEMA)
        db.execute("BEGIN")
        snapshot = ledger.replay(ledger.events(db), known_by=datetime.now(SHANGHAI).isoformat(),
                                 effective_at=datetime.combine(day,time.max,SHANGHAI).isoformat())
        score = scores_in_transaction(db,trade_date,trade_date)[0]
        return risk_in_transaction(db,trade_date,snapshot,score)
