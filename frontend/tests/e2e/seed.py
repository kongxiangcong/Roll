"""An isolated ETF price window for repeatable UI/backtest acceptance."""

from pathlib import Path
import sys
import json
from roll.db import connect
from roll.market.inputs import initialize_inputs

with connect(Path(sys.argv[1]) / "roll.sqlite3") as db:
    initialize_inputs(db)
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
