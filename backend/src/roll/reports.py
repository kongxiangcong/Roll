"""Explicit freezing and offline export of one daily report per Shanghai session."""
from datetime import date, datetime, time
import json
from pathlib import Path

from roll.accounts.ledger import Ledger
from roll.db import connect
from roll.market.calendar import is_session
from roll.market.daily import SHANGHAI, initialize_market, status_in_transaction


SCHEMA = """CREATE TABLE IF NOT EXISTS frozen_reports (
    trade_date TEXT PRIMARY KEY, content TEXT NOT NULL)"""


def read_report(data_dir: Path, trade_date: str):
    with connect(data_dir / "roll.sqlite3") as db:
        db.execute(SCHEMA)
        row = db.execute("SELECT content FROM frozen_reports WHERE trade_date=?", (trade_date,)).fetchone()
    if row is None:
        raise ValueError(f"{trade_date} 尚无冻结日报")
    return json.loads(row[0])


def freeze_report(data_dir: Path, trade_date: str):
    day = date.fromisoformat(trade_date)
    now = datetime.now(SHANGHAI)
    if not is_session(day) or datetime.combine(day, time(15), SHANGHAI) > now:
        raise ValueError("请选择已经收盘的交易日")
    trade_date = day.isoformat()
    ledger = Ledger(data_dir)
    with connect(ledger.path) as db:
        initialize_market(db)
        db.execute(SCHEMA)
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT content FROM frozen_reports WHERE trade_date=?", (trade_date,)).fetchone()
        if row:
            return json.loads(row[0])
        cutoff = datetime.now(SHANGHAI).isoformat()
        snapshot = ledger.replay(ledger.events(db), known_by=cutoff,
                                 effective_at=datetime.combine(day, time.max, SHANGHAI).isoformat())
        market = status_in_transaction(db, trade_date)
        obtained = [row["symbol"] for row in market if row["close"] is not None]
        missing = [row["symbol"] for row in market if row["close"] is None]
        missing_inputs = ["两市成交额", "四只宽基 ETF 份额及单位净值", "两市两融余额",
                          "每日上涨与下跌家数", "沪深 300 PE(TTM) 与 PB"]
        index = next(row for row in market if row["symbol"] == "000300.SH")
        if index["count"] < 270:
            missing_inputs.append("沪深 300 波动分位预热所需 270 个收盘")
        report = {
            "trade_date": trade_date, "cutoff_at": cutoff,
            "account": {"cash_balance": snapshot["cash_balance"], "confirmed_at": snapshot["confirmed_at"],
                        "positions": [{k: p[k] for k in ("instrument", "quantity", "sellable_quantity")}
                                      for p in snapshot["positions"]]},
            "market": market, "obtained": obtained, "missing": missing + missing_inputs,
            "barometer": {"status": "今日晴雨表不可用", "coverage": 0, "score": None, "position_cap": None},
        }
        db.execute("INSERT INTO frozen_reports VALUES (?,?)", (trade_date, json.dumps(report, ensure_ascii=False)))
        db.commit()
        return report


def report_markdown(report):
    account, barometer = report["account"], report["barometer"]
    def show(value):
        return "暂无" if value is None else str(value)
    lines = [f"# {report['trade_date']} 盘后日报", "", f"冻结截止时间 {report['cutoff_at']}", "",
             "## 账户", "", f"现金余额（元） {show(account['cash_balance'])}",
             f"账户确认时间 {show(account['confirmed_at'])}", "",
             "| 证券 | 数量（股） | 已确认可卖（股） |", "|---|---:|---:|"]
    for row in account["positions"]:
        lines.append(f"| {row['instrument']} | {row['quantity']} | {show(row['sellable_quantity'])} |")
    if not account["positions"]:
        lines.append("| 暂无持仓 | — | — |")
    lines.extend(["", "## 行情", "", "| 证券 | 类型 | 原始收盘 | 首日 | 最近交易日 | 条数 | 最后成功时间 | 同步错误 |",
                  "|---|---|---:|---|---|---:|---|---|"])
    for row in report["market"]:
        cells = (row[key] for key in ("symbol", "kind", "close", "first_date", "last_date", "count",
                                      "last_success_at", "error"))
        lines.append("| " + " | ".join(show(v) for v in cells) + " |")
    lines.extend(["", "## 晴雨表", "", barometer["status"], f"覆盖率 {barometer['coverage']:.0%}",
                  f"总分 {show(barometer['score'])}", f"总仓位上限 {show(barometer['position_cap'])}",
                  "", "已取得：" + ("、".join(report["obtained"]) or "暂无"),
                  "", "缺项：" + ("、".join(report["missing"]) or "无")])
    return "\n".join(lines)
