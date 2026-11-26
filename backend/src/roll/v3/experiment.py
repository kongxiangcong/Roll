"""Replay a frozen trend candidate and its two continuous control accounts."""
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field, replace
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from roll.market.calendar import LAST_NOTICE_DAY, is_session
from roll.market.rules import next_trading_day
from roll.v3.account import AccountLedger, PositionLot
from roll.v3.decision import DECISION_RULES_VERSION, DecisionData, DecisionRules, SecurityInput, decide
from roll.v3.entitlements import CompanyAction, SIMULATION_BASIS, settle_entitlements, value_account
from roll.v3.execution import EXECUTION_RULES_VERSION, ExecutionIntent, ExecutionRules, OpeningQuote, execute
from roll.v3.market import (
    RECONSTRUCTED_RESEARCH, STRICT_HISTORICAL_AS_OF, get_snapshot, read_snapshot, snapshot_windows, utc_timestamp,
)
from roll.v3.storage import database, ensure_schema, json_text, session_time, sessions
from roll.v3.strategy import StrategyRegistry, replay_signals


EXPERIMENT_VERSION = "continuous-trend-experiment-v1"
PATHS = ("trend", "buy_and_hold", "no_active_trading")
SERIES = ("daily_bar", "daily_open", "corporate_action", "adjustment_factor")
EXECUTION_GAPS = {
    "MISSING_OPENING", "UNKNOWN_OPENING", "MISSING_REFERENCE_CLOSE", "OPEN_OUTSIDE_PRICE_BAND",
    "UNKNOWN_SELLABLE_SHARES", "UNKNOWN_AVAILABLE_CASH", "UNSUPPORTED_SECURITY",
}
ZERO = Decimal(0)
_SCHEMA = """
CREATE TABLE IF NOT EXISTS experiment_run (
    run_id TEXT PRIMARY KEY,
    frozen_at TEXT NOT NULL,
    configuration TEXT NOT NULL,
    report_id TEXT UNIQUE,
    report TEXT
)
"""


def _digest(value):
    return sha256(json_text(value).encode()).hexdigest()


def _number(value):
    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def _price(value):
    parsed = _number(value)
    return parsed if parsed is not None and parsed > 0 else None


def _previous(day):
    prior = date.fromisoformat(day) - timedelta(days=1)
    while not is_session(prior):
        prior -= timedelta(days=1)
    return prior.isoformat()


def _initial_configuration(protocol, symbol, initial):
    initial = initial or {}
    cash = _number(initial.get("cash", protocol["initial_cash_cny"]))
    available = _number(initial.get("available_cash", cash))
    if cash is None or available is None or not 0 <= available <= cash:
        raise ValueError("初始可用现金须在零与初始现金之间")
    lots = tuple(PositionLot(**lot) for lot in initial.get("lots", ()))
    if any(lot.symbol != symbol or lot.acquired_on and lot.acquired_on >= protocol["windows"]["development"]["start"]
           for lot in lots):
        raise ValueError("初始批次须为实验标的且已经持有")
    if len({lot.lot_id for lot in lots}) != len(lots):
        raise ValueError("初始批次标识须唯一")
    budget = {
        "cash_reserve": "0", "max_total_exposure": "1", "max_symbol_exposure": "1",
        "max_industry_exposure": "1", **initial.get("risk_budget", {}),
    }
    for key in ("cash_reserve", "max_total_exposure", "max_symbol_exposure", "max_industry_exposure"):
        amount = _number(budget[key])
        if amount is None or amount < 0 or key != "cash_reserve" and amount > 1:
            raise ValueError("初始预算须使用非负保留额及 0 至 1 的仓位上限")
        budget[key] = str(amount.normalize())
    return {"cash": str(cash), "available_cash": str(available), "lots": [asdict(lot) for lot in lots],
            "risk_budget": budget}


def _configuration(entry, snapshot, initial, replay, research_ref):
    strategy, protocol = entry["strategy"], entry["protocol"]
    symbol, = strategy["scope"]["symbols"]
    mode = snapshot["use_mode"]
    if mode not in (RECONSTRUCTED_RESEARCH, STRICT_HISTORICAL_AS_OF):
        raise ValueError("历史实验需要重建研究或严格历史时点数据快照")
    costs = protocol["costs"]
    execution = ExecutionRules(Decimal(costs["commission_rate"]), Decimal(costs["minimum_commission_yuan"]),
                               Decimal(costs["slippage_rate"]))
    return {
        "experiment_version": EXPERIMENT_VERSION, "strategy": strategy, "protocol": protocol,
        "strategy_frozen_at": entry["frozen_at"], "market_snapshot": snapshot, "symbol": symbol,
        "replay_only": replay, "research_ref": research_ref,
        "initial": _initial_configuration(protocol, symbol, initial),
        "rules": {
            "decision": DECISION_RULES_VERSION, "execution": EXECUTION_RULES_VERSION,
            "execution_parameters": asdict(execution), "accounting_basis": SIMULATION_BASIS,
            "price_only_simulation": True, "research_dossiers": [], "external_reservations": [],
            "decision_cutoff": "15:05 Asia/Shanghai", "execution_cutoff": "09:30 Asia/Shanghai",
            "valuation": "同日原始收盘价。确认停牌且当天无权益变化时可沿用上一已知原始收盘价。",
            "date_only_cash_dividend": "15:00 Asia/Shanghai", "share_listing": "09:30 Asia/Shanghai",
            "price_bands": "按开盘记录和对应交易日规则。未提供特殊价格限制时按规则推导板块涨跌幅。",
            "previous_close_fallback": mode == RECONSTRUCTED_RESEARCH,
            "availability": (
                "按冻结来源记录的可得性证据或重建假设逐时点读取。原始日线盘后 15:05，"
                "开盘观测 09:30，只消费开盘字段。首日昨收可从开盘记录中前一交易日的原始收盘字段重建。"
                if mode == RECONSTRUCTED_RESEARCH else "仅使用具有历史时点可得性证据的记录。"
            ),
        },
    }


def _saved_run(data_dir, reference):
    with database(data_dir) as db:
        ensure_schema(db, _SCHEMA)
        row = db.execute("SELECT * FROM experiment_run WHERE run_id=? OR report_id=?",
                         (reference, reference)).fetchone()
    if row is None:
        raise ValueError(f"没有实验运行 {reference}")
    return row


def _reserve_run(data_dir, run_id, configuration, frozen_at):
    encoded = json_text(configuration)
    with database(data_dir, write=True) as db:
        ensure_schema(db, _SCHEMA)
        db.execute("INSERT OR IGNORE INTO experiment_run (run_id, frozen_at, configuration) VALUES (?, ?, ?)",
                   (run_id, frozen_at, encoded))
        row = db.execute("SELECT * FROM experiment_run WHERE run_id=?", (run_id,)).fetchone()
        if row["configuration"] != encoded:
            raise ValueError(f"实验运行编号已绑定到其他配置 {run_id}")
    return row


def run_experiment(data_dir, version, snapshot_id, *, run_id=None, at=None, initial=None, replay=False,
                   research_ref=None):
    registry = StrategyRegistry(data_dir)
    frozen_at = utc_timestamp(at)
    entry = registry.get(version, frozen_at)
    snapshot = get_snapshot(data_dir, snapshot_id)
    if entry is None or snapshot is None:
        raise ValueError("找不到冻结策略版本或行情数据快照")
    if snapshot["as_of"] > frozen_at:
        raise ValueError("实验登记时点早于数据快照")
    configuration = json.loads(json_text(_configuration(entry, snapshot, initial, replay, research_ref)))
    run_id = run_id or f"experiment-{_digest(configuration)[:24]}"
    registered = _reserve_run(data_dir, run_id, configuration, frozen_at)
    dates = configuration["protocol"]["windows"]
    if replay:
        exposure = registry.record_replay(
            version, snapshot_id, start=dates["development"]["start"], end=dates["acceptance"]["end"],
            exposed_at=registered["frozen_at"],
        )
    else:
        exposure = registry.begin_acceptance(version, snapshot_id, run_id=run_id,
                                             evaluated_at=registered["frozen_at"])
    exposure = {key: exposure[key] for key in ("run_id", "use", "independent", "opened_at")}
    if registered["report"] is None:
        market = _market_inputs(data_dir, configuration)
        with database(data_dir, write=True) as db:
            current = db.execute("SELECT report FROM experiment_run WHERE run_id=?", (run_id,)).fetchone()
            if current["report"] is None:
                report = _replay(data_dir, db, run_id, configuration, exposure, market)
                db.execute("UPDATE experiment_run SET report_id=?, report=? WHERE run_id=?",
                           (report["report_id"], json_text(report), run_id))
    result = read_experiment(data_dir, run_id)
    if not replay:
        registry.record_historical_result(version, run_id=run_id, verdict=result["verdict"],
                                          evidence_ref=result["report_id"], recorded_at=registered["frozen_at"])
    return result


def list_experiments(data_dir, symbol):
    """List completed runs for a security without loading the daily traces."""
    with database(data_dir) as db:
        ensure_schema(db, _SCHEMA)
        rows = db.execute("""
            SELECT run_id, report_id, frozen_at,
                   json_extract(configuration, '$.strategy.version') AS strategy_version
            FROM experiment_run
            WHERE report_id IS NOT NULL AND json_extract(configuration, '$.symbol') = ?
            ORDER BY frozen_at DESC, run_id
        """, (symbol.upper(),)).fetchall()
    return [dict(row) for row in rows]


def read_experiment(data_dir, run_id, *, trace=False):
    row = _saved_run(data_dir, run_id)
    if row["report"] is None:
        raise ValueError(f"实验运行已登记，结果尚未保存 {run_id}")
    report = json.loads(row["report"])
    if not trace:
        del report["sessions"]
    return report


def verify_experiment(data_dir, run_id):
    reproducible = read_experiment(data_dir, run_id)
    run_id = reproducible["run_id"]
    configuration = reproducible["configuration"]
    if configuration["experiment_version"] != EXPERIMENT_VERSION:
        raise ValueError("当前回测版本无法重建该实验")
    market = _market_inputs(data_dir, configuration)
    with TemporaryDirectory(prefix="roll-experiment-") as directory:
        ledger_dir = Path(directory)
        with database(ledger_dir, write=True) as db:
            verification = _replay(ledger_dir, db, run_id, configuration, reproducible["exposure"], market)
    return {
        "run_id": run_id, "report_id": reproducible["report_id"],
        "reproduced_report_id": verification["report_id"],
        "matches": verification["report_id"] == reproducible["report_id"],
    }


def _action_phase(data_dir, db, scope, at, previous_cutoff, previous):
    record = read_snapshot(data_dir, series="corporate_action", cutoff=at, db=db, **scope)
    visible = {}
    issues = []
    for row in record["observations"]:
        try:
            action = CompanyAction.from_observation(row)
            term_dates = (action.record_date, action.ex_date, action.payment_date, action.listing_date)
            if any(value and date.fromisoformat(value).isoformat() != value for value in term_dates):
                raise ValueError("公司行动日期须为 ISO 日期")
            if any(not rate.is_finite() or rate < 0 for rate in (action.cash_per_share, action.shares_per_share)):
                raise ValueError("权益比例须为非负数")
        except (KeyError, ValueError, InvalidOperation):
            issues.append((row["trade_date"], "INVALID_CORPORATE_ACTION", ()))
            continue
        visible[action.key] = action
    relevant = []
    for key, action in visible.items():
        old = previous.get(key)
        day = at.date().isoformat()
        due_times = (
            session_time(action.payment_date, 15) if action.payment_date else None,
            session_time(action.listing_date, 9, 30) if action.listing_date else None,
        )
        if action != old or any(due and previous_cutoff < due <= at for due in due_times):
            relevant.append(action)
            if (day > action.ex_date and (old is None or _terms(old) != _terms(action))) or (
                at.hour >= 15 and action.listing_date == day and action.shares_per_share and old is None
            ):
                issues.append((action.ex_date, "CORPORATE_ACTION_LATE_OR_REVISED", (action.record_date,)))
    for key in previous.keys() - visible.keys():
        action = previous[key]
        issues.append((action.ex_date, "CORPORATE_ACTION_NO_LONGER_USABLE", (action.record_date,)))
    return visible, tuple(relevant), issues


def _terms(action):
    return (
        action.record_date, action.ex_date, action.payment_date, action.listing_date,
        action.cash_per_share, action.shares_per_share,
    )


def _economic_action_gap(bar, factors, actions):
    if any((action.cash_per_share and not action.payment_date)
           or (action.shares_per_share and not action.listing_date) for action in actions):
        return "ENTITLEMENT_SETTLEMENT_DATE_MISSING"
    if not factors:
        if actions or bar.get("pre_close_basis") == "fuyao_adjustment_factor":
            return "MISSING_ADJUSTMENT_FACTOR"
        return None
    if len(factors) != 1:
        return "AMBIGUOUS_ADJUSTMENT_FACTOR"
    factor = factors[0]["payload"]
    dividend = _number(factor.get("dividend_per_share"))
    bonus = _number(factor.get("bonus_per_share"))
    rights = _number(factor.get("rights_per_share", 0))
    if rights:
        return "UNSUPPORTED_RIGHTS_ISSUE"
    if dividend is None or bonus is None or rights is None:
        return "INVALID_ADJUSTMENT_FACTOR"
    if (dividend, bonus) != (sum(action.cash_per_share for action in actions),
                             sum(action.shares_per_share for action in actions)):
        return "ENTITLEMENT_TERMS_UNVERIFIED"
    return None


def _market_inputs(data_dir, configuration):
    snapshot = configuration["market_snapshot"]
    symbol, snapshot_id = configuration["symbol"], snapshot["snapshot_id"]
    windows = configuration["protocol"]["windows"]
    start, end = windows["development"]["start"], windows["acceptance"]["end"]
    days = list(sessions(start, min(end, LAST_NOTICE_DAY.isoformat())))
    market = {"days": days, "gaps": [], "opens": {}, "closes": {}, "actions": {}, "signals": {}}
    covered = {item["series"] for item in snapshot["scope"]
               if item["symbol"] == symbol and item["start"] <= start and item["end"] >= end}
    for series in SERIES:
        if series not in covered:
            market["gaps"].append((start, f"SNAPSHOT_SCOPE_MISSING:{series}", PATHS))
    if end > LAST_NOTICE_DAY.isoformat():
        market["gaps"].append((LAST_NOTICE_DAY.isoformat(), "EXCHANGE_CALENDAR_GAP", PATHS))
    if not days:
        return market

    open_times = {day: session_time(day, 9, 30) for day in days}
    close_times = {day: session_time(day, 15, 5) for day in days}
    prior = _previous(days[0])
    market["prior_date"] = prior
    market["opens"] = snapshot_windows(data_dir, snapshot_id, series="daily_open", symbol=symbol, cutoffs=open_times)
    market["closes"] = snapshot_windows(
        data_dir, snapshot_id, symbol=symbol, cutoffs={prior: session_time(prior, 15, 5), **close_times},
    )
    market["signals"] = {
        item["trade_date"]: item for item in replay_signals(
            data_dir, configuration["strategy"]["version"], snapshot_id, symbol=symbol, start=days[0], end=days[-1],
            registered_at=configuration["strategy_frozen_at"],
        )
    }
    # Select sparse action versions at the opening and evening cutoffs. A late
    # change remains visible in the trace and makes the earlier affected path incomplete.
    with database(data_dir) as db:
        prior_actions = {}
        prior_cutoff = session_time(prior, 15, 5)
        for day in days:
            scope = dict(snapshot_id=snapshot_id, symbol=symbol, start=days[0], end=day)
            open_at, close_at = open_times[day], close_times[day]
            open_actions, opening, open_issues = _action_phase(data_dir, db, scope, open_at, prior_cutoff, prior_actions)
            prior_actions, closing, close_issues = _action_phase(data_dir, db, scope, close_at, open_at, open_actions)
            prior_cutoff = close_at
            mark = market["closes"][day]
            factors = read_snapshot(
                data_dir, snapshot_id, series="adjustment_factor", symbol=symbol, start=day, end=day,
                cutoff=close_times[day], db=db,
            )["observations"]
            actions_today = [action for action in prior_actions.values() if action.ex_date == day]
            issue = _economic_action_gap(mark["payload"] if mark else {}, factors, actions_today)
            issues = [*open_issues, *close_issues]
            if issue:
                record_dates = tuple(action.record_date for action in actions_today)
                issues.append((day, issue, record_dates))
            market["actions"][day] = {
                "opening": opening, "closing": closing, "issues": issues,
                "factors": [factor["seq"] for factor in factors],
            }
    return market


@dataclass
class _Book:
    name: str
    book_id: str
    configured: bool = False
    pending: ExecutionIntent | None = None
    holding_days: set[str] = field(default_factory=set)

    def target(self, signal):
        if self.name == "trend":
            return signal
        if self.name == "buy_and_hold" and not self.configured:
            return {"status": "ready", "signal": "initial_allocation", "target_fraction": "1"}
        return None


def _opening(row, symbol, day):
    if row is None:
        return None
    quote = OpeningQuote.from_payload(symbol, day, row["payload"], observation_seq=row["seq"])
    return replace(quote, raw_open=_price(quote.raw_open), pre_close=_price(quote.pre_close))


def _decision(book, account, configuration, rules, signal, as_of, session, close, status):
    strategy, protocol = configuration["strategy"], configuration["protocol"]
    version, symbol = strategy["version"], configuration["symbol"]
    if book.name == "buy_and_hold":
        version = "buy-and-hold-initial-allocation-v1"
        strategy = {**strategy, "version": version, "exit": protocol["baselines"]["buy_and_hold"]}
    target = book.target(signal)
    if target is None:
        return {"action": "HOLD", "reason": "NO_ACTIVE_TRADING" if book.name == "no_active_trading"
                else "BUY_AND_HOLD_CONFIGURED"}, None
    if session is None:
        return {"action": "WATCH", "reason": "NEXT_SESSION_CALENDAR_UNAVAILABLE"}, None
    security = SecurityInput(close=close, trading_status=status, signals={version: target})
    data = DecisionData(as_of, session, configuration["market_snapshot"]["snapshot_id"], {symbol: security})
    entry = {"strategy": strategy, "protocol": protocol, "status": "frozen", "simulation_eligible": True}
    simulation = DecisionRules(simulated=True, allow_price_only=True, strategy_versions=(version,), execution=rules)
    plan, = decide(data, account, account.risk_budget, {}, {symbol: (entry,)}, simulation)
    if book.name == "buy_and_hold" and close is not None and status == "trading":
        at_limit = {
            "TOTAL_EXPOSURE_LIMIT", "SYMBOL_EXPOSURE_LIMIT", "INDUSTRY_EXPOSURE_LIMIT",
            "CASH_RESERVE_OR_COMMITMENTS",
        }.intersection(plan.reasons["P1"])
        if plan.reasons["P4"] == ["TARGET_ALREADY_MET"] or (plan.quantity == 0 and at_limit):
            book.configured = True
    plan_id = f"{book.book_id}:{as_of.date()}"
    return {**plan.as_dict(), "plan_id": plan_id}, plan.execution_intent(plan_id)


def _observation(row):
    if row is None:
        return None
    return {field: row[field] for field in (
        "seq", "source", "source_ref", "selected_available_at", "availability_assumption", "reconstruction_only",
    )}


def _mark(row, previous_close, actions):
    payload = row["payload"] if row else {}
    close = _price(payload.get("close"))
    status = payload.get("trading_status", "unknown")
    if close is not None:
        return close, status, "RAW_CLOSE"
    if status == "suspended" and previous_close is not None and not actions:
        return previous_close, status, "CONFIRMED_SUSPENSION_LAST_RAW_CLOSE"
    return None, status, "MISSING_RAW_CLOSE"


def _valuation(account, symbol, close):
    positions_require_mark = account.lots or any(item.kind == "shares" for item in account.receivables)
    if close is None and positions_require_mark:
        return None
    return value_account(account, {symbol: close}).as_dict()


def _account_at(ledger, data_dir, db, book, actions, at):
    if actions:
        return settle_entitlements(data_dir, book.book_id, actions, as_of=at, simulated=True, db=db)
    return ledger.snapshot(book.book_id, as_of=at)


def _intent_payload(intent, session):
    return {**asdict(intent), "target_session": session} if intent else None


def _session_after(day):
    try:
        return str(next_trading_day(date.fromisoformat(day)))
    except ValueError:
        return None


def _replay(data_dir, db, run_id, configuration, exposure, market):
    from roll.v3.experiment_metrics import summarize

    ledger = AccountLedger(data_dir, db=db)
    rules = ExecutionRules(**{key: Decimal(value) if key != "lot_size" else value
                              for key, value in configuration["rules"]["execution_parameters"].items()})
    symbol = configuration["symbol"]
    books = [_Book(name, f"experiment:{run_id}:{name}") for name in PATHS]
    gaps = defaultdict(set)
    for day, reason, paths in market["gaps"]:
        gaps[day, reason].update(paths)
    trace = []
    starting_values = {}
    starting_decision = None
    if days := market["days"]:
        prior_date = market["prior_date"]
        prior_cutoff = session_time(prior_date, 15, 5)
        prior_row = market["closes"][prior_date]
        prior_close, prior_status, prior_basis = _mark(prior_row, None, ())
        source = _observation(prior_row)
        first_open = market["opens"][days[0]]
        if prior_row is None and first_open and configuration["rules"]["previous_close_fallback"]:
            prior_close = _price(first_open["payload"].get("prior_close"))
            if prior_close is not None:
                prior_status = "trading"
                prior_basis = "RECONSTRUCTED_PREVIOUS_RAW_CLOSE"
                source = _observation(first_open)
        if prior_close is None:
            affected = PATHS if configuration["initial"]["lots"] else ("buy_and_hold",)
            gaps[prior_date, "PRE_WINDOW_MARK_OR_BASELINE_DECISION_UNAVAILABLE"].update(affected)
        initial = configuration["initial"]
        for book in books:
            ledger.initialize(
                book.book_id, cash=initial["cash"], available_cash=initial["available_cash"],
                lots=[PositionLot(**lot) for lot in initial["lots"]], effective_at=prior_cutoff,
                known_at=prior_cutoff, source="frozen-experiment-baseline",
            )
            ledger.set_risk_budget(
                book.book_id, budget_id=f"experiment-budget-{_digest(initial['risk_budget'])[:16]}",
                effective_at=prior_cutoff, known_at=prior_cutoff, **initial["risk_budget"],
            )
            account = ledger.snapshot(book.book_id, as_of=prior_cutoff)
            starting_values[book.name] = _valuation(account, symbol, prior_close)
            if account.lots:
                book.holding_days.add(prior_date)
            if book.name == "buy_and_hold":
                decision, book.pending = _decision(book, account, configuration, rules, None, prior_cutoff,
                                                   days[0], prior_close, prior_status)
                starting_decision = {
                    "date": prior_date, "close": prior_close, "basis": prior_basis, "observation": source,
                    "decision": decision, "pending_intent": _intent_payload(book.pending, days[0]),
                }

        last_mark = prior_close
        previous_day = prior_date
        for day in days:
            following = _session_after(day)
            open_at, close_at = session_time(day, 9, 30), session_time(day, 15, 5)
            opening_row, closing_row = market["opens"][day], market["closes"][day]
            open_quote = _opening(opening_row, symbol, day)
            action = market["actions"][day]
            close, status, mark_basis = _mark(closing_row, last_mark, action["factors"] or action["issues"])
            last_mark = close
            signal = market["signals"][day]
            if following is None:
                gaps[day, "NEXT_SESSION_CALENDAR_UNAVAILABLE"].update(("trend", "buy_and_hold"))
            for missing in signal["missing"]:
                if missing["reason"] != "suspended":
                    gaps[missing["trade_date"], f"TREND_FEATURE_UNAVAILABLE:{missing['reason']}"].add("trend")
            paths = {}
            for book in books:
                open_account = _account_at(ledger, data_dir, db, book, action["opening"], open_at)
                execution = {"status": "NO_INTENT", "reason": None, "fill": None}
                if book.pending:
                    outcome = execute(book.pending, open_quote, open_account, rules)
                    execution = outcome.as_dict()
                    if outcome.reason in EXECUTION_GAPS:
                        gaps[day, outcome.reason].add(book.name)
                    if outcome.fill:
                        ledger.record_fill(book.book_id, **outcome.fill.ledger_fields(), known_at=open_at,
                                           source="historical-simulation", plan_id=book.pending.intent_id)
                        if book.name == "buy_and_hold":
                            book.configured = True
                account = _account_at(ledger, data_dir, db, book, action["closing"], close_at)
                valuation = _valuation(account, symbol, close)
                if valuation is None:
                    gaps[day, "MISSING_VALUATION_MARK"].add(book.name)
                if (book.name == "buy_and_hold" and not book.configured and status != "suspended"
                    and (close is None or status != "trading")):
                    gaps[day, "BASELINE_DECISION_INPUT_UNAVAILABLE"].add(book.name)
                if account.lots:
                    book.holding_days.add(day)
                for impacted_day, reason, record_dates in action["issues"]:
                    dates = record_dates or (previous_day,)
                    if book.holding_days.intersection(dates) or open_account.lots or account.receivables:
                        gaps[impacted_day, reason].add(book.name)
                decision, book.pending = _decision(
                    book, account, configuration, rules, signal, close_at, following, close, status,
                )
                paths[book.name] = {
                    "signal": signal if book.name == "trend" else None, "execution": execution,
                    "open_account": open_account.as_dict(), "account": account.as_dict(), "valuation": valuation,
                    "decision": decision, "pending_intent": _intent_payload(book.pending, following),
                }
            trace.append({
                "date": day, "close": close, "mark_basis": mark_basis, "trading_status": status,
                "closing_observation": _observation(closing_row), "opening_observation": _observation(opening_row),
                "entitlements": {"opening": [asdict(item) for item in action["opening"]],
                                 "closing": [asdict(item) for item in action["closing"]],
                                 "factor_observation_ids": action["factors"]},
                "paths": paths,
            })
            previous_day = day

    coverage = {
        "path_gaps": [{"date": day, "reason": reason, "paths": sorted(paths)}
                      for (day, reason), paths in sorted(gaps.items()) if paths],
        "sessions": len(trace), "signal_status": dict(Counter(item["paths"]["trend"]["signal"]["status"] for item in trace)),
        "confirmed_suspensions": [item["date"] for item in trace if item["trading_status"] == "suspended"],
    }
    boundary = {
        "pre_window": starting_decision, "initial_mark": starting_values,
        "last_session": trace[-1]["date"] if trace else None,
        "pending_intents": {book.name: _intent_payload(book.pending, _session_after(trace[-1]["date"]))
                            for book in books if book.pending} if trace else {},
        "pending_policy": "冻结结束后的开盘不在本次试验内，悬而未决意图不计入成交或成交失败。",
    }
    report = {
        "run_id": run_id, "independent": exposure["independent"], "exposure": exposure,
        "configuration": configuration, "sessions": trace, "coverage": coverage, "boundary": boundary,
        "books": {book.name: book.book_id for book in books},
        **summarize(trace, coverage, starting_values, boundary, configuration),
    }
    return {**report, "report_id": f"experiment-result-{_digest(report)}"}
