"""Simulated settlement of frozen intents against raw opening quotes."""
from bisect import bisect_right
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from math import lcm

from roll.costs import execution_price, stock_rates, transaction_cost
from roll.market.rules import next_trading_day
from roll.v3.account import AccountSnapshot, apply_fill
from roll.v3.market import read_snapshot
from roll.v3.storage import instant, session_time


TICK = Decimal("0.01")
EXECUTION_RULES_VERSION = "a-share-next-open-v1"
# SZSE's ChiNext registration reform and both exchanges' 2026 trading rules.
CHINEXT_REFORM = date(2020, 8, 24)
RISK_WARNING_REFORM = date(2026, 7, 6)

# Minimum order, increment and single limit order maximum by board.
ORDER_SIZES = {
    "main": (100, 100, 1_000_000),
    "star": (200, 1, 100_000),
    "chinext": (100, 100, 300_000),
}


@dataclass(frozen=True)
class ExecutionIntent:
    intent_id: str
    symbol: str
    side: str
    quantity: int
    decision_at: str
    limit_price: Decimal | None = None
    cash_limit: Decimal | None = None


@dataclass(frozen=True)
class OpeningQuote:
    symbol: str
    session: date | str
    raw_open: Decimal | None
    pre_close: Decimal | None
    prior_close: Decimal | None = None
    trading_status: str = "trading"
    risk_warning: bool = False
    price_limit_rate: Decimal | None = None
    observation_seq: int | None = None

    @classmethod
    def from_payload(cls, symbol, session, payload, *, observation_seq=None):
        return cls(symbol, session, payload.get("open"), payload.get("pre_close"),
                   payload.get("prior_close"), payload.get("trading_status", "unknown"),
                   payload.get("risk_warning", False), payload.get("price_limit_rate"), observation_seq)


@dataclass(frozen=True)
class ExecutionRules:
    commission_rate: Decimal = Decimal("0.0003")
    minimum_commission: Decimal = Decimal("5")
    slippage_rate: Decimal = Decimal("0.0005")
    lot_size: int = 1


@dataclass(frozen=True)
class Fill:
    event_id: str
    symbol: str
    side: str
    quantity: int
    price: Decimal
    fee: Decimal
    gross: Decimal
    effective_at: str

    def ledger_fields(self):
        fields = asdict(self)
        del fields["gross"]
        return fields


@dataclass(frozen=True)
class ExecutionResult:
    intent: ExecutionIntent
    session: str
    status: str
    reason: str | None
    opening: OpeningQuote | None
    fill: Fill | None
    account: AccountSnapshot

    def as_dict(self):
        return {
            "intent": asdict(self.intent), "session": self.session, "status": self.status,
            "reason": self.reason, "opening": asdict(self.opening) if self.opening else None,
            "fill": asdict(self.fill) if self.fill else None, "account": self.account.as_dict(),
        }


def execution_session(intent: ExecutionIntent) -> date:
    return next_trading_day(instant(intent.decision_at).date())


def read_opening_quote(data_dir, snapshot_id, symbol, session, *, cutoff=None) -> OpeningQuote | None:
    day = str(session)
    rows = read_snapshot(data_dir, snapshot_id, series="daily_open", symbol=symbol, start=day, end=day,
                         cutoff=cutoff or session_time(day, 9, 30))["observations"]
    if not rows:
        return None
    row = rows[0]
    return OpeningQuote.from_payload(symbol, day, row["payload"], observation_seq=row["seq"])


def estimate_fees(symbol, session, side, price, quantity, rules=ExecutionRules()) -> Decimal:
    day = date.fromisoformat(str(session))
    if _board(symbol, day) is None:
        raise ValueError(f"{symbol} 不适用沪深 A 股交易费率")
    transfer, stamp = stock_rates(day, side)
    return transaction_cost(Decimal(str(price)) * quantity, Decimal(str(rules.commission_rate)),
                            Decimal(str(rules.minimum_commission)), transfer, stamp)


def _board(symbol, session):
    code, _, exchange = symbol.partition(".")
    if exchange == "SH":
        if code.startswith("688"):
            return "star"
        if code.startswith(("600", "601", "603", "605")):
            return "main"
    if exchange == "SZ":
        if code.startswith(("300", "301")):
            return "chinext" if session >= CHINEXT_REFORM else "main"
        if code.startswith(("000", "001", "002", "003")):
            return "main"
    return None


def _buy_quantities(board, quantity, rules):
    minimum, increment, maximum = ORDER_SIZES[board]
    step = lcm(increment, rules.lot_size)
    first = (minimum + step - 1) // step * step
    return range(first, min(quantity, maximum) + 1, step)


def _price_limit_rate(opening, board, session):
    if opening.price_limit_rate is not None:
        return Decimal(str(opening.price_limit_rate))
    if board in {"star", "chinext"}:
        return Decimal("0.20")
    if opening.risk_warning and session < RISK_WARNING_REFORM:
        return Decimal("0.05")
    return Decimal("0.10")


def affordable_quantity(symbol, session, price, max_quantity, cash, rules=ExecutionRules()) -> int:
    price = Decimal(str(price))
    cash = Decimal(str(cash))
    board = _board(symbol, date.fromisoformat(str(session)))
    if board is None:
        return 0
    quantities = _buy_quantities(board, max_quantity, rules)

    def cost(quantity):
        return price * quantity + estimate_fees(symbol, session, "BUY", price, quantity, rules)

    index = bisect_right(quantities, cash, key=cost)
    return quantities[index - 1] if index else 0


def sellable_order_quantity(symbol, session, quantity, lots, rules=ExecutionRules()) -> int:
    """Apply order sizes to a quantity already capped by confirmed sellable shares."""
    board = _board(symbol, date.fromisoformat(str(session)))
    if board is None:
        return 0
    minimum, increment, maximum = ORDER_SIZES[board]
    shares = sum(lot.quantity for lot in lots if lot.symbol == symbol)
    if board == "star" and shares < minimum:
        return shares if quantity >= shares else 0
    quantity = min(quantity, maximum)
    legal_quantities = _buy_quantities(board, quantity, rules)
    rounded = legal_quantities[-1] if legal_quantities else 0
    # The whole exchange odd-lot remainder may be sold on its own or with full lots.
    odd = shares % increment
    if 0 < odd <= quantity:
        full_lots = _buy_quantities(board, quantity - odd, rules)
        rounded = max(rounded, (full_lots[-1] if full_lots else 0) + odd)
    return rounded


def execute(intent: ExecutionIntent, opening: OpeningQuote | None, account: AccountSnapshot,
            rules: ExecutionRules = ExecutionRules()) -> ExecutionResult:
    """Evaluate one intent on its next exchange session, returning the projected account."""
    session = execution_session(intent)
    day = str(session)
    effective_at = session_time(session, 9, 30)

    def unfilled(reason):
        return ExecutionResult(intent, day, "UNFILLED", reason, opening, None, account)

    if opening is None or str(opening.session) != day or opening.symbol != intent.symbol:
        return unfilled("MISSING_OPENING")
    if opening.trading_status == "suspended":
        return unfilled("SUSPENDED")
    if opening.trading_status != "trading" or opening.raw_open is None:
        return unfilled("UNKNOWN_OPENING")
    if instant(account.effective_at) > effective_at:
        return unfilled("ACCOUNT_AFTER_OPEN")
    board = _board(intent.symbol, session)
    if board is None:
        return unfilled("UNSUPPORTED_SECURITY")
    limit_rate = _price_limit_rate(opening, board, session)
    raw_open = Decimal(str(opening.raw_open))
    buy = intent.side == "BUY"
    price = execution_price(raw_open, intent.side, Decimal(str(rules.slippage_rate)), TICK)
    if limit_rate:
        if opening.pre_close is None:
            return unfilled("MISSING_REFERENCE_CLOSE")
        pre_close = Decimal(str(opening.pre_close))
        lower = (pre_close * (1 - limit_rate)).quantize(TICK, rounding=ROUND_HALF_UP)
        upper = (pre_close * (1 + limit_rate)).quantize(TICK, rounding=ROUND_HALF_UP)
        lower, upper = max(TICK, min(lower, pre_close - TICK)), max(upper, pre_close + TICK)
        if not lower <= raw_open <= upper:
            return unfilled("OPEN_OUTSIDE_PRICE_BAND")
        if raw_open == (upper if buy else lower):
            return unfilled("LIMIT_QUEUE_UNCONFIRMED")
        price = min(upper, max(lower, price))
    if intent.limit_price is not None:
        limit = Decimal(str(intent.limit_price))
        if (buy and price > limit) or (not buy and price < limit):
            return unfilled("ORDER_LIMIT_NOT_MET")

    requested = intent.quantity
    reason = "ORDER_QUANTITY"
    if buy:
        if account.available_cash is None:
            return unfilled("UNKNOWN_AVAILABLE_CASH")
        cash = min(account.cash, account.available_cash)
        if intent.cash_limit is not None:
            cash = min(cash, Decimal(str(intent.cash_limit)))
        legal_quantities = _buy_quantities(board, requested, rules)
        quantity = affordable_quantity(intent.symbol, session, price, requested, cash, rules)
        if legal_quantities and quantity < legal_quantities[-1]:
            reason = "INSUFFICIENT_CASH"
    else:
        sellable = account.known_sellable(intent.symbol, session)
        if sellable is None:
            return unfilled("UNKNOWN_SELLABLE_SHARES")
        if not sellable:
            return unfilled("NO_SELLABLE_SHARES")
        quantity = sellable_order_quantity(intent.symbol, session, min(requested, sellable),
                                           account.lots, rules)
        if requested > sellable:
            reason = "INSUFFICIENT_SELLABLE_SHARES"

    if quantity <= 0:
        return unfilled(reason)

    gross = price * quantity
    fee = estimate_fees(intent.symbol, session, intent.side, price, quantity, rules)
    if not buy and gross + account.cash < fee:
        return unfilled("INSUFFICIENT_CASH_FOR_FEES")
    fill = Fill(f"{intent.intent_id}:{day}", intent.symbol, intent.side, quantity, price, fee, gross,
                effective_at.isoformat())
    projected = apply_fill(account, **fill.ledger_fields())
    if quantity == requested:
        return ExecutionResult(intent, day, "FILLED", None, opening, fill, projected)
    return ExecutionResult(intent, day, "PARTIAL", reason, opening, fill, projected)
