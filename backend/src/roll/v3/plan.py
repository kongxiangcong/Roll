"""Local after-close input freezing and immutable TradingPlan publication."""
from collections import defaultdict
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re
from sqlite3 import Connection

from roll.market.calendar import is_session
from roll.market.rules import next_trading_day
from roll.v3.account import AccountLedger
from roll.v3.commitments import SCHEMA as COMMITMENT_SCHEMA, money, project_reservation
from roll.v3.decision import DecisionData, DecisionRules, SecurityInput, decide, uncommitted_cash
from roll.v3.industry_sources import STOCK
from roll.v3.market import LIVE_RUN, freeze_snapshot, get_snapshot, read_research_features, read_snapshot, utc_timestamp
from roll.v3.market_research import DEFAULT_BENCHMARK
from roll.v3.research import ResearchDossiers
from roll.v3.storage import database, ensure_schema, instant, json_text, session_time, sessions
from roll.v3.strategy import StrategyRegistry, signal_at


_SCHEMA = """
CREATE TABLE IF NOT EXISTS plan_revision (
    plan_id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    session TEXT NOT NULL,
    revision INTEGER NOT NULL,
    as_of TEXT NOT NULL,
    published_at TEXT NOT NULL,
    valid_until TEXT NOT NULL,
    replaces_plan_id TEXT REFERENCES plan_revision(plan_id),
    input_hash TEXT NOT NULL,
    payload TEXT NOT NULL,
    UNIQUE (book_id, symbol, session, revision)
);
CREATE TABLE IF NOT EXISTS active_plan (
    book_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    session TEXT NOT NULL,
    plan_id TEXT NOT NULL REFERENCES plan_revision(plan_id),
    PRIMARY KEY (book_id, symbol, session)
);
CREATE TABLE IF NOT EXISTS plan_reservation (
    plan_id TEXT PRIMARY KEY REFERENCES plan_revision(plan_id),
    max_amount TEXT NOT NULL,
    order_quantity INTEGER NOT NULL,
    expires_at TEXT NOT NULL
);
""" + COMMITMENT_SCHEMA


class PlanLedger:
    """Publish together with the caller's same-account/session records when a DB is supplied."""

    def __init__(self, data_dir, *, db: Connection | None = None):
        self.data_dir = data_dir
        self.db = db

    def read(self, plan_id):
        """Read a revision by ID, including replaced or expired plans."""
        with database(self.data_dir, db=self.db) as db:
            ensure_schema(db, _SCHEMA)
            row = db.execute("SELECT payload FROM plan_revision WHERE plan_id = ?", (plan_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def active(self, book_id, session=None):
        """Read the current revisions, scoped to a trading session when specified."""
        with database(self.data_dir, db=self.db) as db:
            ensure_schema(db, _SCHEMA)
            rows = db.execute(
                """SELECT r.payload FROM active_plan a JOIN plan_revision r ON a.plan_id = r.plan_id
                   WHERE a.book_id = ? AND (? IS NULL OR a.session = ?) ORDER BY a.session, a.symbol""",
                (book_id, session, session),
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def revisions(self, book_id, session, *, as_of):
        """Read revisions from a session that had been published by the observation time."""
        cutoff = utc_timestamp(as_of)
        with database(self.data_dir, db=self.db) as db:
            ensure_schema(db, _SCHEMA)
            rows = db.execute(
                """SELECT payload FROM plan_revision
                   WHERE book_id = ? AND session = ? AND as_of <= ? AND published_at <= ?
                   ORDER BY symbol, revision""", (book_id, session, cutoff, cutoff),
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def reservations(self, book_id, *, as_of, known_at=None, replacing_session=None, replacing_symbols=None):
        """Read commitments visible to the next account-wide decision."""
        balances = self._reservation_balances(book_id, as_of, known_at, replacing_session, replacing_symbols)
        return tuple(reservation for _, reservation in balances if reservation.remaining or reservation.quantity)

    def _reservation_balances(self, book_id, as_of, known_at, replacing_session=None, replacing_symbols=None,
                              plan_id=None):
        as_of = utc_timestamp(as_of)
        known_at = utc_timestamp(known_at) if known_at is not None else as_of
        with database(self.data_dir, db=self.db) as db:
            ensure_schema(db, _SCHEMA)
            rows = db.execute(
                """WITH visible_plans AS (
                       SELECT *, ROW_NUMBER() OVER (
                           PARTITION BY symbol, session ORDER BY revision DESC
                       ) AS latest FROM plan_revision
                       WHERE book_id = ? AND as_of <= ? AND published_at <= ?
                   )
                   SELECT v.plan_id, v.symbol, v.session, v.latest, json_extract(v.payload, '$.action') AS side,
                          COALESCE(r.max_amount, '0') AS max_amount,
                          COALESCE(r.order_quantity, json_extract(v.payload, '$.quantity')) AS order_quantity,
                          COALESCE(r.expires_at, v.valid_until) AS expires_at
                   FROM visible_plans v LEFT JOIN plan_reservation r ON v.plan_id = r.plan_id
                   WHERE side IN ('BUY', 'SELL') AND (v.plan_id = ? OR (
                       v.latest = 1 AND COALESCE(r.expires_at, v.valid_until) > ?
                   ) OR EXISTS (
                       SELECT 1 FROM commitment_event c
                       WHERE c.plan_id = v.plan_id AND c.effective_at <= ? AND c.known_at <= ?
                   )) ORDER BY v.session, v.symbol, v.revision""",
                (book_id, as_of, known_at, plan_id, as_of, as_of, known_at),
            ).fetchall()
            if not rows:
                return []
            events = defaultdict(list)
            for event in db.execute(
                """SELECT * FROM commitment_event WHERE book_id = ? AND effective_at <= ? AND known_at <= ?
                   ORDER BY effective_at, known_at, seq""", (book_id, as_of, known_at),
            ):
                events[event["plan_id"]].append(event)
            fills = defaultdict(list)
            for fill in AccountLedger(self.data_dir, db=db).effective_fills(book_id, as_of=as_of, known_at=known_at):
                fills[fill["plan_id"]].append(fill)
        return [project_reservation(row, events[row["plan_id"]], fills[row["plan_id"]], as_of=as_of,
                                    replacing_session=replacing_session, replacing_symbols=replacing_symbols)
                for row in rows]

    def commitment_summary(self, book_id, *, as_of=None, known_at=None, plan_id=None):
        """Read current commitments and their impact on the broker's available cash."""
        as_of = utc_timestamp(as_of)
        with database(self.data_dir, write=True, db=self.db) as db:
            account = AccountLedger(self.data_dir, db=db).snapshot(book_id, as_of=as_of, known_at=known_at)
            balances = PlanLedger(self.data_dir, db=db)._reservation_balances(book_id, as_of, known_at, plan_id=plan_id)
        remaining = sum((reservation.remaining for _, reservation in balances), Decimal(0))
        broker_offset = sum((reservation.broker_offset for _, reservation in balances), Decimal(0))
        budget = account.risk_budget
        net = remaining - broker_offset
        return {"book_id": book_id, "as_of": as_of, "known_at": account.known_at,
                "account_snapshot_id": account.snapshot_id, "cash": money(account.cash),
                "broker_available_cash": money(account.available_cash),
                "cash_reserve": money(budget.cash_reserve) if budget else None,
                "remaining_commitment": money(remaining), "broker_frozen_offset": money(broker_offset),
                "net_commitment": money(net), "cash_available_to_allocate": money(uncommitted_cash(account, budget, net)),
                "plans": [details for details, reservation in balances if details["plan_id"] == plan_id
                          or (plan_id is None and (reservation.remaining or reservation.quantity))]}

    def record_condition(self, book_id, *, plan_id, event_id, status, effective_at, expires_at=None,
                         description=None, known_at=None):
        """Register or revoke the user's cross-day execution condition."""
        effective_at = utc_timestamp(effective_at)
        expires_at = utc_timestamp(expires_at) if expires_at is not None else None
        if status not in {"active", "revoked"} or (status == "active" and not (expires_at and expires_at > effective_at)):
            raise ValueError("跨日条件状态须为 active 或 revoked，生效条件须指定晚于生效时间的有效期")
        return self._record_commitment(
            book_id, plan_id, event_id, "condition", plan_id, status, effective_at, known_at,
            {"expires_at": expires_at, "description": description},
        )

    def record_order(self, book_id, *, plan_id, order_id, event_id, status, effective_at,
                     known_at=None, max_amount=None, order_quantity=None, broker_frozen=None,
                     broker_available_cash=None):
        """Register a user-confirmed external order or a subsequent broker result."""
        if not order_id or status not in {"pending", "cancelled", "expired", "filled"}:
            raise ValueError("委托须包含券商委托标识，状态须为 pending、cancelled、expired 或 filled")
        if order_quantity is not None and (type(order_quantity) is not int or order_quantity <= 0):
            raise ValueError("委托股数须为正整数")
        amounts = {key: _nonnegative(value) for key, value in {
            "max_amount": max_amount, "broker_frozen": broker_frozen,
            "broker_available_cash": broker_available_cash,
        }.items()}
        return self._record_commitment(
            book_id, plan_id, event_id, "order", order_id, status, utc_timestamp(effective_at), known_at,
            {"order_quantity": order_quantity, **amounts},
        )

    def _record_commitment(self, book_id, plan_id, event_id, kind, reference, status, effective_at, known_at, payload):
        known_at = utc_timestamp(known_at)
        encoded = json_text(payload)
        with database(self.data_dir, write=True, db=self.db) as db:
            ensure_schema(db, _SCHEMA)
            plan = db.execute("SELECT payload FROM plan_revision WHERE book_id = ? AND plan_id = ?",
                              (book_id, plan_id)).fetchone()
            if plan is None or json.loads(plan["payload"])["action"] not in {"BUY", "SELL"}:
                raise ValueError(f"找不到账本 {book_id} 可登记承诺的交易计划 {plan_id}")
            state = (plan_id, kind, reference, status, effective_at, encoded)
            previous = db.execute(
                """SELECT plan_id, kind, reference_id, status, effective_at, payload FROM commitment_event
                   WHERE book_id = ? AND event_id = ?""", (book_id, event_id),
            ).fetchone()
            if previous is not None:
                if tuple(previous) != state:
                    raise ValueError(f"承诺事件标识 {event_id} 已用于另一条事实，请使用新标识")
                return event_id
            if kind == "order" and db.execute(
                """SELECT 1 FROM commitment_event
                   WHERE book_id = ? AND kind = 'order' AND reference_id = ? AND plan_id <> ? LIMIT 1""",
                (book_id, reference, plan_id),
            ).fetchone() is not None:
                raise ValueError(f"券商委托 {reference} 已关联其他计划版本")
            db.execute(
                """INSERT INTO commitment_event (book_id, event_id, plan_id, kind, reference_id, status,
                                                 effective_at, payload, known_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (book_id, event_id, *state, known_at),
            )
            if payload.get("broker_available_cash") is not None:
                AccountLedger(self.data_dir, db=db).record_cash(
                    book_id, event_id=f"order:{event_id}", delta=0, effective_at=effective_at, known_at=known_at,
                    broker_available_after=payload["broker_available_cash"], plan_id=plan_id,
                    reason=f"券商委托 {reference} 回报的可用现金", source="broker",
                )
        return event_id

    def publish(self, plans, *, published_at=None):
        """Atomically save revisions, replace current pointers and register maximum cash commitments."""
        plans = tuple(plans)
        identity = {(plan.book_id, plan.session, plan.as_of, plan.simulated) for plan in plans}
        if len(identity) > 1 or len({plan.symbol for plan in plans}) != len(plans):
            raise ValueError("一次计划发布须使用同一账户、裁决时点与交易时段，每个标的仅一份")
        published_at = utc_timestamp(published_at)
        with database(self.data_dir, write=True, db=self.db) as db:
            ensure_schema(db, _SCHEMA)
            if plans:
                AccountLedger(self.data_dir, db=db).require_role(plans[0].book_id, simulated=plans[0].simulated)
            return [self._publish(db, plan, published_at) for plan in plans]

    def _publish(self, db, plan, published_at):
        payload = plan.as_dict()
        input_hash = sha256(json_text(payload).encode()).hexdigest()
        key = (plan.book_id, plan.symbol, plan.session)
        current = db.execute(
            """SELECT r.* FROM active_plan a JOIN plan_revision r ON a.plan_id = r.plan_id
               WHERE a.book_id = ? AND a.symbol = ? AND a.session = ?""", key,
        ).fetchone()
        if current and current["input_hash"] == input_hash:
            return json.loads(current["payload"])
        if current and (current["as_of"] > plan.as_of or current["published_at"] > published_at):
            raise ValueError(f"{plan.symbol} 已有更新的计划裁决，请使用预览读取历史输入")

        replaces = current["plan_id"] if current else None
        revision = current["revision"] + 1 if current else 1
        plan_id = sha256(json_text((input_hash, replaces)).encode()).hexdigest()
        stored = {
            **payload, "plan_id": plan_id, "revision": revision, "replaces_plan_id": replaces,
            "published_at": published_at,
        }
        db.execute(
            """INSERT INTO plan_revision (plan_id, book_id, symbol, session, revision, as_of, published_at,
                                         valid_until, replaces_plan_id, input_hash, payload)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (plan_id, *key, revision, plan.as_of, published_at, plan.valid_until, replaces, input_hash,
             json_text(stored)),
        )
        db.execute(
            """INSERT INTO active_plan (book_id, symbol, session, plan_id) VALUES (?, ?, ?, ?)
               ON CONFLICT (book_id, symbol, session) DO UPDATE SET plan_id = excluded.plan_id""",
            (*key, plan_id),
        )
        if plan.action in {"BUY", "SELL"}:
            db.execute(
                """INSERT INTO plan_reservation (plan_id, max_amount, order_quantity, expires_at)
                   VALUES (?, ?, ?, ?)""",
                (plan_id, str(plan.cash_reserved), plan.quantity, plan.valid_until),
            )
        return stored


def _nonnegative(value):
    if value is None:
        return None
    try:
        amount = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError("委托金额、冻结金额及可用现金须为非负金额") from error
    if not amount.is_finite() or amount < 0:
        raise ValueError("委托金额、冻结金额及可用现金须为非负金额")
    return money(amount)


def _scope(symbols, benchmark, start, day):
    return [
        dict(series=series, symbol=symbol, start=first, end=day)
        for symbol in symbols
        for series, first in (("daily_bar", start), ("adjustment_factor", start),
                              ("industry_membership", "1900-01-01"))
    ] + [dict(series="daily_bar", symbol=benchmark, start=start, end=day)]


def _industry(data_dir, snapshot_id, symbol, day, cutoff, db):
    rows = read_snapshot(data_dir, snapshot_id, symbol=symbol, series="industry_membership", end=day,
                         cutoff=cutoff, db=db)["observations"]
    covering = []
    for row in rows:
        membership = row["payload"]
        start, end = membership.get("effective_start"), membership.get("effective_end")
        if start and end and start <= day <= end and membership.get("index_symbol"):
            covering.append(membership["index_symbol"])
    indices = set(covering)
    return next(iter(indices)) if len(indices) == 1 else None


def _freeze_market(data_dir, symbols, start, day, cutoff, db, *, market_mode, market_as_of, dossiers):
    scope = _scope(symbols, DEFAULT_BENCHMARK, start, day)
    scope.extend(
        dict(series="research_feature", symbol=symbol, start="1900-01-01", end=day)
        for symbol, dossier in dossiers.items() if dossier and dossier.get("invalidation_triggers")
    )
    initial = freeze_snapshot(data_dir, as_of=market_as_of, use_mode=market_mode, scope=scope, db=db)
    industries = {_industry(data_dir, initial["snapshot_id"], symbol, day, cutoff, db) for symbol in symbols}
    if industries - {None}:
        scope.extend(dict(series="daily_bar", symbol=code, start=start, end=day)
                     for code in sorted(industries - {None}))
        return freeze_snapshot(data_dir, as_of=market_as_of, use_mode=market_mode, scope=scope, db=db)
    return initial


def _observed_price(value):
    if value is None:
        return None
    try:
        number = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation):
        return None
    return number if number.is_finite() and number > 0 else None


def _daily_status(rows, dates):
    bars = {row["trade_date"]: row["payload"] for row in rows}
    prices = [_observed_price(bars.get(day, {}).get("close")) for day in dates]
    if len(prices) < 21 or any(price is None for price in prices):
        return "unknown"
    change = prices[-1] / prices[0] - 1
    if change > Decimal("0.03"):
        return "uptrend"
    if change < Decimal("-0.03"):
        return "downtrend"
    return "range"


def _load_inputs(data_dir, snapshot, symbols, registry, day, session, cutoff, rules, db):
    snapshot_id = snapshot["snapshot_id"]
    begin = max(date.fromisoformat(day) - timedelta(days=40), date(2013, 1, 1)).isoformat()
    regime_dates = list(sessions(begin, day))[-21:]
    industries = {symbol: _industry(data_dir, snapshot_id, symbol, day, cutoff, db) for symbol in symbols}
    scope = set(symbols) | ({DEFAULT_BENCHMARK} | set(industries.values())) - {None}
    observations = {
        symbol: read_snapshot(data_dir, snapshot_id, symbol=symbol, start=begin, end=day,
                              cutoff=cutoff, db=db)
        for symbol in scope
    }
    states = {symbol: _daily_status(out["observations"], regime_dates) for symbol, out in observations.items()}
    securities = {}
    for symbol in symbols:
        out = observations[symbol]
        rows = out["observations"]
        bar = next((row["payload"] for row in rows if row["trade_date"] == day), {})
        close = _observed_price(bar.get("close"))
        # Use the last visible mark when today's quote is unavailable, retaining unknown tradeability.
        mark = close or next((_observed_price(row["payload"].get("close")) for row in reversed(rows)
                              if _observed_price(row["payload"].get("close")) is not None), None)
        industry = industries[symbol]
        signals = {
            version: signal_at(data_dir, version, snapshot_id, symbol=symbol, as_of=cutoff, db=db)
            for entry in registry[symbol] if (version := entry["strategy"]["version"]) and (
                entry["production_eligible"] or (
                    rules.simulated and version in rules.strategy_versions and entry["simulation_eligible"]
                )
            )
        }
        market_state = states[DEFAULT_BENCHMARK]
        industry_state, stock_state = states.get(industry, "unknown"), states[symbol]
        trading_status = bar.get("trading_status", "unknown")
        if trading_status == "trading" and close is None:
            trading_status = "unknown"
        research_facts = read_research_features(data_dir, snapshot_id, symbol=symbol, cutoff=cutoff, db=db)
        market_features = dict(close=close, market_state=market_state, industry_state=industry_state,
                               stock_state=stock_state, suspended=trading_status == "suspended",
                               trading_status_unknown=trading_status == "unknown", close_unavailable=close is None,
                               volume=bar.get("volume"), amount=bar.get("amount"),
                               turnover_rate=bar.get("turnover_rate"))
        features = {**{name: row["payload"].get("value") for name, row in research_facts.items()}, **market_features}
        security = SecurityInput(
            close=mark, trading_status=trading_status, industry=industry,
            industry_state=industry_state, stock_state=stock_state, signals=signals,
            upper_limit=_observed_price(bar.get("upper_limit")), lower_limit=_observed_price(bar.get("lower_limit")),
            features=features,
            feature_observations={
                name: {**{field: row[field] for field in ("seq", "trade_date", "source", "source_ref",
                                                         "selected_available_at")}, "value": features[name]}
                for name, row in research_facts.items() if name not in market_features
            },
        )
        securities[symbol] = security
    return DecisionData(cutoff, session, snapshot_id, securities, states[DEFAULT_BENCHMARK])


def generate_plans(data_dir, *, book_id="real", as_of=None, symbols=(), snapshot_id=None, simulated=False,
                   strategy_versions=(), publish=True, db=None, allow_price_only=False, published_at=None,
                   rules=None, market_mode=LIVE_RUN, market_as_of=None):
    """Freeze and publish the next-session account plan; a caller can join it to an outer transaction."""
    cutoff = instant(as_of)
    day = cutoff.date()
    if not is_session(day) or cutoff < session_time(day, 15):
        raise ValueError("计划须在交易日收盘后生成，请指定对应的盘后裁决时间")
    session = next_trading_day(day).isoformat()
    inputs = rules or DecisionRules(simulated, tuple(strategy_versions), allow_price_only=allow_price_only)
    if not inputs.simulated and market_mode != LIVE_RUN:
        raise ValueError("真实账户计划须使用保留实际取得时间的 LIVE_RUN 数据快照")
    with database(data_dir, write=True, db=db) as connection:
        accounts = AccountLedger(data_dir, db=connection)
        if publish:
            accounts.require_role(book_id, simulated=inputs.simulated)
        account = accounts.snapshot(book_id, as_of=cutoff)
        selected = sorted({symbol.upper() for symbol in symbols or (STOCK,)}
                          | {lot.symbol for lot in account.lots}
                          | {receivable.symbol for receivable in account.receivables})
        if any(not re.fullmatch(r"[0-9]{6}\.(SH|SZ|BJ)", symbol) for symbol in selected):
            raise ValueError("证券代码须包含交易所后缀，例如 600362.SH")
        research = ResearchDossiers(data_dir)
        strategies = StrategyRegistry(data_dir)
        dossiers = {symbol: research.effective_version(symbol, cutoff, db=connection) for symbol in selected}
        registry = {symbol: strategies.for_symbol(symbol, cutoff, include_ineligible=True, db=connection)
                    for symbol in selected}
        if snapshot_id:
            snapshot = get_snapshot(data_dir, snapshot_id, db=connection)
            if not inputs.simulated and snapshot["use_mode"] != LIVE_RUN:
                raise ValueError("真实账户计划须使用保留实际取得时间的 LIVE_RUN 数据快照")
        else:
            slowest = max((entry["strategy"]["parameters"]["slow"] for entries in registry.values()
                           for entry in entries), default=60)
            start = max(day - timedelta(days=max(120, slowest * 3)), date(2013, 1, 1)).isoformat()
            snapshot = _freeze_market(
                data_dir, selected, start, day.isoformat(), cutoff, connection,
                market_mode=market_mode, market_as_of=market_as_of or cutoff, dossiers=dossiers,
            )
        data = _load_inputs(data_dir, snapshot, selected, registry, day.isoformat(), session, cutoff, inputs, connection)
        ledger = PlanLedger(data_dir, db=connection)
        reservations = ledger.reservations(book_id, as_of=cutoff, replacing_session=session, replacing_symbols=selected)
        inputs = replace(inputs, reservations=(*reservations, *inputs.reservations))
        plans = decide(data, account, account.risk_budget, dossiers, registry, inputs)
        return {
            "book_id": book_id, "as_of": data.as_of, "session": session, "snapshot_id": data.snapshot_id,
            "account_snapshot_id": account.snapshot_id,
            "plans": ledger.publish(plans, published_at=published_at) if publish else [plan.as_dict() for plan in plans],
        }
