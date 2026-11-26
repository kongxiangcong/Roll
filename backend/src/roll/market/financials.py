"""Versioned quarterly disclosures and the as-of financial risk light."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json

from roll.db import connect

SHANGHAI = timezone(timedelta(hours=8))
FIELDS = {"indicators": ("TOTALOPERATEREVETZ", "KCFJCXSYJLRTZ", "ZCFZL"), "cash": ("NETCASH_OPERATE",)}
SCHEMA = """
CREATE TABLE IF NOT EXISTS fundamentals (
    symbol TEXT NOT NULL, period TEXT NOT NULL, series TEXT NOT NULL, version TEXT NOT NULL,
    notice_date TEXT, update_date TEXT, announce_date TEXT, available_from TEXT NOT NULL,
    observed_at TEXT NOT NULL, metrics TEXT NOT NULL, PRIMARY KEY(symbol,period,series,version));
CREATE TABLE IF NOT EXISTS financial_sync (
    symbol TEXT NOT NULL, series TEXT NOT NULL, last_success_at TEXT, error TEXT, PRIMARY KEY(symbol,series));
"""


def _date(value):
    if str(value) in {"None", "nan", "NaT", ""}:
        return None
    return date.fromisoformat(str(value)[:10]).isoformat()


def _number(value):
    if value is None:
        return None
    number = Decimal(str(value))
    return str(number) if number.is_finite() else None


def _store(db, symbol, series, records, timestamp):
    if not records:
        raise ValueError("财报序列为空")
    observed_day = timestamp[:10]
    for row in records:
        if row["SECUCODE"] != symbol or row.get("CURRENCY", "CNY") != "CNY":
            raise ValueError("财报证券或币种不符")
        period = _date(row["REPORT_DATE"])
        if not period or period[5:] not in {"03-31","06-30","09-30","12-31"}:
            continue
        notice, update = _date(row["NOTICE_DATE"]), _date(row["UPDATE_DATE"])
        metrics = json.dumps({key: _number(row[key]) for key in FIELDS[series]}, sort_keys=True)
        content = json.dumps([notice, update, metrics]).encode()
        version = hashlib.sha256(content).hexdigest()
        announce = notice if notice and update and update <= notice else None
        if announce and announce < period:
            announce = None
        # A changed value under the same notice cannot be dated to the old disclosure.
        conflict = db.execute("""SELECT 1 FROM fundamentals WHERE symbol=? AND period=? AND series=?
                                 AND notice_date IS ? AND metrics!=?""", (symbol,period,series,notice,metrics)).fetchone()
        if conflict:
            announce = None
        available = announce or max(filter(None, (observed_day, notice, update)))
        db.execute("""INSERT OR IGNORE INTO fundamentals VALUES (?,?,?,?,?,?,?,?,?,?)""",
                   (symbol,period,series,version,notice,update,announce,available,timestamp,metrics))


def sync_financials(data_dir, symbols, *, sdk=None):
    if sdk is not None:
        return _sync_financials(data_dir, symbols, sdk)
    from roll.market.akshare_timeout import bounded_requests
    with bounded_requests(300):
        return _sync_financials(data_dir, symbols, None)


def _sync_financials(data_dir, symbols, sdk):
    result = []
    with connect(data_dir / "roll.sqlite3") as db:
        db.executescript(SCHEMA)
        for symbol in symbols:
            code, exchange = symbol.split(".")
            for series in FIELDS:
                try:
                    if sdk is None:
                        import akshare as sdk
                    frame = (sdk.stock_financial_analysis_indicator_em(symbol=symbol, indicator="按报告期")
                             if series == "indicators" else
                             sdk.stock_cash_flow_sheet_by_report_em(symbol=exchange+code))
                    records = frame if isinstance(frame,list) else frame.to_dict("records")
                    stamp = datetime.now(SHANGHAI).isoformat()
                    db.execute("BEGIN IMMEDIATE")
                    _store(db, symbol, series, records, stamp)
                    db.execute("INSERT OR REPLACE INTO financial_sync VALUES (?,?,?,NULL)", (symbol,series,stamp))
                    db.commit()
                except Exception as exc:
                    db.rollback()
                    error = str(exc) if type(exc) is ValueError else type(exc).__name__
                    db.execute("""INSERT INTO financial_sync(symbol,series,error) VALUES (?,?,?)
                                  ON CONFLICT(symbol,series) DO UPDATE SET error=excluded.error""",
                               (symbol,series,error))
                receipt = db.execute("SELECT * FROM financial_sync WHERE symbol=? AND series=?",
                                     (symbol,series)).fetchone()
                result.append(dict(receipt))
    return result


def _previous(period):
    day = date.fromisoformat(period)
    first_day = day.replace(month=day.month - 2, day=1)
    return (first_day - timedelta(days=1)).isoformat()



def _due_period(day):
    # A calendar-year A-share issuer: Q1 by April, H1 by August, Q3 by October.
    # The year-end report is due at the same time as the following Q1.
    year = day.year
    if day.month >= 11:
        return f"{year}-09-30"
    if day.month >= 9:
        return f"{year}-06-30"
    if day.month >= 5:
        return f"{year}-03-31"
    return f"{year - 1}-09-30"


def financial_light(data_dir, symbol, as_of):
    with connect(data_dir / "roll.sqlite3") as db:
        db.executescript(SCHEMA)
        return financial_light_in_transaction(db, symbol, as_of)


def financial_light_in_transaction(db, symbol, as_of):
    day = date.fromisoformat(as_of).isoformat()
    rows = db.execute("""SELECT * FROM fundamentals WHERE symbol=? AND announce_date<=?
                         AND period<=? ORDER BY period,available_from,observed_at,rowid""",(symbol,day,day)).fetchall()
    unverified = db.execute("""SELECT period,series,notice_date,update_date,observed_at
                               FROM fundamentals WHERE symbol=? AND announce_date IS NULL
                               AND available_from<=? AND period<=? ORDER BY period DESC, observed_at DESC""",
                            (symbol,day,day)).fetchall()
    periods = {}
    for row in rows:
        periods.setdefault(row["period"], {})[row["series"]] = row
    period = max(periods, default=None)
    # A disclosure date can establish that a report existed, not what its older version said.
    disclosed = db.execute("""SELECT MAX(period) FROM fundamentals WHERE symbol=?
                               AND notice_date>=period AND notice_date<=?""", (symbol,day)).fetchone()[0]
    due = _due_period(date.fromisoformat(day))
    required = max(due, disclosed or "")
    blocked = None
    if period is None or period < required:
        blocked = (f"{required} 财报已披露，但当时版本未经核实" if disclosed == required
                   else f"{required} 财报缺少可核实版本，不能用旧期次判断")
        period = None
    latest = periods.get(period, {})
    indicators = json.loads(latest["indicators"]["metrics"]) if "indicators" in latest else {}
    revenue, profit, debt = (indicators.get(k) for k in FIELDS["indicators"])
    versions = {}
    def fetch_cash(p):
        row = periods.get(p,{}).get("cash")
        if row is None:
            return None
        versions[p+"/cash"] = row["version"]
        value = json.loads(row["metrics"]).get("NETCASH_OPERATE")
        return Decimal(value) if value is not None else None

    def quarter(p):
        total = fetch_cash(p)
        if p.endswith("03-31") or total is None:
            return total
        before = fetch_cash(_previous(p))
        return total-before if before is not None else None

    if "indicators" in latest:
        versions[period+"/indicators"] = latest["indicators"]["version"]
    cash = quarter(period) if period else None
    prior_cash = quarter(_previous(period)) if period else None
    reasons = []
    missing = [blocked] if blocked else []
    def check(label, conditions):
        if blocked:
            return
        if all(value is True for value in conditions.values()):
            reasons.append(label)
        elif False not in conditions.values():
            missing.extend(key for key, value in conditions.items() if value is None)
    check("营收与扣非净利同比同时下降", {
        "营收同比": Decimal(revenue) < -10 if revenue is not None else None,
        "扣非净利同比": Decimal(profit) < -20 if profit is not None else None,
    })
    check("连续两季经营现金流为负且负债率高于75%", {
        "本季经营现金流": cash < 0 if cash is not None else None,
        "上季经营现金流": prior_cash < 0 if prior_cash is not None else None,
        "资产负债率": Decimal(debt) > 75 if debt is not None else None,
    })
    releases = [r["announce_date"] for r in latest.values()]
    return {"symbol":symbol,"as_of":day,"report_period":period,
            "announce_date":max(releases) if releases and all(releases) else None,
            "available_from":max((r["available_from"] for r in latest.values()),default=None),
            "status":"red" if reasons else "unknown" if missing else "green","reasons":reasons,"missing":missing,
            "revenue_yoy_pct":revenue,"deducted_profit_yoy_pct":profit,"debt_ratio_pct":debt,
            "cashflow_quarter_yuan":str(cash) if cash is not None else None,
            "prior_cashflow_quarter_yuan":str(prior_cash) if prior_cash is not None else None,
            "versions":versions,
            "unverified_versions":[{**dict(r), "missing":"该版本披露日未经核实",
                "source":"stock_financial_analysis_indicator_em" if r["series"]=="indicators"
                else "stock_cash_flow_sheet_by_report_em"} for r in unverified if r["period"] >= (period or "")]}
