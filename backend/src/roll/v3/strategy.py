"""Frozen trend StrategySpecs, experiment protocols, and admission state."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path

from roll.v3.market import get_snapshot, read_snapshot, utc_timestamp
from roll.v3.storage import database, ensure_schema, instant, json_text, session_time, sessions


_DEFAULT_PROTOCOL = Path(__file__).with_name("default_trend_protocol.json")
_SCHEMA = """
CREATE TABLE IF NOT EXISTS strategy_version (
    version TEXT PRIMARY KEY,
    family TEXT NOT NULL,
    frozen_at TEXT NOT NULL,
    spec_json TEXT NOT NULL,
    protocol_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strategy_exposure (
    run_id TEXT PRIMARY KEY,
    version TEXT NOT NULL REFERENCES strategy_version(version),
    snapshot_id TEXT NOT NULL,
    start TEXT NOT NULL,
    end TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    purpose TEXT NOT NULL,
    independent INTEGER NOT NULL,
    verdict TEXT,
    evidence_ref TEXT,
    recorded_at TEXT
);
CREATE TABLE IF NOT EXISTS strategy_event (
    event_id INTEGER PRIMARY KEY,
    version TEXT NOT NULL REFERENCES strategy_version(version),
    kind TEXT NOT NULL,
    effective_at TEXT NOT NULL,
    detail TEXT NOT NULL
);
"""


def _fingerprint(value):
    return sha256(json_text(value).encode()).hexdigest()


def _run(row, as_of=None):
    result = dict(row)
    result["independent"] = bool(row["independent"])
    result["use"] = "independent_acceptance" if row["independent"] else "comparison_only"
    if as_of is not None and row["recorded_at"] and row["recorded_at"] > as_of:
        result.update(verdict=None, evidence_ref=None, recorded_at=None)
    return result


def _exposures(db, family, start, end, as_of=None):
    return [
        _run(row, as_of) for row in db.execute(
            """SELECT exposure.* FROM strategy_exposure AS exposure
               JOIN strategy_version AS strategy ON exposure.version=strategy.version
               WHERE strategy.family=? AND exposure.start<=? AND exposure.end>=?
                 AND (? IS NULL OR exposure.opened_at<=?)
               ORDER BY exposure.opened_at, exposure.run_id""",
            (family, end, start, as_of, as_of),
        )
    ]


def _latest_event(db, version, as_of, kind_filter):
    events = db.execute(
        """SELECT * FROM strategy_event WHERE version=? AND effective_at<=?
           ORDER BY effective_at DESC, event_id DESC""",
        (version, as_of),
    )
    event = next((row for row in events if row["kind"] in kind_filter), None)
    if event is None:
        return None
    result = dict(event)
    detail = json.loads(result.pop("detail"))
    return {**result, **detail}


def _append_event(db, version, kind, at, detail):
    db.execute(
        "INSERT INTO strategy_event(version, kind, effective_at, detail) VALUES (?, ?, ?, ?)",
        (version, kind, at, json_text(detail)),
    )


def _registration(db, row, as_of):
    strategy = json.loads(row["spec_json"])
    protocol = json.loads(row["protocol_json"])
    window = protocol["windows"]["acceptance"]
    exposures = _exposures(db, row["family"], window["start"], window["end"], as_of)
    acceptance = next(
        (run for run in exposures if run["version"] == row["version"] and run["independent"]),
        None,
    )
    verdict = acceptance["verdict"] if acceptance else None
    status = {"pass": "accepted", "fail": "rejected", "insufficient": "frozen"}.get(
        verdict, "evaluating" if acceptance else "frozen",
    )
    publication = _latest_event(db, row["version"], as_of, ("admitted", "suspended", "retired"))
    if publication:
        status = publication["kind"]
    return {
        "strategy": strategy,
        "protocol": protocol,
        "status": status,
        "scope": strategy["scope"],
        "frozen_at": row["frozen_at"],
        "production_eligible": status == "admitted",
        "simulation_eligible": status not in ("suspended", "retired"),
        "publication": publication,
        "forward_review": _latest_event(db, row["version"], as_of, ("forward_review",)),
        "acceptance": {
            "window": window,
            "new_independent_run_allowed": not exposures,
            "independent_run": acceptance,
            "exposures": exposures,
        },
    }


def _covers(snapshot, strategy, window):
    end = session_time(window["end"], 15, 5)
    required = {
        (symbol, series) for symbol in strategy["scope"]["symbols"]
        for series in ("daily_bar", "adjustment_factor")
    }
    covered = {
        (item["symbol"], item["series"]) for item in snapshot["scope"]
        if item["start"] <= window["start"] and item["end"] >= window["end"]
    }
    return snapshot["as_of"] >= utc_timestamp(end) and required <= covered


def _require_version(db, version, as_of):
    row = db.execute(
        "SELECT * FROM strategy_version WHERE version=? AND frozen_at<=?", (version, as_of),
    ).fetchone()
    if row is None:
        raise ValueError(f"该时点没有策略版本 {version}")
    return row


def _date_window(start, end):
    start, end = str(date.fromisoformat(start)), str(date.fromisoformat(end))
    if start > end:
        raise ValueError("开始日期不能晚于结束日期")
    return start, end


@dataclass(frozen=True)
class StrategyRegistry:
    data_dir: Path

    def freeze_default(self, *, fast=20, slow=60, frozen_at=None,
                       acceptance_start=None, acceptance_end=None):
        """Register an immutable trend candidate. Identical re-registration keeps its version."""
        if not 0 < fast < slow:
            raise ValueError("均线窗口须满足 0 < fast < slow")
        definition = json.loads(_DEFAULT_PROTOCOL.read_text(encoding="utf-8"))
        strategy = definition.pop("strategy")
        strategy["parameters"] = {"fast": fast, "slow": slow}
        window = definition["windows"]["acceptance"]
        start, end = _date_window(acceptance_start or window["start"], acceptance_end or window["end"])
        if start <= definition["windows"]["development"]["end"]:
            raise ValueError("验收窗口须晚于开发窗口")
        definition["windows"]["acceptance"] = {"start": start, "end": end}
        version = f"{definition['family']}-{_fingerprint({'strategy': strategy, **definition})[:16]}"
        strategy["version"] = version
        definition["strategy_version"] = version
        definition["version"] = f"protocol-{_fingerprint(definition)[:16]}"
        frozen_at = utc_timestamp(frozen_at)
        with database(self.data_dir) as db:
            db.executescript(_SCHEMA)
            db.execute(
                "INSERT OR IGNORE INTO strategy_version VALUES (?, ?, ?, ?, ?)",
                (version, definition["family"], frozen_at, json_text(strategy), json_text(definition)),
            )
            row = db.execute("SELECT * FROM strategy_version WHERE version=?", (version,)).fetchone()
            return _registration(db, row, max(row["frozen_at"], frozen_at))

    def get(self, version, as_of=None, *, db=None):
        """Read a specific version as it was registered at a given cutoff."""
        as_of = utc_timestamp(as_of)
        with database(self.data_dir, db=db) as db:
            ensure_schema(db, _SCHEMA)
            row = db.execute(
                "SELECT * FROM strategy_version WHERE version=? AND frozen_at<=?", (version, as_of),
            ).fetchone()
            return _registration(db, row, as_of) if row else None

    def for_symbol(self, symbol, as_of=None, *, simulated=False, versions=(), include_ineligible=False, db=None):
        """Return eligible versions. Simulation requires explicit selection of a candidate."""
        as_of = utc_timestamp(as_of)
        with database(self.data_dir, db=db) as db:
            ensure_schema(db, _SCHEMA)
            rows = db.execute(
                "SELECT * FROM strategy_version WHERE frozen_at<=? ORDER BY version", (as_of,),
            ).fetchall()
            entries = [_registration(db, row, as_of) for row in rows]
        return [
            entry for entry in entries
            if symbol.upper() in entry["scope"]["symbols"]
            and (
                include_ineligible or (
                    (not versions or entry["strategy"]["version"] in versions)
                    and (entry["production_eligible"] or (
                        simulated and entry["strategy"]["version"] in versions and entry["simulation_eligible"]
                    ))
                )
            )
        ]


    def begin_acceptance(self, version, snapshot_id, *, run_id, evaluated_at=None,
                         start=None, end=None):
        """Bind a snapshot and reserve the independent window before exposing results."""
        return self._open_run(
            version, snapshot_id, run_id, "acceptance", evaluated_at, start, end,
        )

    def record_replay(self, version, snapshot_id, *, start, end, exposed_at=None):
        """Record the interval of a disclosed ad hoc signal replay."""
        run_id = f"replay-{_fingerprint([version, snapshot_id, start, end])[:24]}"
        return self._open_run(version, snapshot_id, run_id, "replay", exposed_at, start, end)

    def _open_run(self, version, snapshot_id, run_id, purpose, opened_at, start, end):
        snapshot = get_snapshot(self.data_dir, snapshot_id)
        opened_at = utc_timestamp(opened_at)
        with database(self.data_dir) as db:
            db.executescript(_SCHEMA)
            db.execute("BEGIN IMMEDIATE")
            row = _require_version(db, version, opened_at)
            strategy = json.loads(row["spec_json"])
            window = json.loads(row["protocol_json"])["windows"]["acceptance"]
            start, end = _date_window(start or window["start"], end or window["end"])
            existing = db.execute("SELECT * FROM strategy_exposure WHERE run_id=?", (run_id,)).fetchone()
            if existing is not None:
                identity = tuple(existing[key] for key in ("version", "snapshot_id", "start", "end", "purpose"))
                if identity != (version, snapshot_id, start, end, purpose):
                    raise ValueError(f"实验运行编号已绑定到其他输入 {run_id}")
                return _run(existing)

            independent = (
                purpose == "acceptance"
                and start <= window["start"] and end >= window["end"]
                and _covers(snapshot, strategy, window)
                and not _exposures(db, row["family"], window["start"], window["end"])
            )
            result = db.execute(
                """INSERT INTO strategy_exposure
                   (run_id, version, snapshot_id, start, end, opened_at, purpose, independent)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING *""",
                (run_id, version, snapshot_id, start, end, opened_at, purpose, independent),
            ).fetchone()
            return _run(result)

    def record_historical_result(self, version, *, run_id, verdict, evidence_ref, recorded_at=None):
        """Attach the evaluator's verdict to a reserved run without granting production admission."""
        if verdict not in ("pass", "fail", "insufficient") or not evidence_ref:
            raise ValueError("实验结论须为 pass、fail 或 insufficient，并引用结果证据")
        recorded_at = utc_timestamp(recorded_at)
        with database(self.data_dir) as db:
            db.executescript(_SCHEMA)
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute(
                """SELECT * FROM strategy_exposure
                   WHERE run_id=? AND version=? AND purpose='acceptance' AND opened_at<=?""",
                (run_id, version, recorded_at),
            ).fetchone()
            if prior is None:
                raise ValueError(f"该时点没有冻结的验收运行 {run_id}")
            if prior["recorded_at"] is not None:
                if (prior["verdict"], prior["evidence_ref"]) != (verdict, evidence_ref):
                    raise ValueError(f"验收运行已保存结果 {run_id}")
                return _run(prior)
            row = db.execute(
                """UPDATE strategy_exposure SET verdict=?, evidence_ref=?, recorded_at=?
                   WHERE run_id=? RETURNING *""",
                (verdict, evidence_ref, recorded_at, run_id),
            ).fetchone()
            return _run(row)

    def record_forward_result(self, version, *, session_dates, verdict, evidence_ref, recorded_at=None):
        """Register the evaluator's review of live, non-backfilled shadow sessions."""
        if verdict not in ("pass", "fail", "insufficient") or not evidence_ref:
            raise ValueError("前向结论须为 pass、fail 或 insufficient，并引用影子账本证据")
        days = list(session_dates)
        recorded_at = utc_timestamp(recorded_at)
        with database(self.data_dir) as db:
            db.executescript(_SCHEMA)
            db.execute("BEGIN IMMEDIATE")
            row = _require_version(db, version, recorded_at)
            entry = _registration(db, row, recorded_at)
            historical = entry["acceptance"]["independent_run"]
            minimum = entry["protocol"]["evaluation"]["min_forward_sessions"]
            if verdict == "pass":
                if not historical or historical["verdict"] != "pass":
                    raise ValueError("前向通过须建立在独立历史验收通过之后")
                if len(days) < minimum or days != list(sessions(days[0], days[-1])):
                    raise ValueError(f"前向通过须有至少 {minimum} 个连续交易日")
                start = utc_timestamp(session_time(days[0], 15, 5))
                end = utc_timestamp(session_time(days[-1], 15, 5))
                if days[0] <= historical["end"] or start <= historical["recorded_at"] or end > recorded_at:
                    raise ValueError("前向观察须在历史验收完成后开始，并在复核时完成")

            detail = {"verdict": verdict, "evidence_ref": evidence_ref, "session_dates": days}
            last = entry["forward_review"]
            if not last or any(last[key] != value for key, value in detail.items()):
                _append_event(db, version, "forward_review", recorded_at, detail)
            return _registration(db, row, recorded_at)

    def admit(self, version, *, effective_at=None):
        """Explicitly publish a version with independent historical and forward evidence."""
        effective_at = utc_timestamp(effective_at)
        with database(self.data_dir) as db:
            db.executescript(_SCHEMA)
            db.execute("BEGIN IMMEDIATE")
            row = _require_version(db, version, effective_at)
            entry = _registration(db, row, effective_at)
            if entry["status"] == "admitted":
                return entry
            if entry["status"] not in ("accepted", "suspended"):
                raise ValueError("准入须有独立历史验收通过的记录")

            forward = entry["forward_review"]
            if not forward or forward["verdict"] != "pass":
                raise ValueError("准入须有通过的前向影子观察记录")
            history = entry["acceptance"]["independent_run"]
            _append_event(db, version, "admitted", effective_at, {
                "historical_evidence_ref": history["evidence_ref"],
                "forward_evidence_ref": forward["evidence_ref"],
            })
            return _registration(db, row, effective_at)

    def change_availability(self, version, status, *, reason, effective_at=None):
        """Suspend or retire a published version from an explicit time onward."""
        if status not in ("suspended", "retired") or not reason:
            raise ValueError("须指定 suspended 或 retired 和变更原因")
        effective_at = utc_timestamp(effective_at)
        with database(self.data_dir) as db:
            db.executescript(_SCHEMA)
            db.execute("BEGIN IMMEDIATE")
            row = _require_version(db, version, effective_at)
            entry = _registration(db, row, effective_at)
            if entry["status"] == status:
                return entry
            if entry["status"] not in ("admitted", "suspended"):
                raise ValueError("只有已准入或暂停的版本可变更可用性")
            _append_event(db, version, status, effective_at, {"reason": reason})
            return _registration(db, row, effective_at)


def _number(value):
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _economic_close(bar, factors):
    close = _number(bar.get("close"))
    if close is None or close <= 0:
        return None, "close"
    if not factors:
        if bar.get("pre_close_basis") == "fuyao_adjustment_factor":
            return None, "adjustment_factor"
        prior = _number(bar.get("prior_close"))
        reference = _number(bar.get("pre_close"))
        no_adjustment = bar.get("pre_close_basis") == "prior_close_no_adjustment_factor"
        if no_adjustment or (prior is not None and prior > 0 and reference == prior):
            return close, None
        return None, "adjustment_factor"
    if len(factors) != 1:
        return None, "conflicting_adjustment_factors"
    factor = factors[0]
    cash = _number(factor.get("dividend_per_share"))
    bonus = _number(factor.get("bonus_per_share"))
    rights = _number(factor.get("rights_per_share", 0))
    if cash is None or bonus is None or rights is None or min(cash, bonus) < 0:
        return None, "adjustment_factor"
    if rights:
        return None, "rights_issue"
    return close * (1 + bonus) + cash, None


def _bars_start(snapshot, symbol, fallback):
    return min(
        (item["start"] for item in snapshot["scope"]
         if item["symbol"] == symbol and item["series"] == "daily_bar"),
        default=fallback,
    )


def _strategy(data_dir, version, symbol, *, as_of=None, db=None):
    entry = StrategyRegistry(data_dir).get(version, as_of, db=db)
    if entry is None:
        raise ValueError(f"策略版本不存在 {version}")
    strategy = entry["strategy"]
    if symbol not in strategy["scope"]["symbols"]:
        raise ValueError(f"策略不适用于 {symbol}")
    return strategy


def _signal(data_dir, strategy, snapshot, symbol, day, window, as_of, *, db=None):
    parameters = strategy["parameters"]
    result = {
        "trade_date": day,
        "as_of": utc_timestamp(as_of),
        "strategy_version": strategy["version"],
        "symbol": symbol,
        "status": "missing",
        "signal": None,
        "target_fraction": None,
        "conditions": None,
        "required_sessions": parameters["slow"],
        "available_sessions": 0,
        "missing": [],
    }
    data_cutoff = min(as_of, instant(snapshot["as_of"]))
    if not window or data_cutoff < session_time(day, 15, 5):
        reason = "daily_bar" if not window else "close_not_available"
        return {**result, "missing": [{"trade_date": day, "reason": reason}]}

    inputs = {
        "symbol": symbol, "start": window[0], "end": day, "cutoff": data_cutoff, "db": db,
    }
    bars = read_snapshot(data_dir, snapshot["snapshot_id"], **inputs)["observations"]
    factors = read_snapshot(
        data_dir, snapshot["snapshot_id"], series="adjustment_factor", **inputs,
    )["observations"]
    bars_by_day = {row["trade_date"]: row["payload"] for row in bars}
    factors_by_day = {}
    for row in factors:
        factors_by_day.setdefault(row["trade_date"], []).append(row["payload"])

    index = []
    previous_close = None
    for session in window:
        bar = bars_by_day.get(session)
        close = _number(bar.get("close")) if bar else None
        if bar is None:
            reason = "daily_bar"
        elif bar.get("trading_status") != "trading":
            reason = bar.get("trading_status") or "trading_status"
        elif close is None or close <= 0:
            reason = "close"
        elif session == window[0]:
            reason = None
            index.append(Decimal(100))
        else:
            economic_close, reason = _economic_close(bar, factors_by_day.get(session, []))
            if reason is None and previous_close is not None and index:
                level = index[-1]
                index.append(level if economic_close == previous_close else level * economic_close / previous_close)
        if reason:
            result["missing"].append({"trade_date": session, "reason": reason})
        previous_close = close

    result["available_sessions"] = len(window) - len(result["missing"])
    if result["missing"]:
        return result
    if len(index) < parameters["slow"]:
        return {**result, "status": "warmup"}

    fast_average = sum(index[-parameters["fast"]:]) / parameters["fast"]
    slow_average = sum(index) / parameters["slow"]
    rising = fast_average > slow_average
    return {
        **result,
        "status": "ready",
        "signal": "long" if rising else "flat",
        "target_fraction": "1" if rising else "0",
        "conditions": {
            "fast_average": format(fast_average, "f"),
            "slow_average": format(slow_average, "f"),
            "above_slow_average": rising,
            "base_session": window[0],
        },
    }


def replay_signals(data_dir, version, snapshot_id, *, symbol, start, end):
    """Replay every trading day's signal at that day's frozen 15:05 cutoff."""
    symbol = symbol.upper()
    strategy = _strategy(data_dir, version, symbol)
    snapshot = get_snapshot(data_dir, snapshot_id)
    slow = strategy["parameters"]["slow"]
    earliest = _bars_start(snapshot, symbol, start)
    start, end = _date_window(start, end)
    dates = list(sessions(min(start, earliest), end))
    return [
        _signal(data_dir, strategy, snapshot, symbol, day, dates[max(0, index - slow + 1):index + 1],
                session_time(day, 15, 5))
        for index, day in enumerate(dates) if day >= start
    ]


def signal_at(data_dir, version, snapshot_id, *, symbol, as_of, db=None):
    """Compute the most recent trading-session signal from the actual decision cutoff."""
    symbol = symbol.upper()
    strategy = _strategy(data_dir, version, symbol, as_of=as_of, db=db)
    snapshot = get_snapshot(data_dir, snapshot_id, db=db)
    cutoff = instant(as_of)
    day = cutoff.date().isoformat()
    earliest = _bars_start(snapshot, symbol, day)
    window = list(sessions(min(day, earliest), day))[-strategy["parameters"]["slow"]:]
    return _signal(data_dir, strategy, snapshot, symbol, window[-1] if window else day, window, cutoff, db=db)
