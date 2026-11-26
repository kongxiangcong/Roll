"""Exchange-session audit for M0b operational signoff."""
from collections import defaultdict
from datetime import date, timedelta
from hashlib import sha256
import json

from roll.market.calendar import LAST_NOTICE_DAY, SSE_HISTORICAL_HOLIDAYS
from roll.v3.market import utc_timestamp
from roll.v3.review import DecisionLedger
from roll.v3.storage import database, ensure_schema, instant, json_text, session_time, sessions


REQUIRED_SESSIONS = 20
_FIRST_NOTICE_DAY = date(min(SSE_HISTORICAL_HOLIDAYS), 1, 1)
_PLAN_FIELDS = ("plan_id", "revision", "published_at", "action", "quantity", "snapshot_id",
                "account_snapshot_id", "dossier_version", "strategy_version")
_SHADOW_INPUT_GAPS = frozenset({
    "MISSING_OPENING", "UNKNOWN_OPENING", "MISSING_REFERENCE_CLOSE", "OPEN_OUTSIDE_PRICE_BAND",
    "UNKNOWN_SELLABLE_SHARES", "UNKNOWN_AVAILABLE_CASH", "ACCOUNT_AFTER_OPEN",
})
_SCHEMA = """
CREATE TABLE IF NOT EXISTS m0b_signoff (
    signoff_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL
);
"""


def _audit(data_dir, book_id, start, end, clock, db):
    start = date.fromisoformat(start) if start else None
    end = date.fromisoformat(end) if end else None
    if start and end and start > end:
        raise ValueError("开始日期须早于或等于结束日期")
    today = clock.date()
    latest = today if clock >= session_time(today, 15) else today - timedelta(days=1)
    end = min(end or latest, latest)
    records = []
    if start is None or start <= end:
        records = DecisionLedger(data_dir).registrations(
            book_id=book_id, start=start.isoformat() if start else None, end=end.isoformat(), as_of=clock, db=db,
        )
    by_date = defaultdict(list)
    for record in records:
        by_date[record["decision_date"]].append(record)
    if start is None:
        start = date.fromisoformat(records[0]["decision_date"]) if records else end
    coverage = start >= _FIRST_NOTICE_DAY and end <= LAST_NOTICE_DAY

    days = []
    streak = 0
    for day in sessions(max(start, _FIRST_NOTICE_DAY).isoformat(), min(end, LAST_NOTICE_DAY).isoformat()):
        registrations = by_date[day]
        live = next((record for record in registrations if record["mode"] == "live"), None)
        excluded = [
            {key: record[key] for key in ("mode", "registration_id", "registered_at")}
            for record in registrations if record["mode"] != "live"
        ]
        entry = _session(live, clock) if live else {
            "decision_date": day, "registration_id": None, "registered_at": None, "plans": [],
        }
        days.append({**entry, "excluded_registrations": excluded})
        streak = streak + 1 if live else 0
    candidate = _candidate(days[-REQUIRED_SESSIONS:]) if streak >= REQUIRED_SESSIONS else None
    ready = coverage and candidate is not None and not candidate["blocking_issues"]
    return {
        "milestone": "M0b", "book_id": book_id, "as_of": utc_timestamp(clock),
        "status": "ready" if ready else "pending", "required_sessions": REQUIRED_SESSIONS,
        "consecutive_live_sessions": streak,
        "calendar_known_through": LAST_NOTICE_DAY.isoformat(), "calendar_coverage_complete": coverage,
        "missing_live_dates": [entry["decision_date"] for entry in days if entry["registration_id"] is None],
        "window": candidate, "sessions": days,
    }


def _session(live, clock):
    target = live["session"]
    opening_due = clock >= session_time(target, 9, 30)
    closing_due = clock >= session_time(target, 15, 5)
    day = live["decision_date"]
    blockers = []
    pending = []
    exceptions = []
    plans = []
    for entry in live["plans"]:
        symbol = entry["symbol"]
        actual = _actual(entry, clock)
        if actual["status"] == "UNREPORTED":
            blockers.append(_issue(day, "ACTUAL_OUTCOME_MISSING", symbol))
        elif actual["status"] in {"PENDING", "CONFIRMED"}:
            pending.append(_issue(day, "ACTUAL_OUTCOME_PENDING", symbol))

        shadow = entry["shadow"]
        if shadow is None:
            status = "OVERDUE" if opening_due else "PENDING"
            shadow = {"status": status, "reason": None}
            if opening_due:
                blockers.append(_issue(day, "SHADOW_OPENING_MISSING", symbol))
            else:
                pending.append(_issue(day, "SHADOW_OPENING_PENDING", symbol))
        elif shadow["reason"] in _SHADOW_INPUT_GAPS:
            blockers.append(_issue(day, shadow["reason"], symbol))

        exceptions.extend({**finding, "symbol": symbol} for finding in entry["findings"] + entry["deviations"])
        plans.append({
            "symbol": symbol, "actual": actual, "shadow": shadow,
            "real_plan": {key: entry["real_plan"][key] for key in _PLAN_FIELDS},
            "shadow_plan": {key: entry["shadow_plan"][key] for key in _PLAN_FIELDS},
        })

    closing = live["shadow_closing"]
    if closing is None:
        closing = {"status": "OVERDUE" if closing_due else "PENDING"}
        if closing_due:
            blockers.append(_issue(day, "SHADOW_CLOSING_MISSING"))
        else:
            pending.append(_issue(day, "SHADOW_CLOSING_PENDING"))
    elif closing["missing_marks"]:
        closing = {**closing, "status": "INCOMPLETE"}
        blockers.extend(_issue(day, "SHADOW_CLOSE_MARK_MISSING", symbol) for symbol in closing["missing_marks"])
    else:
        closing = {**closing, "status": "SETTLED"}

    return {
        "decision_date": day, "registration_id": live["registration_id"], "registered_at": live["registered_at"],
        "decision_at": live["decision_at"], "mode": live["mode"], "target_session": target,
        "shadow_book_id": live["shadow_book_id"], "baseline_account_snapshot_id": live["baseline_account_snapshot_id"],
        "plans": plans, "shadow_closing": closing, "exceptions": exceptions,
        "blocking_issues": blockers, "pending_results": pending,
    }


def _actual(entry, clock):
    actual = entry["actual"]
    plan = entry["real_plan"]
    status = actual["status"]
    if status == "CONFIRMED" and clock >= instant(plan["valid_until"]):
        status = "UNREPORTED" if plan["action"] in {"BUY", "SELL"} else "OBSERVED"
    reason = next((event["reason"] for event in reversed(actual["events"]) if event["status"] == status), None)
    if not reason:
        reason = {
            "OBSERVED": plan["action"], "UNREPORTED": "RESULT_NOT_REPORTED",
            "DEVIATION": "BROKER_FILL_DEVIATED", "PARTIAL": "PARTIAL_BROKER_FILL",
        }.get(status)
    return {**actual, "status": status, "reason": reason}


def _issue(day, reason, symbol=None):
    result = {"decision_date": day, "reason": reason}
    if symbol is not None:
        result["symbol"] = symbol
    return result


def _candidate(days):
    last = days[-1]
    blocking = [issue for day in days for issue in day["blocking_issues"]]
    blocking.extend(issue for day in days[:-1] for issue in day["pending_results"])
    return {
        "start": days[0]["decision_date"], "end": last["decision_date"],
        "registration_ids": [day["registration_id"] for day in days],
        "pending_target_session": last["target_session"] if last["pending_results"] else None,
        "blocking_issues": blocking,
    }


def audit(data_dir, *, book_id="real", start=None, end=None):
    with database(data_dir) as db:
        db.execute("BEGIN")
        return _audit(data_dir, book_id, start, end, instant(), db)


def signoff(data_dir, *, book_id="real", start=None, end=None):
    with database(data_dir, write=True) as db:
        report = _audit(data_dir, book_id, start, end, instant(), db)
        if not report["calendar_coverage_complete"]:
            raise ValueError("M0b 核查范围缺少已核实的交易所日历")
        candidate = report["window"]
        if candidate is None:
            raise ValueError("M0b 签收需要连续 20 个真实交易日")
        signoff_id = sha256(json_text(candidate["registration_ids"]).encode()).hexdigest()
        ensure_schema(db, _SCHEMA)
        if original := _signed(db, signoff_id):
            return original
        if candidate["blocking_issues"]:
            raise ValueError("M0b 窗口仍有未齐备的结果，请查看 forward-window audit 的 blocking_issues")
        receipt = {
            "signoff_id": signoff_id, "milestone": "M0b", "status": "signed_off", "book_id": book_id,
            "signed_off_at": report["as_of"], "calendar_known_through": report["calendar_known_through"],
            "window": candidate, "sessions": report["sessions"][-REQUIRED_SESSIONS:],
        }
        db.execute("INSERT INTO m0b_signoff VALUES (?, ?)", (signoff_id, json_text(receipt)))
        return receipt


def show(data_dir, signoff_id):
    with database(data_dir) as db:
        ensure_schema(db, _SCHEMA)
        receipt = _signed(db, signoff_id)
    if receipt is None:
        raise ValueError(f"M0b 签收记录不存在：{signoff_id}")
    return receipt


def _signed(db, signoff_id):
    row = db.execute("SELECT payload FROM m0b_signoff WHERE signoff_id = ?", (signoff_id,)).fetchone()
    return json.loads(row["payload"]) if row else None
