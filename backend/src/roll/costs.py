"""Decimal transaction costs and historical A-share fee rates."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP


def stock_rates(day: date, side: str) -> tuple[Decimal, Decimal]:
    """SSE A-share transfer and stamp rates on consideration from August 2015."""
    if day < date(2015, 8, 1) or side not in {"BUY", "SELL"}:
        raise ValueError("不支持的 A 股历史费用日期或方向")
    transfer = Decimal("0.00002") if day < date(2022, 4, 29) else Decimal("0.00001")
    stamp = Decimal("0.001") if day < date(2023, 8, 28) else Decimal("0.0005")
    return transfer, stamp if side == "SELL" else Decimal(0)


def transaction_cost(gross: Decimal, commission: Decimal, minimum: Decimal,
                     transfer: Decimal = Decimal(0), stamp: Decimal = Decimal(0)) -> Decimal:
    if any(value < 0 for value in (gross, commission, minimum, transfer, stamp)):
        raise ValueError("费用金额及费率不能为负")
    if gross == 0:
        return Decimal("0.00")
    components = (max(minimum, gross * commission), gross * transfer, gross * stamp)
    return sum(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) for value in components)


def execution_price(raw_open: Decimal, side: str, slippage: Decimal, tick: Decimal) -> Decimal:
    if raw_open <= 0 or not 0 <= slippage < 1 or tick <= 0 or side not in {"BUY", "SELL"}:
        raise ValueError("无效的成交价参数")
    slipped = raw_open * (1 + slippage if side == "BUY" else 1 - slippage)
    return (slipped / tick).to_integral_value(rounding=ROUND_HALF_UP) * tick
