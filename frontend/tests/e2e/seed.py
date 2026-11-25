"""An isolated ETF price window for repeatable UI/backtest acceptance."""

from datetime import date, timedelta
from pathlib import Path
import sys
import json
from roll.db import connect
from roll.market.calendar import is_session
from roll.market.daily import initialize_market
from roll.market.inputs import initialize_inputs, BROAD_ETFS

with connect(Path(sys.argv[1]) / "roll.sqlite3") as db:
    initialize_inputs(db)
    end = "2024-11-01"
    if sys.argv[2:] == ["backfill"]:
        db.execute("INSERT INTO market_inputs VALUES ('margin','CN',?,?)", (end, '{"balance_yuan":"100"}'))
        sys.exit(0)
    initialize_market(db)
    days = []
    cursor = date.fromisoformat(end)
    while len(days) < 1260:
        if is_session(cursor):
            days.append(str(cursor))
        cursor -= timedelta(days=1)
    days.reverse()
    db.executemany("INSERT INTO daily_bars VALUES ('000300.SH',?,'100','100','100','100')",
                   ((d,) for d in days))
    def put(series, symbol, dates, **fields):
        db.executemany("INSERT INTO market_inputs VALUES(?,?,?,?)",
                       ((series, symbol, d, json.dumps(fields)) for d in dates))
    put("turnover", "CN", days[-20:], turnover_yuan="100")
    put("valuation", "000300.SH", days, pe_ttm="10", pb="2")
    put("breadth", "CN", days[-5:], advancing=55, declining=45)
    put("margin", "CN", days[-11:-1], balance_yuan="100")
    for symbol in BROAD_ETFS:
        put("etf_shares", symbol, days[-270:], shares="1000")
        put("etf_nav", symbol, days[-269:], nav="2")
    for d, p in [
        ("2025-07-29", "3.0"),
        ("2025-07-30", "3.1"),
        ("2025-07-31", "3.2"),
        ("2025-08-01", "3.3"),
    ]:
        obs = dict(open=p, close=p, high=str(float(p) + 0.1), low=str(float(p) - 0.1))
        db.execute(
            "INSERT INTO market_inputs VALUES('etf_bars','510300.SH',?,?)",
            (d, json.dumps(obs)),
        )
