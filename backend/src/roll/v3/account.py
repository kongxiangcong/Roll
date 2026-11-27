"""Local account facts and immutable snapshots shared by real and simulated books."""
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
from pathlib import Path
from sqlite3 import Connection

from roll.market.calendar import LAST_NOTICE_DAY, is_session
from roll.v3.storage import SHANGHAI, database, instant, session_time


CENT = Decimal("0.01")


def _timestamp(value: str | datetime) -> str:
    return instant(value).astimezone(timezone.utc).isoformat(timespec="microseconds")


def _trade_date(value: str) -> date:
    return datetime.fromisoformat(value).astimezone(SHANGHAI).date()


def _decimal(value) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _shares(value) -> int:
    shares = _decimal(value)
    if shares != shares.to_integral_value():
        raise ValueError("股数须为整数")
    return int(shares)


def _encode(value) -> str:
    def stringify(value):
        if isinstance(value, Decimal):
            text = format(value, "f")
            return text.rstrip("0").rstrip(".") if "." in text else text
        raise TypeError(f"无法序列化 {type(value).__name__}")

    return json.dumps(value, default=stringify, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _next_sellable_day(acquired_on: date) -> str:
    day = acquired_on + timedelta(days=1)
    while 2013 <= day.year and day <= LAST_NOTICE_DAY and not is_session(day):
        day += timedelta(days=1)
    return day.isoformat()


@dataclass(frozen=True)
class PositionLot:
    lot_id: str
    symbol: str
    quantity: int
    acquired_on: str | None = None
    sellable_on: str | None = None
    known_sellable: int | None = None
    cost: Decimal | None = None
    source_event_id: str | None = None
    source_lot_id: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "symbol", self.symbol.upper())
        object.__setattr__(self, "cost", _decimal(self.cost))
        object.__setattr__(self, "quantity", _shares(self.quantity))
        if self.known_sellable is not None:
            object.__setattr__(self, "known_sellable", _shares(self.known_sellable))
        for field in ("acquired_on", "sellable_on"):
            if isinstance(value := getattr(self, field), date):
                object.__setattr__(self, field, value.isoformat())
        if self.quantity <= 0 or (
            self.known_sellable is not None and not 0 <= self.known_sellable <= self.quantity
        ):
            raise ValueError("批次股数须为正，可卖数须在零与持仓之间")

    def sellable_quantity(self, session: date | str) -> int | None:
        day = session.isoformat() if isinstance(session, date) else session
        if self.sellable_on is not None:
            if day >= self.sellable_on:
                return self.quantity
            return self.known_sellable or 0
        return self.known_sellable


@dataclass(frozen=True)
class RiskBudget:
    budget_id: str
    effective_at: str
    known_at: str
    cash_reserve: Decimal
    max_total_exposure: Decimal
    max_symbol_exposure: Decimal
    max_industry_exposure: Decimal
    expires_at: str | None = None
    funds_needed_at: str | None = None
    pause_conditions: tuple[str, ...] = ()

    def __post_init__(self):
        for field in ("cash_reserve", "max_total_exposure", "max_symbol_exposure", "max_industry_exposure"):
            object.__setattr__(self, field, _decimal(getattr(self, field)))
        for field in ("effective_at", "known_at", "expires_at", "funds_needed_at"):
            if (value := getattr(self, field)) is not None:
                object.__setattr__(self, field, _timestamp(value))
        object.__setattr__(self, "pause_conditions", tuple(self.pause_conditions))


@dataclass(frozen=True)
class Receivable:
    action_key: str
    symbol: str
    source_lot_id: str
    record_date: str
    ex_date: str
    kind: str
    due_date: str | None
    amount: Decimal = Decimal(0)
    quantity: int = 0

    def __post_init__(self):
        object.__setattr__(self, "symbol", self.symbol.upper())
        object.__setattr__(self, "amount", _decimal(self.amount))


@dataclass(frozen=True)
class AccountSnapshot:
    snapshot_id: str
    book_id: str
    effective_at: str
    known_at: str
    cash: Decimal
    available_cash: Decimal | None
    lots: tuple[PositionLot, ...]
    through_event_id: str
    risk_budget: RiskBudget | None = None
    receivables: tuple[Receivable, ...] = ()

    def known_sellable(self, symbol: str, session: date | str) -> int | None:
        quantities = [lot.sellable_quantity(session) for lot in self.lots if lot.symbol == symbol.upper()]
        confirmed = [quantity for quantity in quantities if quantity is not None]
        return sum(confirmed) if confirmed or not quantities else None

    def as_dict(self) -> dict:
        result = json.loads(_encode(asdict(self)))
        session = _trade_date(self.effective_at)
        result["known_sellable"] = {
            symbol: self.known_sellable(symbol, session) for symbol in sorted({lot.symbol for lot in self.lots})
        }
        return result


def _consume_lots(lots, symbol, session, quantity):
    remaining = list(lots)
    # Prefer confirmed sellable shares. A broker-confirmed fill can also
    # establish sales from lots whose previous availability has changed.
    for confirmed in (True, False):
        for index, lot in enumerate(remaining):
            if lot is None or lot.symbol != symbol or not quantity:
                continue
            sellable = lot.sellable_quantity(session)
            limit = (sellable or 0) if confirmed else lot.quantity
            sold = min(limit, quantity)
            if not sold:
                continue
            quantity -= sold
            shares = lot.quantity - sold
            cost = lot.cost
            if cost is not None:
                cost = (cost * shares / lot.quantity).quantize(CENT, rounding=ROUND_HALF_UP)
            known_sellable = None if lot.known_sellable is None else max(0, lot.known_sellable - sold)
            remaining[index] = (
                replace(lot, quantity=shares, cost=cost, known_sellable=known_sellable) if shares else None
            )
    if quantity:
        raise ValueError(f"{symbol} 的成交卖出股数超过可用于核对的持仓")
    return tuple(lot for lot in remaining if lot is not None)


def _fill_payload(symbol, side, quantity, price, fee=0, sellable_on=None, broker_available_after=None,
                  broker_order_id=None):
    quantity = _shares(quantity)
    price = _decimal(price)
    fee = _decimal(fee)
    if side.upper() not in {"BUY", "SELL"} or quantity <= 0 or price <= 0 or fee < 0:
        raise ValueError("成交需要买卖方向、正股数和价格，以及非负费用")
    payload = {
        "symbol": symbol.upper(),
        "side": side.upper(),
        "quantity": quantity,
        "price": price,
        "fee": fee,
        "sellable_on": sellable_on.isoformat() if isinstance(sellable_on, date) else sellable_on,
        "broker_available_after": _decimal(broker_available_after),
    }
    if broker_order_id is not None:
        payload["broker_order_id"] = broker_order_id
    return payload


def _apply_fill(snapshot, event_id, effective_at, payload):
    quantity = payload["quantity"]
    gross = fill_gross(quantity, payload["price"])
    fee = _decimal(payload["fee"])
    symbol = payload["symbol"]
    acquired_on = _trade_date(effective_at)
    if payload["side"] == "BUY":
        delta = -gross - fee
        lot = PositionLot(
            event_id, symbol, quantity, acquired_on.isoformat(),
            payload["sellable_on"] or _next_sellable_day(acquired_on),
            cost=-delta, source_event_id=event_id,
        )
        lots = (*snapshot.lots, lot)
    else:
        delta = gross - fee
        lots = _consume_lots(snapshot.lots, symbol, acquired_on, quantity)

    return _apply_cash(replace(snapshot, lots=lots), delta, payload["broker_available_after"])


def fill_gross(quantity, price):
    return (quantity * _decimal(price)).quantize(CENT, rounding=ROUND_HALF_UP)


def apply_fill(snapshot: AccountSnapshot, *, event_id, symbol, side, quantity, price, effective_at,
               fee=0, sellable_on=None) -> AccountSnapshot:
    """Project the same cash and lot changes as a recorded fill, without writing a ledger."""
    effective_at = _timestamp(effective_at)
    payload = _fill_payload(symbol, side, quantity, price, fee, sellable_on)
    projected = _apply_fill(snapshot, event_id, effective_at, payload)
    return replace(projected, snapshot_id="", through_event_id=event_id, effective_at=effective_at,
                   known_at=max(_timestamp(snapshot.known_at), effective_at))


def _apply_cash(snapshot, delta, broker_available_after):
    available = _decimal(broker_available_after)
    if available is None and snapshot.available_cash is not None:
        available = max(Decimal(0), snapshot.available_cash + delta)
    cash = snapshot.cash + delta
    if cash < 0:
        raise ValueError("流水入账后的总现金为负，请核对初始现金及资金流水")
    return replace(snapshot, cash=cash, available_cash=available)


def _apply_entitlement_posting(snapshot, event, payload):
    action_key, kind = payload["action_key"], payload["kind"]
    due = tuple(r for r in snapshot.receivables if (r.action_key, r.kind) == (action_key, kind))
    snapshot = replace(snapshot, receivables=tuple(r for r in snapshot.receivables if r not in due))
    actual = payload["actual"]
    if kind == "cash":
        amount = _decimal(actual) if actual is not None else sum((r.amount for r in due), Decimal(0))
        return _apply_cash(snapshot, amount, payload["broker_available_after"])

    quantity = actual if actual is not None else sum(r.quantity for r in due)
    day = _trade_date(event["effective_at"]).isoformat()
    lots = list(snapshot.lots)
    event_id = event["event_id"]
    allocations = []
    for receivable in due:
        shares = min(quantity, receivable.quantity)
        allocations.append((receivable.source_lot_id, shares))
        quantity -= shares
    allocations.append((None, quantity))
    for index, (source_lot_id, shares) in enumerate(allocations):
        if shares:
            lots.append(PositionLot(
                f"{event_id}:{index}", payload["symbol"], shares,
                acquired_on=day, sellable_on=payload["sellable_on"],
                source_event_id=event_id, source_lot_id=source_lot_id,
            ))
    return replace(snapshot, lots=tuple(lots))


def _effective_payloads(facts):
    originals = {event["event_id"]: event["payload"] for event in facts if event["kind"] != "CORRECTION"}
    effective = originals.copy()
    corrections = sorted((event for event in facts if event["kind"] == "CORRECTION"),
                         key=lambda event: (event["known_at"], event["seq"]))
    for correction in corrections:
        payload = correction["payload"]
        target = payload["target_event_id"]
        replacement = payload["replacement"]
        effective[target] = (
            None if replacement is None else {**(effective[target] or originals[target]), **replacement}
        )
    for event in facts:
        if event["kind"] == "FILL" and (payload := effective[event["event_id"]]) is not None:
            effective[event["event_id"]] = {**payload, "symbol": payload["symbol"].upper()}
    return effective


def _baseline_role(book_id, source, payload):
    if "simulated" in payload:
        return payload["simulated"]
    return (
        source == "forward-baseline" and book_id.startswith("review:shadow:")
        or source == "frozen-experiment-baseline" and book_id.startswith("experiment:")
    )


def _project(book_id, effective_at, known_at, facts) -> AccountSnapshot:
    from roll.v3.entitlements import CompanyAction, accrue_receivables

    if not facts or facts[0]["kind"] != "BASELINE":
        raise ValueError(f"账本 {book_id} 在指定时点没有已知基线")
    baseline = json.loads(facts[0]["payload"])
    snapshot = AccountSnapshot(
        "", book_id, effective_at, known_at, _decimal(baseline["cash"]),
        _decimal(baseline["available_cash"]), tuple(PositionLot(**lot) for lot in baseline["lots"]),
        max(facts, key=lambda event: event["seq"])["event_id"],
        receivables=tuple(Receivable(**item) for item in baseline.get("receivables", ())),
    )

    effective = _effective_payloads([{**dict(event), "payload": json.loads(event["payload"])} for event in facts[1:]])

    actions = {}
    for event in sorted(
        (event for event in facts[1:] if event["kind"] == "COMPANY_ACTION"),
        key=lambda event: (event["known_at"], event["seq"]),
    ):
        action = CompanyAction(**effective[event["event_id"]])
        actions[action.key] = (event["event_id"], action)
    action_events = {event_id: action for event_id, action in actions.values()}
    record_dates = sorted({action.record_date for action in action_events.values()})
    record_cutoffs = iter((_timestamp(session_time(day, 15)), day) for day in record_dates)
    record_close = next(record_cutoffs, None)
    record_lots = {}
    posted = set()

    for event in facts[1:]:
        payload = effective.get(event["event_id"])
        if payload is None:
            continue
        while record_close is not None and record_close[0] < event["effective_at"]:
            record_lots[record_close[1]] = snapshot.lots
            record_close = next(record_cutoffs, None)
        if event["kind"] == "FILL":
            snapshot = _apply_fill(snapshot, event["event_id"], event["effective_at"], payload)
        elif event["kind"] == "CASH":
            snapshot = _apply_cash(snapshot, _decimal(payload["delta"]), payload["broker_available_after"])
        elif event["kind"] == "SHARES":
            snapshot = replace(snapshot, lots=(*snapshot.lots, PositionLot(**payload["lot"])))
        elif action := action_events.get(event["event_id"]):
            receivables = tuple(
                item for item in accrue_receivables(action, record_lots.get(action.record_date, ()))
                if (item.action_key, item.kind) not in posted
            )
            snapshot = replace(snapshot, receivables=(*snapshot.receivables, *receivables))
        elif event["kind"] == "ENTITLEMENT_POSTING":
            snapshot = _apply_entitlement_posting(snapshot, event, payload)
            posted.add((payload["action_key"], payload["kind"]))
    return snapshot


_SCHEMA = """
CREATE TABLE IF NOT EXISTS trade_log (
    seq INTEGER PRIMARY KEY,
    book_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    effective_at TEXT NOT NULL,
    known_at TEXT NOT NULL,
    source TEXT NOT NULL,
    plan_id TEXT,
    payload TEXT NOT NULL,
    UNIQUE(book_id, event_id)
);
CREATE INDEX IF NOT EXISTS trade_log_as_of ON trade_log(book_id, effective_at, known_at);
CREATE TABLE IF NOT EXISTS risk_budget (
    seq INTEGER PRIMARY KEY,
    book_id TEXT NOT NULL,
    budget_id TEXT NOT NULL,
    effective_at TEXT NOT NULL,
    known_at TEXT NOT NULL,
    payload TEXT NOT NULL,
    UNIQUE(book_id, budget_id)
);
CREATE INDEX IF NOT EXISTS risk_budget_as_of ON risk_budget(book_id, effective_at, known_at);
CREATE TABLE IF NOT EXISTS account_snapshot (
    snapshot_id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    effective_at TEXT NOT NULL,
    known_at TEXT NOT NULL,
    payload TEXT NOT NULL
);
"""


class AccountLedger:
    """Append facts by book and freeze account snapshots.

    A supplied connection joins the caller's transaction for plan and
    settlement workflows that write account facts together with other records.
    """

    def __init__(self, data_dir: Path, *, db: Connection | None = None):
        self.data_dir = data_dir
        self._db = db
        with self._connection() as connection:
            for statement in _SCHEMA.strip().split(";"):
                if statement.strip():
                    connection.execute(statement)

    @contextmanager
    def _connection(self, *, write=False):
        if self._db is None:
            with database(self.data_dir, write=write) as db:
                yield db
        elif write and not self._db.in_transaction:
            with self._db as db:
                db.execute("BEGIN IMMEDIATE")
                yield db
        else:
            yield self._db

    def initialize(self, book_id, *, cash, available_cash=None, lots=(), effective_at,
                   known_at=None, source="user-confirmed", receivables=(), simulated=False) -> str:
        if type(simulated) is not bool:
            raise ValueError("账本 simulated 须为 JSON 布尔值")
        payload = {
            "simulated": simulated,
            "cash": _decimal(cash),
            "available_cash": _decimal(available_cash),
            "lots": [
                asdict(replace(lot, source_event_id=lot.source_event_id or "baseline"))
                for lot in lots
            ],
        }
        if receivables:
            payload["receivables"] = [asdict(item) for item in receivables]
        return self._record(book_id, "baseline", "BASELINE", effective_at, known_at, source, None, payload)

    def require_role(self, book_id, *, simulated):
        with self._connection() as db:
            row = db.execute(
                "SELECT source, payload FROM trade_log WHERE book_id = ? AND event_id = 'baseline'", (book_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"账本 {book_id} 没有已知基线")
        if _baseline_role(book_id, row["source"], json.loads(row["payload"])) != simulated:
            if simulated:
                raise ValueError("模拟写入需要使用独立的模拟账本")
            raise ValueError("真实操作需要使用真实账本")

    def record_fill(self, book_id, *, event_id, symbol, side, quantity, price, effective_at,
                    fee=0, known_at=None, sellable_on=None, broker_available_after=None,
                    source="broker", plan_id=None, broker_order_id=None) -> str:
        payload = _fill_payload(symbol, side, quantity, price, fee, sellable_on, broker_available_after, broker_order_id)
        return self._record(book_id, event_id, "FILL", effective_at, known_at, source, plan_id, payload)

    def record_cash(self, book_id, *, event_id, delta, effective_at, known_at=None,
                    broker_available_after=None, source="broker", plan_id=None, reason=None) -> str:
        payload = {
            "delta": _decimal(delta), "broker_available_after": _decimal(broker_available_after), "reason": reason,
        }
        return self._record(book_id, event_id, "CASH", effective_at, known_at, source, plan_id, payload)

    def record_shares(self, book_id, *, event_id, lot: PositionLot, effective_at, known_at=None,
                      source="broker", plan_id=None) -> str:
        payload = {"lot": asdict(replace(lot, source_event_id=lot.source_event_id or event_id))}
        return self._record(book_id, event_id, "SHARES", effective_at, known_at, source, plan_id, payload)

    def record_company_action(self, book_id, *, action, effective_at, known_at) -> str:
        payload = asdict(action)
        version = sha256(_encode(payload).encode()).hexdigest()
        return self._record(
            book_id, f"{action.key}:{version}", "COMPANY_ACTION",
            effective_at, known_at, action.source or "company-action", None, payload,
        )

    def record_entitlement_posting(self, book_id, *, action_key, symbol, kind, effective_at, known_at,
                                   source, actual=None, sellable_on=None, broker_available_after=None,
                                   broker_event_id=None) -> str:
        payload = {
            "action_key": action_key, "symbol": symbol, "kind": kind,
            "actual": _shares(actual) if kind == "shares" and actual is not None else _decimal(actual),
            "sellable_on": sellable_on, "broker_available_after": _decimal(broker_available_after),
            "broker_event_id": broker_event_id,
        }
        return self._record(
            book_id, f"{action_key}:{kind}", "ENTITLEMENT_POSTING",
            effective_at, known_at, source, None, payload,
        )

    def correct(self, book_id, *, event_id, target_event_id, replacement, known_at=None,
                source="user-confirmed", reason=None) -> str:
        known_at = _timestamp(known_at or datetime.now(timezone.utc))
        with self._connection(write=True) as db:
            target = db.execute(
                "SELECT * FROM trade_log WHERE book_id = ? AND event_id = ?", (book_id, target_event_id)
            ).fetchone()
            if target is None or target["kind"] != "FILL":
                raise ValueError(f"找不到可更正的成交 {target_event_id}")
            if known_at < target["known_at"]:
                raise ValueError("更正的获知时间不能早于原流水")
            if replacement is not None:
                original = json.loads(target["payload"])
                normalized = _fill_payload(**{**original, **replacement})
                replacement = {key: normalized.get(key) for key in replacement}
            payload = {"target_event_id": target_event_id, "replacement": replacement, "reason": reason}
            return self._append(
                db, book_id, event_id, "CORRECTION", target["effective_at"], known_at,
                source, target["plan_id"], payload,
            )

    def _record(self, book_id, event_id, kind, effective_at, known_at, source, plan_id, payload) -> str:
        effective_at = _timestamp(effective_at)
        known_at = _timestamp(known_at or datetime.now(timezone.utc))
        with self._connection(write=True) as db:
            return self._append(db, book_id, event_id, kind, effective_at, known_at, source, plan_id, payload)

    def _append(self, db, book_id, event_id, kind, effective_at, known_at, source, plan_id, payload) -> str:
        encoded = _encode(payload)
        event = {
            "event_id": event_id, "kind": kind, "effective_at": effective_at, "known_at": known_at,
            "source": source, "plan_id": plan_id, "payload": encoded,
        }
        existing = db.execute(
            "SELECT * FROM trade_log WHERE book_id = ? AND event_id = ?", (book_id, event_id)
        ).fetchone()
        if existing is not None:
            previous_payload = json.loads(existing["payload"])
            if kind == existing["kind"] == "BASELINE":
                previous_payload["simulated"] = _baseline_role(book_id, existing["source"], previous_payload)
                previous_payload["lots"] = [asdict(PositionLot(**lot)) for lot in previous_payload["lots"]]
                if previous_payload.get("receivables"):
                    previous_payload["receivables"] = [
                        asdict(Receivable(**item)) for item in previous_payload["receivables"]
                    ]
            if kind == existing["kind"] == "FILL":
                previous_payload["symbol"] = previous_payload["symbol"].upper()
            if kind == existing["kind"] == "CORRECTION" and (replacement := previous_payload["replacement"]):
                if "symbol" in replacement:
                    replacement["symbol"] = replacement["symbol"].upper()
            if (_encode(previous_payload) != encoded
                    or any(existing[key] != value for key, value in event.items()
                           if key not in {"known_at", "payload"})):
                raise ValueError(f"流水标识 {event_id} 已用于另一条事实，请录入更正")
            return event_id

        facts = db.execute("SELECT * FROM trade_log WHERE book_id = ? ORDER BY effective_at, seq", (book_id,)).fetchall()
        event["seq"] = max((fact["seq"] for fact in facts), default=0) + 1
        facts.append(event)
        facts.sort(key=lambda fact: (fact["effective_at"], fact["seq"]))
        _project(book_id, effective_at, known_at, facts)
        db.execute(
            """INSERT INTO trade_log (book_id, event_id, kind, effective_at, known_at, source, plan_id, payload)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (book_id, event_id, kind, effective_at, known_at, source, plan_id, encoded),
        )
        return event_id

    def trade_log(self, book_id, *, as_of, known_at=None, plan_id=None) -> list[dict]:
        effective_at = _timestamp(as_of)
        known_at = _timestamp(known_at) if known_at is not None else effective_at
        query = "SELECT * FROM trade_log WHERE book_id = ? AND effective_at <= ? AND known_at <= ?"
        params = (book_id, effective_at, known_at)
        if plan_id is not None:
            query += " AND plan_id = ?"
            params += (plan_id,)
        with self._connection() as db:
            rows = db.execute(query + " ORDER BY effective_at, seq", params).fetchall()
        return [
            {**dict(row), "payload": json.loads(row["payload"])}
            for row in rows
        ]

    def effective_fills(self, book_id, *, as_of, known_at=None, plan_id=None):
        """Return fill facts with the same visible corrections used for account snapshots."""
        facts = [event for event in self.trade_log(book_id, as_of=as_of, known_at=known_at, plan_id=plan_id)
                 if event["kind"] in {"FILL", "CORRECTION"}]
        effective = _effective_payloads(facts)
        return [{**event, "payload": effective[event["event_id"]]} for event in facts
                if event["kind"] == "FILL" and effective[event["event_id"]] is not None]

    def set_risk_budget(self, book_id, *, budget_id, effective_at, cash_reserve, max_total_exposure,
                        max_symbol_exposure, max_industry_exposure, known_at=None, expires_at=None,
                        funds_needed_at=None, pause_conditions=()) -> str:
        budget = RiskBudget(
            budget_id, effective_at, known_at or datetime.now(timezone.utc), cash_reserve,
            max_total_exposure, max_symbol_exposure, max_industry_exposure,
            expires_at, funds_needed_at, pause_conditions,
        )
        limits = (budget.max_total_exposure, budget.max_symbol_exposure, budget.max_industry_exposure)
        if budget.cash_reserve < 0 or any(not 0 <= limit <= 1 for limit in limits):
            raise ValueError("现金保留额须为非负数，仓位与集中度上限以 0 至 1 的比例填写")
        if budget.expires_at is not None and budget.expires_at <= budget.effective_at:
            raise ValueError("风险预算到期时间须晚于生效时间")
        payload = asdict(budget)
        del payload["known_at"]
        encoded = _encode(payload)
        with self._connection(write=True) as db:
            existing = db.execute(
                "SELECT payload FROM risk_budget WHERE book_id = ? AND budget_id = ?", (book_id, budget_id)
            ).fetchone()
            if existing is None:
                db.execute(
                    """INSERT INTO risk_budget (book_id, budget_id, effective_at, known_at, payload)
                       VALUES (?, ?, ?, ?, ?)""",
                    (book_id, budget_id, budget.effective_at, budget.known_at, encoded),
                )
            elif existing["payload"] != encoded:
                raise ValueError(f"预算标识 {budget_id} 已存在，请用新版本")
        return budget_id

    def snapshot(self, book_id, *, as_of, known_at=None) -> AccountSnapshot:
        effective_at = _timestamp(as_of)
        known_at = _timestamp(known_at) if known_at is not None else effective_at
        with self._connection(write=True) as db:
            facts = db.execute(
                """SELECT * FROM trade_log
                   WHERE book_id = ? AND effective_at <= ? AND known_at <= ?
                   ORDER BY effective_at, seq""",
                (book_id, effective_at, known_at),
            ).fetchall()
            snapshot = _project(book_id, effective_at, known_at, facts)
            row = db.execute(
                """SELECT known_at, payload FROM risk_budget WHERE book_id = ? AND effective_at <= ? AND known_at <= ?
                   ORDER BY effective_at DESC, known_at DESC, seq DESC LIMIT 1""",
                (book_id, effective_at, known_at),
            ).fetchone()
            if row is not None:
                budget = RiskBudget(known_at=row["known_at"], **json.loads(row["payload"]))
                if budget.expires_at is None or effective_at < budget.expires_at:
                    snapshot = replace(snapshot, risk_budget=budget)
            payload = asdict(snapshot)
            del payload["snapshot_id"]
            if not snapshot.receivables:
                del payload["receivables"]
            encoded = _encode(payload)
            snapshot_id = sha256(encoded.encode()).hexdigest()
            db.execute(
                "INSERT OR IGNORE INTO account_snapshot VALUES (?, ?, ?, ?, ?)",
                (snapshot_id, book_id, effective_at, known_at, encoded),
            )
        return replace(snapshot, snapshot_id=snapshot_id)

    def read_snapshot(self, snapshot_id) -> AccountSnapshot:
        with self._connection() as db:
            row = db.execute(
                "SELECT payload FROM account_snapshot WHERE snapshot_id = ?", (snapshot_id,)
            ).fetchone()
        if row is None:
            raise ValueError(f"账户快照 {snapshot_id} 不存在")
        value = json.loads(row["payload"])
        value["cash"] = _decimal(value["cash"])
        value["available_cash"] = _decimal(value["available_cash"])
        value["lots"] = tuple(PositionLot(**lot) for lot in value["lots"])
        value["receivables"] = tuple(Receivable(**item) for item in value.get("receivables", ()))
        if value["risk_budget"] is not None:
            value["risk_budget"] = RiskBudget(**value["risk_budget"])
        return AccountSnapshot(snapshot_id, **value)
