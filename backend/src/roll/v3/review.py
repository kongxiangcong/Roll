"""Decision ledger for forward registration, shadow execution and actual outcomes."""
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from hashlib import sha256
import json

from roll.market.calendar import is_session
from roll.v3.account import AccountLedger
from roll.v3.decision import execution_intent
from roll.v3.entitlements import SIMULATION_BASIS, read_company_actions, settle_entitlements, value_account
from roll.v3.execution import EXECUTION_RULES_VERSION, ExecutionRules, OpeningQuote, execute
from roll.v3.industry_sources import STOCK
from roll.v3.market import LIVE_RUN, RECONSTRUCTED_RESEARCH, freeze_snapshot, read_snapshot, utc_timestamp
from roll.v3.plan import generate_plans
from roll.v3.storage import database, ensure_schema, instant, json_text, session_time
from roll.v3.strategy import StrategyRegistry


MODES = ("live", "rehearsal", "reconstructed")
FINDING_CATEGORIES = (
    "research_hypothesis", "strategy_applicability", "data_quality",
    "execution_deviation", "user_deviation", "normal_variation",
)
OUTCOMES = ("confirmed", "rejected", "not_executed", "filled")
_SCHEMA = """
CREATE TABLE IF NOT EXISTS forward_registration (
    registration_id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    decision_date TEXT NOT NULL,
    registered_at TEXT NOT NULL,
    payload TEXT NOT NULL,
    UNIQUE (book_id, mode, decision_date)
);
CREATE TABLE IF NOT EXISTS shadow_settlement (
    registration_id TEXT NOT NULL REFERENCES forward_registration(registration_id),
    stage TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (registration_id, stage)
);
CREATE TABLE IF NOT EXISTS forward_event (
    seq INTEGER PRIMARY KEY,
    registration_id TEXT NOT NULL REFERENCES forward_registration(registration_id),
    event_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    symbol TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    payload TEXT NOT NULL,
    UNIQUE (registration_id, event_id)
);
"""


def _identity(*fields):
    return sha256(json_text(fields).encode()).hexdigest()


def _clock(mode, now):
    if mode not in MODES:
        raise ValueError(f"未知登记模式 {mode}")
    if mode == "live" and now is not None:
        raise ValueError("真实前向登记须使用当前系统时间，固定时钟请使用演练模式")
    return instant(now)


def _clone(ledger, book_id, account, cutoff):
    ledger.initialize(
        book_id, cash=account.cash, available_cash=account.available_cash, lots=account.lots,
        receivables=account.receivables, effective_at=cutoff, known_at=cutoff, source="forward-baseline",
    )
    if account.risk_budget:
        budget = asdict(account.risk_budget)
        budget.update(effective_at=cutoff, known_at=cutoff)
        ledger.set_risk_budget(book_id, **budget)


def _symbols(account):
    return {lot.symbol for lot in account.lots} | {item.symbol for item in account.receivables}


class DecisionLedger:
    """Read original decisions and append receipts as each execution phase becomes known."""

    def __init__(self, data_dir):
        self.data_dir = data_dir

    def register(self, *, book_id="real", as_of=None, symbols=(), strategy_versions=(), mode="live",
                 price_only=False, snapshot_id=None, now=None):
        clock = _clock(mode, now)
        cutoff = instant(as_of) if as_of is not None else clock
        day = cutoff.date()
        if book_id.startswith("review:"):
            raise ValueError("请使用原始账户登记复盘")
        if not is_session(day) or not session_time(day, 15) <= cutoff <= clock:
            raise ValueError("请使用交易日收盘后、当前时点以前的裁决时间")
        if mode in {"live", "rehearsal"} and clock.date() != day:
            raise ValueError("已过登记日，请使用 reconstructed 模式重建")
        if mode == "reconstructed" and day >= clock.date():
            raise ValueError("历史重建需要已过去的交易日")

        today = day.isoformat()
        registration_id = _identity(book_id, mode, today)
        partition = _identity(book_id, mode, today if mode == "reconstructed" else None)
        shadow_book = f"review:shadow:{partition}"
        actual_book = f"review:rehearsal:{partition}" if mode == "rehearsal" else book_id
        with database(self.data_dir, write=True) as db:
            ensure_schema(db, _SCHEMA)
            cached = self._registration(db, registration_id)
            if cached is not None:
                return self._view(db, cached, clock)

            previous = self._registered(db, book_id, mode=mode)
            if mode == "reconstructed":
                previous = []
            if previous and previous[-1]["decision_date"] >= today:
                raise ValueError("连续账本只能按交易日向前登记")
            for record in previous:
                self._settle_record(db, record, cutoff, clock)

            ledger = AccountLedger(self.data_dir, db=db)
            registry = StrategyRegistry(self.data_dir)
            selected = {symbol.upper() for symbol in symbols or (STOCK,)}
            versions = sorted(set(strategy_versions))
            for version in versions:
                strategy = registry.get(version, cutoff, db=db)
                if strategy is None:
                    raise ValueError(f"裁决时点没有已冻结策略 {version}")
                selected.update(strategy["strategy"]["scope"]["symbols"])

            if not previous:
                baseline = ledger.snapshot(book_id, as_of=cutoff)
                _clone(ledger, shadow_book, baseline, cutoff)
                if actual_book != book_id:
                    _clone(ledger, actual_book, baseline, cutoff)
                anchor = baseline.snapshot_id
            else:
                anchor = previous[0]["baseline_account_snapshot_id"]

            # Settle known actions through the decision cutoff between registrations,
            # including dates with no registered intent.
            books = [(actual_book, False), (shadow_book, True)]
            accounts = [ledger.snapshot(book, as_of=cutoff) for book, _ in books]
            for account in accounts:
                selected.update(_symbols(account))
            for (book, simulated), account in zip(books, accounts):
                if book == book_id and mode == "reconstructed":
                    continue
                self._settle_actions(db, book, account, selected, cutoff, LIVE_RUN, simulated=simulated)

            real = generate_plans(
                self.data_dir, book_id=actual_book, as_of=cutoff, symbols=selected,
                db=db, publish=mode != "reconstructed", published_at=clock,
                snapshot_id=snapshot_id if mode != "reconstructed" else None,
            )
            shadow = generate_plans(
                self.data_dir, book_id=shadow_book, as_of=cutoff, symbols=selected,
                snapshot_id=snapshot_id if mode == "reconstructed" else real["snapshot_id"],
                simulated=True, strategy_versions=versions, allow_price_only=price_only,
                db=db, published_at=clock,
            )
            real_plans = {plan["symbol"]: plan for plan in real["plans"]}
            if mode == "reconstructed":
                for plan in real_plans.values():
                    plan.update(plan_id=_identity(registration_id, plan), revision=None, published_at=None)
            plans = [
                {"symbol": plan["symbol"], "real_plan": real_plans[plan["symbol"]], "shadow_plan": plan}
                for plan in shadow["plans"]
            ]
            record = {
                "registration_id": registration_id, "book_id": book_id, "mode": mode,
                "decision_date": today, "decision_at": real["as_of"], "session": real["session"],
                "registered_at": utc_timestamp(clock), "shadow_book_id": shadow_book, "actual_book_id": actual_book,
                "strategy_versions": versions, "baseline_account_snapshot_id": anchor,
                "shadow_accounting_basis": SIMULATION_BASIS, "plans": plans,
            }
            db.execute(
                "INSERT INTO forward_registration VALUES (?, ?, ?, ?, ?, ?)",
                (registration_id, book_id, mode, today, record["registered_at"], json_text(record)),
            )
            for plan in plans:
                self._record_trigger_findings(db, record, plan, clock)
            return self._view(db, record, clock)

    def read(self, registration_id, *, as_of=None):
        with database(self.data_dir) as db:
            ensure_schema(db, _SCHEMA)
            return self._view(db, self._require_registration(db, registration_id), instant(as_of))

    def registrations(self, *, book_id="real", start=None, end=None, as_of=None, mode=None):
        """Read committed registrations known at the requested observation time."""
        start = date.fromisoformat(start).isoformat() if start else None
        end = date.fromisoformat(end).isoformat() if end else None
        if start and end and start > end:
            raise ValueError("开始日期须早于或等于结束日期")
        if mode is not None and mode not in MODES:
            raise ValueError(f"未知登记模式 {mode}")
        clock = instant(as_of)
        with database(self.data_dir) as db:
            ensure_schema(db, _SCHEMA)
            records = self._registered(db, book_id, start=start, end=end, as_of=clock, mode=mode)
            return [self._view(db, record, clock) for record in records]

    def settle(self, registration_id, *, now=None):
        with database(self.data_dir, write=True) as db:
            ensure_schema(db, _SCHEMA)
            record = self._require_registration(db, registration_id)
            clock = _clock(record["mode"], now)
            if clock < instant(record["registered_at"]):
                raise ValueError("结算时点早于登记时间")
            earlier = self._registered(db, record["book_id"], end=record["decision_date"], mode=record["mode"])
            if record["mode"] == "reconstructed":
                earlier = [record]
            for prior in earlier:
                self._settle_record(db, prior, clock, clock)
            return self._view(db, record, clock)

    def _settle_actions(self, db, book_id, account, symbols, cutoff, mode, *, simulated):
        ledger = AccountLedger(self.data_dir, db=db)
        baseline = ledger.trade_log(book_id, as_of=cutoff)[0]
        first = instant(baseline["effective_at"]).date().isoformat()
        last = cutoff.date().isoformat()
        scope = [{"series": "corporate_action", "symbol": symbol, "start": first, "end": last}
                 for symbol in symbols]
        snapshot = freeze_snapshot(self.data_dir, as_of=cutoff, use_mode=mode, scope=scope, db=db)
        actions = read_company_actions(self.data_dir, snapshot["snapshot_id"], db=db)
        settled = settle_entitlements(
            self.data_dir, book_id, actions, as_of=cutoff, simulated=simulated, db=db,
        )
        return settled, snapshot["snapshot_id"]

    def _settle_record(self, db, record, through, clock):
        session = record["session"]
        opening = session_time(session, 9, 30)
        closing = session_time(session, 15, 5)
        if through < opening:
            return
        ledger = AccountLedger(self.data_dir, db=db)
        book = record["shadow_book_id"]
        symbols = [plan["symbol"] for plan in record["plans"]]
        use_mode = LIVE_RUN if record["mode"] == "live" else RECONSTRUCTED_RESEARCH
        if self._receipt(db, record, "open") is None:
            account = ledger.snapshot(book, as_of=opening)
            account, entitlement_id = self._settle_actions(
                db, book, account, symbols, opening, use_mode, simulated=True,
            )
            opening_scope = [{"series": "daily_open", "symbol": symbol, "start": session, "end": session}
                             for symbol in symbols]
            frozen = freeze_snapshot(self.data_dir, as_of=clock, use_mode=use_mode, scope=opening_scope, db=db)
            openings = {
                row["symbol"]: row for row in read_snapshot(
                    self.data_dir, frozen["snapshot_id"], series="daily_open", cutoff=opening, db=db,
                )["observations"] if not row["item_id"]
            }
            results = {}
            for entry in record["plans"]:
                plan = entry["shadow_plan"]
                symbol = plan["symbol"]
                intent = execution_intent(plan)
                before = account.snapshot_id
                if intent is None:
                    result = {"status": "OBSERVED", "reason": plan["action"], "fill": None,
                              "opening": None, "intent": None}
                else:
                    if plan["execution_rules_version"] != EXECUTION_RULES_VERSION:
                        raise ValueError("当前执行核不支持该计划冻结的规则版本")
                    evidence = openings.get(symbol)
                    quote = OpeningQuote.from_payload(
                        symbol, session, evidence["payload"], observation_seq=evidence["seq"],
                    ) if evidence else None
                    execution = execute(intent, quote, account, ExecutionRules(**plan["execution_parameters"]))
                    result = execution.as_dict()
                    if execution.fill:
                        ledger.record_fill(
                            book, **execution.fill.ledger_fields(), known_at=opening,
                            plan_id=plan["plan_id"], source="forward-shadow",
                        )
                        account = ledger.snapshot(book, as_of=opening)
                results[symbol] = {
                    **result, "session": session, "recorded_at": utc_timestamp(clock),
                    "opening_snapshot_id": frozen["snapshot_id"], "entitlement_snapshot_id": entitlement_id,
                    "before_account_snapshot_id": before, "account": account.as_dict(),
                    "after_account_snapshot_id": account.snapshot_id,
                }
            self._save_receipt(db, record, "open", clock, results)
        if through >= closing and self._receipt(db, record, "close") is None:
            account = ledger.snapshot(book, as_of=closing)
            account, entitlement_id = self._settle_actions(
                db, book, account, symbols, closing, use_mode, simulated=True,
            )
            marks = freeze_snapshot(
                self.data_dir, as_of=clock, use_mode=use_mode, db=db,
                scope=[{"series": "daily_bar", "symbol": symbol, "start": session, "end": session}
                       for symbol in symbols],
            )
            rows = read_snapshot(
                self.data_dir, marks["snapshot_id"], cutoff=closing, db=db,
            )["observations"]
            prices = {row["symbol"]: row["payload"].get("close") for row in rows if not row["item_id"]}
            needed = {lot.symbol for lot in account.lots} | {r.symbol for r in account.receivables if r.quantity}
            missing = sorted(symbol for symbol in needed if prices.get(symbol) is None)
            self._save_receipt(db, record, "close", clock, {
                "account": account.as_dict(), "market_snapshot_id": marks["snapshot_id"],
                "entitlement_snapshot_id": entitlement_id, "missing_marks": missing,
                "valuation": None if missing else value_account(account, prices).as_dict(),
            })

    @staticmethod
    def _save_receipt(db, record, stage, clock, result):
        db.execute(
            "INSERT INTO shadow_settlement VALUES (?, ?, ?, ?)",
            (record["registration_id"], stage, utc_timestamp(clock), json_text(result)),
        )

    @staticmethod
    def _receipt(db, record, stage, as_of=None):
        row = db.execute(
            "SELECT recorded_at, payload FROM shadow_settlement WHERE registration_id = ? AND stage = ?",
            (record["registration_id"], stage),
        ).fetchone()
        if row is None or (as_of is not None and row["recorded_at"] > utc_timestamp(as_of)):
            return None
        return json.loads(row["payload"])

    @staticmethod
    def _registered(db, book_id, *, start=None, end=None, as_of=None, mode=None):
        rows = db.execute(
            """SELECT payload FROM forward_registration WHERE book_id = ?
               AND (? IS NULL OR decision_date >= ?) AND (? IS NULL OR decision_date <= ?)
               AND (? IS NULL OR registered_at <= ?) AND (? IS NULL OR mode = ?)
               ORDER BY decision_date, mode""",
            (book_id, start, start, end, end, utc_timestamp(as_of) if as_of else None,
             utc_timestamp(as_of) if as_of else None, mode, mode),
        )
        return [json.loads(row["payload"]) for row in rows]

    @staticmethod
    def _registration(db, registration_id):
        row = db.execute(
            "SELECT payload FROM forward_registration WHERE registration_id = ?", (registration_id,),
        ).fetchone()
        return json.loads(row["payload"]) if row else None

    def _require_registration(self, db, registration_id):
        record = self._registration(db, registration_id)
        if record is None:
            raise ValueError(f"复盘登记不存在：{registration_id}")
        return record

    def record_outcome(self, registration_id, symbol, status, *, reason=None, fill=None,
                       reported_at=None, event_id=None, now=None):
        if status not in OUTCOMES:
            raise ValueError(f"未知实际结果 {status}")
        if status in {"rejected", "not_executed"} and not (reason and reason.strip()):
            raise ValueError("拒绝或未执行须提供原因")
        if (fill is not None) != (status == "filled"):
            raise ValueError("实际成交须提供经确认的券商成交")
        with database(self.data_dir, write=True) as db:
            ensure_schema(db, _SCHEMA)
            record = self._require_registration(db, registration_id)
            clock = _clock(record["mode"], now)
            if record["mode"] == "reconstructed":
                raise ValueError("历史重建不能登记实际执行，请关联原始前向计划或录入账户流水")
            entry = self._visible_plan(record, symbol, clock)
            plan = entry["real_plan"]
            reported = instant(reported_at) if reported_at else None
            if reported and reported > clock:
                raise ValueError("券商回报时间不能晚于本次获知时间")
            data = {
                "symbol": plan["symbol"], "plan_id": plan["plan_id"], "status": status.upper(),
                "reason": reason, "reported_at": utc_timestamp(reported) if reported else None,
            }
            if fill is not None:
                data.update(self._record_fill(db, record, plan, fill, clock, reported))
                event_id = f"fill:{data['broker_event_id']}"
            else:
                event_id = event_id or _identity("outcome", data)
            self._append_event(db, record, event_id, "outcome", data, clock)
            return self._view(db, record, clock)

    def _record_fill(self, db, record, plan, fill, clock, reported):
        fill = dict(fill)
        required = ("event_id", "effective_at", "side", "quantity", "price")
        if any(key not in fill for key in required) or not str(fill["event_id"]).strip():
            raise ValueError("实际成交须提供券商流水标识、发生时点、买卖方向、股数及成交价格")
        occurred = instant(fill["effective_at"])
        if not instant(plan["as_of"]) <= occurred <= (reported or clock):
            raise ValueError("成交发生时点须在计划裁决之后、回报或获知之前")
        if fill.pop("symbol", plan["symbol"]).upper() != plan["symbol"]:
            raise ValueError("成交证券与冻结计划不一致")
        fill["effective_at"] = utc_timestamp(occurred)
        if {"known_at", "plan_id"} & fill.keys():
            raise ValueError("成交获知时点与关联计划由复盘登记")
        ledger = AccountLedger(self.data_dir, db=db)
        event_id = ledger.record_fill(
            record["actual_book_id"], **fill, symbol=plan["symbol"], known_at=clock, plan_id=plan["plan_id"],
        )
        return {"broker_event_id": event_id, "effective_at": utc_timestamp(occurred)}

    def record_finding(self, registration_id, symbol, *, category, reason, evidence_refs=(), trigger_id=None,
                       now=None):
        if category not in FINDING_CATEGORIES or not (reason and reason.strip()):
            raise ValueError("复盘事项须提供已定义的归因类别与说明")
        refs = sorted({ref.strip() for ref in evidence_refs if ref.strip()})
        if trigger_id and (category != "research_hypothesis" or not refs):
            raise ValueError("证伪须归类为研究假设并附可核对的证据")
        with database(self.data_dir, write=True) as db:
            ensure_schema(db, _SCHEMA)
            record = self._require_registration(db, registration_id)
            clock = _clock(record["mode"], now)
            entry = self._visible_plan(record, symbol, clock)
            self._append_finding(db, record, entry, category, reason, refs, trigger_id, clock)
            return self._view(db, record, clock)

    @staticmethod
    def _visible_plan(record, symbol, clock):
        if clock < instant(record["registered_at"]):
            raise ValueError("该时点尚未登记此复盘")
        entry = next((item for item in record["plans"] if item["symbol"] == symbol.upper()), None)
        if entry is None:
            raise ValueError(f"登记记录没有 {symbol} 的计划")
        return entry

    def _record_trigger_findings(self, db, record, entry, clock):
        plan = entry["real_plan"]
        for trigger in plan["research"].get("triggers", ()):
            if trigger["status"] is True:
                refs = [f"market:{plan['snapshot_id']}", *trigger["evidence_refs"]]
                self._append_finding(
                    db, record, entry, "research_hypothesis", "盘后裁决命中已发布档案的证伪条件",
                    refs, trigger["id"], clock,
                )

    def _append_finding(self, db, record, entry, category, reason, refs, trigger_id, clock):
        plan = entry["real_plan"]
        data = {
            "symbol": entry["symbol"], "plan_id": plan["plan_id"], "category": category,
            "reason": reason, "evidence_refs": refs,
        }
        if trigger_id:
            if trigger_id not in {trigger["id"] for trigger in plan["research"].get("triggers", ())}:
                raise ValueError("证伪条件须来自原计划引用的已发布档案")
            data["research_followup"] = {
                "followup_id": _identity("research", record["registration_id"], plan["plan_id"], trigger_id),
                "symbol": plan["symbol"], "dossier_version": plan["dossier_version"],
                "trigger_id": trigger_id, "plan_id": plan["plan_id"],
                "registration_id": record["registration_id"], "evidence_refs": refs,
            }
        self._append_event(db, record, _identity("finding", data), "finding", data, clock)

    @staticmethod
    def _append_event(db, record, event_id, kind, payload, clock):
        registration_id = record["registration_id"]
        prior = db.execute(
            "SELECT kind, payload FROM forward_event WHERE registration_id = ? AND event_id = ?",
            (registration_id, event_id),
        ).fetchone()
        encoded = json_text(payload)
        if prior:
            if prior["kind"] != kind or prior["payload"] != encoded:
                raise ValueError(f"复盘流水标识 {event_id} 已关联其他事实")
            return
        db.execute(
            """INSERT INTO forward_event (registration_id, event_id, kind, symbol, recorded_at, payload)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (registration_id, event_id, kind, payload["symbol"], utc_timestamp(clock), encoded),
        )

    def _view(self, db, record, clock):
        if clock < instant(record["registered_at"]):
            raise ValueError("该时点尚未登记此复盘")
        rows = db.execute(
            """SELECT * FROM forward_event WHERE registration_id = ? AND recorded_at <= ?
               ORDER BY recorded_at, seq""",
            (record["registration_id"], utc_timestamp(clock)),
        )
        events = [
            {**json.loads(row["payload"]), "event_id": row["event_id"], "recorded_at": row["recorded_at"],
             "kind": row["kind"]}
            for row in rows
        ]
        opening = self._receipt(db, record, "open", clock) or {}
        ledger = AccountLedger(self.data_dir, db=db)
        return {
            **record, "shadow_closing": self._receipt(db, record, "close", clock),
            "plans": [
                self._review_plan(record, entry, opening.get(entry["symbol"]), ledger, events, clock)
                for entry in record["plans"]
            ],
        }

    @staticmethod
    def _review_plan(record, entry, shadow, ledger, events, clock):
        symbol = entry["symbol"]
        plan = entry["real_plan"]
        events = [event for event in events if event["symbol"] == symbol]
        outcomes = [event for event in events if event["kind"] == "outcome"]
        findings = [event for event in events if event["kind"] == "finding"]
        account_events = ledger.trade_log(record["actual_book_id"], as_of=clock, plan_id=plan["plan_id"])
        fills = [event for event in account_events if event["kind"] == "FILL"]
        trades = plan["action"] in {"BUY", "SELL"}
        due = clock >= session_time(record["session"], 15)
        status = "UNREPORTED" if due and trades else "OBSERVED" if due else "PENDING"
        if record["mode"] == "reconstructed":
            status = "HISTORICAL_RECONSTRUCTION"
        reports = [event for event in outcomes if event["status"] != "FILLED"]
        if reports:
            status = reports[-1]["status"]
        if fills:
            aligned = [event for event in fills if event["payload"]["side"] == plan["action"]]
            quantity = sum(event["payload"]["quantity"] for event in aligned)
            if len(aligned) != len(fills) or quantity > plan["quantity"]:
                status = "DEVIATION"
            else:
                status = "FILLED" if quantity == plan["quantity"] else "PARTIAL"

        comparisons = []
        if shadow and shadow["reason"] in {"MISSING_OPENING", "UNKNOWN_OPENING", "MISSING_REFERENCE_CLOSE",
                                           "OPEN_OUTSIDE_PRICE_BAND", "UNKNOWN_SELLABLE_SHARES"}:
            comparisons.append({"category": "data_quality", "reason": shadow["reason"],
                                "evidence_refs": [shadow["opening_snapshot_id"]]})
        if trades and status in {"REJECTED", "NOT_EXECUTED", "DEVIATION"}:
            comparisons.append({"category": "user_deviation", "reason": status})
        if fills and any(instant(event["effective_at"]).date().isoformat() != plan["session"] for event in fills):
            comparisons.append({"category": "execution_deviation", "reason": "OUTSIDE_TARGET_SESSION"})

        return {
            **entry, "shadow": shadow,
            "actual": {"status": status, "events": outcomes, "account_events": account_events, "fills": fills},
            "findings": findings, "deviations": comparisons,
        }
