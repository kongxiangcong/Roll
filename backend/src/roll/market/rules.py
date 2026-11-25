"""A-share lot sizing and the next eligible Shanghai trading session."""
from datetime import date, timedelta
from decimal import Decimal, ROUND_DOWN

from roll.market.calendar import is_session


def round_lot(quantity: Decimal, lot: int = 100) -> int:
    if lot <= 0 or quantity < 0:
        raise ValueError("无效的整手单位或数量")
    return int((quantity / lot).to_integral_value(rounding=ROUND_DOWN)) * lot


def next_trading_day(day: date) -> date:
    candidate = day + timedelta(days=1)
    while not is_session(candidate):
        candidate += timedelta(days=1)
    return candidate
