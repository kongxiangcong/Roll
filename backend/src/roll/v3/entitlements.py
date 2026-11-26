"""Company actions, record-date entitlements and account valuation."""
import json
import sys
from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP

from roll.v3.account import AccountLedger, AccountSnapshot, CENT, Receivable
from roll.v3.market import read_snapshot
from roll.v3.storage import database, instant, json_text, session_time


SIMULATION_BASIS = "股息红利税前、含交易成本"
REAL_ACCOUNT_BASIS = "按券商实际入账及扣税流水"


@dataclass(frozen=True)
class CompanyAction:
    action_id: str
    symbol: str
    record_date: str
    ex_date: str
    payment_date: str | None = None
    listing_date: str | None = None
    cash_per_share: Decimal = Decimal(0)
    shares_per_share: Decimal = Decimal(0)
    reference_deduction: Decimal | None = None
    source: str | None = None
    source_ref: str | None = None
    observation_seq: int | None = None

    def __post_init__(self):
        for field in ("cash_per_share", "shares_per_share", "reference_deduction"):
            if (value := getattr(self, field)) is not None:
                object.__setattr__(self, field, Decimal(str(value)))
        if self.record_date >= self.ex_date:
            raise ValueError("登记日须早于除权除息日")

    @property
    def key(self):
        return f"entitlement:{self.symbol}:{self.action_id}"

    @classmethod
    def from_observation(cls, row):
        terms = row["payload"]
        return cls(
            action_id=row["item_id"] or row["trade_date"], symbol=row["symbol"],
            record_date=terms["record_date"], ex_date=terms.get("ex_date", row["trade_date"]),
            payment_date=terms.get("payment_date"), listing_date=terms.get("listing_date"),
            cash_per_share=terms.get("cash_per_share") or 0, shares_per_share=terms.get("shares_per_share") or 0,
            reference_deduction=terms.get("reference_deduction"),
            source=row["source"], source_ref=row["source_ref"] or terms.get("source_url"), observation_seq=row["seq"],
        )


def read_company_actions(data_dir, snapshot_id, *, symbol=None, cutoff=None, start=None, end=None, db=None):
    rows = read_snapshot(data_dir, snapshot_id, series="corporate_action", symbol=symbol,
                         cutoff=cutoff, start=start, end=end, db=db)["observations"]
    return tuple(CompanyAction.from_observation(row) for row in rows)


def accrue_receivables(action: CompanyAction, record_lots) -> tuple[Receivable, ...]:
    receivables = []
    registered_quantity = 0
    prior_cash = Decimal(0)
    prior_shares = 0
    for lot in record_lots:
        if lot.symbol != action.symbol:
            continue
        registered_quantity += lot.quantity
        cash = (registered_quantity * action.cash_per_share).quantize(CENT, rounding=ROUND_HALF_UP)
        shares = int(registered_quantity * action.shares_per_share)
        details = action.key, action.symbol, lot.lot_id, action.record_date, action.ex_date
        if cash > prior_cash:
            receivables.append(Receivable(*details, "cash", action.payment_date, amount=cash - prior_cash))
        if shares > prior_shares:
            receivables.append(Receivable(*details, "shares", action.listing_date, quantity=shares - prior_shares))
        prior_cash, prior_shares = cash, shares
    return tuple(receivables)


def settle_entitlements(data_dir, book_id, actions, *, as_of, known_at=None, simulated=False, db=None) -> AccountSnapshot:
    """Recognize announced entitlements and post due simulated distributions atomically."""
    if db is None:
        with database(data_dir, write=True) as connection:
            return settle_entitlements(data_dir, book_id, actions, as_of=as_of, known_at=known_at,
                                       simulated=simulated, db=connection)
    if not db.in_transaction:
        with db:
            db.execute("BEGIN IMMEDIATE")
            return settle_entitlements(data_dir, book_id, actions, as_of=as_of, known_at=known_at,
                                       simulated=simulated, db=db)

    as_of = instant(as_of)
    known_at = instant(known_at) if known_at is not None else as_of
    ledger = AccountLedger(data_dir, db=db)
    ledger.require_role(book_id, simulated=simulated)
    existing = ledger.trade_log(book_id, as_of=as_of, known_at=known_at)
    if not existing:
        raise ValueError(f"账本 {book_id} 在指定时点没有已知基线")
    baseline = existing[0]
    baseline_day = instant(baseline["effective_at"]).date().isoformat()
    for action in actions:
        ex = session_time(action.ex_date, 0)
        if action.record_date < baseline_day or ex > as_of:
            continue
        ledger.record_company_action(book_id, action=action, effective_at=ex, known_at=known_at)
        if simulated:
            _post_simulated(ledger, book_id, action, as_of, known_at)
    if simulated:
        for receivable in baseline["payload"].get("receivables", ()):
            _post_due(ledger, book_id, receivable["action_key"], receivable["symbol"], receivable["kind"],
                      receivable["due_date"], as_of, known_at, not_before=instant(baseline["effective_at"]))
    return ledger.snapshot(book_id, as_of=as_of, known_at=known_at)


def _post_simulated(ledger, book_id, action, as_of, known_at):
    # Date-only cash notices do not establish pre-open spending power. Bonus
    # shares enter on the published listing session when they become tradable.
    for kind, day in (
        ("cash", action.payment_date if action.cash_per_share else None),
        ("shares", action.listing_date if action.shares_per_share else None),
    ):
        _post_due(ledger, book_id, action.key, action.symbol, kind, day, as_of, known_at)


def _post_due(ledger, book_id, action_key, symbol, kind, day, as_of, known_at, *, not_before=None):
    if day is None:
        return
    hour, minute = (9, 30) if kind == "shares" else (15, 0)
    posting = session_time(day, hour, minute)
    if not_before is not None:
        posting = max(posting, not_before)
    if posting <= as_of:
        ledger.record_entitlement_posting(
            book_id, action_key=action_key, symbol=symbol, kind=kind,
            effective_at=posting, known_at=known_at, source="simulated-company-action",
            sellable_on=day if kind == "shares" else None,
        )


def record_broker_entitlement(data_dir, book_id, *, symbol, action_id, kind, broker_event_id,
                              effective_at, actual, known_at=None, source="broker",
                              broker_available_after=None, sellable_on=None):
    if kind not in {"cash", "shares"} or Decimal(str(actual)) < 0:
        raise ValueError("到账权益需要现金或股份类型及非负实际到账量")
    symbol = symbol.upper()
    ledger = AccountLedger(data_dir)
    ledger.require_role(book_id, simulated=False)
    return ledger.record_entitlement_posting(
        book_id, action_key=f"entitlement:{symbol}:{action_id}", symbol=symbol, kind=kind,
        effective_at=effective_at, known_at=known_at, source=source, actual=actual,
        broker_available_after=broker_available_after, sellable_on=sellable_on, broker_event_id=broker_event_id,
    )


@dataclass(frozen=True)
class AccountValuation:
    cash: Decimal
    position_value: Decimal
    receivable_value: Decimal

    @property
    def nav(self):
        return self.cash + self.position_value + self.receivable_value

    def as_dict(self):
        return {
            name: format(value.normalize(), "f")
            for name, value in {**asdict(self), "nav": self.nav}.items()
        }


def value_account(snapshot: AccountSnapshot, prices) -> AccountValuation:
    def price(symbol):
        if symbol not in prices or prices[symbol] is None:
            raise ValueError(f"缺少 {symbol} 的原始估值价")
        return Decimal(str(prices[symbol]))

    positions = sum((lot.quantity * price(lot.symbol) for lot in snapshot.lots), Decimal(0))
    receivables = sum((
        item.amount if item.kind == "cash" else item.quantity * price(item.symbol)
        for item in snapshot.receivables
    ), Decimal(0))
    return AccountValuation(snapshot.cash, positions, receivables)


def register_entitlement_commands(commands):
    command = commands.add_parser("entitlements", help="查看、结算及核对公司行动权益")
    operations = command.add_subparsers(required=True)
    for name, handler, help_text in (
        ("settle", _settle, "确认登记所得权益并结算到期的模拟权益"),
        ("value", _value, "以冻结行情的原始收盘价计算账本净值"),
    ):
        operation = operations.add_parser(name, help=help_text)
        operation.add_argument("--book-id", default="real")
        operation.add_argument("--snapshot-id", required=True, help="行情数据快照")
        operation.add_argument("--known-at")
        operation.set_defaults(handler=handler)
        if name == "settle":
            operation.add_argument("--as-of", required=True)
            operation.add_argument("--simulated", action="store_true", help="以公告日期结转模拟权益")
        else:
            cutoff = operation.add_mutually_exclusive_group(required=True)
            cutoff.add_argument("--as-of")
            cutoff.add_argument("--account-snapshot-id", help="按已冻结的账户状态估值")

    confirm = operations.add_parser(
        "confirm", help="从标准输入登记券商实际到账权益",
        description="从标准输入读取 JSON，字段包括 symbol、action_id、kind、broker_event_id、effective_at 和 actual。"
                    "股份可填 sellable_on，现金可填 broker_available_after。",
    )
    confirm.add_argument("--book-id", default="real")
    confirm.set_defaults(handler=_confirm)

    evidence = operations.add_parser("evidence", help="核对公告派息、除息参考扣减和原始开盘行情")
    evidence.add_argument("--snapshot-id", required=True)
    evidence.add_argument("--symbol", required=True)
    evidence.add_argument("--ex-date", required=True)
    evidence.set_defaults(handler=_evidence)


def _settle(args, data_dir):
    actions = read_company_actions(data_dir, args.snapshot_id, cutoff=args.known_at or args.as_of)
    snapshot = settle_entitlements(
        data_dir, args.book_id, actions, as_of=args.as_of, known_at=args.known_at, simulated=args.simulated,
    )
    return {
        "account": snapshot.as_dict(), "market_snapshot_id": args.snapshot_id,
        "basis": SIMULATION_BASIS if args.simulated else REAL_ACCOUNT_BASIS,
    }


def _value(args, data_dir):
    ledger = AccountLedger(data_dir)
    if args.account_snapshot_id:
        account = ledger.read_snapshot(args.account_snapshot_id)
    else:
        account = ledger.snapshot(args.book_id, as_of=args.as_of, known_at=args.known_at)
    rows = read_snapshot(data_dir, args.snapshot_id, cutoff=account.effective_at)["observations"]
    symbols = {lot.symbol for lot in account.lots} | {r.symbol for r in account.receivables if r.kind == "shares"}
    prices = {
        row["symbol"]: {"close": row["payload"]["close"], "trade_date": row["trade_date"], "observation_seq": row["seq"]}
        for row in rows if row["symbol"] in symbols and row["payload"].get("close") is not None
    }
    valuation = value_account(account, {symbol: quote["close"] for symbol, quote in prices.items()})
    return {
        "account": account.as_dict(), "market_snapshot_id": args.snapshot_id,
        "prices": prices, "valuation": valuation.as_dict(),
    }


def _confirm(args, data_dir):
    payload = json.load(sys.stdin, parse_float=Decimal)
    event_id = record_broker_entitlement(data_dir, args.book_id, **payload)
    return {"book_id": args.book_id, "event_id": event_id}


def _evidence(args, data_dir):
    scope = dict(symbol=args.symbol, start=args.ex_date, end=args.ex_date)
    actions = read_company_actions(data_dir, args.snapshot_id, **scope)
    opening = read_snapshot(data_dir, args.snapshot_id, series="daily_open", **scope)["observations"]
    return {
        "snapshot_id": args.snapshot_id,
        "actions": [json.loads(json_text(asdict(action))) for action in actions],
        "opening": next(iter(opening), None),
    }
